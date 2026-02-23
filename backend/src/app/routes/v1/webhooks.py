"""
Webhook endpoints for external service notifications.

POST /webhooks/gmail    - Receives Gmail Pub/Sub push notifications
POST /webhooks/calendar - Receives Google Calendar push notifications
"""

import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.data.models import (
    CalendarWatchChannel,
    GmailAccount,
    Message,
    WebhookDelivery,
    WebhookLog,
)
from app.infra.config import get_settings
from app.infra.database import SessionLocal
from app.integrations.gmail import GmailClient
from app.jobs.queue import queue_service
from app.jobs.worker import handle_process_email_batch
from app.security.encryption import encrypt_body
from app.services.email_filter import EmailFilterService, FilterAction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _log_webhook_event(
    source: str,
    event_type: str,
    processed: bool,
    error: str = None,
    customer_id: str = None,
) -> None:
    """Best-effort webhook audit logging."""
    log_db = SessionLocal()
    try:
        log_db.add(
            WebhookLog(
                source=source,
                event_type=event_type,
                processed=processed,
                error=error,
                customer_id=customer_id,
            )
        )
        log_db.commit()
    except Exception:
        # Logging must never break webhook handling.
        pass
    finally:
        log_db.close()


def _coerce_history_id(value) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except Exception:
        return None


def _max_history_id(*values) -> str | None:
    numeric_values = [v for v in (_coerce_history_id(x) for x in values) if v is not None]
    if not numeric_values:
        return None
    return str(max(numeric_values))


def _is_duplicate_delivery(db, source: str, delivery_id: str | None) -> bool:
    if not delivery_id:
        return False
    existing = db.query(WebhookDelivery).filter(
        WebhookDelivery.source == source,
        WebhookDelivery.delivery_id == delivery_id,
    ).first()
    return existing is not None


def _record_processed_delivery(
    db,
    source: str,
    delivery_id: str | None,
    event_type: str,
    customer_id: str = None,
) -> None:
    if not delivery_id:
        return
    db.add(
        WebhookDelivery(
            source=source,
            delivery_id=delivery_id,
            event_type=event_type,
            customer_id=customer_id,
            processed_at=datetime.now(timezone.utc),
        )
    )


def _verify_gmail_webhook_request(request: Request, body: dict) -> None:
    """
    Verify Gmail Pub/Sub push origin.

    Modes:
    - Shared secret token (GMAIL_WEBHOOK_TOKEN), checked via header/query.
    - OIDC bearer verification (default when REQUIRE_AUTH=true and no token).
    """
    settings = get_settings()

    expected_subscription = settings.GMAIL_PUBSUB_SUBSCRIPTION
    incoming_subscription = body.get("subscription")
    if expected_subscription and incoming_subscription != expected_subscription:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized_webhook_source",
        )

    # Shared secret mode avoids external cert fetch per request.
    if settings.GMAIL_WEBHOOK_TOKEN:
        supplied = request.headers.get("X-Webhook-Token") or request.query_params.get("token")
        if supplied != settings.GMAIL_WEBHOOK_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unauthorized_webhook_source",
            )
        return

    if not settings.GMAIL_WEBHOOK_REQUIRE_AUTH:
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized_webhook_source",
        )

    token = auth_header.split(" ", 1)[1].strip()
    audience = settings.GMAIL_WEBHOOK_AUDIENCE or f"{settings.API_URL.rstrip('/')}/v1/webhooks/gmail"

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=audience,
        )
        issuer = claims.get("iss")
        if issuer not in ("accounts.google.com", "https://accounts.google.com"):
            raise ValueError("invalid_issuer")

        expected_email = settings.GMAIL_PUBSUB_PUSH_SERVICE_ACCOUNT
        if expected_email and claims.get("email") != expected_email:
            raise ValueError("invalid_push_service_account")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized_webhook_source",
        )


def _decode_pubsub_data(encoded_data: str) -> dict:
    """
    Decode Pub/Sub base64 payload.
    Supports urlsafe payloads and missing padding.
    """
    padded = encoded_data + "=" * ((4 - len(encoded_data) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


@router.post("/gmail")
async def handle_gmail_push(request: Request):
    """
    Receive Gmail Pub/Sub push notifications.

    Pub/Sub sends:
    {
        "message": {
            "data": "<base64 JSON>",  // {"emailAddress":"...","historyId":"..."}
            "messageId": "...",
            "publishTime": "..."
        },
        "subscription": "projects/.../subscriptions/..."
    }
    """
    email_address = None
    pubsub_message_id = None

    try:
        body = await request.json()
    except Exception:
        logger.warning("Gmail webhook: invalid JSON body")
        _log_webhook_event("gmail", "gmail_push", False, "invalid_json")
        # Ack malformed payloads to avoid pointless retries.
        return {"status": "ignored", "reason": "invalid_json"}

    _verify_gmail_webhook_request(request, body)

    message = body.get("message", {})
    encoded_data = message.get("data")
    pubsub_message_id = message.get("messageId")

    if not encoded_data:
        logger.warning("Gmail webhook: no data in message")
        _log_webhook_event("gmail", "gmail_push", False, "no_data")
        return {"status": "ignored", "reason": "no_data"}

    try:
        decoded = _decode_pubsub_data(encoded_data)
    except Exception:
        logger.warning("Gmail webhook: failed to decode message data")
        _log_webhook_event("gmail", "gmail_push", False, "decode_failed")
        return {"status": "ignored", "reason": "decode_failed"}

    email_address = decoded.get("emailAddress")
    notification_history_id = decoded.get("historyId")

    if not email_address:
        logger.warning("Gmail webhook: no emailAddress in payload")
        _log_webhook_event("gmail", "gmail_push", False, "no_email")
        return {"status": "ignored", "reason": "no_email"}

    logger.info(
        "Gmail webhook: notification for %s, historyId=%s, messageId=%s",
        email_address,
        notification_history_id,
        pubsub_message_id,
    )

    db = SessionLocal()
    try:
        if _is_duplicate_delivery(db, "gmail", pubsub_message_id):
            logger.info("Gmail webhook: duplicate delivery ignored messageId=%s", pubsub_message_id)
            return {"status": "duplicate"}

        account = db.query(GmailAccount).filter(
            GmailAccount.email == email_address
        ).first()

        if not account or not account.user_id:
            logger.info("Gmail webhook: no linked account for %s", email_address)
            return {"status": "ignored", "reason": "unknown_account"}

        user_id = account.user_id

        # First notification after connect: initialize cursor.
        if not account.last_history_id:
            if notification_history_id:
                account.last_history_id = str(notification_history_id)
            _record_processed_delivery(
                db=db,
                source="gmail",
                delivery_id=pubsub_message_id,
                event_type="gmail_push",
                customer_id=email_address,
            )
            db.commit()
            logger.info("Gmail webhook: initialized history ID for %s", email_address)
            return {"status": "initialized", "history_id": notification_history_id}

        try:
            db.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": user_id},
            )
        except Exception:
            # SQLite/test environments do not support Postgres set_config.
            logger.debug("Gmail webhook: RLS context not applied (non-Postgres backend)")

        gmail_client = GmailClient(db=db, user_id=user_id)
        new_msg_ids, new_history_id = gmail_client.get_new_message_ids(account.last_history_id)

        if not new_msg_ids:
            account.last_history_id = _max_history_id(
                account.last_history_id,
                new_history_id,
                notification_history_id,
            ) or account.last_history_id
            _record_processed_delivery(
                db=db,
                source="gmail",
                delivery_id=pubsub_message_id,
                event_type="gmail_push",
                customer_id=email_address,
            )
            db.commit()
            return {"status": "ok", "new_messages": 0}

        logger.info("Gmail webhook: %s new messages for %s", len(new_msg_ids), email_address)

        filter_service = EmailFilterService(db=db, user_id=user_id)
        synced_count = 0
        process_ids: list[int] = []

        for gmail_msg_id in new_msg_ids:
            existing = db.query(Message).filter(
                Message.message_id == gmail_msg_id
            ).first()
            if existing:
                continue

            try:
                msg_data = gmail_client.get_message_detail(gmail_msg_id)
            except Exception as fetch_error:
                logger.warning(
                    "Gmail webhook: failed to fetch message %s: %s",
                    gmail_msg_id,
                    fetch_error,
                )
                continue

            if not msg_data:
                continue

            gmail_labels = msg_data.get("gmail_labels", [])
            headers = msg_data.get("headers", {})
            body_preview = msg_data.get("body", "")[:200] if msg_data.get("body") else None
            filter_result = filter_service.apply_filters(
                gmail_labels=gmail_labels,
                sender_email=msg_data["sender"],
                subject=msg_data["subject"],
                headers=headers,
                body_preview=body_preview,
                thread_id=msg_data.get("thread_id"),
            )

            if filter_result.action == FilterAction.SKIP:
                continue

            attachments = msg_data.get("attachments") or []
            db_message = Message(
                message_id=msg_data["message_id"],
                thread_id=msg_data["thread_id"],
                user_id=user_id,
                subject=msg_data["subject"],
                sender=msg_data["sender"],
                recipient=msg_data["recipient"],
                body=encrypt_body(msg_data["body"]),
                body_encrypted=True,
                received_at=msg_data["received_at"],
                processed=filter_result.action == FilterAction.METADATA_ONLY,
                has_attachments=bool(attachments),
                attachments=attachments,
            )

            db.add(db_message)
            db.flush()
            synced_count += 1

            if filter_result.action == FilterAction.PROCESS:
                process_ids.append(db_message.id)

        if process_ids:
            for msg_id in process_ids:
                queue_service.enqueue(
                    task_type="process_email",
                    payload={"message_id": msg_id, "user_id": user_id},
                    user_id=user_id,
                    db=db,
                )

            await queue_service.process_batch_now(
                user_id=user_id,
                task_type="process_email",
                handler=handle_process_email_batch,
                db=db,
            )

        account.last_history_id = _max_history_id(
            account.last_history_id,
            new_history_id,
            notification_history_id,
        ) or account.last_history_id
        _record_processed_delivery(
            db=db,
            source="gmail",
            delivery_id=pubsub_message_id,
            event_type="gmail_push",
            customer_id=email_address,
        )
        db.commit()

        logger.info(
            "Gmail webhook: processed %s messages (%s for AI) for %s",
            synced_count,
            len(process_ids),
            email_address,
        )
        _log_webhook_event("gmail", "gmail_push", True, customer_id=email_address)
        return {"status": "ok", "new_messages": synced_count, "processed": len(process_ids)}

    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        # Delivery insert collision from retry/concurrency. Safe to ack.
        logger.info("Gmail webhook: duplicate delivery race messageId=%s", pubsub_message_id)
        return {"status": "duplicate"}
    except Exception as exc:
        db.rollback()
        logger.error("Gmail webhook processing failed for %s: %s", email_address, exc, exc_info=True)
        _log_webhook_event("gmail", "gmail_push", False, "processing_failed", customer_id=email_address)
        # Non-2xx so Pub/Sub retries transient failures.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="gmail_webhook_processing_failed",
        )
    finally:
        db.close()


@router.post("/calendar")
async def handle_calendar_push(request: Request):
    """
    Receive Google Calendar push notifications.

    Google sends a POST to this endpoint whenever a watched calendar changes.
    The notification carries no body - only headers identify the channel and event.

    Headers:
        X-Goog-Channel-ID:     Our UUID assigned when the watch was created
        X-Goog-Resource-ID:    Google's identifier for the watched resource
        X-Goog-Resource-State: "sync" | "exists" | "not_exists"
        X-Goog-Resource-URI:   URI of the resource that changed
    """
    channel_id = request.headers.get("X-Goog-Channel-ID")
    resource_state = request.headers.get("X-Goog-Resource-State")

    if not channel_id:
        logger.warning("Calendar webhook: missing X-Goog-Channel-ID header")
        return {"status": "ignored", "reason": "missing_channel_id"}

    if resource_state == "sync":
        logger.info("Calendar webhook: sync ping acknowledged for channel=%s", channel_id)
        return {"status": "ok"}

    if resource_state != "exists":
        logger.info("Calendar webhook: ignoring state=%s for channel=%s", resource_state, channel_id)
        return {"status": "ignored", "reason": f"state_{resource_state}"}

    db = SessionLocal()
    try:
        channel = db.query(CalendarWatchChannel).filter(
            CalendarWatchChannel.channel_id == channel_id
        ).first()

        if not channel:
            logger.info("Calendar webhook: unknown channel_id=%s, ignoring", channel_id)
            return {"status": "ignored", "reason": "unknown_channel"}

        user_id = channel.user_id
        logger.info(
            "Calendar webhook: change detected user=%s calendar=%s channel=%s",
            user_id,
            channel.calendar_id,
            channel_id,
        )

        queue_service.enqueue(
            task_type="sync_calendar_for_user",
            payload={"user_id": user_id},
            user_id=user_id,
            db=db,
        )
        return {"status": "ok"}

    except Exception as exc:
        logger.error("Calendar webhook processing failed: %s", exc, exc_info=True)
        # Return 200 to prevent Google retry storms for calendar channel pings.
        return {"status": "error"}
    finally:
        db.close()

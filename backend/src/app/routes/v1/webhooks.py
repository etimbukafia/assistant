"""
Webhook endpoints for external service notifications.

POST /webhooks/gmail - Receives Gmail Pub/Sub push notifications
"""

import base64
import json
import logging

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infra.database import SessionLocal
from app.data.models import Message, GmailAccount
from app.integrations.gmail import GmailClient
from app.services.email_filter import EmailFilterService, FilterAction
from app.security.encryption import encrypt_body
from app.jobs.task_queue import queue_service
from app.jobs.worker import handle_process_email_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/gmail")
async def handle_gmail_push(request: Request):
    """
    Receive Gmail Pub/Sub push notifications.

    Google Pub/Sub sends a POST with:
    {
        "message": {
            "data": "<base64 encoded JSON>",  // {"emailAddress": "...", "historyId": "..."}
            "messageId": "...",
            "publishTime": "..."
        },
        "subscription": "projects/.../subscriptions/..."
    }

    The data payload tells us which user received mail and the history ID
    to fetch changes from. We then use the History API to get actual new
    messages and feed them through the existing processing pipeline.
    """
    try:
        body = await request.json()
    except Exception:
        # Must return 200 to avoid Pub/Sub retries on bad payloads
        logger.warning("Gmail webhook: invalid JSON body")
        return {"status": "ignored", "reason": "invalid_json"}

    # Extract and decode Pub/Sub message data
    message = body.get("message", {})
    encoded_data = message.get("data")

    if not encoded_data:
        logger.warning("Gmail webhook: no data in message")
        return {"status": "ignored", "reason": "no_data"}

    try:
        decoded = json.loads(base64.b64decode(encoded_data))
    except Exception:
        logger.warning("Gmail webhook: failed to decode message data")
        return {"status": "ignored", "reason": "decode_failed"}

    email_address = decoded.get("emailAddress")
    notification_history_id = decoded.get("historyId")

    if not email_address:
        logger.warning("Gmail webhook: no emailAddress in payload")
        return {"status": "ignored", "reason": "no_email"}

    logger.info(f"Gmail webhook: notification for {email_address}, historyId={notification_history_id}")

    # Process in a new DB session (no request-scoped user auth here)
    db = SessionLocal()
    try:
        # Look up the Gmail account
        account = db.query(GmailAccount).filter(
            GmailAccount.email == email_address
        ).first()

        if not account or not account.user_id:
            logger.info(f"Gmail webhook: no linked account for {email_address}")
            return {"status": "ignored", "reason": "unknown_account"}

        user_id = account.user_id

        # If no stored history ID, save this one for future use
        if not account.last_history_id:
            account.last_history_id = str(notification_history_id)
            db.commit()
            logger.info(f"Gmail webhook: initialized history ID for {email_address}")
            return {"status": "initialized", "history_id": notification_history_id}

        # Set RLS context for this user
        db.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": user_id}
        )

        # Create Gmail client and fetch new messages via History API
        gmail_client = GmailClient(db=db, user_id=user_id)
        new_msg_ids, new_history_id = gmail_client.get_new_message_ids(
            account.last_history_id
        )

        if not new_msg_ids:
            # No new inbox messages — update history ID and return
            account.last_history_id = str(new_history_id)
            db.commit()
            return {"status": "ok", "new_messages": 0}

        logger.info(f"Gmail webhook: {len(new_msg_ids)} new messages for {email_address}")

        # Initialize filter service
        filter_service = EmailFilterService(db=db, user_id=user_id)

        synced_count = 0
        process_ids = []

        for gmail_msg_id in new_msg_ids:
            # Deduplicate: skip if already in DB
            existing = db.query(Message).filter(
                Message.message_id == gmail_msg_id
            ).first()
            if existing:
                continue

            # Fetch full message details
            try:
                msg_data = gmail_client.get_message_detail(gmail_msg_id)
            except Exception as e:
                logger.warning(f"Gmail webhook: failed to fetch message {gmail_msg_id}: {e}")
                continue

            if not msg_data:
                continue

            # Apply email filters
            gmail_labels = msg_data.get('gmail_labels', [])
            headers = msg_data.get('headers', {})
            body_preview = msg_data.get('body', '')[:200] if msg_data.get('body') else None
            filter_result = filter_service.apply_filters(
                gmail_labels=gmail_labels,
                sender_email=msg_data['sender'],
                subject=msg_data['subject'],
                headers=headers,
                body_preview=body_preview,
                thread_id=msg_data.get('thread_id'),
            )

            if filter_result.action == FilterAction.SKIP:
                continue

            # Save to database
            attachments = msg_data.get('attachments') or []
            db_message = Message(
                message_id=msg_data['message_id'],
                thread_id=msg_data['thread_id'],
                user_id=user_id,
                subject=msg_data['subject'],
                sender=msg_data['sender'],
                recipient=msg_data['recipient'],
                body=encrypt_body(msg_data['body']),
                body_encrypted=True,
                received_at=msg_data['received_at'],
                processed=filter_result.action == FilterAction.METADATA_ONLY,
                has_attachments=bool(attachments),
                attachments=attachments,
            )

            db.add(db_message)
            db.flush()
            synced_count += 1

            if filter_result.action == FilterAction.PROCESS:
                process_ids.append(db_message.id)

        # Enqueue AI processing tasks
        if process_ids:
            for msg_id in process_ids:
                queue_service.enqueue(
                    task_type="process_email",
                    payload={"message_id": msg_id, "user_id": user_id},
                    user_id=user_id,
                    db=db
                )

            # Trigger immediate batch processing
            await queue_service.process_batch_now(
                user_id=user_id,
                task_type="process_email",
                handler=handle_process_email_batch,
                db=db
            )

        # Update history ID for next notification
        account.last_history_id = str(new_history_id)
        db.commit()

        logger.info(
            f"Gmail webhook: processed {synced_count} messages "
            f"({len(process_ids)} for AI) for {email_address}"
        )

        return {
            "status": "ok",
            "new_messages": synced_count,
            "processed": len(process_ids),
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Gmail webhook processing failed for {email_address}: {e}", exc_info=True)
        # Return 200 anyway to prevent Pub/Sub retry storms during transient errors.
        # The next notification will re-fetch from the same history ID.
        return {"status": "error", "detail": str(e)}

    finally:
        db.close()

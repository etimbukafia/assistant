"""
Event handlers for message processing

Architecture: State-Based Thread Processing
- Threads are state machines. Messages are state updates.
- Each new message updates thread state incrementally.
- No full thread transcript re-analysis.
"""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from core.events import register_handler
from app.infra.database import SessionLocal
from app.data.models import Message
from app.jobs.task_queue import enqueue_task
from app.processors.document import document_processor
from app.integrations.gmail import GmailClient
from sqlalchemy import text

logger = logging.getLogger(__name__)

@register_handler("message_received")
async def enqueue_message_for_processing(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Enqueue message for batch processing.

    Instead of processing immediately, we enqueue a task that will be:
    1. Collected with other messages for the same user
    2. Processed together (leveraging shared LLM provider)
    3. Triggered immediately after sync (no delay for manual syncs)

    The actual processing logic is in app.message_processor.

    Security: user_id is derived from the Message record in DB, not from payload.
    """
    message_id = payload.get("message_id")

    if not message_id:
        logger.error("No message_id in payload", extra={"correlation_id": event["correlation_id"]})
        return

    db = SessionLocal()
    try:
        # First fetch message WITHOUT RLS to get the authoritative user_id
        # This prevents payload injection attacks where user_id could be spoofed
        message = db.query(Message).filter(Message.id == message_id).first()

        if not message:
            logger.error(f"Message {message_id} not found", extra={"correlation_id": event["correlation_id"]})
            return

        # Get user_id from the database record, NOT from payload (security)
        user_id = message.user_id
        if not user_id:
            raise ValueError(f"Message {message_id} has no user_id in database")

        # Now set RLS context with verified user_id
        db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

        if message.processed:
            logger.info(f"Message {message_id} already processed", extra={"correlation_id": event["correlation_id"]})
            return

        # Enqueue for batch processing with verified user_id
        enqueue_task(
            task_type="process_email",
            payload={"message_id": message_id, "user_id": user_id},
            correlation_id=event["correlation_id"],
            db=db
        )

        logger.info(
            f"Message {message_id} enqueued for batch processing",
            extra={"correlation_id": event["correlation_id"], "user_id": user_id}
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to enqueue message {message_id}: {str(e)}",
            extra={"correlation_id": event["correlation_id"]},
            exc_info=True
        )
        raise
    finally:
        db.close()


@register_handler("message_received")
async def update_contact_stats(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Update contact statistics when a message is received.

    Increments message_count for the sender in ContactContext.
    This powers Layer 3 relationship-based email filtering.

    Security: user_id is derived from the Message record in DB, not from payload.
    """
    message_id = payload.get("message_id")

    if not message_id:
        return

    db = SessionLocal()
    try:
        # Fetch message first to get authoritative user_id (not from payload)
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            return

        # Get user_id from DB record, not payload (security)
        user_id = message.user_id
        if not user_id:
            return

        db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

        # Extract sender email
        sender = message.sender or ""
        if '<' in sender and '>' in sender:
            sender_email = sender[sender.index('<') + 1:sender.index('>')].strip().lower()
        else:
            sender_email = sender.strip().lower()

        if sender_email:
            from app.services.contact_stats import increment_message_count
            increment_message_count(db, user_id, sender_email)

    except Exception as e:
        logger.warning(f"Failed to update contact stats for message {message_id}: {e}")
    finally:
        db.close()


@register_handler("message_processed")
async def notify_on_processed(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Example handler for message_processed event (emitted after AI processing completes)

    This demonstrates event chaining:
    - message_received → process_message_content → enqueues emit_event task
    - Worker processes task → emits message_processed event
    - This handler receives message_processed event

    Use cases:
    - Send notifications (WhatsApp, Email, Slack)
    - Trigger another AI agent
    - Update analytics
    - Start another workflow
    """
    message_id = payload.get("message_id")
    needs_reply = payload.get("needs_reply")
    task_count = payload.get("task_count", 0)

    logger.info(
        f"Message processed event received: message_id={message_id}, "
        f"needs_reply={needs_reply}, tasks={task_count}",
        extra={
            "correlation_id": event["correlation_id"],
            "message_id": message_id,
            "needs_reply": needs_reply,
            "task_count": task_count
        }
    )

    # Future implementations:
    # if needs_reply:
    #     enqueue_task("send_notification", {"message_id": message_id, "type": "whatsapp"})
    # if task_count > 0:
    #     enqueue_task("trigger_agent", {"message_id": message_id, "agent": "task_organizer"})


@register_handler("message_received")
async def process_attachments(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Process attachments from received messages.
    Downloads files and extracts insights using DocumentProcessor.

    Security: user_id is derived from the Message record in DB, not from payload.
    """
    message_id = payload.get("message_id")

    if not message_id:
        return

    db = SessionLocal()
    try:
        # Fetch message first to get authoritative user_id (not from payload)
        message = db.query(Message).filter(Message.id == message_id).first()

        if not message or not message.has_attachments:
            return

        # Get user_id from DB record, not payload (security)
        user_id = message.user_id
        if not user_id:
            raise ValueError(f"Message {message_id} has no user_id in database")

        # Now set RLS context with verified user_id
        db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

        attachments_meta = message.attachments or []
        if not attachments_meta:
            return

        logger.info(
            f"Processing {len(attachments_meta)} attachment(s) for message {message_id}",
            extra={"correlation_id": event["correlation_id"]}
        )

        # Initialize Gmail client to download attachments
        gmail = GmailClient(db=db)
        if not gmail.load_credentials():
            logger.error("Failed to load Gmail credentials for attachment download")
            return

        # Collect attachment data for processing and track skipped
        attachment_data: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []

        for att in attachments_meta:
            mime_type = att.get("mime_type", "")
            filename = att.get("filename", "unknown")

            # Skip unsupported types
            if not document_processor.is_supported(mime_type):
                logger.info(f"Skipping unsupported attachment type: {mime_type}")
                skipped.append({"filename": filename, "mime_type": mime_type, "reason": "unsupported_type"})
                continue

            # Download attachment bytes
            file_bytes = gmail.download_attachment(
                message_id=att["message_id"],
                attachment_id=att["attachment_id"]
            )

            if file_bytes:
                attachment_data.append({
                    "bytes": file_bytes,
                    "mime_type": mime_type,
                    "filename": filename
                })
            else:
                logger.warning(f"Failed to download attachment: {filename}")
                skipped.append({"filename": filename, "mime_type": mime_type, "reason": "download_failed"})

        # Process attachments or record skip-only results
        if attachment_data:
            insights = document_processor.process_multiple(attachment_data)
        else:
            insights = {"processed_count": 0, "error_count": 0}

        # Add skipped attachments to insights
        if skipped:
            insights["skipped"] = skipped

        # Always save insights when there are attachments (even if all skipped)
        message.attachment_insights = insights
        db.commit()

        # Notify user about skipped attachments
        if skipped:
            try:
                from app.services.notification import NotificationService
                svc = NotificationService(db, user_id)

                skipped_names = ", ".join(s["filename"] for s in skipped[:3])
                suffix = f" and {len(skipped) - 3} more" if len(skipped) > 3 else ""

                svc.create_notification(
                    title=f"{len(skipped)} attachment(s) couldn't be processed",
                    body=f"{skipped_names}{suffix}",
                    category="system",
                    priority="normal",
                    target_type="message",
                    target_id=str(message_id),
                    send_push=False,
                )
            except Exception as e:
                logger.warning(f"Failed to create attachment skip notification: {e}")

        logger.info(
            f"Attachment processing complete for message {message_id}: "
            f"processed={insights.get('processed_count', 0)}, skipped={len(skipped)}",
            extra={
                "correlation_id": event["correlation_id"],
                "tasks_found": len(insights.get("tasks", [])),
                "errors": insights.get("error_count", 0),
                "skipped_count": len(skipped)
            }
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to process attachments for message {message_id}: {str(e)}",
            extra={"correlation_id": event["correlation_id"]},
            exc_info=True
        )
    finally:
        db.close()
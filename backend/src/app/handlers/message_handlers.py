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
from app.database import SessionLocal
from app.models import Message
from app.queue import enqueue_task
from app.document_processor import document_processor
from app.gmail_integration import GmailClient
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
    """
    message_id = payload.get("message_id")

    if not message_id:
        logger.error("No message_id in payload", extra={"correlation_id": event["correlation_id"]})
        return

    db = SessionLocal()
    try:
        # Require user_id from payload for RLS context
        user_id = payload.get("user_id")
        if not user_id:
             logger.error("No user_id in payload for message processing - cannot proceed safely", extra={"correlation_id": event["correlation_id"]})
             return

        # Set RLS context
        db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

        # Validate message exists and isn't already processed
        message = db.query(Message).filter(Message.id == message_id).first()

        if not message:
            logger.error(f"Message {message_id} not found", extra={"correlation_id": event["correlation_id"]})
            return

        if message.processed:
            logger.info(f"Message {message_id} already processed", extra={"correlation_id": event["correlation_id"]})
            return
        
        # Enqueue for batch processing
        enqueue_task(
            task_type="process_email",
            payload={"message_id": message_id, "user_id": user_id},  # Include user_id in payload instead
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
async def log_message_stats(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Log statistics about received messages (example of multiple handlers)
    """
    message_id = payload.get("message_id")

    logger.info(
        f"Message statistics logged for {message_id}",
        extra={
            "correlation_id": event["correlation_id"],
            "event_name": event["name"],
            "timestamp": event["timestamp"]
        }
    )

    # In future: update analytics dashboard, increment counters, etc.


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
    """
    message_id = payload.get("message_id")
    user_id = payload.get("user_id")

    if not message_id:
        return
        
    # Require user_id for RLS context
    if not user_id:
        logger.warning(f"process_attachments skipped for message {message_id}: missing user_id")
        return

    db = SessionLocal()
    # Set RLS context
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        message = db.query(Message).filter(Message.id == message_id).first()

        if not message or not message.has_attachments:
            return

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

        # Collect attachment data for processing
        attachment_data: List[Dict[str, Any]] = []
        for att in attachments_meta:
            # Skip unsupported types
            if not document_processor.is_supported(att.get("mime_type", "")):
                logger.info(f"Skipping unsupported attachment type: {att.get('mime_type')}")
                continue

            # Download attachment bytes
            file_bytes = gmail.download_attachment(
                message_id=att["message_id"],
                attachment_id=att["attachment_id"]
            )

            if file_bytes:
                attachment_data.append({
                    "bytes": file_bytes,
                    "mime_type": att["mime_type"],
                    "filename": att["filename"]
                })

        if not attachment_data:
            logger.info(f"No processable attachments for message {message_id}")
            return

        # Process all attachments and merge insights
        insights = document_processor.process_multiple(attachment_data)

        # Save insights to message
        message.attachment_insights = insights
        db.commit()

        logger.info(
            f"Processed {insights['processed_count']} attachment(s) for message {message_id}",
            extra={
                "correlation_id": event["correlation_id"],
                "tasks_found": len(insights.get("tasks", [])),
                "errors": insights.get("error_count", 0)
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
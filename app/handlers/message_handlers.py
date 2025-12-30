"""
Event handlers for message processing
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from core.events import register_handler
from app.database import SessionLocal
from app.models import Message
from app.ai_processor import AIProcessor
from app.queue import enqueue_task

logger = logging.getLogger(__name__)

# Initialize AI processor (could be dependency injected in future)
ai_processor = AIProcessor()


@register_handler("message_received")
async def process_message_content(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Process a new message with AI:
    - Summarize
    - Extract tasks, dates, people, decisions
    - Classify needs_reply
    """
    message_id = payload.get("message_id")

    if not message_id:
        logger.error("No message_id in payload", extra={"correlation_id": event["correlation_id"]})
        return

    db = SessionLocal()
    try:
        # Get message from database
        message = db.query(Message).filter(Message.id == message_id).first()

        if not message:
            logger.error(f"Message {message_id} not found", extra={"correlation_id": event["correlation_id"]})
            return

        # Skip if already processed
        if message.processed:
            logger.info(f"Message {message_id} already processed", extra={"correlation_id": event["correlation_id"]})
            return

        # Prepare message data for AI processing
        message_data = {
            "subject": message.subject,
            "body": message.decrypted_body,
            "sender": message.sender
        }

        # Process with AI (with thread context for replies)
        logger.info(f"Processing message {message_id} with AI (thread_id={message.thread_id})")
        ai_results = ai_processor.process_message(
            message_data,
            db=db,
            thread_id=message.thread_id,
            message_id=message.id
        )

        # Update message with AI results
        message.summary = ai_results["summary"]
        message.needs_reply = ai_results["needs_reply"]
        message.extracted_tasks = ai_results["extracted_tasks"]
        message.extracted_dates = ai_results["extracted_dates"]
        message.extracted_people = ai_results["extracted_people"]
        message.extracted_decisions = ai_results["extracted_decisions"]
        message.processed = True

        db.commit()

        logger.info(
            f"Message {message_id} processed successfully",
            extra={
                "correlation_id": event["correlation_id"],
                "needs_reply": ai_results["needs_reply"],
                "task_count": len(ai_results["extracted_tasks"]),
                "date_count": len(ai_results["extracted_dates"])
            }
        )

        # Enqueue task to emit completion event (Phase 2: DB Queue)
        # This allows downstream handlers to react to processing completion
        enqueue_task(
            task_type="emit_event",
            payload={
                "event_name": "message_processed",
                "event_payload": {
                    "message_id": message_id,
                    "needs_reply": ai_results["needs_reply"],
                    "task_count": len(ai_results["extracted_tasks"]),
                    "date_count": len(ai_results["extracted_dates"]),
                    "people_count": len(ai_results["extracted_people"]),
                    "decision_count": len(ai_results["extracted_decisions"])
                }
            },
            correlation_id=event["correlation_id"],
            db=db
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to process message {message_id}: {str(e)}",
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

"""
Message Processing Logic - Reusable across channels (Email, Slack, WhatsApp)

This module contains the actual message processing logic that can be called:
- From event handlers (single message, immediate processing)
- From batch handlers (multiple messages, batched LLM calls)
- From any channel adapter (email, Slack, WhatsApp)

The processing is channel-agnostic. Channel-specific adapters prepare the
message data, then call these functions.
"""
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from app.data.models import Message, GmailAccount
from app.services.thread_state import ThreadStateService
from app.jobs.queue import enqueue_task

logger = logging.getLogger(__name__)


# def get_user_id(db: Session) -> str:
#     """Get current user ID from Gmail account (or default) - DEPRECATED/UNSAFE"""
#     # account = db.query(GmailAccount).first()
#     # return account.email if account else "default"
#     pass


def process_message(
    message: Message,
    db: Session,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a single message using state-based thread processing.

    This is the core processing logic - updates thread state incrementally,
    extracts tasks, dates, people, decisions, and scheduling intent.

    Args:
        message: Message model instance
        db: Database session
        correlation_id: Optional correlation ID for tracking

    Returns:
        Dict with processing results (summary, needs_reply, extracted_*, etc.)
    """
    # Prepare message data for processing
    message_data = {
        "subject": message.subject,
        "body": message.decrypted_body,
        "sender": message.sender
    }

    # Process using state-based thread approach
    logger.info(f"Processing message {message.id} with thread state (thread_id={message.thread_id})")
    thread_state_service = ThreadStateService(db)
    ai_results = thread_state_service.process_message(message, message_data)

    # Update message with results
    message.summary = ai_results["summary"]
    message.needs_reply = ai_results["needs_reply"]
    message.extracted_tasks = ai_results["extracted_tasks"]
    message.extracted_dates = ai_results.get("extracted_dates", [])
    message.extracted_people = ai_results.get("extracted_people", [])
    message.extracted_decisions = ai_results.get("extracted_decisions", [])
    message.scheduling_intent = ai_results.get("scheduling_intent", False)
    message.scheduling_intent_type = ai_results.get("scheduling_intent_type")
    message.scheduling_intent_confidence = ai_results.get("scheduling_intent_confidence")
    message.processed = True

    # Enqueue completion event
    enqueue_task(
        task_type="emit_event",
        payload={
            "event_name": "message_processed",
            "event_payload": {
                "message_id": message.id,
                "needs_reply": ai_results["needs_reply"],
                "task_count": len(ai_results["extracted_tasks"]),
                "date_count": len(ai_results["extracted_dates"]),
                "people_count": len(ai_results["extracted_people"]),
                "decision_count": len(ai_results["extracted_decisions"]),
                "scheduling_intent": ai_results.get("scheduling_intent", False)
            }
        },
        correlation_id=correlation_id,
        db=db
    )

    # Emit scheduling_intent_detected event if intent found
    if ai_results.get("scheduling_intent") and ai_results.get("scheduling_intent_confidence", 0) >= 0.6:
        enqueue_task(
            task_type="emit_event",
            payload={
                "event_name": "scheduling_intent_detected",
                "event_payload": {
                    "message_id": message.id,
                    "user_id": message.user_id,
                    "thread_id": message.thread_id,
                    "intent_type": ai_results["scheduling_intent_type"],
                    "confidence": ai_results["scheduling_intent_confidence"]
                }
            },
            correlation_id=correlation_id,
            db=db
        )

    logger.info(
        f"Message {message.id} processed successfully",
        extra={
            "correlation_id": correlation_id,
            "needs_reply": ai_results["needs_reply"],
            "task_count": len(ai_results["extracted_tasks"]),
            "scheduling_intent": ai_results.get("scheduling_intent", False)
        }
    )

    return ai_results


def process_messages_batch(
    message_ids: List[int],
    db: Session,
    user_id: str,
    correlation_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Process multiple messages, leveraging batch LLM calls where possible.

    Messages are sorted by thread_id then received_at to ensure correct
    thread state evolution (first message initializes, subsequent update).

    Currently processes sequentially (each uses ThreadStateService).
    Future optimization: batch the initial AI extraction, then apply
    thread state updates individually.

    Args:
        message_ids: List of message IDs to process
        db: Database session with RLS context set
        user_id: User ID for RLS context
        correlation_id: Optional correlation ID

    Returns:
        List of processing results
    """
    results = []
    try:
        # Fetch all messages and sort by thread_id, then received_at
        # This ensures messages within the same thread are processed chronologically
        messages = db.query(Message).filter(
            Message.id.in_(message_ids)
        ).order_by(Message.thread_id, Message.received_at).all()

        # Filter out already processed messages
        to_process = []
        for message in messages:
            if message.processed:
                logger.info(f"Message {message.id} already processed, skipping")
                results.append({"_skipped": True, "message_id": message.id})
            else:
                to_process.append(message)

        if to_process:
            # Use ThreadStateService batch processing (batches LLM calls for new threads)
            thread_state_service = ThreadStateService(db)
            batch_results = thread_state_service.process_messages_batch(to_process)
            
            # Update message records and emit events
            for message, ai_results in zip(to_process, batch_results):
                if ai_results.get("_error"):
                    results.append(ai_results)
                    continue
                    
                # Update message with results
                message.summary = ai_results["summary"]
                message.needs_reply = ai_results["needs_reply"]
                message.extracted_tasks = ai_results["extracted_tasks"]
                message.extracted_dates = ai_results.get("extracted_dates", [])
                message.extracted_people = ai_results.get("extracted_people", [])
                message.extracted_decisions = ai_results.get("extracted_decisions", [])
                message.scheduling_intent = ai_results.get("scheduling_intent", False)
                message.scheduling_intent_type = ai_results.get("scheduling_intent_type")
                message.scheduling_intent_confidence = ai_results.get("scheduling_intent_confidence")
                message.processed = True
                
                # Emit scheduling_intent_detected event if intent found
                if ai_results.get("scheduling_intent") and ai_results.get("scheduling_intent_confidence", 0) >= 0.6:
                    enqueue_task(
                        task_type="emit_event",
                        payload={
                            "event_name": "scheduling_intent_detected",
                            "event_payload": {
                                "message_id": message.id,
                                "user_id": message.user_id,
                                "thread_id": message.thread_id,
                                "intent_type": ai_results["scheduling_intent_type"],
                                "confidence": ai_results["scheduling_intent_confidence"]
                            }
                        },
                        correlation_id=correlation_id,
                        db=db
                    )
                
                results.append(ai_results)

        db.commit()
        return results

    except Exception as e:
        db.rollback()
        logger.error(f"Batch processing failed: {e}", exc_info=True)
        raise

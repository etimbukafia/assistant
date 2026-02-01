"""
Event handlers for scheduling intent detection.

When scheduling_intent_detected event is emitted, automatically
generate a SchedulingSuggestion with time slots and draft reply.
"""
import logging
from typing import Dict, Any

from core.events import register_handler
from app.infra.database import SessionLocal
from app.data.models import Message, SchedulingSuggestion
from app.agents.modules.scheduling import SchedulingModule
from sqlalchemy import text

logger = logging.getLogger(__name__)


@register_handler("scheduling_intent_detected")
async def handle_scheduling_intent(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Auto-generate scheduling suggestion when intent is detected.
    
    Flow:
    1. Message is processed, scheduling_intent_detected event emitted
    2. This handler creates SchedulingSuggestion with:
       - Available time slots from calendar
       - Draft availability reply
       - Draft event description
    3. User opens message in UI, sees SchedulingSuggestionCard
    4. User approves/sends or dismisses
    """
    message_id = payload.get("message_id")
    # Try to get user_id from payload, or potentially thread/message context if we trusted it
    user_id = payload.get("user_id") 
    thread_id = payload.get("thread_id")
    intent_type = payload.get("intent_type")
    confidence = payload.get("confidence", 0)
    
    if not message_id:
        logger.error("No message_id in scheduling_intent_detected payload")
        return

    if not user_id:
        raise ValueError(f"RLS context missing: no user_id for scheduling_intent_detected, message {message_id}")

    logger.info(
        f"Scheduling intent detected for message {message_id}",
        extra={
            "correlation_id": event["correlation_id"],
            "intent_type": intent_type,
            "confidence": confidence
        }
    )
    
    db = SessionLocal()
    # Set RLS context
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
    try:
        # Check if suggestion already exists (avoid duplicates)
        existing = db.query(SchedulingSuggestion).filter(
            SchedulingSuggestion.message_id == message_id,
            SchedulingSuggestion.status == "pending"
        ).first()
        
        if existing:
            logger.info(
                f"Scheduling suggestion already exists for message {message_id}",
                extra={"correlation_id": event["correlation_id"]}
            )
            return
        
        # Get message details
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.error(f"Message {message_id} not found")
            return
        
        # Generate scheduling suggestion using SchedulingModule
        scheduling_module = SchedulingModule()
        result = scheduling_module.generate_suggestions(
            message_id=message_id,
            message_body=message.decrypted_body or message.body or "",
            message_subject=message.subject or "",
            sender_email=message.sender or "",
            thread_id=thread_id or message.thread_id
        )
        
        if result.get("success"):
            logger.info(
                f"Created scheduling suggestion for message {message_id}",
                extra={
                    "correlation_id": event["correlation_id"],
                    "suggestion_id": result.get("suggestion_id"),
                    "slot_count": len(result.get("suggested_slots", []))
                }
            )
        else:
            logger.warning(
                f"Failed to generate scheduling suggestion for message {message_id}: {result.get('error')}",
                extra={"correlation_id": event["correlation_id"]}
            )
    
    except Exception as e:
        logger.error(
            f"Error handling scheduling intent for message {message_id}: {str(e)}",
            extra={"correlation_id": event["correlation_id"]},
            exc_info=True
        )
    finally:
        db.close()

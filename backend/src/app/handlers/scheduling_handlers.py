"""
Event handlers for scheduling intent detection.

When scheduling_intent_detected event is emitted, creates a lean SchedulingIntent
record — no pre-generated slots or draft replies. Those are produced on-demand by
CalendarOrchestrator when the user takes action in the UI.
"""
import logging
from datetime import date
from difflib import SequenceMatcher
from typing import Dict, Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.events import register_handler
from app.infra.database import SessionLocal
from app.data.models import Message, SchedulingIntent, CalendarEvent
from core.cache import thread_cache
from sqlalchemy import text

logger = logging.getLogger(__name__)


@register_handler("scheduling_intent_detected")
async def handle_scheduling_intent(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Create a lean SchedulingIntent record when scheduling intent is detected.

    Flow:
    1. Email processed → scheduling_intent_detected event emitted (confidence ≥ 0.6)
    2. This handler stores: intent_type, intent_summary, meeting_title, meeting_date
    3. For meeting_reminder: checks calendar for matching event (title + date)
    4. User sees intent card in calendar sidebar; takes action when ready
    5. CalendarOrchestrator runs on-demand at action time
    """
    message_id = payload.get("message_id")
    user_id = payload.get("user_id")
    thread_id = payload.get("thread_id")

    if not message_id:
        logger.error("No message_id in scheduling_intent_detected payload")
        return

    if not user_id:
        raise ValueError(
            f"RLS context missing: no user_id for scheduling_intent_detected, message {message_id}"
        )

    logger.info(
        f"Scheduling intent detected for message {message_id}",
        extra={
            "correlation_id": event.get("correlation_id"),
            "intent_type": payload.get("intent_type"),
            "confidence": payload.get("confidence", 0),
        }
    )

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
    try:
        # Deduplicate — one pending intent per message
        existing = db.query(SchedulingIntent).filter(
            SchedulingIntent.message_id == message_id,
            SchedulingIntent.status == "pending"
        ).first()
        if existing:
            logger.info(f"Scheduling intent already exists for message {message_id}")
            return

        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.error(f"Message {message_id} not found")
            return

        # Parse meeting_date from ISO string
        meeting_date = _parse_date(payload.get("meeting_date"))

        # For meeting_reminder: check if event is already in the calendar
        matched_event_id = None
        if payload.get("intent_type") == "meeting_reminder":
            matched_event_id = _find_calendar_match(
                db=db,
                user_id=user_id,
                title=payload.get("meeting_title"),
                meeting_date=meeting_date,
            )

        # Expire any previous pending intents for the same thread
        db.query(SchedulingIntent).filter(
            SchedulingIntent.thread_id == message.thread_id,
            SchedulingIntent.status == "pending"
        ).update({"status": "expired"})

        intent = SchedulingIntent(
            user_id=user_id,
            message_id=message_id,
            thread_id=thread_id or message.thread_id,
            sender_name=_name_from_email(message.sender),
            sender_email=message.sender,
            intent_type=payload.get("intent_type", "availability_request"),
            intent_summary=payload.get("intent_summary"),
            meeting_title=payload.get("meeting_title"),
            meeting_date=meeting_date,
            matched_event_id=matched_event_id,
            status="pending",
        )
        db.add(intent)
        db.commit()

        if user_id and message.thread_id:
            thread_cache.invalidate(user_id, message.thread_id)

        logger.info(
            f"Created scheduling intent {intent.id} for message {message_id}",
            extra={
                "correlation_id": event.get("correlation_id"),
                "intent_type": intent.intent_type,
                "matched_event_id": matched_event_id,
            }
        )

    except Exception as e:
        logger.error(
            f"Error handling scheduling intent for message {message_id}: {e}",
            extra={"correlation_id": event.get("correlation_id")},
            exc_info=True,
        )
    finally:
        db.close()


def _find_calendar_match(
    db: Session,
    user_id: str,
    title: Optional[str],
    meeting_date: Optional[date],
) -> Optional[int]:
    """
    Find an existing calendar event matching the given title and date.
    Uses fuzzy title similarity (threshold 0.7) + same calendar date.
    Returns the event id, or None if no match found.
    """
    if not title or not meeting_date:
        return None

    candidates = db.query(CalendarEvent).filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.status != "cancelled",
        func.date(CalendarEvent.start_time) == meeting_date,
    ).all()

    for event in candidates:
        ratio = SequenceMatcher(None, title.lower(), event.title.lower()).ratio()
        if ratio > 0.7:
            return event.id

    return None


def _parse_date(raw: Optional[str]) -> Optional[date]:
    """Parse ISO date string to date object. Returns None on failure."""
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except (ValueError, TypeError):
        return None


def _name_from_email(email: Optional[str]) -> Optional[str]:
    """Derive a display name from an email address local part."""
    if not email:
        return None
    local = email.split("@")[0]
    return local.replace(".", " ").replace("_", " ").title()

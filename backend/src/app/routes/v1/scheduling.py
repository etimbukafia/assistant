from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.security.auth import get_db_for_user, get_current_user, AuthenticatedUser
from app.integrations.gmail import GmailClient, get_gmail_client
from app.data.models import SchedulingIntent, SchedulingSuggestion, Message, Task, CalendarEvent
from app.data.schemas import (
    SchedulingIntentResponse,
    SchedulingIntentsListResponse,
    OrchestratorRunRequest,
    OrchestratorRunResponse,
    IntentSendRequest,
    SchedulingSuggestionResponse,
)
from app.services.calendar_orchestrator import CalendarOrchestrator
from app.services.calendar import CalendarService
from app.services.entity_cache_coordinator import EntityCacheCoordinator

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])
cache_coordinator = EntityCacheCoordinator()


def _tenant_id() -> str:
    return "default"


def _invalidate_thread_and_prewarm(db: Session, user_id: str, thread_id: str) -> None:
    if not thread_id:
        return
    cache_coordinator.invalidate_thread(_tenant_id(), user_id, thread_id)
    cache_coordinator.prewarm_action_chips(db=db, tenant_id=_tenant_id(), user_id=user_id)


# ── Intent endpoints ──────────────────────────────────────────────────────────

@router.get("/intents", response_model=SchedulingIntentsListResponse)
def get_scheduling_intents(
    status: str = "pending",
    thread_id: str = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db_for_user),
):
    """Get scheduling intents, optionally filtered by status or thread."""
    query = db.query(SchedulingIntent)
    if status:
        query = query.filter(SchedulingIntent.status == status)
    if thread_id:
        query = query.filter(SchedulingIntent.thread_id == thread_id)
    total = query.count()
    intents = query.order_by(SchedulingIntent.created_at.desc()).offset(offset).limit(limit).all()
    return {"intents": [SchedulingIntentResponse.model_validate(i) for i in intents], "total": total}


@router.get("/intents/{intent_id}", response_model=SchedulingIntentResponse)
def get_scheduling_intent(intent_id: int, db: Session = Depends(get_db_for_user)):
    """Get a specific scheduling intent."""
    intent = db.query(SchedulingIntent).filter(SchedulingIntent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    return intent


@router.post("/intents/{intent_id}/run", response_model=OrchestratorRunResponse)
def run_calendar_orchestrator(
    intent_id: int,
    request: OrchestratorRunRequest = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """
    Run the CalendarOrchestrator for a scheduling intent.
    Returns suggested slots + draft reply. Nothing is stored — result is ephemeral.
    User confirms (send / add-to-calendar) in a separate action.
    """
    intent = db.query(SchedulingIntent).filter(SchedulingIntent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    user_note = (request.user_note or "") if request else ""

    try:
        orchestrator = CalendarOrchestrator(db=db, user_id=user.user_id)
        result = orchestrator.run(intent=intent, user_note=user_note)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestrator failed: {str(e)}")


@router.post("/intents/{intent_id}/send")
def send_intent_reply(
    intent_id: int,
    request: IntentSendRequest = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
    gmail_client: GmailClient = Depends(get_gmail_client),
):
    """
    Send a scheduling reply for an intent.
    Optionally creates a calendar event if slot_index is provided.
    """
    intent = db.query(SchedulingIntent).filter(SchedulingIntent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    message = db.query(Message).filter(Message.id == intent.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Source message not found")

    reply_text = request.edited_reply if request and request.edited_reply else None
    if not reply_text:
        raise HTTPException(status_code=400, detail="No reply text provided")

    try:
        gmail_client.send_message(
            to=message.sender,
            subject=f"Re: {message.subject}",
            body=reply_text,
        )

        intent.status = "sent"
        db.commit()

        # Create follow-up task
        follow_up = Task(
            message_id=message.id,
            user_id=message.user_id,
            title=f"Follow up on scheduling with {(message.sender or '').split('@')[0]}",
            description="Check if they responded to your availability",
            task_type="follow_up",
            task_signal="explicit",
            priority="normal",
            status="approved",
            approved_at=datetime.now(timezone.utc),
        )
        db.add(follow_up)
        db.commit()

        if intent.thread_id:
            _invalidate_thread_and_prewarm(db, user.user_id, intent.thread_id)

        return {"success": True, "message": "Reply sent", "follow_up_task_id": follow_up.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send reply: {str(e)}")


@router.post("/intents/{intent_id}/dismiss")
def dismiss_intent(
    intent_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Dismiss a scheduling intent."""
    intent = db.query(SchedulingIntent).filter(SchedulingIntent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    intent.status = "dismissed"
    db.commit()
    if intent.thread_id:
        _invalidate_thread_and_prewarm(db, user.user_id, intent.thread_id)
    return {"success": True}


@router.post("/intents/{intent_id}/acknowledge")
def acknowledge_intent(
    intent_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """
    Acknowledge a meeting reminder intent.
    Used when the meeting is already in the calendar (matched_event_id is set).
    """
    intent = db.query(SchedulingIntent).filter(SchedulingIntent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    intent.status = "acknowledged"
    db.commit()
    return {"success": True}


@router.post("/intents/{intent_id}/add-to-calendar")
def add_intent_to_calendar(
    intent_id: int,
    slot_index: int = 0,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """
    Create a CalendarEvent from an intent's meeting details.
    Used for meeting_confirmation and meeting_reminder (when not already in calendar).
    The slot comes from the most recent orchestrator run (passed by the frontend as slot data).
    """
    intent = db.query(SchedulingIntent).filter(SchedulingIntent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    # For meeting_confirmation / meeting_reminder: create event from extracted meeting_date
    if not intent.meeting_date:
        raise HTTPException(status_code=400, detail="No meeting date extracted from this intent")

    from datetime import datetime as dt
    start = dt.combine(intent.meeting_date, dt.min.time()).replace(tzinfo=timezone.utc)
    end = start.replace(hour=start.hour + 1)  # default 1h duration

    calendar_event = CalendarEvent(
        user_id=user.user_id,
        title=intent.meeting_title or "Meeting",
        start_time=start,
        end_time=end,
        participants=[intent.sender_email] if intent.sender_email else [],
        timezone="UTC",
        source_message_id=intent.message_id,
        provider="manual",
        status="created",
        label="meeting",
    )
    db.add(calendar_event)
    intent.status = "added"
    intent.matched_event_id = calendar_event.id
    db.commit()
    db.refresh(calendar_event)

    from core.cache import calendar_cache
    calendar_cache.invalidate_all(user.user_id)

    return {"success": True, "event_id": calendar_event.id}


# ── Backwards compatibility stubs ────────────────────────────────────────────
# These keep old mobile/web clients from 404-ing during the transition.

@router.get("/suggestions")
def get_scheduling_suggestions_compat(db: Session = Depends(get_db_for_user)):
    """Deprecated. Use GET /scheduling/intents instead."""
    return {"suggestions": [], "total": 0}


@router.get("/suggestions/{suggestion_id}")
def get_scheduling_suggestion_compat(suggestion_id: int, db: Session = Depends(get_db_for_user)):
    """Deprecated."""
    raise HTTPException(status_code=404, detail="Suggestions have been replaced by intents")


@router.post("/detect")
def detect_scheduling_intent_compat(message_id: int, db: Session = Depends(get_db_for_user)):
    """Deprecated. Intent detection is automatic during email processing."""
    return {"success": False, "reason": "Manual detection is no longer supported. Intents are created automatically during email processing."}

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.security.auth import get_db_for_user
from app.data.models import (
    Message, Task, TaskReminder, SchedulingSuggestion,
    CalendarEvent, AgentActivityLog,
    PrincipalMemory, DecisionPattern, ContactContext,
    UserSettings, GmailAccount, TaskQueue
)

router = APIRouter(prefix="/user", tags=["User & GDPR"])

@router.get("/export")
def export_user_data(db: Session = Depends(get_db_for_user)):
    """
    GDPR Data Export - Export all user data as JSON.

    Exports:
    - Messages (with decrypted bodies where available)
    - Tasks
    - Scheduling suggestions
    - Calendar events
    - Memory (preferences, patterns, contacts)
    - Settings
    - Agent activity logs
    """

    export_data = {
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "export_version": "1.0",
    }

    # Messages with decrypted bodies
    messages = db.query(Message).all()
    export_data["messages"] = [
        {
            "id": m.id,
            "message_id": m.message_id,
            "thread_id": m.thread_id,
            "subject": m.subject,
            "sender": m.sender,
            "recipient": m.recipient,
            "body": m.decrypted_body if not m.content_expired else "[CONTENT EXPIRED]",
            "received_at": m.received_at.isoformat() if m.received_at else None,
            "summary": m.summary,
            "needs_reply": m.needs_reply,
            "extracted_tasks": m.extracted_tasks,
            "extracted_dates": m.extracted_dates,
            "extracted_people": m.extracted_people,
            "extracted_decisions": m.extracted_decisions,
            "draft_reply": m.draft_reply,
            "status": m.status,
            "content_expired": m.content_expired,
            "source_deleted": m.source_deleted,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

    # Tasks
    tasks = db.query(Task).all()
    export_data["tasks"] = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "task_type": t.task_type,
            "priority": t.priority,
            "status": t.status,
            "source_snippet": t.source_snippet,
            "confidence_score": t.confidence_score,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in tasks
    ]

    # Scheduling suggestions
    suggestions = db.query(SchedulingSuggestion).all()
    export_data["scheduling_suggestions"] = [
        {
            "id": s.id,
            "participants": s.participants,
            "suggested_slots": s.suggested_slots,
            "meeting_type": s.meeting_type,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in suggestions
    ]

    # Calendar events
    events = db.query(CalendarEvent).all()
    export_data["calendar_events"] = [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "start_time": e.start_time.isoformat() if e.start_time else None,
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "participants": e.participants,
            "status": e.status,
        }
        for e in events
    ]

    # Memory data
    export_data["principal_memory"] = [
        {"key": p.key, "value": p.value, "context_type": p.context_type}
        for p in db.query(PrincipalMemory).all()
    ]

    export_data["decision_patterns"] = [
        {
            "pattern_key": d.pattern_key,
            "pattern_type": d.pattern_type,
            "action": d.action,
            "occurrences": d.occurrences,
            "status": d.status,
        }
        for d in db.query(DecisionPattern).all()
    ]

    export_data["contact_contexts"] = [
        {
            "contact_email": c.contact_email,
            "contact_name": c.contact_name,
            "category": c.category,
            "notes": c.notes,
            "contact_metadata": c.contact_metadata,
        }
        for c in db.query(ContactContext).all()
    ]

    # Agent activity logs
    export_data["agent_activity_logs"] = [
        {
            "id": a.id,
            "action_type": a.action_type,
            "action_description": a.action_description,
            "confidence": a.confidence,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in db.query(AgentActivityLog).all()
    ]

    # Settings
    settings = db.query(UserSettings).first()
    if settings:
        export_data["settings"] = {
            "user_email": settings.user_email,
            "auto_approve_tasks": settings.auto_approve_tasks,
            "task_detection_instructions": settings.task_detection_instructions,
            "reminder_preferences": settings.reminder_preferences,
            "calendar_settings": {
                "default_meeting_duration": settings.default_meeting_duration,
                "working_hours_start": settings.working_hours_start,
                "working_hours_end": settings.working_hours_end,
                "default_timezone": settings.default_timezone,
            }
        }

    # Gmail account info (no tokens)
    account = db.query(GmailAccount).first()
    if account:
        export_data["gmail_account"] = {
            "email": account.email,
            "last_sync": account.last_sync.isoformat() if account.last_sync else None,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        }

    return export_data


@router.delete("/delete")
def delete_user_data(
    confirm: bool = False,
    db: Session = Depends(get_db_for_user)
):
    """
    GDPR Right to Erasure - Complete data deletion.

    Requires confirm=true query parameter as safety check.
    This deletes ALL user data including UserSettings.

    Use /auth/gmail/revoke to delete data while keeping settings.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete all data. This action is irreversible."
        )

    try:
        deletion_summary = {}

        # Delete in order respecting foreign keys
        deletion_summary["task_reminders"] = db.query(TaskReminder).delete()
        deletion_summary["tasks"] = db.query(Task).delete()
        deletion_summary["scheduling_suggestions"] = db.query(SchedulingSuggestion).delete()
        deletion_summary["calendar_events"] = db.query(CalendarEvent).delete()
        deletion_summary["agent_logs"] = db.query(AgentActivityLog).delete()
        deletion_summary["messages"] = db.query(Message).delete()
        deletion_summary["principal_memory"] = db.query(PrincipalMemory).delete()
        deletion_summary["decision_patterns"] = db.query(DecisionPattern).delete()
        deletion_summary["contact_contexts"] = db.query(ContactContext).delete()
        deletion_summary["queue_tasks"] = db.query(TaskQueue).delete()
        deletion_summary["gmail_accounts"] = db.query(GmailAccount).delete()
        deletion_summary["user_settings"] = db.query(UserSettings).delete()  # Includes settings

        db.commit()

        return {
            "success": True,
            "message": "All user data has been permanently deleted.",
            "deleted": deletion_summary
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete data: {str(e)}")

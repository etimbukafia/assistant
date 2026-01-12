from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.auth import get_db_for_user, get_db
from app.gmail_integration import GmailClient, get_gmail_client
from app.models import SchedulingSuggestion, Message, Task
from app.schemas import SchedulingSuggestionResponse, SchedulingSuggestionSendRequest
from app.agents.modules.scheduling import SchedulingModule

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])

@router.get("/suggestions")
def get_scheduling_suggestions(
    message_id: int = None,
    status: str = None,
    db: Session = Depends(get_db_for_user)
):
    """Get scheduling suggestions, optionally filtered by message or status"""

    query = db.query(SchedulingSuggestion)

    if message_id:
        query = query.filter(SchedulingSuggestion.message_id == message_id)
    if status:
        query = query.filter(SchedulingSuggestion.status == status)

    suggestions = query.order_by(SchedulingSuggestion.created_at.desc()).all()

    return {
        "suggestions": [SchedulingSuggestionResponse.model_validate(s) for s in suggestions],
        "total": len(suggestions)
    }


@router.get("/suggestions/{suggestion_id}", response_model=SchedulingSuggestionResponse)
def get_scheduling_suggestion(suggestion_id: int, db: Session = Depends(get_db_for_user)):
    """Get a specific scheduling suggestion"""
    
    suggestion = db.query(SchedulingSuggestion).filter(
        SchedulingSuggestion.id == suggestion_id
    ).first()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    return suggestion


@router.post("/suggestions/{suggestion_id}/send")
def send_scheduling_suggestion(
    suggestion_id: int,
    request: SchedulingSuggestionSendRequest = None,
    db: Session = Depends(get_db_for_user),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """Send availability reply for a scheduling suggestion"""
    
    suggestion = db.query(SchedulingSuggestion).filter(
        SchedulingSuggestion.id == suggestion_id
    ).first()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    # Get source message for reply
    message = db.query(Message).filter(Message.id == suggestion.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Source message not found")

    # Use edited reply or draft
    reply_text = (request.edited_reply if request and request.edited_reply else suggestion.draft_reply)

    if not reply_text:
        raise HTTPException(status_code=400, detail="No reply text available")

    try:
        # Send reply via Gmail
        gmail_client.send_message(
            to=message.sender,
            subject=f"Re: {message.subject}",
            body=reply_text
        )

        # Update suggestion status
        suggestion.status = "sent"
        db.commit()

        # Create follow-up task
        follow_up_task = Task(
            message_id=message.id,
            title=f"Follow up on scheduling with {message.sender.split('@')[0]}",
            description="Check if they responded to your availability",
            task_type="follow_up",
            priority="normal",
            status="approved",
            approved_at=datetime.now(timezone.utc)
        )
        db.add(follow_up_task)
        db.commit()

        return {
            "success": True,
            "message": "Availability reply sent",
            "follow_up_task_id": follow_up_task.id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send reply: {str(e)}")


@router.post("/suggestions/{suggestion_id}/dismiss")
def dismiss_scheduling_suggestion(suggestion_id: int, db: Session = Depends(get_db_for_user)):
    """Dismiss a scheduling suggestion"""

    suggestion = db.query(SchedulingSuggestion).filter(
        SchedulingSuggestion.id == suggestion_id
    ).first()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion.status = "dismissed"
    db.commit()

    return {"success": True, "message": "Suggestion dismissed"}


@router.post("/detect")
def detect_scheduling_intent(
    message_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Manually trigger scheduling detection for a message.

    This is useful for testing or re-processing messages.
    Normally, this happens automatically via the message_received event.
    """

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    scheduling_module = SchedulingModule()

    # Run synchronously for immediate feedback
    result = scheduling_module.generate_suggestions(
        message_id=message.id,
        message_body=message.decrypted_body,
        message_subject=message.subject,
        sender_email=message.sender,
        thread_id=message.thread_id,
        db=db
    )

    return result

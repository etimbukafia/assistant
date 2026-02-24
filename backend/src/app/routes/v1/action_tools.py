"""Action tool endpoints (email drafting and meeting brief generation)."""

from __future__ import annotations

from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, get_db_for_user, require_active_subscription, AuthenticatedUser
from app.superpowers.email_drafting import EmailDraftingService
from app.superpowers.meeting_brief import MeetingBriefService


router = APIRouter(prefix="/action-tools", tags=["Action Tools"])


class EmailDraftRequest(BaseModel):
    subject: str
    intent: str
    recipient: Optional[str] = None
    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    thread: Optional[str] = None
    message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class MeetingBriefRequest(BaseModel):
    event_id: Optional[str] = None
    meeting_subject: Optional[str] = None
    participant_ids: Optional[List[str]] = None
    include_recent_context: bool = False


@router.post("/email-draft")
def draft_email(
    request: EmailDraftRequest,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    if not request.subject.strip():
        raise HTTPException(status_code=400, detail="subject is required")
    if not request.intent.strip():
        raise HTTPException(status_code=400, detail="intent is required")
    service = EmailDraftingService(db=db, user_id=user.user_id)
    return service.draft(
        subject=request.subject,
        intent=request.intent,
        recipient=request.recipient,
        thread_id=request.thread_id,
        message_id=request.message_id,
        thread=request.thread,
        message=request.message,
        context=request.context,
    )


@router.post("/meeting-brief")
def generate_meeting_brief(
    request: MeetingBriefRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = MeetingBriefService(db=db, user_id=user.user_id)
    return service.build_brief(
        event_id=request.event_id,
        meeting_subject=request.meeting_subject,
        participant_ids=request.participant_ids,
        include_recent_context=request.include_recent_context,
    )

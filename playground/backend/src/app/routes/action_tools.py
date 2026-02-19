"""Action tool routes for playground superpowers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.superpowers.email_drafting import EmailDraftingService
from app.superpowers.meeting_brief import MeetingBriefService
from app.superpowers.thread_intelligence import ThreadIntelligenceService


router = APIRouter(prefix="/action-tools", tags=["Action Tools"])


class EmailDraftRequest(BaseModel):
    user_id: str
    subject: str
    intent: str
    recipient: Optional[str] = None
    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    thread: Optional[str] = None
    message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class MeetingBriefRequest(BaseModel):
    user_id: str
    event_id: Optional[str] = None
    meeting_subject: Optional[str] = None
    participant_ids: Optional[List[str]] = None
    include_recent_context: bool = True


class ThreadIntelligenceRequest(BaseModel):
    user_id: str
    thread_id: str


@router.post("/email-draft", response_model=Dict[str, Any])
def draft_email(
    request: EmailDraftRequest,
    db: Session = Depends(get_db),
):
    service = EmailDraftingService(db=db, user_id=request.user_id)
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


@router.post("/meeting-brief", response_model=Dict[str, Any])
def meeting_brief(
    request: MeetingBriefRequest,
    db: Session = Depends(get_db),
):
    service = MeetingBriefService(db=db, user_id=request.user_id)
    return service.build_brief(
        event_id=request.event_id,
        meeting_subject=request.meeting_subject,
        participant_ids=request.participant_ids,
        include_recent_context=request.include_recent_context,
    )


@router.post("/thread-intelligence", response_model=Dict[str, Any])
def thread_intelligence(
    request: ThreadIntelligenceRequest,
    db: Session = Depends(get_db),
):
    service = ThreadIntelligenceService(db=db, user_id=request.user_id)
    return service.analyze(thread_id=request.thread_id)

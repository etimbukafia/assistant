"""Playground inbox routes."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.data.models import InboxMessage, InboxThread
from app.data.schemas import InboxMessageResponse, InboxThreadResponse
from app.db import get_db
from app.superpowers.thread_intelligence import ThreadIntelligenceService


router = APIRouter(prefix="/inbox", tags=["Inbox"])


class ThreadStatusUpdateRequest(BaseModel):
    user_id: str
    status: str


@router.get("/threads", response_model=List[InboxThreadResponse])
def list_threads(
    user_id: str = Query(...),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(InboxThread).filter(InboxThread.user_id == user_id)
    if status:
        query = query.filter(InboxThread.status == status)
    return query.order_by(InboxThread.last_received_at.desc()).all()


@router.patch("/threads/{thread_id}/status", response_model=InboxThreadResponse)
def update_thread_status(
    thread_id: str,
    payload: ThreadStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    status = (payload.status or "").strip().lower()
    if status not in {"open", "waiting", "closed"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    thread = (
        db.query(InboxThread)
        .filter(
            InboxThread.user_id == payload.user_id,
            InboxThread.thread_id == thread_id,
        )
        .first()
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.status = status
    db.commit()
    db.refresh(thread)
    return thread


@router.get("/threads/{thread_id}/messages", response_model=List[InboxMessageResponse])
def list_thread_messages(
    thread_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(InboxMessage)
        .filter(
            InboxMessage.user_id == user_id,
            InboxMessage.thread_id == thread_id,
        )
        .order_by(InboxMessage.sent_at.asc())
        .all()
    )


@router.get("/messages/{message_id}", response_model=InboxMessageResponse)
def get_message(
    message_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    message = (
        db.query(InboxMessage)
        .filter(
            InboxMessage.user_id == user_id,
            InboxMessage.message_id == message_id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message


@router.get("/threads/{thread_id}/intelligence")
def get_thread_intelligence(
    thread_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    service = ThreadIntelligenceService(db=db, user_id=user_id)
    return service.analyze(thread_id=thread_id)

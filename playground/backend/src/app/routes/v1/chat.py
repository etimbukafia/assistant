"""
Playground v1 Chat API Routes (parity surface).

Production-like contract:
- Sessions CRUD
- Send message (sync complete / async processing contract)
- Job status polling endpoint
- Mentions + slash suggestions
- Action chips
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.chat.service import ChatService, ProcessingStatus
from app.security.auth import (
    AuthenticatedUser as User,
    get_current_user,
    get_db_for_user,
    require_active_subscription,
    require_credits_available,
    require_admin_user,
)
from app.infra.database import get_db
from app.services.action_chips import get_cached_action_chips
from app.services.chat_metrics import summarize_chat_metrics
from app.services.mention_context import MentionContextService
from app.services.warm_cache import get_warm_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Basic in-memory rate limiter
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = 20


def _check_rate_limit(user_id: str) -> None:
    now = time.time()
    timestamps = _rate_limit_store[user_id]
    _rate_limit_store[user_id] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[user_id]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {_RATE_LIMIT_MAX} messages per minute.",
        )
    _rate_limit_store[user_id].append(now)


class CreateSessionRequest(BaseModel):
    session_type: str = "command"


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    mentions: Optional[List[dict]] = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    session_type: str
    title: Optional[str]
    created_at: str
    last_activity_at: str
    message_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class MentionSuggestionResponse(BaseModel):
    kind: str
    ref: str
    label: str
    display_label: Optional[str] = None
    subtitle: Optional[str] = None
    last_seen_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    search_text: Optional[str] = None


class ActionChipResponse(BaseModel):
    id: str
    label: str
    prompt: str


class ChatMetricsResponse(BaseModel):
    days: int
    total_calls: int
    successful_calls: int
    failed_calls: int
    latency_ms_p50: float
    latency_ms_p90: float
    latency_ms_p95: float
    prompt_tokens_total: int
    prompt_tokens_avg: float
    repeated_prefix_rate_avg: float
    repeated_prefix_rate_weighted: float
    calls_by_model: Dict[str, int]
    calls_by_path: Dict[str, int]


@router.get("/action-chips", response_model=List[ActionChipResponse])
async def get_action_chips(
    limit: int = Query(default=5, ge=1, le=8),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    return get_cached_action_chips(
        db=db,
        warm_cache=get_warm_cache_service(),
        tenant_id="default",
        user_id=user.user_id,
        limit=limit,
    )


@router.get("/metrics", response_model=ChatMetricsResponse)
def get_chat_metrics(
    days: int = Query(default=7, ge=1, le=30),
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=255),
    model: Optional[str] = Query(default=None, min_length=1, max_length=120),
    _admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    return summarize_chat_metrics(db=db, days=days, user_id=user_id, model=model)


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    user: User = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    service = ChatService(db, user.user_id)
    first_name = user.display_name.split()[0] if user.display_name else None
    session = service.create_session(request.session_type, user_first_name=first_name)
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        session_type=session.session_type,
        title=session.title,
        created_at=session.created_at.isoformat(),
        last_activity_at=session.last_activity_at.isoformat(),
        message_count=0,
    )


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = ChatService(db, user.user_id)
    sessions, total = service.list_sessions(limit=limit, offset=offset)
    return {
        "sessions": [
            {
                "id": s.id,
                "session_type": s.session_type,
                "title": s.title or ("Reflection" if s.session_type == "reflection" else "Work Chat"),
                "created_at": s.created_at.isoformat(),
                "last_activity_at": s.last_activity_at.isoformat(),
                "message_count": len(s.messages) if s.messages else 0,
            }
            for s in sessions
        ],
        "total": total,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = ChatService(db, user.user_id)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = service.get_messages(session_id)
    pending_actions = service.get_pending_actions(session_id)
    return {
        "session": {
            "id": session.id,
            "session_type": session.session_type,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat(),
            "state": session.state,
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.message_metadata,
            }
            for m in messages
        ],
        "pending_actions": [
            {
                "id": pa.id,
                "message_id": pa.message_id,
                "action_type": pa.action_type,
                "action_data": pa.action_data,
                "status": pa.status,
                "created_at": pa.created_at.isoformat(),
            }
            for pa in pending_actions
        ],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = ChatService(db, user.user_id)
    success = service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    user: User = Depends(require_active_subscription),
    _credits: User = Depends(require_credits_available),
    db: Session = Depends(get_db_for_user),
):
    _check_rate_limit(user.user_id)
    service = ChatService(db, user.user_id)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    result = await service.send_message(session_id, request.content, mentions=request.mentions or [])
    if result.status == ProcessingStatus.FAILED:
        raise HTTPException(status_code=500, detail=result.error or "Failed to process message")
    response = {"status": result.status.value, "message_id": result.message_id}
    if result.status == ProcessingStatus.PROCESSING:
        response["job_id"] = result.job_id
    else:
        response["response"] = result.response
        response["pending_actions"] = result.pending_actions or []
    return response


@router.post("/sessions/{session_id}/messages/stream")
async def stream_message(
    session_id: str,
    request: SendMessageRequest,
    http_request: Request,
    user: User = Depends(require_active_subscription),
    _credits: User = Depends(require_credits_available),
    db: Session = Depends(get_db_for_user),
):
    _check_rate_limit(user.user_id)
    service = ChatService(db, user.user_id)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream():
        async for event in service.stream_message(session_id, request.content, mentions=request.mentions or []):
            if await http_request.is_disconnected():
                break
            yield ChatService.format_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = ChatService(db, user.user_id)
    result = service.get_job_status(job_id)
    if result.status == ProcessingStatus.FAILED and result.error == "Job not found":
        raise HTTPException(status_code=404, detail="Job not found")
    response = {"status": result.status.value, "job_id": job_id}
    if result.message_id:
        response["message_id"] = result.message_id
    if result.status == ProcessingStatus.COMPLETE:
        response["response"] = result.response
        response["pending_actions"] = result.pending_actions or []
    elif result.status == ProcessingStatus.FAILED:
        response["error"] = result.error
    return response


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = ChatService(db, user.user_id)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = service.get_messages(session_id, limit=limit, offset=offset)
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.message_metadata,
            }
            for m in rows
        ]
    }


@router.get("/mentions", response_model=List[MentionSuggestionResponse])
async def suggest_mentions(
    q: str = Query(default=""),
    limit: int = Query(default=8, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=5000),
    kind: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default="default"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = MentionContextService(
        db=db,
        warm_cache=get_warm_cache_service(),
        tenant_id="default",
        user_id=user.user_id,
        session_id=session_id or "default",
    )
    return service.suggest_mentions(query=q, limit=limit, offset=offset, kind=kind)


@router.get("/slash-suggestions", response_model=List[MentionSuggestionResponse])
async def suggest_slash(
    q: str = Query(default=""),
    limit: int = Query(default=8, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=5000),
    memory_type: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default="default"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = MentionContextService(
        db=db,
        warm_cache=get_warm_cache_service(),
        tenant_id="default",
        user_id=user.user_id,
        session_id=session_id or "default",
    )
    return service.suggest_memory_entries(query=q, limit=limit, offset=offset, memory_type=memory_type)

"""
Chat API Routes

REST endpoints for AI Chat feature.

Processing Strategy: Optimistic Sync with Async Fallback
- Reflection mode: Always synchronous (warm, immediate)
- Action mode: Sync with timeout, falls back to async for tool-heavy requests
"""
import time
from collections import defaultdict
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

import logging
from app.security.auth import (
    get_current_user,
    get_db_for_user,
    require_active_subscription,
    require_credits_available,
    require_admin_user,
    AuthenticatedUser as User,
)
from app.infra.database import get_db
from app.chat.service import ChatService, ProcessingStatus
from app.services.chat_metrics import summarize_chat_metrics
from app.services.action_chips import get_cached_action_chips
from app.services.warm_cache import get_warm_cache_service
from app.services.mention_context import MentionContextService
from app.chat.tools import ChatToolRegistry

logger = logging.getLogger(__name__)


# Simple in-memory rate limiter for chat messages
# Tracks recent message timestamps per user
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 20  # max messages per window


def _check_rate_limit(user_id: str):
    """Raise 429 if user exceeds message rate limit."""
    now = time.time()
    timestamps = _rate_limit_store[user_id]
    # Prune old entries
    _rate_limit_store[user_id] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[user_id]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {_RATE_LIMIT_MAX} messages per minute."
        )
    _rate_limit_store[user_id].append(now)

router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    session_type: str = "command"  # 'command' or 'reflection'


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


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: str
    metadata: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class PendingActionResponse(BaseModel):
    id: str
    session_id: str
    message_id: Optional[int]
    action_type: str
    action_data: dict
    status: str
    created_at: str

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
    """
    Fast, deterministic personalized action chips for new chat sessions.
    Uses lightweight DB reads only (no LLM calls).
    """
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
    """Admin-only chat model metrics: token volume, latency percentiles, repeated-prefix rate."""
    return summarize_chat_metrics(db=db, days=days, user_id=user_id, model=model)


# =============================================================================
# Session Endpoints
# =============================================================================

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    user: User = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user)
):
    """Create a new chat session."""
    logger.info(f"Creating chat session: type={request.session_type}, user={user.user_id}")
    service = ChatService(db, user.user_id)
    
    # Extract first name from display_name for personalization
    first_name = None
    if user.display_name:
        first_name = user.display_name.split()[0]
    
    session = service.create_session(request.session_type, user_first_name=first_name)
    logger.info(f"Chat session created: id={session.id}, type={session.session_type}, user={user.user_id}")
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        session_type=session.session_type,
        title=session.title,
        created_at=session.created_at.isoformat(),
        last_activity_at=session.last_activity_at.isoformat(),
        message_count=0
    )


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """List user's chat sessions."""
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
                "message_count": len(s.messages) if s.messages else 0
            }
            for s in sessions
        ],
        "total": total
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Get a session with its messages and pending actions."""
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
            "state": session.state
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.message_metadata
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
                "created_at": pa.created_at.isoformat()
            }
            for pa in pending_actions
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Delete a chat session."""
    service = ChatService(db, user.user_id)
    success = service.delete_session(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"success": True}


# =============================================================================
# Message Endpoints
# =============================================================================

@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    user: User = Depends(require_active_subscription),
    _credits: User = Depends(require_credits_available),
    db: Session = Depends(get_db_for_user)
):
    """
    Send a message and get AI response.

    Response varies based on processing path:
    - Sync (immediate): status="complete", response included
    - Async (queued): status="processing", job_id for polling

    Frontend should:
    1. Show typing indicator
    2. If status="complete": display response immediately
    3. If status="processing": poll /jobs/{job_id} every 1-2s
    """
    # Rate limit check
    _check_rate_limit(user.user_id)

    logger.info(f"Chat message: session={session_id}, user={user.user_id}, length={len(request.content)}")
    service = ChatService(db, user.user_id)

    # Verify session exists
    session = service.get_session(session_id)
    if not session:
        logger.warning(f"Chat session not found: session={session_id}, user={user.user_id}")
        raise HTTPException(status_code=404, detail="Session not found")

    # Process message
    try:
        result = await service.send_message(session_id, request.content, mentions=request.mentions or [])
    except Exception as e:
        logger.error(f"Chat send_message failed: session={session_id}, user={user.user_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process message")

    if result.status == ProcessingStatus.FAILED:
        logger.error(f"Chat processing failed: session={session_id}, error={result.error}")
        raise HTTPException(status_code=500, detail=result.error or "Failed to process message")

    # Return unified response format
    response = {
        "status": result.status.value,
        "message_id": result.message_id
    }

    if result.status == ProcessingStatus.PROCESSING:
        # Async path - return job_id for polling
        response["job_id"] = result.job_id
        logger.info(f"Chat async: session={session_id}, job_id={result.job_id}")
    else:
        # Sync path - return response immediately
        response["response"] = result.response
        response["pending_actions"] = result.pending_actions or []
        logger.info(f"Chat sync complete: session={session_id}, response_length={len(result.response or '')}")

    return response


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """
    Check the status of an async chat job.

    Poll this endpoint every 1-2 seconds when status="processing".

    Returns:
    - status="processing": Still working, keep polling
    - status="complete": Done, response and pending_actions included
    - status="failed": Error occurred, error message included
    """
    service = ChatService(db, user.user_id)
    result = service.get_job_status(job_id)

    if result.status == ProcessingStatus.FAILED and result.error == "Job not found":
        logger.warning("Chat job polling failed: user=%s job_id=%s reason=not_found", user.user_id, job_id)
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "status": result.status.value,
        "job_id": job_id
    }

    if result.message_id:
        response["message_id"] = result.message_id

    if result.status == ProcessingStatus.COMPLETE:
        response["response"] = result.response
        response["pending_actions"] = result.pending_actions or []
    elif result.status == ProcessingStatus.FAILED:
        logger.error(
            "Chat job failed: user=%s job_id=%s message_id=%s error=%s",
            user.user_id,
            job_id,
            result.message_id,
            result.error,
        )
        response["error"] = result.error

    return response


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Get conversation history."""
    service = ChatService(db, user.user_id)
    
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = service.get_messages(session_id, limit=limit, offset=offset)
    
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.message_metadata
            }
            for m in messages
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
    # Unified entity search (Jobs-style: single entry point, strict filters).
    entity_types = []
    kind_norm = (kind or "").strip().lower()
    if kind_norm:
        if kind_norm in {"contact", "thread", "event", "task"}:
            entity_types = [kind_norm]
    else:
        entity_types = ["contact", "thread", "event", "task"]

    registry = ChatToolRegistry(db, user.user_id)
    result = registry.execute_tool(
        "entity_search",
        {
            "query": q,
            "entity_types": entity_types,
            "limit": limit,
            "offset": offset,
            "recent_first": True,
            "include_archived": False,
        },
    )
    if not result.success:
        return []
    items = result.data.get("items", []) if isinstance(result.data, dict) else []
    response: List[MentionSuggestionResponse] = []
    for item in items:
        response.append(
            MentionSuggestionResponse(
                kind=str(item.get("kind") or ""),
                ref=str(item.get("ref") or ""),
                label=str(item.get("label") or ""),
                display_label=str(item.get("label") or ""),
                subtitle=str(item.get("sample") or "") or None,
                updated_at=item.get("last_updated_at"),
                search_text=str(item.get("search_text") or "") or None,
            )
        )
    return response


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


# =============================================================================
# Action Approval Endpoints (Legacy - Disabled)
# =============================================================================
#
# These legacy direct-approval routes are intentionally disabled.
# Approval now flows through chat text instructions (and approval gate UI),
# via POST /chat/sessions/{session_id}/messages.
#
# @router.post("/sessions/{session_id}/approve/{action_id}")
# async def approve_action(
#     session_id: str,
#     action_id: str,
#     user: User = Depends(get_current_user),
#     db: Session = Depends(get_db_for_user)
# ):
#     """Approve a pending action."""
#     service = ChatService(db, user.user_id)
#
#     # Verify session ownership
#     session = service.get_session(session_id)
#     if not session:
#         raise HTTPException(status_code=404, detail="Session not found")
#
#     result = service.approve_action(action_id)
#
#     if not result.get("success"):
#         raise HTTPException(status_code=400, detail=result.get("error", "Failed to approve action"))
#
#     return result
#
#
# @router.post("/sessions/{session_id}/reject/{action_id}")
# async def reject_action(
#     session_id: str,
#     action_id: str,
#     user: User = Depends(get_current_user),
#     db: Session = Depends(get_db_for_user)
# ):
#     """Reject a pending action."""
#     service = ChatService(db, user.user_id)
#
#     # Verify session ownership
#     session = service.get_session(session_id)
#     if not session:
#         raise HTTPException(status_code=404, detail="Session not found")
#
#     result = service.reject_action(action_id)
#
#     if not result.get("success"):
#         raise HTTPException(status_code=400, detail=result.get("error", "Failed to reject action"))
#
#     return result

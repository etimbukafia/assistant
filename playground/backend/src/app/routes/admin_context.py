"""Admin routes for context inspection."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.context_assembler import ContextAssembler
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.mention_context import MentionContextService
from app.services.warm_cache import get_warm_cache_service


router = APIRouter(prefix="/admin/context", tags=["Admin Context"])


class ContextDebugRequest(BaseModel):
    message: Optional[str] = ""
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    current_state: Optional[Dict[str, Any]] = None
    task_context: Optional[Dict[str, Any]] = None
    assistant_name: Optional[str] = None
    user_name: Optional[str] = None
    include_prompt: bool = False
    mentions: Optional[List[Dict[str, str]]] = None


@router.post("/debug", response_model=Dict[str, Any])
def debug_context_layers(
    request: ContextDebugRequest,
    db: Session = Depends(get_db),
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = request.tenant_id or tenant_header or "default"
    user_id = request.user_id or "anonymous"
    session_id = request.session_id or "default"
    task_context = request.task_context or request.current_state or {}
    warm_cache = get_warm_cache_service()

    assembler = ContextAssembler(
        db=db,
        hot_cache=get_hot_context_cache_service(),
        warm_cache=warm_cache,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        assistant_name=request.assistant_name,
        user_name=request.user_name,
    )
    payload = assembler.build_debug_payload(
        task_context=task_context,
        message=request.message or "",
        include_prompt=request.include_prompt,
    )
    mention_prefetch = MentionContextService(
        db=db,
        warm_cache=warm_cache,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
    ).prefetch_for_mentions(request.mentions or [])
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "mention_prefetch": mention_prefetch,
        **payload,
    }

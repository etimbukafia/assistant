"""Hot cache observability and invalidation endpoints."""

from typing import Dict, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.services.hot_context_cache import get_hot_context_cache_service


router = APIRouter(prefix="/cache/hot", tags=["HotCache"])


class InvalidateSessionRequest(BaseModel):
    user_id: str
    session_id: str
    tenant_id: Optional[str] = None


class InvalidateUserRequest(BaseModel):
    user_id: str
    tenant_id: Optional[str] = None


@router.get("/stats", response_model=Dict[str, int])
def hot_cache_stats():
    return get_hot_context_cache_service().stats()


@router.post("/invalidate/session")
def invalidate_session(
    payload: InvalidateSessionRequest,
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = payload.tenant_id or tenant_header or "default"
    get_hot_context_cache_service().invalidate_session(
        tenant_id=tenant_id,
        user_id=payload.user_id,
        session_id=payload.session_id,
    )
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "user_id": payload.user_id,
        "session_id": payload.session_id,
    }


@router.post("/invalidate/user")
def invalidate_user(
    payload: InvalidateUserRequest,
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = payload.tenant_id or tenant_header or "default"
    get_hot_context_cache_service().invalidate_user(
        tenant_id=tenant_id,
        user_id=payload.user_id,
    )
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "user_id": payload.user_id,
    }

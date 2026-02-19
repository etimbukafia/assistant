"""Warm cache observability and invalidation endpoints."""

from typing import Dict, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.services.warm_cache import get_warm_cache_service


router = APIRouter(prefix="/cache/warm", tags=["WarmCache"])


class InvalidateScopeRequest(BaseModel):
    user_id: str
    scope: str
    tenant_id: Optional[str] = None


class InvalidateUserRequest(BaseModel):
    user_id: str
    tenant_id: Optional[str] = None


class InvalidateTenantRequest(BaseModel):
    tenant_id: str


@router.get("/stats", response_model=Dict[str, int])
def warm_cache_stats():
    return get_warm_cache_service().stats()


@router.post("/invalidate/scope")
def invalidate_scope(
    payload: InvalidateScopeRequest,
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = payload.tenant_id or tenant_header or "default"
    get_warm_cache_service().invalidate_scope(
        tenant_id=tenant_id,
        user_id=payload.user_id,
        scope=payload.scope,
    )
    return {"ok": True, "scope": payload.scope, "user_id": payload.user_id, "tenant_id": tenant_id}


@router.post("/invalidate/user")
def invalidate_user(
    payload: InvalidateUserRequest,
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = payload.tenant_id or tenant_header or "default"
    get_warm_cache_service().invalidate_user(
        tenant_id=tenant_id,
        user_id=payload.user_id,
    )
    return {"ok": True, "user_id": payload.user_id, "tenant_id": tenant_id}


@router.post("/invalidate/tenant")
def invalidate_tenant(payload: InvalidateTenantRequest):
    get_warm_cache_service().invalidate_tenant(tenant_id=payload.tenant_id)
    return {"ok": True, "tenant_id": payload.tenant_id}

"""Playground context entry routes."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.data.models import Contact, ContextEntry, EntityReference
from app.data.schemas import ContextEntryCreate, ContextEntryResponse, ContextEntryUpdate
from app.db import get_db
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.warm_cache import get_warm_cache_service


router = APIRouter(prefix="/context-entries", tags=["Context"])


def _scopes_for_entry(entry: ContextEntry) -> List[str]:
    scopes: List[str] = []
    entity_type = entry.entity_type or ""
    entity_id = entry.entity_id or ""

    if entity_type == "contact" and entity_id:
        scopes.append(f"contact:{entity_id.lower()}")
    if entity_type == "thread" and entity_id:
        scopes.append(f"thread:{entity_id}")
    if entity_type == "event" and entity_id:
        scopes.append(f"event:{entity_id}")

    if entity_type in {"assistant", "executive"} or entry.type == "preferences":
        scopes.append("profile")

    return scopes


def _validate_entity_reference(db: Session, payload: ContextEntryCreate) -> None:
    entity_type = payload.entity_type.value
    entity_id = (payload.entity_id or "").strip()

    if entity_type in {"assistant", "executive"}:
        return

    if not entity_id:
        raise HTTPException(
            status_code=400,
            detail="Non-profile entries must be linked to a contact, thread, message, or event",
        )

    if entity_type == "contact":
        contact = (
            db.query(Contact)
            .filter(
                Contact.user_id == payload.user_id,
                Contact.email == entity_id.lower(),
            )
            .first()
        )
        if not contact:
            raise HTTPException(status_code=400, detail="Contact reference not found for this user")
        return

    if entity_type in {"thread", "message", "event"}:
        ref = (
            db.query(EntityReference)
            .filter(
                EntityReference.user_id == payload.user_id,
                EntityReference.entity_type == entity_type,
                EntityReference.ref == entity_id,
            )
            .first()
        )
        if not ref:
            raise HTTPException(status_code=400, detail=f"{entity_type.title()} reference not found for this user")
        return

    raise HTTPException(status_code=400, detail="Invalid entity reference")


@router.get("", response_model=List[ContextEntryResponse])
def list_context_entries(
    user_id: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    entry_type: Optional[str] = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
):
    query = db.query(ContextEntry)
    if user_id:
        query = query.filter(ContextEntry.user_id == user_id)
    if entity_type:
        query = query.filter(ContextEntry.entity_type == entity_type)
    if entity_id:
        query = query.filter(ContextEntry.entity_id == entity_id)
    if entry_type:
        query = query.filter(ContextEntry.type == entry_type)
    return query.order_by(ContextEntry.created_at.desc()).all()


@router.post("", response_model=ContextEntryResponse)
def create_context_entry(
    payload: ContextEntryCreate,
    db: Session = Depends(get_db),
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = tenant_header or "default"
    if payload.status.value == "stale" and payload.expires_at is None:
        raise HTTPException(status_code=400, detail="Stale entries must include an expiry date")
    _validate_entity_reference(db, payload)
    entry = ContextEntry(
        user_id=payload.user_id,
        type=payload.type.value,
        content=payload.content,
        entity_type=payload.entity_type.value,
        entity_id=(payload.entity_id or "").strip() or None,
        created_by=payload.created_by.value,
        created_at=datetime.now(timezone.utc),
        importance_level=payload.importance_level.value,
        status=payload.status.value,
        expires_at=payload.expires_at,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    warm_cache = get_warm_cache_service()
    for scope in _scopes_for_entry(entry):
        warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=entry.user_id, scope=scope)
    get_hot_context_cache_service().clear_user_context_entries(tenant_id=tenant_id, user_id=entry.user_id)
    return entry


@router.put("/{entry_id}", response_model=ContextEntryResponse)
def update_context_entry(
    entry_id: int,
    payload: ContextEntryUpdate,
    db: Session = Depends(get_db),
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = tenant_header or "default"
    entry = db.query(ContextEntry).filter(ContextEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Context entry not found")

    if payload.content is not None:
        entry.content = payload.content
    if payload.importance_level is not None:
        entry.importance_level = payload.importance_level.value
    if "status" in payload.__fields_set__ and payload.status is not None:
        entry.status = payload.status.value
    if "expires_at" in payload.__fields_set__:
        entry.expires_at = payload.expires_at
    if entry.status == "stale" and entry.expires_at is None:
        raise HTTPException(status_code=400, detail="Stale entries must include an expiry date")

    db.commit()
    db.refresh(entry)
    warm_cache = get_warm_cache_service()
    for scope in _scopes_for_entry(entry):
        warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=entry.user_id, scope=scope)
    get_hot_context_cache_service().clear_user_context_entries(tenant_id=tenant_id, user_id=entry.user_id)
    return entry


@router.delete("/{entry_id}")
def delete_context_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = tenant_header or "default"
    entry = db.query(ContextEntry).filter(ContextEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Context entry not found")
    user_id = entry.user_id
    db.delete(entry)
    db.commit()
    warm_cache = get_warm_cache_service()
    for scope in _scopes_for_entry(entry):
        warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope=scope)
    get_hot_context_cache_service().clear_user_context_entries(tenant_id=tenant_id, user_id=user_id)
    return {"deleted": True, "id": entry_id}

"""Playground entity reference routes for thread/event/message catalogs."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data.models import EntityReference
from app.data.schemas import EntityReferenceCreate, EntityReferenceResponse, EntityReferenceUpdate
from app.db import get_db


router = APIRouter(prefix="/entity-references", tags=["Entity References"])


@router.get("", response_model=List[EntityReferenceResponse])
def list_entity_references(
    user_id: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(EntityReference)
    if user_id:
        query = query.filter(EntityReference.user_id == user_id)
    if entity_type:
        query = query.filter(EntityReference.entity_type == entity_type)
    if q:
        q_norm = q.strip()
        query = query.filter(
            (EntityReference.display_name.ilike(f"%{q_norm}%"))
            | (EntityReference.ref.ilike(f"%{q_norm}%"))
        )
    return query.order_by(EntityReference.entity_type.asc(), EntityReference.display_name.asc()).all()


@router.post("", response_model=EntityReferenceResponse)
def create_entity_reference(
    payload: EntityReferenceCreate,
    db: Session = Depends(get_db),
):
    display_name = payload.display_name.strip()
    ref = payload.ref.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="Display name is required")
    if not ref:
        raise HTTPException(status_code=400, detail="Reference is required")

    existing_name = (
        db.query(EntityReference)
        .filter(
            EntityReference.user_id == payload.user_id,
            EntityReference.entity_type == payload.entity_type.value,
            func.lower(EntityReference.display_name) == display_name.lower(),
        )
        .first()
    )
    if existing_name:
        raise HTTPException(status_code=409, detail="An entity with this name already exists")

    existing_ref = (
        db.query(EntityReference)
        .filter(
            EntityReference.user_id == payload.user_id,
            EntityReference.entity_type == payload.entity_type.value,
            func.lower(EntityReference.ref) == ref.lower(),
        )
        .first()
    )
    if existing_ref:
        raise HTTPException(status_code=409, detail="An entity with this reference already exists")

    now = datetime.now(timezone.utc)
    entity = EntityReference(
        user_id=payload.user_id,
        entity_type=payload.entity_type.value,
        display_name=display_name,
        ref=ref,
        notes=(payload.notes or "").strip() or None,
        created_at=now,
        updated_at=now,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/{entity_id}", response_model=EntityReferenceResponse)
def update_entity_reference(
    entity_id: int,
    payload: EntityReferenceUpdate,
    db: Session = Depends(get_db),
):
    entity = db.query(EntityReference).filter(EntityReference.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity reference not found")

    if payload.display_name is not None:
        display_name = payload.display_name.strip()
        if not display_name:
            raise HTTPException(status_code=400, detail="Display name cannot be empty")
        existing_name = (
            db.query(EntityReference)
            .filter(
                EntityReference.user_id == entity.user_id,
                EntityReference.entity_type == entity.entity_type,
                func.lower(EntityReference.display_name) == display_name.lower(),
                EntityReference.id != entity.id,
            )
            .first()
        )
        if existing_name:
            raise HTTPException(status_code=409, detail="An entity with this name already exists")
        entity.display_name = display_name

    if payload.ref is not None:
        ref = payload.ref.strip()
        if not ref:
            raise HTTPException(status_code=400, detail="Reference cannot be empty")
        existing_ref = (
            db.query(EntityReference)
            .filter(
                EntityReference.user_id == entity.user_id,
                EntityReference.entity_type == entity.entity_type,
                func.lower(EntityReference.ref) == ref.lower(),
                EntityReference.id != entity.id,
            )
            .first()
        )
        if existing_ref:
            raise HTTPException(status_code=409, detail="An entity with this reference already exists")
        entity.ref = ref

    if payload.notes is not None:
        entity.notes = payload.notes.strip() or None

    entity.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entity)
    return entity


@router.delete("/{entity_id}")
def delete_entity_reference(
    entity_id: int,
    db: Session = Depends(get_db),
):
    entity = db.query(EntityReference).filter(EntityReference.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity reference not found")
    db.delete(entity)
    db.commit()
    return {"deleted": True, "id": entity_id}

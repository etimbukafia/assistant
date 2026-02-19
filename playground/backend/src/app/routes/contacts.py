"""Playground contact routes for EA diary."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import Contact
from app.data.schemas import ContactCreate, ContactResponse, ContactUpdate
from app.db import get_db


router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.get("", response_model=List[ContactResponse])
def list_contacts(
    user_id: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Contact)
    if user_id:
        query = query.filter(Contact.user_id == user_id)
    if q:
        q_norm = q.strip()
        query = query.filter(
            or_(
                Contact.name.ilike(f"%{q_norm}%"),
                Contact.email.ilike(f"%{q_norm}%"),
                Contact.organization.ilike(f"%{q_norm}%"),
            )
        )
    return query.order_by(Contact.name.asc()).all()


@router.post("", response_model=ContactResponse)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    email = (payload.email or "").strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Contact name is required")
    if not email:
        existing_name = (
            db.query(Contact)
            .filter(
                Contact.user_id == payload.user_id,
                func.lower(Contact.name) == name.lower(),
            )
            .first()
        )
        if existing_name:
            raise HTTPException(
                status_code=409,
                detail="A contact with this name already exists. Add an email to distinguish.",
            )

    existing_email = (
        db.query(Contact)
        .filter(
            Contact.user_id == payload.user_id,
            func.lower(Contact.email) == email.lower(),
        )
        .first()
    )
    if email and existing_email:
        raise HTTPException(status_code=409, detail="A contact with this email already exists")

    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id=payload.user_id,
        name=name,
        email=email or None,
        role=(payload.role or "").strip() or None,
        organization=(payload.organization or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
        created_at=now,
        updated_at=now,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Contact name cannot be empty")
        existing_name = (
            db.query(Contact)
            .filter(
                Contact.user_id == contact.user_id,
                func.lower(Contact.name) == name.lower(),
                Contact.id != contact.id,
            )
            .first()
        )
        if existing_name:
            raise HTTPException(status_code=409, detail="A contact with this name already exists")
        contact.name = name

    if payload.email is not None:
        email = payload.email.strip().lower()
        if email:
            existing_email = (
                db.query(Contact)
                .filter(
                    Contact.user_id == contact.user_id,
                    func.lower(Contact.email) == email.lower(),
                    Contact.id != contact.id,
                )
                .first()
            )
            if existing_email:
                raise HTTPException(status_code=409, detail="A contact with this email already exists")
            contact.email = email
        else:
            contact.email = None

    if payload.role is not None:
        contact.role = payload.role.strip() or None
    if payload.organization is not None:
        contact.organization = payload.organization.strip() or None
    if payload.notes is not None:
        contact.notes = payload.notes.strip() or None

    contact.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}")
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"deleted": True, "id": contact_id}

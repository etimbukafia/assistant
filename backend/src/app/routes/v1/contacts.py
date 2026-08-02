import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import Contact, ContextEntry, DiaryEntryLink
from app.data.schemas import (
    ContactBriefResponse,
    ContactCreate,
    ContactDeleteResponse,
    ContactListResponse,
    ContactLookupRequest,
    ContactResponse,
    ContactSignalsResponse,
    ContactTimelineResponse,
    ContactUpdate,
)
from app.security.auth import (
    AuthenticatedUser,
    get_current_user,
    get_db_for_user,
)
from app.security.prompt_sanitizer import sanitize_with_detection
from app.services.contact_brief import ContactBriefService
from app.services.contact_signals import ContactSignalsService
from app.services.contact_timeline import ContactTimelineService
from app.services.entity_cache_coordinator import EntityCacheCoordinator


router = APIRouter(prefix="/contacts", tags=["Contacts"])
logger = logging.getLogger(__name__)
cache_coordinator = EntityCacheCoordinator()


def _tenant_id_for_user(_: AuthenticatedUser) -> str:
    return "default"


def _prewarm_action_chips_cache(db: Session, user: AuthenticatedUser) -> None:
    cache_coordinator.prewarm_action_chips(
        db=db,
        tenant_id=_tenant_id_for_user(user),
        user_id=user.user_id,
    )


def list_contacts_impl(
    *,
    q: Optional[str],
    user: AuthenticatedUser,
    db: Session,
) -> ContactListResponse:
    query = db.query(Contact).filter(Contact.user_id == user.user_id)
    if q:
        q_norm = q.strip()
        query = query.filter(
            or_(
                Contact.name.ilike(f"%{q_norm}%"),
                Contact.email.ilike(f"%{q_norm}%"),
                Contact.organization.ilike(f"%{q_norm}%"),
            )
        )
    contacts = query.order_by(Contact.name.asc()).all()
    return ContactListResponse(contacts=contacts, total=len(contacts))


def get_contact_impl(
    *,
    contact_id: int,
    user: AuthenticatedUser,
    db: Session,
) -> Contact:
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.user_id == user.user_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return contact


def get_contact_by_email_impl(
    *,
    email: str,
    user: AuthenticatedUser,
    db: Session,
) -> Contact:
    contact = (
        db.query(Contact)
        .filter(Contact.user_id == user.user_id, func.lower(Contact.email) == email.strip().lower())
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return contact


def create_contact_impl(
    *,
    payload: ContactCreate,
    user: AuthenticatedUser,
    db: Session,
) -> Contact:
    name = payload.name.strip()
    email = (payload.email or "").strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Contact name is required.")

    if not email:
        existing_name = (
            db.query(Contact)
            .filter(
                Contact.user_id == user.user_id,
                func.lower(Contact.name) == name.lower(),
            )
            .first()
        )
        if existing_name:
            raise HTTPException(
                status_code=409,
                detail="A contact with this name already exists. Add an email if this is a different person.",
            )

    if email:
        existing_email = (
            db.query(Contact)
            .filter(Contact.user_id == user.user_id, func.lower(Contact.email) == email.lower())
            .first()
        )
        if existing_email:
            raise HTTPException(status_code=409, detail="A contact with this email already exists.")

    category = (payload.category or "").strip().lower() or None
    if category and category not in ("vip", "colleague", "external", "vendor"):
        raise HTTPException(status_code=400, detail="Invalid category. Must be one of: vip, colleague, external, vendor.")

    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id=user.user_id,
        name=name,
        email=email or None,
        role=(payload.role or "").strip() or None,
        organization=(payload.organization or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
        category=category,
        created_at=now,
        updated_at=now,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    tenant_id = _tenant_id_for_user(user)
    cache_coordinator.invalidate_contact_by_id(
        db=db,
        tenant_id=tenant_id,
        user_id=user.user_id,
        contact_id=contact.id,
    )
    _prewarm_action_chips_cache(db, user)
    return contact


def update_contact_impl(
    *,
    contact_id: int,
    payload: ContactUpdate,
    user: AuthenticatedUser,
    db: Session,
) -> Contact:
    contact = get_contact_impl(contact_id=contact_id, user=user, db=db)

    old_name = (contact.name or "").strip()
    old_email = (contact.email or "").lower()
    next_name = (payload.name.strip() if payload.name is not None else contact.name).strip()
    if not next_name:
        raise HTTPException(status_code=400, detail="Contact name cannot be empty.")

    next_email = (payload.email if payload.email is not None else contact.email) or ""
    next_email = next_email.strip().lower()

    if next_email:
        existing_email = (
            db.query(Contact)
            .filter(
                Contact.user_id == user.user_id,
                func.lower(Contact.email) == next_email.lower(),
                Contact.id != contact.id,
            )
            .first()
        )
        if existing_email:
            raise HTTPException(status_code=409, detail="A contact with this email already exists.")
    else:
        existing_name = (
            db.query(Contact)
            .filter(
                Contact.user_id == user.user_id,
                func.lower(Contact.name) == next_name.lower(),
                Contact.id != contact.id,
            )
            .first()
        )
        if existing_name:
            raise HTTPException(
                status_code=409,
                detail="A contact with this name already exists. Add an email if this is a different person.",
            )

    contact.name = next_name
    contact.email = next_email or None
    if payload.role is not None:
        contact.role = payload.role.strip() or None
    if payload.organization is not None:
        contact.organization = payload.organization.strip() or None
    if payload.notes is not None:
        contact.notes = payload.notes.strip() or None
    if payload.category is not None:
        category = payload.category.strip().lower() or None
        if category and category not in ("vip", "colleague", "external", "vendor"):
            raise HTTPException(status_code=400, detail="Invalid category. Must be one of: vip, colleague, external, vendor.")
        contact.category = category
    now = datetime.now(timezone.utc)
    contact.updated_at = now

    touched_entries: list[tuple[ContextEntry, ContextEntry]] = []

    if old_email:
        linked_entries = (
            db.query(ContextEntry)
            .join(DiaryEntryLink, DiaryEntryLink.entry_id == ContextEntry.id)
            .filter(
                ContextEntry.user_id == user.user_id,
                DiaryEntryLink.entity_type == "contact",
                func.lower(DiaryEntryLink.entity_id) == old_email,
            )
            .all()
        )
        mention_old = f"@{old_name}" if old_name else None
        mention_new = f"@{next_name}" if next_name else None

        for entry in linked_entries:
            prior_entry = ContextEntry(
                user_id=entry.user_id,
                type=entry.type,
                content=entry.content,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                linked_to=entry.linked_to,
                created_by=entry.created_by,
                status=entry.status,
                expires_at=entry.expires_at,
            )
            updated_entry = False
            for link in entry.links:
                if link.entity_type != "contact":
                    continue
                if (link.entity_id or "").strip().lower() != old_email:
                    continue
                prior_label = (link.display_name or "").strip()
                if link.display_name != next_name:
                    link.display_name = next_name
                    updated_entry = True
                    if prior_label and prior_label != next_name:
                        old_token = f"@{prior_label}"
                        new_token = f"@{next_name}"
                        if old_token in (entry.content or ""):
                            entry.content = (entry.content or "").replace(old_token, new_token)
                            updated_entry = True
                if next_email and next_email != old_email and link.entity_id != next_email:
                    link.entity_id = next_email
                    updated_entry = True

            if mention_old and mention_new and mention_old in (entry.content or ""):
                entry.content = (entry.content or "").replace(mention_old, mention_new)
                updated_entry = True

            if (
                entry.entity_type == "contact"
                and (entry.entity_id or "").strip().lower() == old_email
                and next_email
                and next_email != old_email
            ):
                entry.entity_id = next_email
                updated_entry = True

            if updated_entry:
                entry.updated_at = now
                touched_entries.append((entry, prior_entry))

    db.commit()
    db.refresh(contact)
    tenant_id = _tenant_id_for_user(user)
    if old_email:
        cache_coordinator.invalidate_contact(tenant_id, user.user_id, old_email)
    cache_coordinator.invalidate_contact_by_id(
        db=db,
        tenant_id=tenant_id,
        user_id=user.user_id,
        contact_id=contact.id,
    )
    for entry, prior_entry in touched_entries:
        db.refresh(entry)
        cache_coordinator.invalidate_from_context_entry(
            tenant_id,
            entry,
            prior_entry=prior_entry,
        )
    _prewarm_action_chips_cache(db, user)
    return contact


def delete_contact_impl(
    *,
    contact_id: int,
    user: AuthenticatedUser,
    db: Session,
) -> ContactDeleteResponse:
    contact = get_contact_impl(contact_id=contact_id, user=user, db=db)
    email = (contact.email or "").lower()
    db.delete(contact)
    db.commit()
    tenant_id = _tenant_id_for_user(user)
    if email:
        cache_coordinator.invalidate_contact(tenant_id, user.user_id, email)
    cache_coordinator.invalidate_action_chips(tenant_id, user.user_id)
    cache_coordinator.invalidate_mentions_index(tenant_id, user.user_id)
    _prewarm_action_chips_cache(db, user)
    return ContactDeleteResponse(deleted=True, id=contact_id)


@router.get("", response_model=ContactListResponse)
def list_contacts(
    q: Optional[str] = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    return list_contacts_impl(q=q, user=user, db=db)


@router.post("", response_model=ContactResponse)
def create_contact(
    payload: ContactCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    return create_contact_impl(payload=payload, user=user, db=db)


@router.post("/lookup", response_model=ContactResponse)
def lookup_contact(
    payload: ContactLookupRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    return get_contact_by_email_impl(email=payload.email, user=user, db=db)


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    return get_contact_impl(contact_id=contact_id, user=user, db=db)


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    return update_contact_impl(contact_id=contact_id, payload=payload, user=user, db=db)


@router.delete("/{contact_id}", response_model=ContactDeleteResponse)
def delete_contact(
    contact_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    return delete_contact_impl(contact_id=contact_id, user=user, db=db)


@router.get("/{contact_id}/brief", response_model=ContactBriefResponse)
def get_contact_brief(
    contact_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    brief = ContactBriefService(db=db, user_id=user.user_id).get_contact_brief(contact_id, consumer="contacts_api")
    if not brief:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return ContactBriefResponse(**brief)


@router.get("/{contact_id}/timeline", response_model=ContactTimelineResponse)
def get_contact_timeline(
    contact_id: int,
    limit: int = 25,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    brief = ContactBriefService(db=db, user_id=user.user_id).get_contact_brief(contact_id, consumer="contacts_api")
    if not brief:
        raise HTTPException(status_code=404, detail="Contact not found.")

    timeline = ContactTimelineService(db=db, user_id=user.user_id).get_contact_timeline(contact_id, limit=limit)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return ContactTimelineResponse(
        contact=brief["contact"],
        timeline=[_serialize_timeline_item(item, contact_id=contact_id) for item in timeline],
    )


@router.get("/{contact_id}/signals", response_model=ContactSignalsResponse)
def get_contact_signals(
    contact_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    brief = ContactBriefService(db=db, user_id=user.user_id).get_contact_brief(contact_id, consumer="contacts_api")
    if not brief:
        raise HTTPException(status_code=404, detail="Contact not found.")

    signals = ContactSignalsService(db=db, user_id=user.user_id).get_contact_signals(contact_id, consumer="contacts_api")
    if signals is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return ContactSignalsResponse(
        contact=brief["contact"],
        signals=[_serialize_signal_item(item, contact_id=contact_id) for item in signals],
    )


def _serialize_timeline_item(item: dict, *, contact_id: int) -> dict:
    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "title": _sanitize_response_text(
            item.get("title"),
            field=f"timeline.{item.get('kind') or 'item'}",
            contact_id=contact_id,
            max_length=140,
        )
        or "Relationship event",
        "detail": _sanitize_response_text(
            item.get("detail"),
            field=f"timeline.{item.get('kind') or 'item'}_detail",
            contact_id=contact_id,
            max_length=160,
        ),
        "occurred_at": item.get("occurred_at"),
        "source_type": item.get("source_type"),
        "source_ref": item.get("source_ref"),
        "source_resolved": item.get("source_resolved"),
        "status": item.get("status"),
    }


def _serialize_signal_item(item: dict, *, contact_id: int) -> dict:
    return {
        "key": item.get("key"),
        "label": _sanitize_response_text(item.get("label"), field="signal.label", contact_id=contact_id, max_length=80)
        or "Relationship signal",
        "severity": item.get("severity") or "info",
        "detail": _sanitize_response_text(item.get("detail"), field="signal.detail", contact_id=contact_id, max_length=160),
    }


def _sanitize_response_text(value: object, *, field: str, contact_id: int, max_length: int) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return None
    truncated = text[:max_length]
    result = sanitize_with_detection(truncated)
    if result.patterns_detected:
        logger.warning(
            "contact_route_payload_sanitized contact_id=%s field=%s patterns=%s",
            contact_id,
            field,
            result.patterns_detected,
        )
    cleaned = " ".join(result.sanitized_text.split()).strip()
    return cleaned or None

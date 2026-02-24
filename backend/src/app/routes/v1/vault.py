from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import (
    VaultProposal,
    VaultNote,
    VaultMetricsDaily,
    Contact,
    ContextEntry,
    DiaryEntryLink,
    EntityReference,
)
from app.data.schemas import (
    VaultNoteCreate,
    VaultNoteUpdate,
    VaultNoteResponse,
    VaultNotesListResponse,
    VaultProposalResponse,
    VaultProposalsListResponse,
    VaultProposalRejectRequest,
    VaultStatsResponse,
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    ContextEntryCreate,
    ContextEntryUpdate,
    ContextEntryResponse,
    ContextEntityType,
    EntityReferenceCreate,
    EntityReferenceUpdate,
    EntityReferenceResponse,
)
from app.security.auth import (
    get_current_user,
    require_active_subscription,
    get_db_for_user,
    AuthenticatedUser,
)
from app.services.vault import VaultService
from app.services.entity_cache_coordinator import EntityCacheCoordinator
from app.intelligence.pattern_tracker import PatternTracker
from app.infra.config import get_settings


router = APIRouter(prefix="/vault", tags=["Vault"])


cache_coordinator = EntityCacheCoordinator()


def _tenant_id_for_user(_: AuthenticatedUser) -> str:
    # Main backend is currently single-tenant from API perspective.
    return "default"


def _prewarm_action_chips_cache(db: Session, user: AuthenticatedUser) -> None:
    tenant_id = _tenant_id_for_user(user)
    cache_coordinator.prewarm_action_chips(
        db=db,
        tenant_id=tenant_id,
        user_id=user.user_id,
    )


def _effective_diary_status(
    *,
    expires_at: Optional[datetime],
    requested_status: Optional[str] = None,
) -> str:
    if requested_status in {"resolved", "archived"}:
        return requested_status
    now = datetime.now(timezone.utc)
    if expires_at is not None and expires_at <= now:
        return "stale"
    return "active"


def _to_context_entry_response(entry: ContextEntry) -> ContextEntryResponse:
    response = ContextEntryResponse.model_validate(entry)
    if response.status == "active" and response.expires_at is not None and response.expires_at <= datetime.now(timezone.utc):
        response.status = "stale"
    return response


def _assert_proposals_enabled() -> None:
    if not get_settings().PROPOSALS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


def _validate_diary_entity_reference(db: Session, user_id: str, payload: ContextEntryCreate) -> None:
    entity_type = payload.entity_type.value
    entity_id = (payload.entity_id or "").strip()

    if entity_type in {"assistant", "executive"}:
        return

    if entity_type == "message":
        raise HTTPException(status_code=400, detail="Use thread references instead of message references.")

    if not entity_id:
        raise HTTPException(
            status_code=400,
            detail="This memory must be linked to a contact, thread, or event.",
        )

    if entity_type == "contact":
        contact = (
            db.query(Contact)
            .filter(
                Contact.user_id == user_id,
                func.lower(Contact.email) == entity_id.lower(),
            )
            .first()
        )
        if not contact:
            raise HTTPException(status_code=400, detail="Contact reference not found for this user.")
        return

    if entity_type in {"thread", "event"}:
        ref = (
            db.query(EntityReference)
            .filter(
                EntityReference.user_id == user_id,
                EntityReference.entity_type == entity_type,
                EntityReference.ref == entity_id,
            )
            .first()
        )
        if not ref:
            raise HTTPException(status_code=400, detail=f"{entity_type.title()} reference not found for this user.")
        return

    raise HTTPException(status_code=400, detail="Invalid entity reference.")


@router.get("/notes", response_model=VaultNotesListResponse)
def list_notes(
    note_type: Optional[str] = None,
    q: Optional[str] = Query(default=None),
    limit: int = 50,
    offset: int = 0,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    if q:
        notes = service.search_notes(q, note_type=note_type, limit=limit)
        return VaultNotesListResponse(notes=notes, total=len(notes))
    notes, total = service.list_notes(note_type=note_type, limit=limit, offset=offset)
    return VaultNotesListResponse(notes=notes, total=total)


@router.post("/notes", response_model=VaultNoteResponse)
def create_note(
    request: VaultNoteCreate,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    return service.create_note(
        note_type=request.note_type,
        title=request.title,
        body=request.body,
        frontmatter=request.frontmatter,
        canonical_email=request.canonical_email,
        source=request.source,
        confidence=request.confidence,
    )


@router.get("/notes/{note_id}", response_model=VaultNoteResponse)
def get_note(
    note_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    note = service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/notes/{note_id}", response_model=VaultNoteResponse)
def update_note(
    note_id: int,
    request: VaultNoteUpdate,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    note = service.update_note(
        note_id=note_id,
        title=request.title,
        body=request.body,
        frontmatter=request.frontmatter,
        pinned=request.pinned,
        status=request.status,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/notes/{note_id}", response_model=VaultNoteResponse)
def archive_note(
    note_id: int,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    note = service.archive_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.get("/notes/{note_id}/neighbors", response_model=list[VaultNoteResponse])
def get_neighbors(
    note_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    return service.get_neighbors(note_id, depth=1)


@router.get("/proposals", response_model=VaultProposalsListResponse)
def list_proposals(
    status: str = "pending",
    limit: int = 50,
    offset: int = 0,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    _assert_proposals_enabled()
    service = VaultService(db, user.user_id)
    proposals, total = service.list_proposals(status=status, limit=limit, offset=offset)
    return VaultProposalsListResponse(proposals=proposals, total=total)


@router.get("/proposals/count")
def proposals_count(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    _assert_proposals_enabled()
    count = db.query(VaultProposal).filter(
        VaultProposal.user_id == user.user_id,
        VaultProposal.status == "pending",
    ).count()
    return {"count": count}


@router.post("/proposals/{proposal_id}/approve", response_model=VaultProposalResponse)
def approve_proposal(
    proposal_id: int,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    _assert_proposals_enabled()
    service = VaultService(db, user.user_id)
    proposal = service.approve_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    tracker = PatternTracker(db, user.user_id)
    data = proposal.proposed_data or {}
    tracker.track_action(
        action_type="vault_proposal_approve",
        context={
            "proposal_type": proposal.proposal_type,
            "note_type": data.get("note_type"),
            "source_type": proposal.source_type,
        },
        context_category="task_review",
    )
    return proposal


@router.post("/proposals/{proposal_id}/reject", response_model=VaultProposalResponse)
def reject_proposal(
    proposal_id: int,
    request: VaultProposalRejectRequest,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    _assert_proposals_enabled()
    service = VaultService(db, user.user_id)
    proposal = service.reject_proposal(proposal_id, request.reason, request.category)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    tracker = PatternTracker(db, user.user_id)
    data = proposal.proposed_data or {}
    tracker.track_action(
        action_type="vault_proposal_reject",
        context={
            "proposal_type": proposal.proposal_type,
            "note_type": data.get("note_type"),
            "source_type": proposal.source_type,
            "rejection_category": request.category,
        },
        context_category="task_review",
    )
    return proposal


class BulkApproveRequest(BaseModel):
    proposal_ids: list[int]


@router.post("/proposals/bulk-approve")
def bulk_approve(
    request: BulkApproveRequest,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    _assert_proposals_enabled()
    service = VaultService(db, user.user_id)
    approved = 0
    for pid in request.proposal_ids:
        proposal = service.approve_proposal(pid)
        if proposal and proposal.status == "approved":
            approved += 1
    return {"approved": approved, "requested": len(request.proposal_ids)}


@router.get("/export")
def export_vault(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    payload = service.export_vault()
    filename = f"vault_{user.user_id}_{datetime.now(timezone.utc).date().isoformat()}.zip"
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/search", response_model=VaultNotesListResponse)
def search_vault(
    q: str,
    note_type: Optional[str] = None,
    limit: int = 20,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    notes = service.search_notes(q, note_type=note_type, limit=limit)
    return VaultNotesListResponse(notes=notes, total=len(notes))


@router.get("/diary/context-entries", response_model=List[ContextEntryResponse])
def list_context_entries(
    entity_type: Optional[ContextEntityType] = None,
    entity_id: Optional[str] = None,
    entry_type: Optional[str] = Query(default=None, alias="type"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    query = db.query(ContextEntry).filter(ContextEntry.user_id == user.user_id)
    if entity_type:
        query = query.filter(ContextEntry.entity_type == entity_type.value)
    if entity_id:
        query = query.filter(ContextEntry.entity_id == entity_id)
    if entry_type:
        query = query.filter(ContextEntry.type == entry_type)
    rows = query.order_by(ContextEntry.created_at.desc()).all()
    visible_rows: List[ContextEntryResponse] = []
    for row in rows:
        response = _to_context_entry_response(row)
        if response.status in {"active", "stale"}:
            visible_rows.append(response)
    return visible_rows


@router.post("/diary/context-entries", response_model=ContextEntryResponse)
def create_context_entry(
    payload: ContextEntryCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    _validate_diary_entity_reference(db=db, user_id=user.user_id, payload=payload)
    now = datetime.now(timezone.utc)
    primary_link = payload.links[0] if payload.links else None
    entity_type = primary_link.entity_type if primary_link else payload.entity_type.value
    entity_id = primary_link.entity_id if primary_link else ((payload.entity_id or "").strip() or None)
    linked_to = primary_link.display_name if primary_link else payload.linked_to

    entry = ContextEntry(
        user_id=user.user_id,
        type=payload.type.value,
        content=payload.content.strip(),
        entity_type=entity_type,
        entity_id=entity_id,
        linked_to=linked_to,
        created_by=payload.created_by.value,
        importance_level=payload.importance_level.value,
        status=_effective_diary_status(
            expires_at=payload.expires_at,
            requested_status=payload.status.value,
        ),
        expires_at=payload.expires_at,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.flush()  # get entry.id before committing

    for link in payload.links:
        db.add(DiaryEntryLink(
            entry_id=entry.id,
            entity_type=link.entity_type,
            entity_id=link.entity_id,
            display_name=link.display_name,
        ))

    db.commit()
    db.refresh(entry)
    cache_coordinator.invalidate_from_context_entry(_tenant_id_for_user(user), entry)
    _prewarm_action_chips_cache(db, user)
    return _to_context_entry_response(entry)


@router.put("/diary/context-entries/{entry_id}", response_model=ContextEntryResponse)
def update_context_entry(
    entry_id: int,
    payload: ContextEntryUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    entry = (
        db.query(ContextEntry)
        .filter(ContextEntry.id == entry_id, ContextEntry.user_id == user.user_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Context entry not found.")

    prior_entry = ContextEntry(
        user_id=entry.user_id,
        type=entry.type,
        content=entry.content,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        created_by=entry.created_by,
        importance_level=entry.importance_level,
        status=entry.status,
        expires_at=entry.expires_at,
    )

    if payload.content is not None:
        entry.content = payload.content.strip()
    if payload.importance_level is not None:
        entry.importance_level = payload.importance_level.value
    if "expires_at" in payload.model_fields_set:
        entry.expires_at = payload.expires_at
    if payload.status is not None:
        entry.status = _effective_diary_status(
            expires_at=entry.expires_at,
            requested_status=payload.status.value,
        )
    elif entry.status in {"active", "stale"}:
        entry.status = _effective_diary_status(
            expires_at=entry.expires_at,
            requested_status=None,
        )

    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    cache_coordinator.invalidate_from_context_entry(
        _tenant_id_for_user(user),
        entry,
        prior_entry=prior_entry,
    )
    _prewarm_action_chips_cache(db, user)
    return _to_context_entry_response(entry)


@router.delete("/diary/context-entries/{entry_id}")
def delete_context_entry(
    entry_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    entry = (
        db.query(ContextEntry)
        .filter(ContextEntry.id == entry_id, ContextEntry.user_id == user.user_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Context entry not found.")

    prior_entry = ContextEntry(
        user_id=entry.user_id,
        type=entry.type,
        content=entry.content,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        created_by=entry.created_by,
        importance_level=entry.importance_level,
        status=entry.status,
        expires_at=entry.expires_at,
    )
    entry.status = "resolved"
    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    cache_coordinator.invalidate_from_context_entry(
        _tenant_id_for_user(user),
        entry,
        prior_entry=prior_entry,
    )
    _prewarm_action_chips_cache(db, user)
    return {"deleted": True, "id": entry_id}


@router.get("/diary/contacts", response_model=List[ContactResponse])
def list_diary_contacts(
    q: Optional[str] = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
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
    return query.order_by(Contact.name.asc()).all()


@router.post("/diary/contacts", response_model=ContactResponse)
def create_diary_contact(
    payload: ContactCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
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

    now = datetime.now(timezone.utc)
    category = (payload.category or "").strip().lower() or None
    if category and category not in ("vip", "colleague", "external", "vendor"):
        raise HTTPException(status_code=400, detail="Invalid category. Must be one of: vip, colleague, external, vendor.")
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
    if contact.email:
        cache_coordinator.invalidate_contact(_tenant_id_for_user(user), user.user_id, contact.email)
    _prewarm_action_chips_cache(db, user)
    return contact


@router.put("/diary/contacts/{contact_id}", response_model=ContactResponse)
def update_diary_contact(
    contact_id: int,
    payload: ContactUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.user_id == user.user_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")

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
        cat = payload.category.strip().lower() or None
        if cat and cat not in ("vip", "colleague", "external", "vendor"):
            raise HTTPException(status_code=400, detail="Invalid category. Must be one of: vip, colleague, external, vendor.")
        contact.category = cat
    now = datetime.now(timezone.utc)
    contact.updated_at = now

    if old_email:
        # Keep diary links and linked memory text in sync with renamed contacts.
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

    db.commit()
    db.refresh(contact)
    tenant_id = _tenant_id_for_user(user)
    if old_email:
        cache_coordinator.invalidate_contact(tenant_id, user.user_id, old_email)
    if contact.email:
        cache_coordinator.invalidate_contact(tenant_id, user.user_id, contact.email)
    _prewarm_action_chips_cache(db, user)
    return contact


@router.get("/diary/contacts/by-email/{email}", response_model=ContactResponse)
def get_diary_contact_by_email(
    email: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    contact = (
        db.query(Contact)
        .filter(Contact.user_id == user.user_id, func.lower(Contact.email) == email.strip().lower())
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return contact


@router.delete("/diary/contacts/{contact_id}")
def delete_diary_contact(
    contact_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.user_id == user.user_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found.")
    email = (contact.email or "").lower()
    db.delete(contact)
    db.commit()
    if email:
        cache_coordinator.invalidate_contact(_tenant_id_for_user(user), user.user_id, email)
    _prewarm_action_chips_cache(db, user)
    return {"deleted": True, "id": contact_id}


@router.get("/diary/entity-references", response_model=List[EntityReferenceResponse])
def list_entity_references(
    entity_type: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    query = db.query(EntityReference).filter(EntityReference.user_id == user.user_id)
    if entity_type == "message":
        raise HTTPException(status_code=400, detail="Message references are disabled. Use thread references.")
    if entity_type:
        query = query.filter(EntityReference.entity_type == entity_type)
    else:
        query = query.filter(EntityReference.entity_type.in_(["thread", "event"]))
    if q:
        q_norm = q.strip()
        query = query.filter(
            or_(
                EntityReference.display_name.ilike(f"%{q_norm}%"),
                EntityReference.ref.ilike(f"%{q_norm}%"),
            )
        )
    return query.order_by(EntityReference.entity_type.asc(), EntityReference.display_name.asc()).all()


@router.post("/diary/entity-references", response_model=EntityReferenceResponse)
def create_entity_reference(
    payload: EntityReferenceCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    display_name = payload.display_name.strip()
    ref = payload.ref.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="Display name is required.")
    if not ref:
        raise HTTPException(status_code=400, detail="Reference is required.")
    if payload.entity_type.value == "message":
        raise HTTPException(status_code=400, detail="Message references are disabled. Use thread references.")

    existing_name = (
        db.query(EntityReference)
        .filter(
            EntityReference.user_id == user.user_id,
            EntityReference.entity_type == payload.entity_type.value,
            func.lower(EntityReference.display_name) == display_name.lower(),
        )
        .first()
    )
    if existing_name:
        raise HTTPException(status_code=409, detail="An entity with this name already exists.")

    existing_ref = (
        db.query(EntityReference)
        .filter(
            EntityReference.user_id == user.user_id,
            EntityReference.entity_type == payload.entity_type.value,
            func.lower(EntityReference.ref) == ref.lower(),
        )
        .first()
    )
    if existing_ref:
        raise HTTPException(status_code=409, detail="An entity with this reference already exists.")

    now = datetime.now(timezone.utc)
    entity = EntityReference(
        user_id=user.user_id,
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
    tenant_id = _tenant_id_for_user(user)
    if entity.entity_type == "thread":
        cache_coordinator.invalidate_thread(tenant_id, user.user_id, entity.ref)
    elif entity.entity_type == "event":
        cache_coordinator.invalidate_event(tenant_id, user.user_id, entity.ref)
    _prewarm_action_chips_cache(db, user)
    return entity


@router.put("/diary/entity-references/{entity_id}", response_model=EntityReferenceResponse)
def update_entity_reference(
    entity_id: int,
    payload: EntityReferenceUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    entity = (
        db.query(EntityReference)
        .filter(EntityReference.id == entity_id, EntityReference.user_id == user.user_id)
        .first()
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Entity reference not found.")

    old_ref = entity.ref
    if payload.display_name is not None:
        display_name = payload.display_name.strip()
        if not display_name:
            raise HTTPException(status_code=400, detail="Display name cannot be empty.")
        existing_name = (
            db.query(EntityReference)
            .filter(
                EntityReference.user_id == user.user_id,
                EntityReference.entity_type == entity.entity_type,
                func.lower(EntityReference.display_name) == display_name.lower(),
                EntityReference.id != entity.id,
            )
            .first()
        )
        if existing_name:
            raise HTTPException(status_code=409, detail="An entity with this name already exists.")
        entity.display_name = display_name

    if payload.ref is not None:
        ref = payload.ref.strip()
        if not ref:
            raise HTTPException(status_code=400, detail="Reference cannot be empty.")
        existing_ref = (
            db.query(EntityReference)
            .filter(
                EntityReference.user_id == user.user_id,
                EntityReference.entity_type == entity.entity_type,
                func.lower(EntityReference.ref) == ref.lower(),
                EntityReference.id != entity.id,
            )
            .first()
        )
        if existing_ref:
            raise HTTPException(status_code=409, detail="An entity with this reference already exists.")
        entity.ref = ref

    if payload.notes is not None:
        entity.notes = payload.notes.strip() or None
    entity.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entity)

    tenant_id = _tenant_id_for_user(user)
    refs_to_invalidate = {old_ref, entity.ref}
    for ref in refs_to_invalidate:
        if entity.entity_type == "thread":
            cache_coordinator.invalidate_thread(tenant_id, user.user_id, ref)
        elif entity.entity_type == "event":
            cache_coordinator.invalidate_event(tenant_id, user.user_id, ref)
    _prewarm_action_chips_cache(db, user)
    return entity


@router.delete("/diary/entity-references/{entity_id}")
def delete_entity_reference(
    entity_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    entity = (
        db.query(EntityReference)
        .filter(EntityReference.id == entity_id, EntityReference.user_id == user.user_id)
        .first()
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Entity reference not found.")

    entity_type = entity.entity_type
    ref = entity.ref
    db.delete(entity)
    db.commit()

    tenant_id = _tenant_id_for_user(user)
    if entity_type == "thread":
        cache_coordinator.invalidate_thread(tenant_id, user.user_id, ref)
    elif entity_type == "event":
        cache_coordinator.invalidate_event(tenant_id, user.user_id, ref)
    _prewarm_action_chips_cache(db, user)
    return {"deleted": True, "id": entity_id}


@router.get("/stats", response_model=VaultStatsResponse)
def vault_stats(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)

    approved = db.query(VaultProposal).filter(
        VaultProposal.user_id == user.user_id,
        VaultProposal.status == "approved",
        VaultProposal.reviewed_at >= since,
    ).count()
    rejected = db.query(VaultProposal).filter(
        VaultProposal.user_id == user.user_id,
        VaultProposal.status == "rejected",
        VaultProposal.reviewed_at >= since,
    ).count()
    pending = db.query(VaultProposal).filter(
        VaultProposal.user_id == user.user_id,
        VaultProposal.status == "pending",
    ).count()
    stale = db.query(VaultProposal).filter(
        VaultProposal.user_id == user.user_id,
        VaultProposal.status == "pending",
        VaultProposal.created_at < (now - timedelta(days=7)),
    ).count()
    total_notes = db.query(VaultNote).filter(VaultNote.user_id == user.user_id).count()

    by_type_rows = db.query(VaultNote.note_type, func.count(VaultNote.id)).filter(
        VaultNote.user_id == user.user_id
    ).group_by(VaultNote.note_type).all()
    notes_by_type = {k: v for k, v in by_type_rows}

    rej_rows = db.query(VaultProposal.rejection_category, func.count(VaultProposal.id)).filter(
        VaultProposal.user_id == user.user_id,
        VaultProposal.status == "rejected",
        VaultProposal.rejection_category.isnot(None),
    ).group_by(VaultProposal.rejection_category).order_by(func.count(VaultProposal.id).desc()).limit(5).all()

    metrics = db.query(VaultMetricsDaily).filter(
        VaultMetricsDaily.user_id == user.user_id,
        VaultMetricsDaily.date >= since.date(),
    ).all()
    attempts = sum(m.context_attempt_count or 0 for m in metrics)
    injected = sum(m.context_injected_count or 0 for m in metrics)
    proposals_created = sum(m.proposals_created_count or 0 for m in metrics)
    days = max(1, len({m.date for m in metrics}))

    denom = approved + rejected
    return VaultStatsResponse(
        proposal_acceptance_rate=(approved / denom) if denom else 0.0,
        proposals_pending=pending,
        proposals_stale_count=stale,
        context_hit_rate=(injected / attempts) if attempts else 0.0,
        total_notes=total_notes,
        notes_by_type=notes_by_type,
        avg_proposals_per_day=(proposals_created / days),
        top_rejection_categories=[{"category": k, "count": v} for k, v in rej_rows],
    )

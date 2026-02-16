from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data.models import ContactContext, VaultProposal, VaultNote, VaultMetricsDaily, Message
from app.data.schemas import (
    VaultNoteCreate,
    VaultNoteUpdate,
    VaultNoteResponse,
    VaultNotesListResponse,
    VaultProposalResponse,
    VaultProposalsListResponse,
    VaultProposalRejectRequest,
    ContactPromoteRequest,
    MentionableContactsResponse,
    MentionableEmailsResponse,
    MentionableNotesResponse,
    MeetingPrepResponse,
    VaultStatsResponse,
)
from app.security.auth import (
    get_current_user,
    require_active_subscription,
    get_db_for_user,
    AuthenticatedUser,
)
from app.services.vault import VaultService
from app.services.vault_context import VaultContextService
from app.intelligence.pattern_tracker import PatternTracker


router = APIRouter(prefix="/vault", tags=["Vault"])


class MeetingPrepRequest(BaseModel):
    event_id: int


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
    service = VaultService(db, user.user_id)
    proposals, total = service.list_proposals(status=status, limit=limit, offset=offset)
    return VaultProposalsListResponse(proposals=proposals, total=total)


@router.get("/proposals/count")
def proposals_count(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
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
    service = VaultService(db, user.user_id)
    approved = 0
    for pid in request.proposal_ids:
        proposal = service.approve_proposal(pid)
        if proposal and proposal.status == "approved":
            approved += 1
    return {"approved": approved, "requested": len(request.proposal_ids)}


@router.get("/contacts/candidates")
def contact_candidates(
    limit: int = 50,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    contacts = db.query(ContactContext).filter(
        ContactContext.user_id == user.user_id,
        ContactContext.promoted == False,  # noqa: E712
    ).all()
    ranked = sorted(
        contacts,
        key=lambda c: (c.contact_metadata or {}).get("message_count", 0),
        reverse=True,
    )
    ranked = ranked[:limit]
    return {
        "contacts": [
            {
                "email": c.contact_email,
                "name": c.contact_name,
                "message_count": (c.contact_metadata or {}).get("message_count", 0),
            }
            for c in ranked
        ]
    }


@router.post("/contacts/{email}/promote", response_model=VaultNoteResponse)
def promote_contact(
    email: str,
    request: ContactPromoteRequest,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    return service.promote_contact(email, display_name=request.display_name)


@router.get("/contacts/mentionable", response_model=MentionableContactsResponse)
def mentionable_contacts(
    q: Optional[str] = Query(default=None),
    limit: int = 10,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    return {"contacts": service.get_mentionable_contacts(q=q, limit=limit)}

@router.get("/emails/mentionable", response_model=MentionableEmailsResponse)
def mentionable_emails(
    q: Optional[str] = Query(default=None),
    limit: int = 10,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    query = db.query(Message).filter(
        Message.user_id == user.user_id,
    )
    if q:
        like_query = f"%{q.strip()}%"
        query = query.filter(
            (Message.subject.ilike(like_query)) |
            (Message.sender.ilike(like_query)) |
            (Message.thread_id.ilike(like_query))
        )
    rows = query.order_by(Message.received_at.desc()).limit(max(1, min(limit, 25))).all()
    return {
        "emails": [
            {
                "message_id": m.id,
                "subject": m.subject,
                "sender": m.sender,
                "thread_id": m.thread_id,
                "received_at": m.received_at,
                "label": f"@email/{m.subject or '(no subject)'} ({m.sender or 'unknown'})",
            }
            for m in rows
        ]
    }


@router.get("/notes/mentionable", response_model=MentionableNotesResponse)
def mentionable_notes(
    q: Optional[str] = Query(default=None),
    limit: int = 10,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = VaultService(db, user.user_id)
    return {"notes": service.get_mentionable_notes(q=q, limit=limit)}


@router.post("/prep/meeting", response_model=MeetingPrepResponse)
def prep_meeting(
    request: MeetingPrepRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    service = VaultContextService(db, user.user_id)
    return service.build_meeting_prep(request.event_id)


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

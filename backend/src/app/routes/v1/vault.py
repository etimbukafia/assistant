import logging
from datetime import datetime, timedelta, timezone
from time import perf_counter
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import (
    VaultProposal,
    VaultNote,
    VaultMetricsDaily,
    CalendarEvent,
    Contact,
    ContextEntry,
    DiaryEntryLink,
    EntityReference,
    Message,
    Task,
    TaskQueue,
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
    ContactResponse,
    ContextCaptureCreate,
    ContextCaptureUpdate,
    ContextCaptureResponse,
    ContextEntityType,
    ContextCaptureScopeType,
    ContextType,
    ContextCreatedBy,
    ContextEntryStatus,
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
from app.services.context_capture_shortener import (
    deterministic_shorten_context_capture_text,
    shorten_context_capture_text,
)
from app.services.voice_capture_observability import log_voice_capture_metric
from app.services.voice_transcription import (
    VoiceAudioValidationError,
    VoiceTranscriptionError,
    inspect_audio_bytes,
    transcribe_audio_bytes,
)
from app.services.context_memory_policy import ages_as_stale_in_diary
from app.intelligence.pattern_tracker import PatternTracker
from app.infra.config import get_settings


router = APIRouter(prefix="/vault", tags=["Vault"])
context_router = APIRouter(prefix="/context", tags=["Context"])
logger = logging.getLogger(__name__)


cache_coordinator = EntityCacheCoordinator()
MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX = "__manual_tasks__"
MAX_CONTEXT_CAPTURE_LENGTH = 2000
MAX_CONTEXT_CAPTURE_LINKS = 8
CONTEXT_CAPTURE_CLASSIFICATION_WINDOW = timedelta(minutes=5)
MAX_CONTEXT_CAPTURE_CLASSIFICATIONS_PER_WINDOW = 10
VOICE_CAPTURE_ALLOWED_EXTENSIONS = {"mp4", "webm"}
VOICE_CAPTURE_ALLOWED_CONTENT_TYPES = {
    "audio/mp4",
    "audio/webm",
    "video/mp4",  # Safari MediaRecorder reports this for audio-only mp4
}
VOICE_CAPTURE_WINDOW = timedelta(minutes=5)
MAX_VOICE_CAPTURES_PER_WINDOW = 6
MAX_VOICE_CAPTURE_DURATION_SECONDS = 45
MAX_SHORTENABLE_VOICE_TRANSCRIPT_LENGTH = MAX_CONTEXT_CAPTURE_LENGTH * 2
VOICE_CAPTURE_LOCK_TASK_TYPE = "voice_capture_transcription"
VOICE_CAPTURE_LOCK_STALE_AFTER = timedelta(minutes=10)
CANONICAL_CONTEXT_TYPE_MAP = {
    "preference": "preference",
    "preferences": "preference",
    "risk": "risk",
    "risks": "risk",
    "relationship": "insight",
    "relationships": "insight",
    "decision": "decision",
    "commitment": "commitment",
    "insight": "insight",
}


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


def _invalidate_entity_reference_scope(
    db: Session,
    user: AuthenticatedUser,
    *,
    entity_type: str,
    ref: Optional[str],
) -> None:
    if not ref:
        return
    tenant_id = _tenant_id_for_user(user)
    if entity_type == "thread":
        cache_coordinator.invalidate_thread_related_contact(
            db=db,
            tenant_id=tenant_id,
            user_id=user.user_id,
            thread_id=ref,
        )
    elif entity_type == "event":
        try:
            event_id = int(ref)
        except Exception:
            cache_coordinator.invalidate_event(tenant_id, user.user_id, ref)
            return
        cache_coordinator.invalidate_event_related_contacts(
            db=db,
            tenant_id=tenant_id,
            user_id=user.user_id,
            event_id=event_id,
        )


def _effective_diary_status(
    *,
    entry_type: Optional[str] = None,
    expires_at: Optional[datetime],
    requested_status: Optional[str] = None,
) -> str:
    if requested_status in {"resolved", "archived", "forgotten"}:
        return requested_status
    if not ages_as_stale_in_diary(entry_type=entry_type):
        return "active"
    now = datetime.now(timezone.utc)
    if expires_at is not None and expires_at <= now:
        return "stale"
    return "active"


def _scope_is_resolved(*, db: Session, user_id: str, entity_type: str, entity_id: Optional[str]) -> bool:
    normalized_type = (entity_type or "").strip().lower()
    normalized_id = (entity_id or "").strip()
    if normalized_type == "global":
        return True
    if not normalized_type or not normalized_id:
        return False
    try:
        _resolve_capture_link(
            db=db,
            user_id=user_id,
            entity_type=normalized_type,
            entity_id=normalized_id,
        )
        return True
    except (HTTPException, ValueError):
        return False


def _to_context_capture_response(*, db: Session, user_id: str, entry: ContextEntry) -> ContextCaptureResponse:
    response = ContextCaptureResponse.model_validate(entry)
    response.type = ContextType(CANONICAL_CONTEXT_TYPE_MAP.get(entry.type, entry.type))
    if (
        response.status == "active"
        and response.expires_at is not None
        and response.expires_at <= datetime.now(timezone.utc)
        and ages_as_stale_in_diary(entry_type=entry.type)
    ):
        response.status = "stale"
    response.links = [
        DiaryEntryLinkSchema.model_validate(link)
        for link in _validated_capture_links(
            db=db,
            user_id=user_id,
            links=getattr(entry, "links", []) or [],
            source="user",
        )
    ]
    response.scope_resolved = _scope_is_resolved(
        db=db,
        user_id=user_id,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
    )
    return response


def _resolve_capture_scope(
    *,
    db: Session,
    user_id: str,
    scope_type: ContextCaptureScopeType,
    scope_id: Optional[str],
) -> tuple[ContextEntityType, Optional[str], Optional[str]]:
    entity_id = (scope_id or "").strip()
    if scope_type == ContextCaptureScopeType.global_:
        return ContextEntityType.global_, None, None
    if not entity_id:
        raise HTTPException(status_code=400, detail="scope_id is required for non-global captures.")

    if scope_type == ContextCaptureScopeType.contact:
        query = db.query(Contact).filter(Contact.user_id == user_id)
        if entity_id.isdigit():
            query = query.filter(or_(Contact.id == int(entity_id), func.lower(Contact.email) == entity_id.lower()))
        else:
            query = query.filter(func.lower(Contact.email) == entity_id.lower())
        contact = query.first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact scope not found for this user.")
        return ContextEntityType.contact, str(contact.id), contact.name

    if scope_type == ContextCaptureScopeType.message:
        message_query = db.query(Message).filter(Message.user_id == user_id)
        if entity_id.isdigit():
            message = message_query.filter(Message.id == int(entity_id)).first()
            if not message:
                raise HTTPException(status_code=400, detail="Message scope not found for this user.")
        else:
            message = message_query.filter(
                or_(Message.message_id == entity_id, Message.external_message_id == entity_id)
            ).first()
        if not message:
            raise HTTPException(status_code=400, detail="Message scope not found for this user.")
        return ContextEntityType.message, message.message_id or message.external_message_id or str(message.id), (
            (message.subject or "").strip() or None
        )

    if scope_type == ContextCaptureScopeType.event:
        event_query = db.query(CalendarEvent).filter(CalendarEvent.user_id == user_id)
        if entity_id.isdigit():
            event = event_query.filter(CalendarEvent.id == int(entity_id)).first()
            if event:
                return ContextEntityType.event, event.external_event_id or str(event.id), (
                    (event.title or "").strip() or None
                )
        event = event_query.filter(CalendarEvent.external_event_id == entity_id).first()
        if event:
            return ContextEntityType.event, event.external_event_id or str(event.id), (
                (event.title or "").strip() or None
            )
        ref = (
            db.query(EntityReference)
            .filter(
                EntityReference.user_id == user_id,
                EntityReference.entity_type == "event",
                EntityReference.ref == entity_id,
            )
            .first()
        )
        if not ref:
            raise HTTPException(status_code=400, detail="Event scope not found for this user.")
        return ContextEntityType.event, ref.ref, ref.display_name

    if scope_type == ContextCaptureScopeType.task:
        if not entity_id.isdigit():
            raise HTTPException(status_code=400, detail="Task scope must use a numeric task id.")
        task = db.query(Task).filter(Task.user_id == user_id, Task.id == int(entity_id)).first()
        if not task:
            raise HTTPException(status_code=400, detail="Task scope not found for this user.")
        return ContextEntityType.task, str(task.id), task.title

    raise HTTPException(status_code=400, detail="Invalid capture scope.")


def _resolve_capture_link(
    *,
    db: Session,
    user_id: str,
    entity_type: str,
    entity_id: str,
) -> tuple[str, str, Optional[str]]:
    link_type = (entity_type or "").strip().lower()
    link_id = (entity_id or "").strip()
    if not link_id:
        raise ValueError("link entity_id is required")

    if link_type == "thread":
        ref = (
            db.query(EntityReference)
            .filter(
                EntityReference.user_id == user_id,
                EntityReference.entity_type == "thread",
                EntityReference.ref == link_id,
            )
            .first()
        )
        if ref:
            return "thread", ref.ref, ref.display_name

        message = (
            db.query(Message)
            .filter(Message.user_id == user_id, Message.thread_id == link_id)
            .order_by(Message.received_at.desc(), Message.id.desc())
            .first()
        )
        if not message:
            raise ValueError("thread link not found")
        return "thread", message.thread_id, (message.subject or "").strip() or None

    if link_type == "contact":
        resolved_type, resolved_id, label = _resolve_capture_scope(
            db=db,
            user_id=user_id,
            scope_type=ContextCaptureScopeType.contact,
            scope_id=link_id,
        )
        return resolved_type.value, resolved_id or "", label

    if link_type == "message":
        resolved_type, resolved_id, label = _resolve_capture_scope(
            db=db,
            user_id=user_id,
            scope_type=ContextCaptureScopeType.message,
            scope_id=link_id,
        )
        return resolved_type.value, resolved_id or "", label

    if link_type == "event":
        resolved_type, resolved_id, label = _resolve_capture_scope(
            db=db,
            user_id=user_id,
            scope_type=ContextCaptureScopeType.event,
            scope_id=link_id,
        )
        return resolved_type.value, resolved_id or "", label

    if link_type == "task":
        resolved_type, resolved_id, label = _resolve_capture_scope(
            db=db,
            user_id=user_id,
            scope_type=ContextCaptureScopeType.task,
            scope_id=link_id,
        )
        return resolved_type.value, resolved_id or "", label

    raise ValueError("unsupported link entity_type")


def _validated_capture_links(
    *,
    db: Session,
    user_id: str,
    links,
    source: str = "user",
) -> List[DiaryEntryLink]:
    validated: List[DiaryEntryLink] = []
    seen: set[tuple[str, str]] = set()
    normalized_source = "teeks" if source == "teeks" else "user"
    for link in list(links or [])[:MAX_CONTEXT_CAPTURE_LINKS]:
        entity_type = getattr(link, "entity_type", None)
        entity_id = getattr(link, "entity_id", None)
        display_name = getattr(link, "display_name", None)
        if isinstance(link, dict):
            entity_type = link.get("entity_type")
            entity_id = link.get("entity_id")
            display_name = link.get("display_name")
        try:
            resolved_type, resolved_id, resolved_label = _resolve_capture_link(
                db=db,
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        except Exception as exc:
            logger.info(
                "Dropping invalid context capture link: user=%s entity_type=%s entity_id=%s reason=%s",
                user_id,
                entity_type,
                entity_id,
                exc,
            )
            continue

        dedupe_key = (resolved_type, resolved_id)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        validated.append(
            DiaryEntryLink(
                entity_type=resolved_type,
                entity_id=resolved_id,
                display_name=(resolved_label or display_name or resolved_id).strip(),
                source=normalized_source,
            )
        )
    return validated


def _preserve_existing_link_provenance(
    *,
    existing_links: List[DiaryEntryLink],
    next_links: List[DiaryEntryLink],
) -> List[DiaryEntryLink]:
    existing_by_ref = {
        (link.entity_type, link.entity_id): link.source or "user"
        for link in existing_links
    }
    for link in next_links:
        preserved_source = existing_by_ref.get((link.entity_type, link.entity_id))
        if preserved_source in {"user", "teeks"}:
            link.source = preserved_source
    return next_links


def _should_enqueue_context_capture_classification(
    *,
    db: Session,
    user_id: str,
    entry_id: int,
) -> tuple[bool, Optional[str]]:
    pending_tasks = (
        db.query(TaskQueue)
        .filter(
            TaskQueue.user_id == user_id,
            TaskQueue.task_type == "classify_context_capture",
            TaskQueue.status.in_(["pending", "in_progress"]),
        )
        .all()
    )
    for task in pending_tasks:
        payload = task.payload or {}
        if str(payload.get("entry_id")) == str(entry_id):
            return False, "duplicate_pending"

    recent_count = (
        db.query(TaskQueue)
        .filter(
            TaskQueue.user_id == user_id,
            TaskQueue.task_type == "classify_context_capture",
            TaskQueue.created_at >= datetime.utcnow() - CONTEXT_CAPTURE_CLASSIFICATION_WINDOW,
        )
        .count()
    )
    if recent_count >= MAX_CONTEXT_CAPTURE_CLASSIFICATIONS_PER_WINDOW:
        return False, "rate_limited"
    return True, None


def _enqueue_context_capture_classification(*, db: Session, user_id: str, entry_id: int) -> None:
    try:
        from app.jobs.queue import enqueue_task

        should_enqueue, reason = _should_enqueue_context_capture_classification(
            db=db,
            user_id=user_id,
            entry_id=entry_id,
        )
        if should_enqueue:
            enqueue_task(
                "classify_context_capture",
                {
                    "user_id": user_id,
                    "entry_id": entry_id,
                },
            )
        else:
            logger.info(
                "Skipped context capture classification enqueue: entry_id=%s user=%s reason=%s",
                entry_id,
                user_id,
                reason,
            )
    except Exception as exc:
        logger.warning("Failed to enqueue context capture classification: entry_id=%s error=%s", entry_id, exc)


def _should_accept_voice_capture(*, db: Session, user_id: str) -> tuple[bool, Optional[str]]:
    recent_voice_count = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.input_source == "voice",
            ContextEntry.created_at >= datetime.utcnow() - VOICE_CAPTURE_WINDOW,
        )
        .count()
    )
    if recent_voice_count >= MAX_VOICE_CAPTURES_PER_WINDOW:
        return False, "rate_limited"
    return True, None


def _acquire_voice_capture_lock(*, db: Session, user_id: str) -> int:
    stale_cutoff = datetime.utcnow() - VOICE_CAPTURE_LOCK_STALE_AFTER
    db.query(TaskQueue).filter(
        TaskQueue.user_id == user_id,
        TaskQueue.task_type == VOICE_CAPTURE_LOCK_TASK_TYPE,
        TaskQueue.status.in_(["pending", "in_progress"]),
        TaskQueue.created_at < stale_cutoff,
    ).delete(synchronize_session=False)
    db.commit()

    existing_lock = (
        db.query(TaskQueue)
        .filter(
            TaskQueue.user_id == user_id,
            TaskQueue.task_type == VOICE_CAPTURE_LOCK_TASK_TYPE,
            TaskQueue.status.in_(["pending", "in_progress"]),
        )
        .first()
    )
    if existing_lock:
        raise HTTPException(status_code=429, detail="Voice capture is temporarily busy. Try again in a moment.")

    lock = TaskQueue(
        task_type=VOICE_CAPTURE_LOCK_TASK_TYPE,
        user_id=user_id,
        payload={"kind": "voice_capture_lock"},
        status="in_progress",
        attempts=1,
        max_attempts=1,
        scheduled_for=datetime.utcnow(),
        started_at=datetime.utcnow(),
    )
    db.add(lock)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=429, detail="Voice capture is temporarily busy. Try again in a moment.")
    db.refresh(lock)
    return lock.id


def _release_voice_capture_lock(*, db: Session, lock_id: Optional[int], user_id: str) -> None:
    if not lock_id:
        return
    try:
        db.query(TaskQueue).filter(
            TaskQueue.id == lock_id,
            TaskQueue.user_id == user_id,
            TaskQueue.task_type == VOICE_CAPTURE_LOCK_TASK_TYPE,
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


def _save_context_capture(
    *,
    db: Session,
    user: AuthenticatedUser,
    payload: ContextCaptureCreate,
    text: str,
    input_source: str = "typed",
) -> ContextCaptureResponse:
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required.")
    if len(text) > MAX_CONTEXT_CAPTURE_LENGTH:
        raise HTTPException(status_code=400, detail=f"text must be at most {MAX_CONTEXT_CAPTURE_LENGTH} characters.")

    entity_type, canonical_scope_id, scope_label = _resolve_capture_scope(
        db=db,
        user_id=user.user_id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
    )

    now = datetime.now(timezone.utc)
    entry = ContextEntry(
        user_id=user.user_id,
        type=ContextType.insight.value,
        content=text,
        raw_text=text,
        input_source=input_source,
        entity_type=entity_type.value,
        entity_id=canonical_scope_id,
        linked_to=(payload.linked_to or "").strip() or scope_label,
        created_by=ContextCreatedBy.you.value,
        status=ContextEntryStatus.active.value,
        classification_status="pending",
        classification_confidence=None,
        user_corrected=False,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.flush()
    for link in _validated_capture_links(db=db, user_id=user.user_id, links=payload.links, source="user"):
        link.entry_id = entry.id
        db.add(link)
    db.commit()
    db.refresh(entry)
    cache_coordinator.invalidate_from_context_entry(_tenant_id_for_user(user), entry)
    _prewarm_action_chips_cache(db, user)
    _enqueue_context_capture_classification(db=db, user_id=user.user_id, entry_id=entry.id)
    logger.info(
        "Context capture saved: entry_id=%s user=%s scope_type=%s scope_id=%s link_count=%s status=%s",
        entry.id,
        user.user_id,
        entry.entity_type,
        entry.entity_id,
        len(entry.links or []),
        entry.classification_status,
    )
    return _to_context_capture_response(db=db, user_id=user.user_id, entry=entry)


async def _read_voice_upload(audio: UploadFile, *, max_bytes: int) -> bytes:
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await audio.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=400, detail="Audio file is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_voice_upload(audio: UploadFile) -> str:
    filename = (audio.filename or "capture").strip()
    suffix = Path(filename).suffix.lower().lstrip(".")
    content_type = (audio.content_type or "").lower().strip()
    if suffix not in VOICE_CAPTURE_ALLOWED_EXTENSIONS and content_type not in VOICE_CAPTURE_ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format. Use webm or mp4.",
        )
    return filename or f"capture.{suffix or 'webm'}"


def _assert_proposals_enabled() -> None:
    if not get_settings().PROPOSALS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


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


@context_router.get("/captures", response_model=List[ContextCaptureResponse])
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
        if entry_type == "preference":
            query = query.filter(ContextEntry.type.in_(["preference", "preferences"]))
        elif entry_type == "risk":
            query = query.filter(ContextEntry.type.in_(["risk", "risks"]))
        elif entry_type == "insight":
            query = query.filter(ContextEntry.type.in_(["insight", "relationship", "relationships"]))
        else:
            query = query.filter(ContextEntry.type == entry_type)
    rows = query.order_by(ContextEntry.created_at.desc()).all()
    visible_rows: List[ContextCaptureResponse] = []
    for row in rows:
        response = _to_context_capture_response(db=db, user_id=user.user_id, entry=row)
        if response.status in {"active", "stale"}:
            visible_rows.append(response)
    return visible_rows


@router.post("/context/captures", response_model=ContextCaptureResponse)
@context_router.post("/captures", response_model=ContextCaptureResponse)
def create_context_capture(
    payload: ContextCaptureCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    return _save_context_capture(
        db=db,
        user=user,
        payload=payload,
        text=payload.text,
    )


@router.post("/context/captures/voice", response_model=ContextCaptureResponse)
@context_router.post("/captures/voice", response_model=ContextCaptureResponse)
async def create_voice_context_capture(
    audio: UploadFile = File(...),
    scope_type: str = Form(...),
    scope_id: Optional[str] = Form(default=None),
    linked_to: Optional[str] = Form(default=None),
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    started_at = perf_counter()
    should_accept, reason = _should_accept_voice_capture(db=db, user_id=user.user_id)
    if not should_accept:
        logger.info("Voice capture throttled: user=%s reason=%s", user.user_id, reason)
        log_voice_capture_metric(
            user_id=user.user_id,
            stage="admission",
            outcome="rejected",
            reason=reason,
        )
        raise HTTPException(status_code=429, detail="Voice capture is temporarily busy. Try again in a moment.")

    lock_id: Optional[int] = None
    try:
        lock_id = _acquire_voice_capture_lock(db=db, user_id=user.user_id)

        filename = _validate_voice_upload(audio)
        settings = get_settings()
        try:
            audio_bytes = await _read_voice_upload(audio, max_bytes=settings.VOICE_CAPTURE_MAX_UPLOAD_BYTES)
        finally:
            await audio.close()

        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Audio file is empty.")

        try:
            capture_scope_type = ContextCaptureScopeType(scope_type)
        except Exception:
            log_voice_capture_metric(
                user_id=user.user_id,
                stage="validation",
                outcome="rejected",
                reason="invalid_scope_type",
            )
            raise HTTPException(status_code=400, detail="Invalid scope_type.")

        try:
            duration_seconds = inspect_audio_bytes(
                audio_bytes=audio_bytes,
                filename=filename,
            )
        except VoiceAudioValidationError as exc:
            logger.info("Voice capture validation failed: user=%s reason=%s", user.user_id, exc)
            log_voice_capture_metric(
                user_id=user.user_id,
                stage="validation",
                outcome="rejected",
                scope_type=capture_scope_type.value,
                reason="invalid_audio",
            )
            raise HTTPException(status_code=400, detail="Use a short supported audio recording.")

        if duration_seconds > MAX_VOICE_CAPTURE_DURATION_SECONDS:
            log_voice_capture_metric(
                user_id=user.user_id,
                stage="validation",
                outcome="rejected",
                scope_type=capture_scope_type.value,
                duration_seconds=duration_seconds,
                reason="duration_limit",
            )
            raise HTTPException(status_code=400, detail="Record up to 45 seconds.")

        try:
            transcript = transcribe_audio_bytes(
                audio_bytes=audio_bytes,
                filename=filename,
                content_type=audio.content_type,
            )
        except VoiceTranscriptionError as exc:
            logger.warning("Voice transcription failed: user=%s reason=%s", user.user_id, exc)
            log_voice_capture_metric(
                user_id=user.user_id,
                stage="transcription",
                outcome="failed",
                scope_type=capture_scope_type.value,
                duration_seconds=duration_seconds,
                latency_ms=int((perf_counter() - started_at) * 1000),
                reason="provider_failure",
            )
            raise HTTPException(status_code=502, detail="Teeks couldn’t transcribe that recording right now. Try again.")

        scope_label = (linked_to or "").strip() or None
        original_transcript_length = len(transcript)
        shortened_with_llm = False
        if len(transcript) > MAX_CONTEXT_CAPTURE_LENGTH:
            if len(transcript) > MAX_SHORTENABLE_VOICE_TRANSCRIPT_LENGTH:
                transcript = deterministic_shorten_context_capture_text(
                    transcript=transcript,
                    max_chars=MAX_CONTEXT_CAPTURE_LENGTH,
                )
                logger.info(
                    "Voice context capture clipped without llm: user=%s scope_type=%s transcript_chars=%s final_chars=%s",
                    user.user_id,
                    capture_scope_type.value,
                    original_transcript_length,
                    len(transcript),
                )
            else:
                shortened = shorten_context_capture_text(
                    transcript=transcript,
                    max_chars=MAX_CONTEXT_CAPTURE_LENGTH,
                    scope_type=capture_scope_type.value,
                    scope_label=scope_label,
                )
                transcript = shortened.text
                logger.info(
                    "Voice context capture shortened: user=%s scope_type=%s shortened=%s transcript_chars=%s final_chars=%s",
                    user.user_id,
                    capture_scope_type.value,
                    shortened.shortened,
                    original_transcript_length,
                    len(transcript),
                )
                shortened_with_llm = shortened.shortened

        log_voice_capture_metric(
            user_id=user.user_id,
            stage="transcription",
            outcome="completed",
            scope_type=capture_scope_type.value,
            duration_seconds=duration_seconds,
            latency_ms=int((perf_counter() - started_at) * 1000),
            transcript_chars=original_transcript_length,
            final_chars=len(transcript),
            shortened=(original_transcript_length > MAX_CONTEXT_CAPTURE_LENGTH),
            reason="llm_shortener" if shortened_with_llm else ("deterministic_clip" if original_transcript_length > MAX_SHORTENABLE_VOICE_TRANSCRIPT_LENGTH else None),
        )

        payload = ContextCaptureCreate.model_construct(
            text=transcript,
            scope_type=capture_scope_type,
            scope_id=scope_id,
            linked_to=linked_to,
            links=[],
        )
        logger.info(
            "Voice context capture transcribed: user=%s scope_type=%s transcript_chars=%s",
            user.user_id,
            payload.scope_type.value,
            len(transcript),
        )
        return _save_context_capture(
            db=db,
            user=user,
            payload=payload,
            text=transcript,
            input_source="voice",
        )
    finally:
        _release_voice_capture_lock(db=db, lock_id=lock_id, user_id=user.user_id)


@router.patch("/context/captures/{entry_id}", response_model=ContextCaptureResponse)
@context_router.patch("/captures/{entry_id}", response_model=ContextCaptureResponse)
def update_context_entry(
    entry_id: int,
    payload: ContextCaptureUpdate,
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
        raw_text=entry.raw_text,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        linked_to=entry.linked_to,
        created_by=entry.created_by,
        status=entry.status,
        expires_at=entry.expires_at,
    )

    if payload.text is not None:
        text = payload.text.strip()
        if len(text) > MAX_CONTEXT_CAPTURE_LENGTH:
            raise HTTPException(status_code=400, detail=f"text must be at most {MAX_CONTEXT_CAPTURE_LENGTH} characters.")
        entry.content = text
        entry.raw_text = text
    if payload.type is not None and payload.type.value != entry.type:
        entry.type = payload.type.value
        entry.classification_status = "user_corrected"
        entry.user_corrected = True
        entry.classification_suggested_type = None
    if payload.scope_type is not None or "scope_id" in payload.model_fields_set:
        scope_type = payload.scope_type or ContextCaptureScopeType(entry.entity_type)
        entity_type, canonical_scope_id, scope_label = _resolve_capture_scope(
            db=db,
            user_id=user.user_id,
            scope_type=scope_type,
            scope_id=payload.scope_id,
        )
        entry.entity_type = entity_type.value
        entry.entity_id = canonical_scope_id
        entry.linked_to = (payload.linked_to or "").strip() or scope_label
    elif payload.linked_to is not None:
        entry.linked_to = payload.linked_to.strip() or None
    if "links" in payload.model_fields_set:
        existing_links = (
            db.query(DiaryEntryLink)
            .filter(DiaryEntryLink.entry_id == entry.id)
            .all()
        )
        reconciled_links = _preserve_existing_link_provenance(
            existing_links=existing_links,
            next_links=_validated_capture_links(
                db=db,
                user_id=user.user_id,
                links=payload.links or [],
                source="user",
            ),
        )
        db.query(DiaryEntryLink).filter(DiaryEntryLink.entry_id == entry.id).delete(synchronize_session=False)
        for link in reconciled_links:
            link.entry_id = entry.id
            db.add(link)
    if "expires_at" in payload.model_fields_set:
        entry.expires_at = payload.expires_at
    if payload.status is not None:
        entry.status = _effective_diary_status(
            entry_type=entry.type,
            expires_at=entry.expires_at,
            requested_status=payload.status.value,
        )
    elif entry.status in {"active", "stale"}:
        entry.status = _effective_diary_status(
            entry_type=entry.type,
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
    if payload.type is not None and payload.type.value == entry.type and entry.user_corrected:
        logger.info(
            "Context capture corrected: entry_id=%s user=%s category=%s link_count=%s",
            entry.id,
            user.user_id,
            entry.type,
            len(entry.links or []),
        )
    return _to_context_capture_response(db=db, user_id=user.user_id, entry=entry)


@router.delete("/context/captures/{entry_id}/links", response_model=ContextCaptureResponse)
@context_router.delete("/captures/{entry_id}/links", response_model=ContextCaptureResponse)
def delete_context_capture_link(
    entry_id: int,
    entity_type: str = Query(...),
    entity_id: str = Query(...),
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

    resolved_type, resolved_id, _ = _resolve_capture_link(
        db=db,
        user_id=user.user_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    link = (
        db.query(DiaryEntryLink)
        .filter(
            DiaryEntryLink.entry_id == entry.id,
            DiaryEntryLink.entity_type == resolved_type,
            DiaryEntryLink.entity_id == resolved_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Context capture link not found.")

    prior_entry = ContextEntry(
        user_id=entry.user_id,
        type=entry.type,
        content=entry.content,
        raw_text=entry.raw_text,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        linked_to=entry.linked_to,
        created_by=entry.created_by,
        status=entry.status,
        expires_at=entry.expires_at,
    )

    db.delete(link)
    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    cache_coordinator.invalidate_from_context_entry(
        _tenant_id_for_user(user),
        entry,
        prior_entry=prior_entry,
    )
    _prewarm_action_chips_cache(db, user)
    return _to_context_capture_response(db=db, user_id=user.user_id, entry=entry)


@context_router.delete("/captures/{entry_id}")
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
        status=entry.status,
        expires_at=entry.expires_at,
    )
    # Legacy delete alias: in the product model, deleting a memory means forgetting it.
    entry.status = "forgotten"
    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    cache_coordinator.invalidate_from_context_entry(
        _tenant_id_for_user(user),
        entry,
        prior_entry=prior_entry,
    )
    _prewarm_action_chips_cache(db, user)
    return {"forgotten": True, "id": entry_id}


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
    query = query.filter(
        ~(
            (EntityReference.entity_type == "thread")
            & EntityReference.ref.ilike(f"{MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX}%")
        )
    )
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
    if payload.entity_type.value == "thread" and ref.lower().startswith(MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX):
        raise HTTPException(status_code=400, detail="Invalid thread reference.")

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
    _invalidate_entity_reference_scope(db, user, entity_type=entity.entity_type, ref=entity.ref)
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
        if entity.entity_type == "thread" and ref.lower().startswith(MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX):
            raise HTTPException(status_code=400, detail="Invalid thread reference.")
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

    refs_to_invalidate = {old_ref, entity.ref}
    for ref in refs_to_invalidate:
        _invalidate_entity_reference_scope(db, user, entity_type=entity.entity_type, ref=ref)
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

    _invalidate_entity_reference_scope(db, user, entity_type=entity_type, ref=ref)
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

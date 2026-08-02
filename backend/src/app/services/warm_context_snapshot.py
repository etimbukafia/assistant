"""Warm context snapshot compiler from structured context entries."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.data.models import Contact, ContextEntry, UserSettings
from app.services.context_memory_policy import is_expiry_retrievable, is_retrieval_confident
from app.security.prompt_sanitizer import sanitize_with_detection


MAX_SOURCE_ROWS = 300
MAX_PER_TYPE = 20
MAX_CRITICAL = 25
MAX_TIMELINE = 50
MAX_PER_ENTITY = 5
MAX_ENTITY_BUCKETS = 80

logger = logging.getLogger(__name__)


def _serialize_entry(entry: ContextEntry) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "type": entry.type,
        "content": entry.content,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "created_by": entry.created_by,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "status": entry.status,
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
    }


def build_profile_snapshot(db: Session, user_id: str) -> Dict[str, Any]:
    settings = (
        db.query(UserSettings)
        .filter(UserSettings.user_id == user_id)
        .first()
    )
    query = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.entity_type == "global",
            ContextEntry.status == "active",
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(MAX_SOURCE_ROWS)
    )
    return _build_snapshot(
        rows=query.all(),
        user_id=user_id,
        scope="profile",
        profile=_serialize_profile(settings),
    )


def build_contact_snapshot(db: Session, user_id: str, contact_email: str) -> Dict[str, Any]:
    email_norm = (contact_email or "").lower().strip()
    query = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.entity_type == "contact",
            ContextEntry.entity_id == email_norm,
            ContextEntry.status == "active",
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(MAX_SOURCE_ROWS)
    )
    snapshot = _build_snapshot(rows=query.all(), user_id=user_id, scope="contact", scope_id=email_norm, entity_type="contact")
    contact = None
    if email_norm:
        contact = (
            db.query(Contact)
            .filter(
                Contact.user_id == user_id,
                Contact.email.isnot(None),
                Contact.email.ilike(email_norm),
            )
            .first()
        )
    if contact:
        _enrich_contact_snapshot(db=db, snapshot=snapshot, user_id=user_id, contact=contact)
    return snapshot


def build_thread_snapshot(db: Session, user_id: str, thread_id: str) -> Dict[str, Any]:
    thread_norm = (thread_id or "").strip()
    query = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.entity_type == "thread",
            ContextEntry.entity_id == thread_norm,
            ContextEntry.status == "active",
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(MAX_SOURCE_ROWS)
    )
    return _build_snapshot(rows=query.all(), user_id=user_id, scope="thread", scope_id=thread_norm, entity_type="thread")


def build_event_snapshot(db: Session, user_id: str, event_id: str) -> Dict[str, Any]:
    event_norm = (event_id or "").strip()
    query = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.entity_type == "event",
            ContextEntry.entity_id == event_norm,
            ContextEntry.status == "active",
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(MAX_SOURCE_ROWS)
    )
    return _build_snapshot(rows=query.all(), user_id=user_id, scope="event", scope_id=event_norm, entity_type="event")


def build_message_snapshot(db: Session, user_id: str, message_id: str) -> Dict[str, Any]:
    message_norm = (message_id or "").strip()
    query = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.entity_type == "message",
            ContextEntry.entity_id == message_norm,
            ContextEntry.status == "active",
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(MAX_SOURCE_ROWS)
    )
    return _build_snapshot(rows=query.all(), user_id=user_id, scope="message", scope_id=message_norm, entity_type="message")


def _build_snapshot(
    rows: List[ContextEntry],
    user_id: str,
    scope: str,
    scope_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    rows = [
        r for r in rows
        if (r.status or "active") == "active"
        and is_expiry_retrievable(entry_type=getattr(r, "type", None), expires_at=getattr(r, "expires_at", None), now=now)
        and is_retrieval_confident(
            classification_confidence=getattr(r, "classification_confidence", None),
            user_corrected=bool(getattr(r, "user_corrected", False)),
        )
    ]
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_entity: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    timeline: List[Dict[str, Any]] = []

    for entry in rows:
        item = _serialize_entry(entry)
        if len(by_type[entry.type]) < MAX_PER_TYPE:
            by_type[entry.type].append(item)

        entity_key = f"{entry.entity_type}:{entry.entity_id or 'profile'}"
        if len(by_entity) < MAX_ENTITY_BUCKETS or entity_key in by_entity:
            if len(by_entity[entity_key]) < MAX_PER_ENTITY:
                by_entity[entity_key].append(item)

        if len(timeline) < MAX_TIMELINE:
            timeline.append(item)

    return {
        "version": "v1",
        "user_id": user_id,
        "scope": scope,
        "scope_id": scope_id,
        "entity_type": entity_type,
        "profile": profile or {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(rows),
        "counts_by_type": {k: len(v) for k, v in by_type.items()},
        "by_type": dict(by_type),
        "by_entity": dict(by_entity),
        "critical_items": [],
        "recent_timeline": timeline,
    }


def _serialize_profile(settings: Optional[UserSettings]) -> Dict[str, Any]:
    if not settings:
        return {}

    return {
        "assistant_name": settings.assistant_name or "Teeks",
        "ea": {
            "full_name": settings.full_name,
            "preferred_name": settings.preferred_name,
            "role": settings.role,
            "preferences": settings.personal_preferences,
        },
        "executive": {
            "full_name": settings.exec_full_name,
            "preferred_name": settings.exec_preferred_name,
            "role": settings.exec_role,
            "preferences": settings.exec_preferences,
        },
    }


def _enrich_contact_snapshot(
    *,
    db: Session,
    snapshot: Dict[str, Any],
    user_id: str,
    contact: Contact,
) -> None:
    from app.services.contact_brief import ContactBriefService

    brief = ContactBriefService(db, user_id=user_id).get_contact_brief(contact.id, consumer="warm_snapshot")
    if not brief:
        return

    summary = brief.get("summary") or {}
    preferences = list(brief.get("preferences") or [])[:3]
    commitments = list(brief.get("commitments") or [])[:3]
    decisions = list(brief.get("decisions") or [])[:3]
    signals = list(brief.get("signals") or [])[:3]
    recent_interactions = list(brief.get("recent_interactions") or [])[:4]

    snapshot["contact"] = {
        "id": contact.id,
        "name": _sanitize_contact_prompt_text(contact.name, field="contact.name", contact_id=contact.id),
        "email": contact.email,
        "role": _sanitize_contact_prompt_text(contact.role, field="contact.role", contact_id=contact.id),
        "organization": _sanitize_contact_prompt_text(contact.organization, field="contact.organization", contact_id=contact.id),
        "category": _sanitize_contact_prompt_text(contact.category, field="contact.category", contact_id=contact.id),
    }
    snapshot["brief_preview"] = {
        "contact_id": contact.id,
        "headline": _sanitize_contact_prompt_text(summary.get("headline"), field="brief.headline", contact_id=contact.id),
        "manual_notes": _sanitize_contact_prompt_text(summary.get("manual_notes"), field="brief.manual_notes", contact_id=contact.id),
        "preferred_tone": _sanitize_contact_prompt_text(summary.get("preferred_tone"), field="brief.preferred_tone", contact_id=contact.id),
        "top_preferences": [
            _sanitize_contact_prompt_text(item.get("content"), field="brief.preference", contact_id=contact.id)
            for item in preferences
            if item.get("content")
        ],
        "open_commitments": [
            _sanitize_contact_prompt_text(item.get("title"), field="brief.commitment", contact_id=contact.id)
            for item in commitments
            if item.get("title")
        ],
        "recent_decisions": [
            _sanitize_contact_prompt_text(item.get("decision"), field="brief.decision", contact_id=contact.id)
            for item in decisions
            if item.get("decision")
        ],
        "signals": [
            _sanitize_contact_prompt_text(item.get("message"), field="brief.signal", contact_id=contact.id)
            for item in signals
            if item.get("message")
        ],
    }

    synthetic_items: List[Dict[str, Any]] = []
    headline = " ".join(
        str(_sanitize_contact_prompt_text(summary.get("headline"), field="headline", contact_id=contact.id) or "").split()
    ).strip()
    if headline:
        synthetic_items.append(
            {
                "id": f"contact-brief:headline:{contact.id}",
                "type": "insight",
                "content": headline,
                "entity_type": "contact",
                "entity_id": (contact.email or "").lower().strip() or str(contact.id),
                "created_by": "Teeks",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",
            }
        )

    for idx, item in enumerate(preferences):
        content = " ".join(
            str(_sanitize_contact_prompt_text(item.get("content"), field="preference", contact_id=contact.id) or "").split()
        ).strip()
        if not content:
            continue
        synthetic_items.append(
            {
                "id": f"contact-brief:preference:{contact.id}:{idx}",
                "type": "preference",
                "content": content,
                "entity_type": "contact",
                "entity_id": (contact.email or "").lower().strip() or str(contact.id),
                "created_by": "Teeks",
                "created_at": _iso_or_none(item.get("created_at")) or datetime.now(timezone.utc).isoformat(),
                "status": "active",
            }
        )

    for idx, item in enumerate(commitments):
        title = " ".join(
            str(_sanitize_contact_prompt_text(item.get("title"), field="commitment", contact_id=contact.id) or "").split()
        ).strip()
        if not title:
            continue
        synthetic_items.append(
            {
                "id": f"contact-brief:commitment:{contact.id}:{idx}",
                "type": "commitment",
                "content": title,
                "entity_type": "contact",
                "entity_id": (contact.email or "").lower().strip() or str(contact.id),
                "created_by": "Teeks",
                "created_at": _iso_or_none(item.get("created_at")) or datetime.now(timezone.utc).isoformat(),
                "status": item.get("status") or "active",
            }
        )

    for idx, item in enumerate(decisions):
        decision = " ".join(
            str(_sanitize_contact_prompt_text(item.get("decision"), field="decision", contact_id=contact.id) or "").split()
        ).strip()
        if not decision:
            continue
        synthetic_items.append(
            {
                "id": f"contact-brief:decision:{contact.id}:{idx}",
                "type": "decision",
                "content": decision,
                "entity_type": "contact",
                "entity_id": (contact.email or "").lower().strip() or str(contact.id),
                "created_by": "Teeks",
                "created_at": _iso_or_none(item.get("created_at")) or datetime.now(timezone.utc).isoformat(),
                "status": "active",
            }
        )

    for idx, item in enumerate(signals):
        message = " ".join(
            str(_sanitize_contact_prompt_text(item.get("message"), field="signal", contact_id=contact.id) or "").split()
        ).strip()
        if not message:
            continue
        synthetic_items.append(
            {
                "id": f"contact-brief:signal:{contact.id}:{idx}",
                "type": "risk",
                "content": message,
                "entity_type": "contact",
                "entity_id": (contact.email or "").lower().strip() or str(contact.id),
                "created_by": "Teeks",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",
            }
        )

    for idx, item in enumerate(recent_interactions):
        summary_text = " ".join(
            str(
                _sanitize_contact_prompt_text(
                    item.get("summary") or item.get("subject"),
                    field="interaction",
                    contact_id=contact.id,
                )
                or ""
            ).split()
        ).strip()
        if not summary_text:
            continue
        synthetic_items.append(
            {
                "id": f"contact-brief:interaction:{contact.id}:{idx}",
                "type": "interaction",
                "content": summary_text,
                "entity_type": "contact",
                "entity_id": (contact.email or "").lower().strip() or str(contact.id),
                "created_by": "Teeks",
                "created_at": _iso_or_none(item.get("occurred_at")) or datetime.now(timezone.utc).isoformat(),
                "status": "active",
            }
        )

    existing_ids = {
        str(item.get("id"))
        for bucket in (snapshot.get("by_type") or {}).values()
        for item in (bucket or [])
        if isinstance(item, dict)
    }
    for item in synthetic_items:
        if str(item.get("id")) in existing_ids:
            continue
        snapshot.setdefault("by_type", {}).setdefault(str(item.get("type") or "insight"), []).append(item)
        entity_key = f"contact:{(contact.email or '').lower().strip() or contact.id}"
        snapshot.setdefault("by_entity", {}).setdefault(entity_key, []).append(item)
        snapshot.setdefault("recent_timeline", []).append(item)

    snapshot["counts_by_type"] = {
        key: len(value)
        for key, value in (snapshot.get("by_type") or {}).items()
    }
    snapshot["source_count"] = max(int(snapshot.get("source_count", 0) or 0), len(snapshot.get("recent_timeline") or []))


def _iso_or_none(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or "").strip()
    return text or None


def _sanitize_contact_prompt_text(value: Any, *, field: str, contact_id: int) -> Optional[str]:
    text = str(value or "")
    if not text:
        return None
    result = sanitize_with_detection(text)
    if result.patterns_detected:
        logger.warning(
            "contact_prompt_sanitized contact_id=%s field=%s patterns=%s",
            contact_id,
            field,
            result.patterns_detected,
        )
    cleaned = " ".join(result.sanitized_text.split()).strip()
    return cleaned or None

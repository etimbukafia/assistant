"""Warm context snapshot compiler from structured context entries."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.data.models import ContextEntry


MAX_SOURCE_ROWS = 300
MAX_PER_TYPE = 20
MAX_CRITICAL = 25
MAX_TIMELINE = 50
MAX_PER_ENTITY = 5
MAX_ENTITY_BUCKETS = 80


def _serialize_entry(entry: ContextEntry) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "type": entry.type,
        "content": entry.content,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "created_by": entry.created_by,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "importance_level": entry.importance_level,
        "status": entry.status,
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
    }


def build_profile_snapshot(db: Session, user_id: str) -> Dict[str, Any]:
    query = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.entity_type == "global",
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(MAX_SOURCE_ROWS)
    )
    return _build_snapshot(rows=query.all(), user_id=user_id, scope="profile")


def build_contact_snapshot(db: Session, user_id: str, contact_email: str) -> Dict[str, Any]:
    email_norm = (contact_email or "").lower().strip()
    query = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.entity_type == "contact",
            ContextEntry.entity_id == email_norm,
        )
        .order_by(ContextEntry.created_at.desc())
        .limit(MAX_SOURCE_ROWS)
    )
    return _build_snapshot(rows=query.all(), user_id=user_id, scope="contact", scope_id=email_norm, entity_type="contact")


def build_thread_snapshot(db: Session, user_id: str, thread_id: str) -> Dict[str, Any]:
    thread_norm = (thread_id or "").strip()
    query = (
        db.query(ContextEntry)
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.entity_type == "thread",
            ContextEntry.entity_id == thread_norm,
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
) -> Dict[str, Any]:
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_entity: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    critical_items: List[Dict[str, Any]] = []
    timeline: List[Dict[str, Any]] = []

    for entry in rows:
        item = _serialize_entry(entry)
        if len(by_type[entry.type]) < MAX_PER_TYPE:
            by_type[entry.type].append(item)

        entity_key = f"{entry.entity_type}:{entry.entity_id or 'profile'}"
        if len(by_entity) < MAX_ENTITY_BUCKETS or entity_key in by_entity:
            if len(by_entity[entity_key]) < MAX_PER_ENTITY:
                by_entity[entity_key].append(item)

        if entry.importance_level == "high" and len(critical_items) < MAX_CRITICAL:
            critical_items.append(item)
        if len(timeline) < MAX_TIMELINE:
            timeline.append(item)

    return {
        "version": "v1",
        "user_id": user_id,
        "scope": scope,
        "scope_id": scope_id,
        "entity_type": entity_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(rows),
        "counts_by_type": {k: len(v) for k, v in by_type.items()},
        "by_type": dict(by_type),
        "by_entity": dict(by_entity),
        "critical_items": critical_items,
        "recent_timeline": timeline,
    }

"""Deterministic personalized action chips for new chat sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.data.models import CalendarEvent, ContextEntry, Message, Task
from app.services.context_memory_policy import apply_confidence_retrieval_filter
from app.services.warm_cache import WarmCacheService


ACTION_CHIPS_CACHE_SCOPE = "action_chips_v1"
ACTION_CHIPS_CACHE_TTL_SECONDS = 120

GENERIC_ACTION_CHIPS: List[Dict[str, str]] = [
    {"id": "chip_generic_reply", "label": "Draft quick update to a contact", "prompt": "Draft a concise update email I can send now."},
    {"id": "chip_generic_prep", "label": "Prep me for a meeting", "prompt": "Prep me for my next meeting: agenda, risks, decisions, and talking points."},
    {"id": "chip_generic_brief", "label": "Turn notes into a brief", "prompt": "Turn this into a one-page brief with decisions, commitments, and open questions."},
    {"id": "chip_generic_changes", "label": "What changed since yesterday?", "prompt": "What changed since yesterday? Keep it tight and action-oriented."},
    {"id": "chip_generic_commitments", "label": "Extract commitments", "prompt": "Extract commitments and owners from recent messages, then suggest next actions."},
]


def _clean_chip_text(value: Optional[str], max_len: int = 64) -> str:
    text = " ".join((value or "").strip().split())
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}..."


def _add_chip(chips: List[Dict[str, str]], seen_labels: set[str], chip_id: str, label: str, prompt: str) -> None:
    clean_label = _clean_chip_text(label, max_len=68)
    clean_prompt = _clean_chip_text(prompt, max_len=300)
    if not clean_label or not clean_prompt:
        return
    dedupe_key = clean_label.lower()
    if dedupe_key in seen_labels:
        return
    seen_labels.add(dedupe_key)
    chips.append({"id": chip_id, "label": clean_label, "prompt": clean_prompt})


def build_action_chips_payload(db: Session, user_id: str, max_items: int = 8) -> Dict[str, List[Dict[str, str]]]:
    now = datetime.now(timezone.utc)
    chips: List[Dict[str, str]] = []
    seen_labels: set[str] = set()
    max_items = max(1, min(max_items, 12))

    upcoming_events = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time >= now,
            CalendarEvent.status.in_(["upcoming", "created", "pending"]),
        )
        .order_by(CalendarEvent.start_time.asc())
        .limit(3)
        .all()
    )
    for event in upcoming_events:
        title = _clean_chip_text(event.title or "meeting", max_len=52)
        _add_chip(
            chips,
            seen_labels,
            chip_id=f"event_{event.id}",
            label=f"Prep me for {title}",
            prompt=f"Prep me for {title}. Include goals, risks, decisions to confirm, and talking points.",
        )

    recent_messages = (
        db.query(Message)
        .filter(
            Message.user_id == user_id,
            Message.status == "inbox",
            or_(Message.needs_reply.is_(True), Message.needs_reply.is_(None)),
        )
        .order_by(Message.received_at.desc(), Message.created_at.desc())
        .limit(4)
        .all()
    )
    for msg in recent_messages:
        subject = _clean_chip_text(msg.subject or "latest thread", max_len=56)
        _add_chip(
            chips,
            seen_labels,
            chip_id=f"msg_{msg.id}",
            label=f"Draft follow-up: {subject}",
            prompt=f"Draft a clear follow-up email for \"{subject}\". Keep it short and action-oriented.",
        )

    active_commitments = (
        apply_confidence_retrieval_filter(db.query(ContextEntry))
        .filter(
            ContextEntry.user_id == user_id,
            ContextEntry.type == "commitment",
            ContextEntry.status == "active",
            or_(ContextEntry.expires_at.is_(None), ContextEntry.expires_at >= now),
        )
        .order_by(ContextEntry.updated_at.desc())
        .limit(4)
        .all()
    )
    for entry in active_commitments:
        snippet = _clean_chip_text(entry.content, max_len=58)
        _add_chip(
            chips,
            seen_labels,
            chip_id=f"commitment_{entry.id}",
            label=f"Move this forward: {snippet}",
            prompt=f"Help me move this commitment forward: \"{entry.content}\". Suggest assistant-executable next steps and draft the next message.",
        )

    open_tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.status.in_(["pending_approval", "approved", "snoozed"]),
        )
        .order_by(Task.updated_at.desc())
        .limit(3)
        .all()
    )
    for task in open_tasks:
        title = _clean_chip_text(task.title or f"Task {task.id}", max_len=56)
        _add_chip(
            chips,
            seen_labels,
            chip_id=f"task_{task.id}",
            label=f"Unblock: {title}",
            prompt=(
                f"Turn this into assistant-executable next steps: \"{task.title}\". "
                "If someone else owns delivery, draft a follow-up and status check."
            ),
        )

    for generic in GENERIC_ACTION_CHIPS:
        if len(chips) >= max_items:
            break
        _add_chip(chips, seen_labels, generic["id"], generic["label"], generic["prompt"])

    return {"chips": chips[:max_items]}


def get_cached_action_chips(
    db: Session,
    warm_cache: WarmCacheService,
    tenant_id: str,
    user_id: str,
    limit: int = 5,
) -> List[Dict[str, str]]:
    safe_limit = max(1, min(limit, 8))
    payload = warm_cache.get_or_build(
        tenant_id=tenant_id,
        user_id=user_id,
        scope=ACTION_CHIPS_CACHE_SCOPE,
        builder=lambda: build_action_chips_payload(db, user_id=user_id, max_items=8),
        ttl_seconds=ACTION_CHIPS_CACHE_TTL_SECONDS,
    )
    return (payload.get("chips") or [])[:safe_limit]


def prewarm_action_chips(
    db: Session,
    warm_cache: WarmCacheService,
    tenant_id: str,
    user_id: str,
) -> None:
    payload = build_action_chips_payload(db, user_id=user_id, max_items=8)
    warm_cache.set(
        tenant_id=tenant_id,
        user_id=user_id,
        scope=ACTION_CHIPS_CACHE_SCOPE,
        payload=payload,
        ttl_seconds=ACTION_CHIPS_CACHE_TTL_SECONDS,
    )

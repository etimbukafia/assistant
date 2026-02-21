"""Entity mention resolution and scoped context prefetch."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import Contact, ContextEntry, EntityReference, Message, Task
from app.services.warm_cache import WarmCacheService
from app.services.warm_context_snapshot import (
    build_contact_snapshot,
    build_event_snapshot,
    build_thread_snapshot,
)


logger = logging.getLogger(__name__)

ALLOWED_KINDS = {"contact", "event", "thread", "task"}
DEFAULT_PER_ENTITY_LIMIT = 5
DEFAULT_TOTAL_LIMIT = 25
MAX_MENTIONS_PER_MESSAGE = 8
MENTIONS_INDEX_SCOPE = "mentions_index_v1"
MENTIONS_INDEX_TTL_SECONDS = 180
MENTIONS_INDEX_MAX_CONTACTS = 300
MENTIONS_INDEX_MAX_THREADS = 220
MENTIONS_INDEX_MAX_EVENTS = 160
MENTIONS_INDEX_MAX_TASKS = 80


@dataclass
class Mention:
    kind: str
    ref: str
    label: str


class MentionContextService:
    """Resolves mentions and prefetches scoped context with budgets."""

    def __init__(
        self,
        db: Session,
        warm_cache: WarmCacheService,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> None:
        self.db = db
        self.warm_cache = warm_cache
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id

    def suggest_mentions(
        self,
        query: str,
        limit: int = 8,
        offset: int = 0,
        kind: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        q = (query or "").strip().lower()
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        kind_filter = (kind or "").strip().lower()
        if kind_filter and kind_filter not in ALLOWED_KINDS:
            return []

        payload = self.warm_cache.get_or_build(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            scope=MENTIONS_INDEX_SCOPE,
            builder=self._build_mentions_index,
            ttl_seconds=MENTIONS_INDEX_TTL_SECONDS,
        )
        indexed = list(payload.get("items") or [])

        matches: List[Dict[str, Any]] = []
        for item in indexed:
            item_kind = str(item.get("kind") or "").lower()
            if kind_filter and item_kind != kind_filter:
                continue
            label = str(item.get("label") or "")
            ref = str(item.get("ref") or "")
            search_text = str(item.get("search_text") or "")
            sample = str(item.get("sample") or "")
            haystack = f"{label} {ref} {search_text} {sample}".lower()
            if q and q not in haystack:
                continue
            matches.append(item)

        matches.sort(
            key=lambda item: (
                _match_rank(item, q),
                _kind_rank(item.get("kind", "")),
                _last_seen_rank(item.get("last_seen_at", "")),
            )
        )
        matches = matches[offset : offset + limit]

        label_counts: Dict[str, int] = {}
        for item in matches:
            key = f"{item.get('kind')}::{str(item.get('label') or '').lower()}"
            label_counts[key] = label_counts.get(key, 0) + 1
        label_index: Dict[str, int] = {}

        results: List[Dict[str, str]] = []
        for item in matches:
            kind = str(item.get("kind") or "")
            label = str(item.get("label") or "")
            dupe_key = f"{kind}::{label.lower()}"
            label_index[dupe_key] = label_index.get(dupe_key, 0) + 1
            subtitle = _format_suggestion_subtitle(
                kind=kind,
                last_seen_at=str(item.get("last_seen_at") or ""),
                sample=str(item.get("sample") or ""),
                mention_count=int(item.get("mentions", 0)),
            )
            display_label = label
            if label_counts.get(dupe_key, 0) > 1:
                display_label = f"{label} ({label_index[dupe_key]})"
            results.append(
                {
                    "kind": kind,
                    "ref": str(item.get("ref") or ""),
                    "label": label,
                    "display_label": display_label,
                    "subtitle": subtitle,
                    "last_seen_at": str(item.get("last_seen_at") or ""),
                    "created_at": str(item.get("created_at") or ""),
                    "updated_at": str(item.get("updated_at") or ""),
                    "search_text": str(item.get("search_text") or ""),
                }
            )
        return results

    def suggest_memory_entries(
        self,
        query: str,
        limit: int = 8,
        offset: int = 0,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        q_raw = (query or "").strip()
        q = q_raw.lower()
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        memory_query = self.db.query(ContextEntry).filter(ContextEntry.user_id == self.user_id)
        normalized_type = _normalize_memory_type_query((memory_type or "").strip()) if memory_type else None
        if normalized_type:
            memory_query = memory_query.filter(ContextEntry.type == normalized_type)
        normalized_q_type = _normalize_memory_type_query(q)
        if not normalized_type and normalized_q_type:
            memory_query = memory_query.filter(ContextEntry.type == normalized_q_type)
            q = ""
        if q:
            memory_query = memory_query.filter(
                or_(
                    ContextEntry.content.ilike(f"%{q}%"),
                    ContextEntry.type.ilike(f"%{q}%"),
                    ContextEntry.entity_type.ilike(f"%{q}%"),
                    ContextEntry.entity_id.ilike(f"%{q}%"),
                )
            )

        rows = (
            memory_query
            .order_by(ContextEntry.updated_at.desc(), ContextEntry.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        results: List[Dict[str, str]] = []
        for row in rows:
            results.append(
                {
                    "kind": "memory",
                    "ref": f"ctx:{row.id}",
                    "label": _memory_display_label(row.type, row.content),
                    "display_label": _memory_display_label(row.type, row.content),
                    "subtitle": _memory_subtitle(row.entity_type, row.entity_id, row.status, row.importance_level),
                    "last_seen_at": row.updated_at.isoformat() if row.updated_at else "",
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "updated_at": row.updated_at.isoformat() if row.updated_at else "",
                    "search_text": _compact_search_text(row.content or "", max_len=80),
                }
            )
        return results

    def _build_mentions_index(self) -> Dict[str, Any]:
        context_rows = (
            self.db.query(ContextEntry)
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.entity_type.in_(["contact", "event", "thread"]),
                ContextEntry.entity_id.isnot(None),
            )
            .order_by(ContextEntry.created_at.desc())
            .limit(400)
            .all()
        )

        context_index: Dict[str, Dict[str, Any]] = {}
        for row in context_rows:
            ref = (row.entity_id or "").strip()
            if not ref:
                continue
            ref_key = ref.lower() if row.entity_type == "contact" else ref
            key = f"{row.entity_type}:{ref_key.lower()}"
            if key not in context_index:
                sample = (row.content or "").strip()
                stamp = row.updated_at or row.created_at
                context_index[key] = {
                    "kind": row.entity_type,
                    "ref": ref_key,
                    "label": _displayable_label(row.entity_type, ref_key, sample),
                    "sample": sample,
                    "mentions": 0,
                    "last_seen_at": stamp.isoformat() if stamp else "",
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "updated_at": row.updated_at.isoformat() if row.updated_at else "",
                }
            context_index[key]["mentions"] += 1

        grouped: Dict[str, Dict[str, Any]] = {}

        contacts = (
            self.db.query(Contact)
            .filter(Contact.user_id == self.user_id)
            .order_by(Contact.updated_at.desc())
            .limit(MENTIONS_INDEX_MAX_CONTACTS)
            .all()
        )
        for contact in contacts:
            ref = (contact.email or "").strip().lower()
            if not ref:
                continue
            key = f"contact:{ref}"
            ctx = context_index.get(key, {})
            updated_dt = contact.updated_at or contact.created_at
            grouped[key] = {
                "kind": "contact",
                "ref": ref,
                "label": (contact.name or "").strip() or _entity_label("contact", ref),
                "sample": ctx.get("sample", (contact.notes or "").strip()),
                "mentions": int(ctx.get("mentions", 0)),
                "last_seen_at": ctx.get("last_seen_at", updated_dt.isoformat() if updated_dt else ""),
                "created_at": ctx.get("created_at", contact.created_at.isoformat() if contact.created_at else ""),
                "updated_at": ctx.get("updated_at", contact.updated_at.isoformat() if contact.updated_at else ""),
            }

        entities = (
            self.db.query(EntityReference)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type.in_(["thread", "event"]),
            )
            .order_by(EntityReference.updated_at.desc())
            .limit(MENTIONS_INDEX_MAX_THREADS + MENTIONS_INDEX_MAX_EVENTS)
            .all()
        )
        for entity in entities:
            ref = (entity.ref or "").strip()
            if not ref:
                continue
            key = f"{entity.entity_type}:{ref.lower()}"
            ctx = context_index.get(key, {})
            updated_dt = entity.updated_at or entity.created_at
            grouped[key] = {
                "kind": entity.entity_type,
                "ref": ref,
                "label": (entity.display_name or "").strip() or ctx.get("label") or _entity_label(entity.entity_type, ref),
                "sample": ctx.get("sample", (entity.notes or "").strip()),
                "mentions": int(ctx.get("mentions", 0)),
                "last_seen_at": ctx.get("last_seen_at", updated_dt.isoformat() if updated_dt else ""),
                "created_at": ctx.get("created_at", entity.created_at.isoformat() if entity.created_at else ""),
                "updated_at": ctx.get("updated_at", entity.updated_at.isoformat() if entity.updated_at else ""),
            }

        tasks = (
            self.db.query(Task)
            .filter(Task.user_id == self.user_id)
            .order_by(Task.updated_at.desc())
            .limit(MENTIONS_INDEX_MAX_TASKS)
            .all()
        )
        for task in tasks:
            ref = str(task.id)
            key = f"task:{ref}"
            if key in grouped:
                continue
            updated_dt = task.updated_at or task.created_at
            grouped[key] = {
                "kind": "task",
                "ref": ref,
                "label": (task.title or "").strip() or f"Task {task.id}",
                "sample": (task.description or "").strip() or f"Status: {task.status}",
                "mentions": 0,
                "last_seen_at": updated_dt.isoformat() if updated_dt else "",
                "created_at": task.created_at.isoformat() if task.created_at else "",
                "updated_at": task.updated_at.isoformat() if task.updated_at else "",
            }

        recent_messages = (
            self.db.query(Message)
            .filter(Message.user_id == self.user_id)
            .order_by(Message.received_at.desc(), Message.created_at.desc())
            .limit(MENTIONS_INDEX_MAX_THREADS)
            .all()
        )
        seen_thread_refs: set[str] = set()
        for msg in recent_messages:
            stamp = msg.received_at or msg.updated_at or msg.created_at
            ts = stamp.isoformat() if stamp else ""
            subject = (msg.subject or "").strip()

            thread_ref = (msg.thread_id or "").strip()
            if thread_ref:
                key_lower = thread_ref.lower()
                if key_lower in seen_thread_refs:
                    continue
                seen_thread_refs.add(key_lower)
                key = f"thread:{key_lower}"
                if key not in grouped:
                    ctx = context_index.get(key, {})
                    grouped[key] = {
                        "kind": "thread",
                        "ref": thread_ref,
                        "label": subject or _entity_label("thread", thread_ref),
                        "sample": ctx.get("sample", subject),
                        "mentions": int(ctx.get("mentions", 0)),
                        "last_seen_at": ctx.get("last_seen_at", ts),
                        "created_at": ctx.get("created_at", msg.created_at.isoformat() if msg.created_at else ""),
                        "updated_at": ctx.get("updated_at", msg.updated_at.isoformat() if msg.updated_at else ""),
                    }

        for key, value in context_index.items():
            if key not in grouped and value.get("kind") in {"contact", "thread", "event"}:
                grouped[key] = value

        items: List[Dict[str, Any]] = []
        for item in grouped.values():
            kind = str(item.get("kind") or "")
            label = str(item.get("label") or "")
            ref = str(item.get("ref") or "")
            sample = str(item.get("sample") or "")
            tiny_search = _compact_search_text(sample, max_len=80)
            items.append(
                {
                    **item,
                    "kind": kind,
                    "label": label,
                    "ref": ref,
                    "sample": sample,
                    "search_text": tiny_search,
                }
            )

        items.sort(key=lambda item: (_kind_rank(item.get("kind", "")), _last_seen_rank(item.get("last_seen_at", ""))))
        items = _cap_mentions_index(items)

        return {
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_count": len(items),
            "items": items,
        }

    def prefetch_for_mentions(
        self,
        mentions: List[Dict[str, str]],
        max_items_per_entity: int = DEFAULT_PER_ENTITY_LIMIT,
        max_items_total: int = DEFAULT_TOTAL_LIMIT,
    ) -> Dict[str, Any]:
        max_items_per_entity = max(1, min(max_items_per_entity, 10))
        max_items_total = max(1, min(max_items_total, 50))

        parsed_mentions = self._normalize_mentions(mentions)
        overflow_mentions: List[Dict[str, str]] = []
        if len(parsed_mentions) > MAX_MENTIONS_PER_MESSAGE:
            overflow = parsed_mentions[MAX_MENTIONS_PER_MESSAGE:]
            parsed_mentions = parsed_mentions[:MAX_MENTIONS_PER_MESSAGE]
            overflow_mentions = [{"kind": m.kind, "ref": m.ref, "label": m.label, "reason": "mention_limit_exceeded"} for m in overflow]
        resolved, unresolved = self._resolve_mentions(parsed_mentions)
        unresolved.extend(overflow_mentions)

        entities: List[Dict[str, Any]] = []
        for mention in resolved:
            snapshot = self._get_snapshot_for_mention(mention)
            entries = _extract_entries(snapshot, mention.kind)
            scored = _score_entries(entries, mention.kind, mention.label)
            trimmed = scored[:max_items_per_entity]
            entities.append(
                {
                    "kind": mention.kind,
                    "ref": mention.ref,
                    "label": mention.label,
                    "scope": f"{mention.kind}:{mention.ref}",
                    "available_count": len(scored),
                    "selected_count": len(trimmed),
                    "entries": [_to_context_entry_payload(item, mention, score) for item, score in trimmed],
                }
            )

        flattened: List[Tuple[Dict[str, Any], float]] = []
        for entity in entities:
            for item in entity["entries"]:
                flattened.append((item, float(item.get("_score", 0.0))))
        flattened.sort(key=lambda tup: tup[1], reverse=True)
        selected = [item for item, _ in flattened[:max_items_total]]
        selected = _dedupe_entries(selected)
        dropped = max(0, len(flattened) - len(selected))
        for item in selected:
            item.pop("_score", None)

        kinds = OrderedDict()
        for mention in resolved:
            kinds[mention.kind] = True

        return {
            "mentions_received": len(mentions or []),
            "resolved_mentions": [{"kind": m.kind, "ref": m.ref, "label": m.label} for m in resolved],
            "unresolved_mentions": unresolved,
            "entities": entities,
            "selected_entries": selected,
            "selected_count": len(selected),
            "dropped_count": dropped,
            "context_types": list(kinds.keys()),
            "budgets": {
                "max_items_per_entity": max_items_per_entity,
                "max_items_total": max_items_total,
                "max_mentions_per_message": MAX_MENTIONS_PER_MESSAGE,
            },
        }

    def _normalize_mentions(self, mentions: Iterable[Dict[str, str]]) -> List[Mention]:
        results: List[Mention] = []
        seen = set()
        for raw in mentions or []:
            kind = (raw.get("kind") or "").strip().lower()
            ref = (raw.get("ref") or "").strip()
            label = (raw.get("label") or "").strip()
            if kind not in ALLOWED_KINDS or not ref:
                continue
            normalized_ref = ref.lower() if kind == "contact" else ref
            key = f"{kind}:{normalized_ref.lower()}"
            if key in seen:
                continue
            seen.add(key)
            results.append(Mention(kind=kind, ref=normalized_ref, label=label or ref))
        return results

    def _resolve_mentions(self, mentions: List[Mention]) -> Tuple[List[Mention], List[Dict[str, str]]]:
        resolved: List[Mention] = []
        unresolved: List[Dict[str, str]] = []

        for mention in mentions:
            if mention.kind == "contact":
                contact = (
                    self.db.query(Contact)
                    .filter(Contact.user_id == self.user_id, func.lower(Contact.email) == mention.ref.lower())
                    .first()
                )
                if not contact:
                    contact = (
                        self.db.query(Contact)
                        .filter(Contact.user_id == self.user_id, func.lower(Contact.name) == mention.label.lower())
                        .first()
                    )
                if contact and contact.email:
                    resolved.append(Mention(kind="contact", ref=contact.email.lower(), label=(contact.name or "").strip() or mention.label))
                    continue

            if mention.kind in {"thread", "event", "task"}:
                entity = (
                    self.db.query(EntityReference)
                    .filter(
                        EntityReference.user_id == self.user_id,
                        EntityReference.entity_type == mention.kind,
                        EntityReference.ref == mention.ref,
                    )
                    .first()
                )
                if not entity:
                    entity = (
                        self.db.query(EntityReference)
                        .filter(
                            EntityReference.user_id == self.user_id,
                            EntityReference.entity_type == mention.kind,
                            func.lower(EntityReference.display_name) == mention.label.lower(),
                        )
                        .first()
                )
                if entity:
                    resolved.append(Mention(kind=mention.kind, ref=entity.ref, label=entity.display_name))
                    continue

                if mention.kind == "task":
                    task = None
                    if mention.ref.isdigit():
                        task = (
                            self.db.query(Task)
                            .filter(
                                Task.user_id == self.user_id,
                                Task.id == int(mention.ref),
                            )
                            .first()
                        )
                    if not task:
                        lookup = mention.label or mention.ref
                        task = (
                            self.db.query(Task)
                            .filter(
                                Task.user_id == self.user_id,
                                func.lower(Task.title) == lookup.lower(),
                            )
                            .order_by(Task.updated_at.desc())
                            .first()
                        )
                    if task:
                        resolved.append(
                            Mention(
                                kind="task",
                                ref=str(task.id),
                                label=(task.title or "").strip() or mention.label or mention.ref,
                            )
                        )
                        continue

                if mention.kind == "thread":
                    thread_message = (
                        self.db.query(Message)
                        .filter(
                            Message.user_id == self.user_id,
                            Message.thread_id == mention.ref,
                        )
                        .order_by(Message.received_at.desc(), Message.created_at.desc())
                        .first()
                    )
                    if not thread_message and mention.label:
                        thread_message = (
                            self.db.query(Message)
                            .filter(
                                Message.user_id == self.user_id,
                                func.lower(Message.subject) == mention.label.lower(),
                            )
                            .order_by(Message.received_at.desc(), Message.created_at.desc())
                            .first()
                        )
                    if thread_message and thread_message.thread_id:
                        resolved.append(
                            Mention(
                                kind="thread",
                                ref=thread_message.thread_id,
                                label=(thread_message.subject or "").strip() or mention.label or thread_message.thread_id,
                            )
                        )
                        continue

            unresolved.append({"kind": mention.kind, "ref": mention.ref, "label": mention.label, "reason": "entity_not_found_for_user"})

        deduped = OrderedDict()
        for mention in resolved:
            deduped[f"{mention.kind}:{mention.ref.lower()}"] = mention
        return list(deduped.values()), unresolved

    def _get_snapshot_for_mention(self, mention: Mention) -> Dict[str, Any]:
        scope = f"{mention.kind}:{mention.ref}"
        if mention.kind == "contact":
            builder = lambda: build_contact_snapshot(self.db, self.user_id, mention.ref)
        elif mention.kind == "event":
            builder = lambda: build_event_snapshot(self.db, self.user_id, mention.ref)
        elif mention.kind == "task":
            builder = lambda: self._build_task_snapshot(mention.ref)
        else:
            builder = lambda: build_thread_snapshot(self.db, self.user_id, mention.ref)
        return self.warm_cache.get_or_build(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            scope=scope,
            builder=builder,
        )

    def _build_task_snapshot(self, task_ref: str) -> Dict[str, Any]:
        task = None
        if (task_ref or "").isdigit():
            task = (
                self.db.query(Task)
                .filter(
                    Task.user_id == self.user_id,
                    Task.id == int(task_ref),
                )
                .first()
            )
        if not task:
            task = (
                self.db.query(Task)
                .filter(
                    Task.user_id == self.user_id,
                    func.lower(Task.title) == (task_ref or "").lower(),
                )
                .order_by(Task.updated_at.desc())
                .first()
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        if not task:
            return {
                "version": "v1",
                "user_id": self.user_id,
                "scope": "task",
                "scope_id": task_ref,
                "entity_type": "task",
                "generated_at": now_iso,
                "source_count": 0,
                "counts_by_type": {},
                "by_type": {},
                "by_entity": {},
                "critical_items": [],
                "recent_timeline": [],
            }

        importance = "high" if (task.priority or "").lower() in {"high", "urgent"} else "normal"
        entity_id = str(task.id)
        timeline: List[Dict[str, Any]] = [
            {
                "id": f"task:{task.id}:title",
                "type": "commitment",
                "content": task.title,
                "entity_type": "task",
                "entity_id": entity_id,
                "created_by": "Teeks",
                "created_at": task.created_at.isoformat() if task.created_at else now_iso,
                "importance_level": importance,
            },
            {
                "id": f"task:{task.id}:status",
                "type": "insight",
                "content": f"Task status: {task.status}",
                "entity_type": "task",
                "entity_id": entity_id,
                "created_by": "Teeks",
                "created_at": task.updated_at.isoformat() if task.updated_at else now_iso,
                "importance_level": "normal",
            },
        ]
        if task.deadline:
            timeline.append(
                {
                    "id": f"task:{task.id}:deadline",
                    "type": "commitment",
                    "content": f"Deadline: {task.deadline.isoformat()}",
                    "entity_type": "task",
                    "entity_id": entity_id,
                    "created_by": "Teeks",
                    "created_at": task.deadline.isoformat(),
                    "importance_level": importance,
                }
            )
        if task.description:
            timeline.append(
                {
                    "id": f"task:{task.id}:description",
                    "type": "insight",
                    "content": task.description,
                    "entity_type": "task",
                    "entity_id": entity_id,
                    "created_by": "Teeks",
                    "created_at": task.updated_at.isoformat() if task.updated_at else now_iso,
                    "importance_level": "normal",
                }
            )

        by_type: Dict[str, List[Dict[str, Any]]] = {"commitment": [], "insight": []}
        for item in timeline:
            by_type.setdefault(item["type"], []).append(item)

        return {
            "version": "v1",
            "user_id": self.user_id,
            "scope": "task",
            "scope_id": entity_id,
            "entity_type": "task",
            "generated_at": now_iso,
            "source_count": len(timeline),
            "counts_by_type": {k: len(v) for k, v in by_type.items() if v},
            "by_type": {k: v for k, v in by_type.items() if v},
            "by_entity": {f"task:{entity_id}": timeline},
            "critical_items": [item for item in timeline if item.get("importance_level") == "high"],
            "recent_timeline": timeline,
        }


def _extract_entries(snapshot: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    by_type = snapshot.get("by_type", {}) or {}
    order_map = {
        "contact": ["relationships", "preferences", "insight", "decision", "commitment"],
        "event": ["decision", "commitment", "insight", "relationships", "preferences"],
        "message": ["commitment", "decision", "insight", "relationships", "preferences"],
        "thread": ["decision", "commitment", "insight", "relationships", "preferences"],
        "task": ["commitment", "insight", "decision", "relationships", "preferences"],
    }
    order = order_map.get(kind, ["insight"])
    results: List[Dict[str, Any]] = []
    seen = set()
    for type_name in order:
        for item in by_type.get(type_name, []) or []:
            key = item.get("id") or f"{item.get('type')}::{item.get('content')}"
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
    return results or list(snapshot.get("recent_timeline", []) or [])


def _score_entries(entries: List[Dict[str, Any]], kind: str, label: str) -> List[Tuple[Dict[str, Any], float]]:
    scored: List[Tuple[Dict[str, Any], float]] = []
    for item in entries:
        importance = item.get("importance_level") or "normal"
        importance_score = {"low": 0.0, "normal": 1.0, "high": 3.0}.get(importance, 1.0)
        recency_score = _recency_score(item.get("created_at"))
        kind_bonus = _kind_bonus(kind, item.get("type"))
        label_bonus = 0.5 if label and label.lower() in (item.get("content") or "").lower() else 0.0
        scored.append((item, importance_score + recency_score + kind_bonus + label_bonus))
    scored.sort(key=lambda tup: tup[1], reverse=True)
    return scored


def _kind_bonus(kind: str, entry_type: Optional[str]) -> float:
    priorities = {
        "contact": {"relationships": 1.5, "preferences": 0.75},
        "event": {"decision": 1.5, "commitment": 1.25},
        "message": {"commitment": 1.5, "decision": 1.25},
        "thread": {"decision": 1.5, "commitment": 1.25},
        "task": {"commitment": 1.5, "insight": 1.0},
    }
    return priorities.get(kind, {}).get(entry_type or "", 0.0)


def _recency_score(created_at: Optional[str]) -> float:
    if not created_at:
        return 0.0
    try:
        ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta_days = (datetime.now(timezone.utc) - ts).days
        if delta_days <= 3:
            return 2.0
        if delta_days <= 14:
            return 1.0
    except Exception:
        return 0.0
    return 0.0


def _to_context_entry_payload(item: Dict[str, Any], mention: Mention, score: float) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "type": item.get("type"),
        "content": item.get("content"),
        "entity_type": item.get("entity_type"),
        "entity_id": item.get("entity_id"),
        "created_by": item.get("created_by"),
        "created_at": item.get("created_at"),
        "importance_level": item.get("importance_level"),
        "mention_kind": mention.kind,
        "mention_ref": mention.ref,
        "mention_label": mention.label,
        "_score": score,
    }


def _dedupe_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = OrderedDict()
    for entry in entries:
        key = entry.get("id") or f"{entry.get('type')}::{entry.get('content')}"
        if str(key) not in out:
            out[str(key)] = entry
    return list(out.values())


def _compact_search_text(value: str, max_len: int = 80) -> str:
    text = " ".join((value or "").replace("\n", " ").split()).strip()
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}..."


def _memory_type_title(value: str) -> str:
    mapping = {
        "decision": "Decision",
        "commitment": "Commitment",
        "preferences": "Preference",
        "relationships": "Relationship",
        "insight": "Watchout",
    }
    return mapping.get((value or "").strip().lower(), "Remember")


def _memory_display_label(entry_type: str, content: str) -> str:
    prefix = _memory_type_title(entry_type)
    snippet = _compact_search_text((content or "").replace("\n", " "), max_len=68)
    if snippet:
        return f"{prefix}: {snippet}"
    return prefix


def _memory_subtitle(entity_type: Optional[str], entity_id: Optional[str], status: Optional[str], importance: Optional[str]) -> str:
    parts: List[str] = []
    if entity_type:
        scope_label = (entity_type or "").strip().title()
        if entity_id:
            parts.append(f"{scope_label} · {entity_id}")
        else:
            parts.append(scope_label)
    if status:
        parts.append(str(status).title())
    if importance:
        parts.append(f"{str(importance).title()} priority")
    return " | ".join(parts)


def _normalize_memory_type_query(query: str) -> Optional[str]:
    token = (query or "").strip().lower()
    if not token:
        return None
    aliases = {
        "decision": "decision",
        "decisions": "decision",
        "commitment": "commitment",
        "commitments": "commitment",
        "preference": "preferences",
        "preferences": "preferences",
        "relationship": "relationships",
        "relationships": "relationships",
        "watchout": "insight",
        "watchouts": "insight",
        "insight": "insight",
        "insights": "insight",
        "risk": "insight",
        "risks": "insight",
    }
    return aliases.get(token)


def _cap_mentions_index(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    caps = {
        "contact": MENTIONS_INDEX_MAX_CONTACTS,
        "thread": MENTIONS_INDEX_MAX_THREADS,
        "event": MENTIONS_INDEX_MAX_EVENTS,
        "task": MENTIONS_INDEX_MAX_TASKS,
    }
    counts: Dict[str, int] = {k: 0 for k in caps.keys()}
    out: List[Dict[str, Any]] = []
    for item in items:
        kind = str(item.get("kind") or "")
        if kind not in caps:
            continue
        if counts[kind] >= caps[kind]:
            continue
        counts[kind] += 1
        out.append(item)
    return out


def _entity_label(kind: str, ref: str) -> str:
    clean = (ref or "").strip()
    if kind == "contact" and "@" in clean:
        local = clean.split("@", 1)[0]
        return local.replace(".", " ").replace("_", " ").replace("-", " ").title()
    return clean.title() if kind == "contact" else clean


def _displayable_label(kind: str, ref: str, sample: str) -> str:
    default = _entity_label(kind, ref)
    if kind not in {"event", "thread", "message"}:
        return default
    if not _looks_opaque_ref(ref):
        return default
    derived = (sample or "").replace("\n", " ").strip()
    if len(derived) > 45:
        derived = f"{derived[:42]}..."
    return derived or default


def _looks_opaque_ref(ref: str) -> bool:
    clean = (ref or "").strip()
    return bool(clean and ((len(clean) >= 18 and any(ch.isdigit() for ch in clean) and "-" in clean) or clean.lower().startswith(("evt_", "thr_", "msg_"))))


def _kind_rank(kind: str) -> int:
    order = {"contact": 0, "task": 1, "event": 2, "thread": 3}
    return order.get(kind, 9)


def _match_rank(item: Dict[str, Any], query: str) -> int:
    if not query:
        return 0
    label = str(item.get("label") or "").lower()
    ref = str(item.get("ref") or "").lower()
    sample = str(item.get("sample") or "").lower()
    if label.startswith(query) or ref.startswith(query):
        return 0
    if query in label or query in ref:
        return 1
    if query in sample:
        return 2
    return 3


def _last_seen_rank(last_seen_at: str) -> int:
    if not last_seen_at:
        return 0
    try:
        dt = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return -int(dt.timestamp())
    except Exception:
        return 0


def _format_suggestion_subtitle(kind: str, last_seen_at: str, sample: str, mention_count: int) -> str:
    date_hint = ""
    try:
        if last_seen_at:
            dt = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
            date_hint = dt.strftime("%b %d")
    except Exception:
        date_hint = ""
    sample_hint = (sample or "").replace("\n", " ").strip()
    if len(sample_hint) > 70:
        sample_hint = f"{sample_hint[:67]}..."
    base = {"contact": "Contact context", "event": "Event context", "thread": "Thread context", "task": "Task context"}.get(kind, "Entity context")
    parts = [base]
    if date_hint:
        parts.append(f"last noted {date_hint}")
    if mention_count > 1:
        parts.append(f"{mention_count} notes")
    if sample_hint:
        parts.append(sample_hint)
    return " | ".join(parts)

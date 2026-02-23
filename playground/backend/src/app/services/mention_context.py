"""Entity mention resolution and scoped context prefetch."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import Contact, ContextEntry, EntityReference
from app.services.warm_cache import WarmCacheService
from app.services.warm_context_snapshot import (
    build_contact_snapshot,
    build_event_snapshot,
    build_message_snapshot,
    build_thread_snapshot,
)


logger = logging.getLogger(__name__)

ALLOWED_KINDS = {"contact", "event", "thread", "message"}
DEFAULT_PER_ENTITY_LIMIT = 5
DEFAULT_TOTAL_LIMIT = 25
MAX_MENTIONS_PER_MESSAGE = 8


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
        q = (query or "").strip()
        limit = max(1, min(limit, 500))
        offset = max(0, min(offset, 5000))
        kind_norm = (kind or "").strip().lower()

        context_query = (
            self.db.query(ContextEntry)
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.entity_type.in_(["contact", "event", "thread", "message"]),
                ContextEntry.entity_id.isnot(None),
            )
        )
        if kind_norm in {"contact", "event", "thread", "message"}:
            context_query = context_query.filter(ContextEntry.entity_type == kind_norm)
        if q:
            context_query = context_query.filter(
                or_(
                    ContextEntry.entity_id.ilike(f"%{q}%"),
                    ContextEntry.content.ilike(f"%{q}%"),
                )
            )
        context_rows = (
            context_query
            .order_by(ContextEntry.created_at.desc())
            .limit(400 if not q else 300)
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
                context_index[key] = {
                    "kind": row.entity_type,
                    "ref": ref_key,
                    "label": _displayable_label(row.entity_type, ref_key, sample),
                    "last_seen_at": row.created_at.isoformat() if row.created_at else "",
                    "sample": sample,
                    "mentions": 0,
                }
            context_index[key]["mentions"] += 1

        grouped: Dict[str, Dict[str, Any]] = {}

        contact_query = self.db.query(Contact).filter(Contact.user_id == self.user_id)
        if kind_norm and kind_norm != "contact":
            contact_query = contact_query.filter(Contact.id == -1)
        if q:
            contact_query = contact_query.filter(
                or_(
                    Contact.name.ilike(f"%{q}%"),
                    Contact.email.ilike(f"%{q}%"),
                )
            )
        contacts = contact_query.order_by(Contact.updated_at.desc()).limit(150).all()
        for contact in contacts:
            ref = (contact.email or "").strip().lower()
            if not ref:
                continue
            key = f"contact:{ref}"
            ctx = context_index.get(key, {})
            grouped[key] = {
                "kind": "contact",
                "ref": ref,
                "label": (contact.name or "").strip() or _entity_label("contact", ref),
                "last_seen_at": ctx.get("last_seen_at", contact.updated_at.isoformat() if contact.updated_at else ""),
                "sample": ctx.get("sample", ""),
                "mentions": int(ctx.get("mentions", 0)),
            }

        entity_query = (
            self.db.query(EntityReference)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type.in_(["thread", "event", "message"]),
            )
        )
        if kind_norm in {"thread", "event", "message"}:
            entity_query = entity_query.filter(EntityReference.entity_type == kind_norm)
        elif kind_norm:
            entity_query = entity_query.filter(EntityReference.id == -1)
        if q:
            entity_query = entity_query.filter(
                or_(
                    EntityReference.display_name.ilike(f"%{q}%"),
                    EntityReference.ref.ilike(f"%{q}%"),
                )
            )
        entities = entity_query.order_by(EntityReference.updated_at.desc()).limit(200).all()
        for entity in entities:
            ref = (entity.ref or "").strip()
            if not ref:
                continue
            key = f"{entity.entity_type}:{ref.lower()}"
            ctx = context_index.get(key, {})
            grouped[key] = {
                "kind": entity.entity_type,
                "ref": ref,
                "label": (entity.display_name or "").strip() or ctx.get("label") or _entity_label(entity.entity_type, ref),
                "last_seen_at": ctx.get("last_seen_at", entity.updated_at.isoformat() if entity.updated_at else ""),
                "sample": ctx.get("sample", ""),
                "mentions": int(ctx.get("mentions", 0)),
            }

        # Backward compatibility for existing context data without catalog rows.
        for key, value in context_index.items():
            if key not in grouped and value.get("kind") in {"contact", "thread", "event"}:
                grouped[key] = value

        suggestions: List[Dict[str, Any]] = []
        query_lower = q.lower()
        for item in grouped.values():
            label = str(item.get("label") or "")
            ref = str(item.get("ref") or "")
            sample = str(item.get("sample") or "")
            haystack = f"{label} {ref} {sample}".lower()
            if query_lower and query_lower not in haystack:
                continue
            suggestions.append(item)

        suggestions.sort(
            key=lambda item: (
                _match_rank(item, query_lower),
                _kind_rank(item["kind"]),
                _last_seen_rank(item.get("last_seen_at", "")),
            )
        )
        suggestions = suggestions[offset : offset + limit]

        label_counts: Dict[str, int] = {}
        for item in suggestions:
            key = f"{item['kind']}::{item['label'].lower()}"
            label_counts[key] = label_counts.get(key, 0) + 1
        label_index: Dict[str, int] = {}

        results: List[Dict[str, str]] = []
        for item in suggestions:
            dupe_key = f"{item['kind']}::{item['label'].lower()}"
            label_index[dupe_key] = label_index.get(dupe_key, 0) + 1
            subtitle = _format_suggestion_subtitle(
                kind=item["kind"],
                last_seen_at=item.get("last_seen_at", ""),
                sample=item.get("sample", ""),
                mention_count=int(item.get("mentions", 0)),
            )
            display_label = item["label"]
            if label_counts.get(dupe_key, 0) > 1:
                display_label = f"{item['label']} ({label_index[dupe_key]})"
            results.append(
                {
                    "kind": item["kind"],
                    "ref": item["ref"],
                    "label": item["label"],
                    "display_label": display_label,
                    "subtitle": subtitle,
                    "last_seen_at": item.get("last_seen_at") or None,
                    "created_at": None,
                    "updated_at": item.get("last_seen_at") or None,
                    "search_text": (item.get("sample") or "").strip() or None,
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
        q = (query or "").strip()
        limit = max(1, min(limit, 500))
        offset = max(0, min(offset, 5000))
        memory_type_norm = (memory_type or "").strip().lower()

        qy = self.db.query(ContextEntry).filter(ContextEntry.user_id == self.user_id)
        if memory_type_norm:
            qy = qy.filter(ContextEntry.type == memory_type_norm)
        if q:
            qy = qy.filter(
                or_(
                    ContextEntry.content.ilike(f"%{q}%"),
                    ContextEntry.type.ilike(f"%{q}%"),
                    ContextEntry.entity_type.ilike(f"%{q}%"),
                    ContextEntry.entity_id.ilike(f"%{q}%"),
                )
            )

        rows = (
            qy.order_by(ContextEntry.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        results: List[Dict[str, str]] = []
        for row in rows:
            label = (row.content or "").strip()
            if len(label) > 96:
                label = label[:93].rstrip() + "..."
            subtitle = _memory_subtitle(
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                status=row.status,
                importance=row.importance_level,
            )
            results.append(
                {
                    "kind": "memory",
                    "ref": f"memory:{row.id}",
                    "label": label,
                    "display_label": label,
                    "subtitle": subtitle,
                    "last_seen_at": row.updated_at.isoformat() if row.updated_at else "",
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "updated_at": row.updated_at.isoformat() if row.updated_at else "",
                    "search_text": (row.content or "").strip(),
                }
            )
        return results

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
            overflow_mentions = [
                {
                    "kind": m.kind,
                    "ref": m.ref,
                    "label": m.label,
                    "reason": "mention_limit_exceeded",
                }
                for m in overflow
            ]
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

        kind_types = OrderedDict()
        for mention in resolved:
            kind_types[mention.kind] = True

        result = {
            "mentions_received": len(mentions or []),
            "resolved_mentions": [
                {"kind": m.kind, "ref": m.ref, "label": m.label}
                for m in resolved
            ],
            "unresolved_mentions": unresolved,
            "entities": entities,
            "selected_entries": selected,
            "selected_count": len(selected),
            "dropped_count": dropped,
            "context_types": list(kind_types.keys()),
            "budgets": {
                "max_items_per_entity": max_items_per_entity,
                "max_items_total": max_items_total,
                "max_mentions_per_message": MAX_MENTIONS_PER_MESSAGE,
            },
        }
        logger.info(
            "mention_prefetch tenant=%s user=%s session=%s received=%s resolved=%s unresolved=%s selected=%s dropped=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            result["mentions_received"],
            len(result["resolved_mentions"]),
            len(result["unresolved_mentions"]),
            result["selected_count"],
            result["dropped_count"],
        )
        return result

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
                    .filter(
                        Contact.user_id == self.user_id,
                        func.lower(Contact.email) == mention.ref.lower(),
                    )
                    .first()
                )
                if not contact:
                    contact = (
                        self.db.query(Contact)
                        .filter(
                            Contact.user_id == self.user_id,
                            func.lower(Contact.name) == mention.label.lower(),
                        )
                        .first()
                    )
                if contact and contact.email:
                    resolved.append(
                        Mention(
                            kind="contact",
                            ref=contact.email.lower(),
                            label=(contact.name or "").strip() or mention.label or _entity_label("contact", contact.email),
                        )
                    )
                    continue

            if mention.kind in {"thread", "event", "message"}:
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
                    resolved.append(
                        Mention(
                            kind=mention.kind,
                            ref=entity.ref,
                            label=entity.display_name,
                        )
                    )
                    continue

            # Legacy fallback for older records.
            row = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    ContextEntry.entity_type == mention.kind,
                    ContextEntry.entity_id == mention.ref,
                )
                .order_by(ContextEntry.created_at.desc())
                .first()
            )
            if row and row.entity_id:
                canonical_ref = row.entity_id.lower() if mention.kind == "contact" else row.entity_id
                resolved.append(
                    Mention(
                        kind=mention.kind,
                        ref=canonical_ref,
                        label=mention.label or _entity_label(mention.kind, canonical_ref),
                    )
                )
                continue

            unresolved.append(
                {
                    "kind": mention.kind,
                    "ref": mention.ref,
                    "label": mention.label,
                    "reason": "entity_not_found_for_user",
                }
            )

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
        elif mention.kind == "message":
            builder = lambda: build_message_snapshot(self.db, self.user_id, mention.ref)
        else:
            builder = lambda: build_thread_snapshot(self.db, self.user_id, mention.ref)
        return self.warm_cache.get_or_build(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            scope=scope,
            builder=builder,
        )


def _extract_entries(snapshot: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    by_type = snapshot.get("by_type", {}) or {}
    order_map = {
        "contact": ["relationships", "preferences", "insight", "decision", "commitment"],
        "event": ["decision", "commitment", "insight", "relationships", "preferences"],
        "message": ["commitment", "decision", "insight", "relationships", "preferences"],
        "thread": ["decision", "commitment", "insight", "relationships", "preferences"],
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
    if results:
        return results

    for item in snapshot.get("recent_timeline", []) or []:
        key = item.get("id") or f"{item.get('type')}::{item.get('content')}"
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
    return results


def _score_entries(
    entries: List[Dict[str, Any]],
    kind: str,
    label: str,
) -> List[Tuple[Dict[str, Any], float]]:
    scored: List[Tuple[Dict[str, Any], float]] = []
    for item in entries:
        importance = item.get("importance_level") or "normal"
        importance_score = {"low": 0.0, "normal": 1.0, "high": 3.0}.get(importance, 1.0)
        recency_score = _recency_score(item.get("created_at"))
        kind_bonus = _kind_bonus(kind, item.get("type"))
        label_bonus = 0.5 if label and label.lower() in (item.get("content") or "").lower() else 0.0
        total = importance_score + recency_score + kind_bonus + label_bonus
        scored.append((item, total))
    scored.sort(key=lambda tup: tup[1], reverse=True)
    return scored


def _kind_bonus(kind: str, entry_type: Optional[str]) -> float:
    priorities = {
        "contact": {"relationships": 1.5, "preferences": 0.75},
        "event": {"decision": 1.5, "commitment": 1.25},
        "message": {"commitment": 1.5, "decision": 1.25},
        "thread": {"decision": 1.5, "commitment": 1.25},
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


def _entity_label(kind: str, ref: str) -> str:
    clean = (ref or "").strip()
    if kind == "contact":
        if "@" in clean:
            local = clean.split("@", 1)[0]
            return local.replace(".", " ").replace("_", " ").replace("-", " ").title()
        return clean.title()
    return clean


def _displayable_label(kind: str, ref: str, sample: str) -> str:
    default = _entity_label(kind, ref)
    if kind not in {"event", "thread"}:
        return default
    if not _looks_opaque_ref(ref):
        return default
    derived = _derive_label_from_sample(sample)
    return derived or default


def _looks_opaque_ref(ref: str) -> bool:
    clean = (ref or "").strip()
    if not clean:
        return True
    if len(clean) >= 18 and any(ch.isdigit() for ch in clean) and "-" in clean:
        return True
    if clean.lower().startswith("evt_") or clean.lower().startswith("thr_") or clean.lower().startswith("msg_"):
        return True
    return False


def _derive_label_from_sample(sample: str) -> str:
    text = (sample or "").replace("\n", " ").strip()
    if not text:
        return ""
    if len(text) > 45:
        return f"{text[:42]}..."
    return text


def _kind_rank(kind: str) -> int:
    order = {"contact": 0, "event": 1, "thread": 2, "message": 3}
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


def _memory_subtitle(
    entity_type: Optional[str],
    entity_id: Optional[str],
    status: Optional[str],
    importance: Optional[str],
) -> str:
    parts: List[str] = ["Remember"]
    if entity_type:
        scope = str(entity_type).strip().title()
        if entity_id:
            parts.append(f"{scope} · {entity_id}")
        else:
            parts.append(scope)
    if status:
        parts.append(str(status).title())
    if importance:
        parts.append(str(importance).title())
    return " | ".join(parts)


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

    base = {
        "contact": "Contact context",
        "event": "Event context",
        "thread": "Thread context",
        "message": "Message context",
    }.get(kind, "Entity context")
    parts = [base]
    if date_hint:
        parts.append(f"last noted {date_hint}")
    if mention_count > 1:
        parts.append(f"{mention_count} notes")
    if sample_hint:
        parts.append(sample_hint)
    return " | ".join(parts)

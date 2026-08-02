"""Context layer assembler for chat prompts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.data.models import Contact
from app.security.prompt_sanitizer import sanitize_with_detection
from app.services.hot_context_cache import HotContextCacheService
from app.services.warm_cache import WarmCacheService
from app.services.contact_brief import ContactBriefService
from app.services.warm_context_snapshot import build_contact_snapshot, build_profile_snapshot


DEFAULT_ASSISTANT_NAME = "Teeks"
DEFAULT_USER_NAME = "you"
MAX_SESSION_MESSAGES = 10
MAX_STRUCTURED_ITEMS = 15
ALLOWED_TASK_KEYS = {
    "task",
    "goal",
    "constraints",
    "deadline",
    "priority",
    "current_thread_id",
    "current_contact_id",
    "current_email_id",
    "current_event_id",
}

logger = logging.getLogger(__name__)


@dataclass
class ContextLayers:
    instruction: str
    task: Dict[str, Any]
    session: List[Dict[str, Any]]
    contact: Dict[str, Any]
    profile: Dict[str, Any]
    structured: List[Dict[str, Any]]


class ContextAssembler:
    """Builds layered context blocks for chat prompts."""

    def __init__(
        self,
        db: Session,
        hot_cache: HotContextCacheService,
        warm_cache: WarmCacheService,
        tenant_id: str,
        user_id: str,
        session_id: str,
        assistant_name: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> None:
        self.db = db
        self.hot_cache = hot_cache
        self.warm_cache = warm_cache
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id
        self.assistant_name = assistant_name or DEFAULT_ASSISTANT_NAME
        self.user_name = user_name or DEFAULT_USER_NAME

    def build_instruction(self, extra_instructions: str = "") -> str:
        template = _load_instruction_template()
        rendered = template.format(
            assistant_name=self.assistant_name,
            user_name=self.user_name,
        ).strip()
        if extra_instructions:
            return f"{rendered}\n\n{extra_instructions.strip()}"
        return rendered

    def build_session_memory(self) -> List[Dict[str, Any]]:
        state = self.hot_cache.get_session_state(self.tenant_id, self.user_id, self.session_id)
        messages = list(state.get("messages", []))
        return messages[-MAX_SESSION_MESSAGES:]

    def build_layers_with_trace(
        self,
        task_context: Optional[Dict[str, Any]] = None,
        include_task: bool = True,
        include_session: bool = True,
        include_structured: bool = True,
    ) -> Tuple[ContextLayers, Dict[str, Any]]:
        instruction = self.build_instruction()
        task_filtered, raw_task_meta = self._filter_task_context(task_context)
        if not include_task:
            task_filtered = {}
            task_meta = {
                "included_keys": [],
                "dropped_keys": sorted((task_context or {}).keys()),
                "reason": "task_layer_disabled_by_policy",
            }
        else:
            task_meta = raw_task_meta

        session_items = self.build_session_memory() if include_session else []

        snapshot: Dict[str, Any] = {}
        structured: List[Dict[str, Any]] = []
        profile: Dict[str, Any] = {}
        contact_layer: Dict[str, Any] = {}
        structured_reasons: List[Dict[str, Any]] = []
        contact_trace = {
            "included": False,
            "reason": "no_active_contact",
            "contact_id": task_filtered.get("current_contact_id"),
        }
        if include_structured:
            contact_layer, contact_trace = self._build_contact_layer(task_filtered.get("current_contact_id"))
            snapshot = self.warm_cache.get_or_build(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                scope="profile",
                builder=lambda: build_profile_snapshot(self.db, self.user_id),
            )
            profile = snapshot.get("profile") or {}
            structured, structured_reasons = _select_structured_items(snapshot, MAX_STRUCTURED_ITEMS)

        layers = ContextLayers(
            instruction=instruction,
            task=task_filtered,
            session=session_items,
            contact=contact_layer,
            profile=profile,
            structured=structured,
        )

        trace = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "instruction": {
                "included": True,
                "reason": "always_on",
                "template": "backend/prompts/teeks_chat_agent_prompt.md",
            },
            "task": task_meta,
            "session": {
                "included_count": len(session_items),
                "max_count": MAX_SESSION_MESSAGES,
                "reason": "conversation_continuity" if include_session else "session_layer_disabled_by_policy",
            },
            "contact": contact_trace,
            "structured": {
                "included_count": len(structured),
                "max_count": MAX_STRUCTURED_ITEMS,
                "snapshot_scope": "profile",
                "snapshot_source_count": snapshot.get("source_count", 0),
                "profile_present": bool(profile),
                "snapshot_counts_by_type": snapshot.get("counts_by_type", {}),
                "reasons": structured_reasons,
                "policy_enabled": include_structured,
                "reason": "durable_memory_for_personalization" if include_structured else "structured_layer_disabled_by_policy",
            },
        }
        return layers, trace

    def log_context_trace(self, trace: Dict[str, Any], message: str) -> None:
        message_preview = (message or "").replace("\n", " ")[:140]
        logger.info(
            "context_assembly %s",
            json.dumps(
                {
                    "trace": trace,
                    "message": {
                        "length": len(message or ""),
                        "preview": message_preview,
                    },
                },
                default=str,
            ),
        )

    def render_user_prompt(
        self,
        layers: ContextLayers,
        message: str,
        retrieved_context: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        session_lines = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in layers.session]
        retrieved = retrieved_context or []
        return (
            "Respond concisely and actionably. Minimize cognitive load. "
            "Lead with the answer. Do not over-contextualize. Use tools only when needed. "
            "Do not mention internal tools or cache behavior.\n\n"
            f"Task context (ephemeral): {layers.task or {}}\n\n"
            "Session memory (last 10 turns):\n"
            f"{chr(10).join(session_lines) or '[none]'}\n\n"
            "Active contact context:\n"
            f"{layers.contact or '[none]'}\n\n"
            "Shared profile context (EA + executive):\n"
            f"{layers.profile or '[none]'}\n\n"
            "Structured memory (durable):\n"
            f"{layers.structured or '[none]'}\n\n"
            "Retrieved entity context (optional):\n"
            f"{retrieved or '[none]'}\n\n"
            f"User message:\n{message}\n"
        )

    def _filter_task_context(
        self,
        task_context: Optional[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        raw = task_context or {}
        if not raw:
            return {}, {"included_keys": [], "dropped_keys": [], "reason": "no_task_context"}

        included = {k: v for k, v in raw.items() if k in ALLOWED_TASK_KEYS and v is not None}
        dropped = sorted([k for k in raw.keys() if k not in ALLOWED_TASK_KEYS or raw.get(k) is None])
        return included, {
            "included_keys": sorted(list(included.keys())),
            "dropped_keys": dropped,
            "reason": "allowed_ephemeral_keys_only",
        }

    def _build_contact_layer(self, contact_id: Optional[int]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if contact_id is None:
            return {}, {"included": False, "reason": "no_active_contact", "contact_id": None}

        contact = (
            self.db.query(Contact)
            .filter(Contact.user_id == self.user_id, Contact.id == contact_id)
            .first()
        )
        if not contact:
            return {}, {"included": False, "reason": "contact_not_found", "contact_id": contact_id}

        email_norm = (contact.email or "").strip().lower()
        snapshot: Dict[str, Any] = {}
        if email_norm:
            snapshot = self.warm_cache.get_or_build(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                scope=f"contact:{email_norm}",
                builder=lambda: build_contact_snapshot(self.db, self.user_id, email_norm),
            )

        brief_preview = snapshot.get("brief_preview") or {}
        if not brief_preview:
            brief = ContactBriefService(self.db, user_id=self.user_id).get_contact_brief(contact_id, consumer="chat")
            if brief:
                summary = brief.get("summary") or {}
                brief_preview = {
                    "contact_id": contact.id,
                    "headline": summary.get("headline"),
                    "manual_notes": summary.get("manual_notes"),
                    "preferred_tone": summary.get("preferred_tone"),
                    "top_preferences": [item.get("content") for item in (brief.get("preferences") or [])[:3] if item.get("content")],
                    "open_commitments": [item.get("title") for item in (brief.get("commitments") or [])[:3] if item.get("title")],
                    "recent_decisions": [item.get("decision") for item in (brief.get("decisions") or [])[:2] if item.get("decision")],
                    "signals": [item.get("message") for item in (brief.get("signals") or [])[:2] if item.get("message")],
                }

        layer = {
            "contact_id": contact.id,
            "name": self._sanitize_contact_prompt_value(contact.name, field="contact.name", contact_id=contact.id),
            "email": contact.email,
            "role": self._sanitize_contact_prompt_value(contact.role, field="contact.role", contact_id=contact.id),
            "organization": self._sanitize_contact_prompt_value(contact.organization, field="contact.organization", contact_id=contact.id),
            "category": self._sanitize_contact_prompt_value(contact.category, field="contact.category", contact_id=contact.id),
            "headline": self._sanitize_contact_prompt_value(brief_preview.get("headline"), field="brief.headline", contact_id=contact.id),
            "manual_notes": self._sanitize_contact_prompt_value(brief_preview.get("manual_notes"), field="brief.manual_notes", contact_id=contact.id),
            "preferred_tone": self._sanitize_contact_prompt_value(brief_preview.get("preferred_tone"), field="brief.preferred_tone", contact_id=contact.id),
            "top_preferences": self._sanitize_contact_prompt_list(brief_preview.get("top_preferences") or [], field="brief.preference", contact_id=contact.id),
            "open_commitments": self._sanitize_contact_prompt_list(brief_preview.get("open_commitments") or [], field="brief.commitment", contact_id=contact.id),
            "recent_decisions": self._sanitize_contact_prompt_list(brief_preview.get("recent_decisions") or [], field="brief.decision", contact_id=contact.id),
            "signals": self._sanitize_contact_prompt_list(brief_preview.get("signals") or [], field="brief.signal", contact_id=contact.id),
        }
        return layer, {
            "included": True,
            "reason": "active_contact_context",
            "contact_id": contact.id,
            "contact_email": email_norm or None,
            "has_brief_preview": bool(brief_preview),
        }

    def _sanitize_contact_prompt_value(self, value: Any, *, field: str, contact_id: int) -> Optional[str]:
        text = str(value or "")
        if not text:
            return None
        result = sanitize_with_detection(text)
        if result.patterns_detected:
            logger.warning(
                "contact_prompt_layer_sanitized contact_id=%s field=%s patterns=%s",
                contact_id,
                field,
                result.patterns_detected,
            )
        cleaned = " ".join(result.sanitized_text.split()).strip()
        return cleaned or None

    def _sanitize_contact_prompt_list(self, values: List[Any], *, field: str, contact_id: int) -> List[str]:
        cleaned: List[str] = []
        for value in values:
            item = self._sanitize_contact_prompt_value(value, field=field, contact_id=contact_id)
            if item:
                cleaned.append(item)
        return cleaned


def _load_instruction_template() -> str:
    root = Path(__file__).resolve().parents[3]
    prompt_path = root / "prompts" / "teeks_chat_agent_prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "You are {assistant_name}, a personal assistant for {user_name}. Every interaction must feel like a human co-assistant who remembers and acts."


def _select_structured_items(
    snapshot: Dict[str, Any],
    limit: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not snapshot:
        return [], []

    results: List[Dict[str, Any]] = []
    reasons: List[Dict[str, Any]] = []
    seen = set()

    for item in snapshot.get("critical_items", []) or []:
        key = item.get("id") or item.get("content")
        if key in seen:
            continue
        seen.add(key)
        results.append(_compact_item(item))
        reasons.append(_selection_reason(item, source="critical_items", reason="high_importance_first"))
        if len(results) >= limit:
            return results, reasons

    order = ["preference", "commitment", "decision", "insight", "risk"]
    by_type = snapshot.get("by_type", {}) or {}
    for type_key in order:
        items = by_type.get(type_key, [])
        for item in items:
            key = item.get("id") or item.get("content")
            if key in seen:
                continue
            seen.add(key)
            results.append(_compact_item(item))
            reasons.append(_selection_reason(item, source=f"by_type:{type_key}", reason="type_priority"))
            if len(results) >= limit:
                return results, reasons

    return results, reasons


def _compact_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": item.get("type"),
        "content": item.get("content"),
        "entity_type": item.get("entity_type"),
        "entity_id": item.get("entity_id"),
        "created_at": item.get("created_at"),
        "status": item.get("status"),
    }


def _selection_reason(item: Dict[str, Any], source: str, reason: str) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "type": item.get("type"),
        "entity_type": item.get("entity_type"),
        "entity_id": item.get("entity_id"),
        "source": source,
        "reason": reason,
    }

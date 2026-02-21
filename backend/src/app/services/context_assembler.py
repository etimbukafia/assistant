"""Context layer assembler for chat prompts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.hot_context_cache import HotContextCacheService
from app.services.warm_cache import WarmCacheService
from app.services.warm_context_snapshot import build_profile_snapshot


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
        structured_reasons: List[Dict[str, Any]] = []
        if include_structured:
            snapshot = self.warm_cache.get_or_build(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                scope="profile",
                builder=lambda: build_profile_snapshot(self.db, self.user_id),
            )
            structured, structured_reasons = _select_structured_items(snapshot, MAX_STRUCTURED_ITEMS)

        layers = ContextLayers(
            instruction=instruction,
            task=task_filtered,
            session=session_items,
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
            "structured": {
                "included_count": len(structured),
                "max_count": MAX_STRUCTURED_ITEMS,
                "snapshot_scope": "profile",
                "snapshot_source_count": snapshot.get("source_count", 0),
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

    order = ["preferences", "commitment", "decision", "relationships", "insight"]
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
        "importance_level": item.get("importance_level"),
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

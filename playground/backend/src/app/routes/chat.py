"""Playground chat route using Gemini function-calling for context tools."""

from __future__ import annotations

from datetime import datetime
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from google.genai import types as genai_types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.chat.tools import ChatToolRegistry, ToolCall
from app.db import get_db
from app.services.context_assembler import ContextAssembler
from app.services.genai_client import get_client
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.mention_context import MentionContextService
from app.services.warm_cache import get_warm_cache_service
from dotenv import load_dotenv

load_dotenv()


router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)
MAX_AUTO_ACTIONS = int(os.getenv("CHAT_MAX_AUTO_ACTIONS", "5"))
ACTION_TOOL_NAMES = {
    "draft_email",
    "generate_meeting_brief",
    "generate_thread_intelligence",
}


SYSTEM_CONTEXT_TOOL_USAGE = """
You are Teeks, a personal assistant.

Context Tool Usage:
You have tools to retrieve user context from memory. Use them judiciously.

ALWAYS fetch context when:
- The user references a specific person, thread, or past decision.
- You need to draft a reply (fetch tone preferences + contact history).
- The user asks about commitments, deadlines, or relationship history.

NEVER fetch context when:
- Greeting or small talk.
- The user's message is self-contained.
- You already have relevant context in this conversation.

When unsure, err toward NOT fetching. Speed matters.

Response Style:
- Minimize cognitive load.
- Start with the direct answer or next action.
- Keep responses brief and high-signal.
- No over-contextualization unless the user asks for detail.
- Use short bullets when listing steps or options.

Action Tools:
- Use `draft_email` when user asks to draft/rewrite an email reply.
- Use `generate_meeting_brief` when user asks for meeting prep/briefing.

Multi-Action Behavior:
- If a request includes multiple actions, decompose and prioritize.
- Execute up to 5 actions in the first pass.
- Do not announce batching before execution.
- After execution, keep wording natural and human.
- Never use mechanical terms like "queued", "pipeline", or "batch".
- Use real action titles and quote each title in your summary.
""".strip()


ENTITY_TYPE_TOKENS = {
    "contact",
    "contacts",
    "thread",
    "threads",
    "message",
    "messages",
    "event",
    "events",
    "meeting",
    "meetings",
    "email",
    "emails",
}
CONTEXT_TYPE_TOKENS = {
    "decision",
    "decisions",
    "commitment",
    "commitments",
    "preference",
    "preferences",
    "insight",
    "insights",
    "relationship",
    "relationships",
    "risk",
    "risks",
}
ENTITY_STATE_KEYS = {
    "current_thread_id",
    "current_contact_id",
    "current_email_id",
    "current_event_id",
}
NO_CONTEXT_MESSAGES = {
    "hi",
    "hello",
    "hey",
    "yo",
    "thanks",
    "thank you",
    "ok",
    "okay",
    "got it",
    "sounds good",
    "cool",
    "noted",
}
STRUCTURED_MEMORY_HINT_TOKENS = {
    "draft",
    "reply",
    "tone",
    "schedule",
    "availability",
    "working hours",
    "preferences",
    "preference",
    "style",
    "voice",
    "recap",
    "summary",
    "summarize",
}
ACTION_TOOL_HINT_TOKENS = {
    "draft",
    "reply",
    "email",
    "brief",
    "briefing",
    "agenda",
    "prep",
    "prepare",
    "intelligence",
}
CONTINUE_EXACT_MESSAGES = {
    "continue",
    "proceed",
    "go on",
    "keep going",
    "carry on",
    "next",
    "yes",
    "yeah",
    "yep",
    "sure",
    "ok",
    "okay",
    "do it",
    "please do",
    "implement",
}
CONTINUE_TOKEN_HINTS = {
    "continue",
    "proceed",
    "next",
    "resume",
    "go on",
    "keep going",
    "carry on",
    "implement",
}


class MentionPayload(BaseModel):
    kind: str
    ref: str
    label: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    current_state: Optional[Dict[str, Any]] = None
    detected_entities: Optional[List[str]] = None
    task_context: Optional[Dict[str, Any]] = None
    assistant_name: Optional[str] = None
    user_name: Optional[str] = None
    mentions: Optional[List[MentionPayload]] = None


@router.get("/tools", response_model=List[Dict[str, Any]])
def list_chat_tools(
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
):
    resolved_tenant = tenant_id or tenant_header or "default"
    resolved_user = user_id or "anonymous"
    registry = ChatToolRegistry(db=db, tenant_id=resolved_tenant, user_id=resolved_user, session_id="default")
    return registry.list_definitions_for_prompt()


@router.get("/mentions", response_model=List[Dict[str, str]])
def suggest_mentions(
    q: str = Query(default=""),
    user_id: Optional[str] = Query(default=None),
    tenant_id: Optional[str] = Query(default=None),
    limit: int = Query(default=8, ge=1, le=20),
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
):
    resolved_tenant = tenant_id or tenant_header or "default"
    resolved_user = user_id or "anonymous"
    service = MentionContextService(
        db=db,
        warm_cache=get_warm_cache_service(),
        tenant_id=resolved_tenant,
        user_id=resolved_user,
        session_id="default",
    )
    return service.suggest_mentions(query=q, limit=limit)


def _execute_function_calls(
    registry: ChatToolRegistry,
    function_calls: List[genai_types.FunctionCall],
    remaining_action_budget: int,
) -> tuple[List[Dict[str, Any]], List[genai_types.Content], List[Dict[str, Any]], int]:
    tool_outputs: List[Dict[str, Any]] = []
    tool_contents: List[genai_types.Content] = []
    deferred_actions: List[Dict[str, Any]] = []
    executed_actions = 0

    for fc in function_calls:
        name = (fc.name or "").strip()
        args = dict(fc.args or {})
        if not name:
            continue

        if registry.is_action_tool(name) and executed_actions >= remaining_action_budget:
            output = {
                "name": name,
                "arguments": args,
                "success": False,
                "data": None,
                "error": "deferred_due_to_auto_action_limit",
                "deferred": True,
            }
            tool_outputs.append(output)
            deferred_actions.append(
                {
                    "name": name,
                    "arguments": args,
                    "reason": "auto_action_limit",
                }
            )
            part = genai_types.Part.from_function_response(
                name=name,
                response={
                    "success": False,
                    "data": None,
                    "error": "deferred_due_to_auto_action_limit",
                },
            )
            tool_contents.append(genai_types.Content(role="tool", parts=[part]))
            continue

        result = registry.execute_tool(ToolCall(name=name, arguments=args))
        output = {
            "name": name,
            "arguments": args,
            "success": result.success,
            "data": result.data if result.success else None,
            "error": result.error,
            "deferred": False,
        }
        tool_outputs.append(output)
        if registry.is_action_tool(name):
            executed_actions += 1

        part = genai_types.Part.from_function_response(
            name=name,
            response={
                "success": result.success,
                "data": result.data,
                "error": result.error,
            },
        )
        tool_contents.append(genai_types.Content(role="tool", parts=[part]))

    return tool_outputs, tool_contents, deferred_actions, executed_actions


def _context_types_from_tool_outputs(tool_outputs: List[Dict[str, Any]]) -> List[str]:
    types: List[str] = []
    for item in tool_outputs:
        data = item.get("data") or {}
        if not isinstance(data, dict):
            continue
        entries = data.get("entries")
        if isinstance(entries, list):
            for entry in entries:
                entry_type = (entry or {}).get("type")
                if isinstance(entry_type, str) and entry_type and entry_type not in types:
                    types.append(entry_type)
        context_entries = data.get("context_entries")
        if isinstance(context_entries, list):
            for entry in context_entries:
                entry_type = (entry or {}).get("type")
                if isinstance(entry_type, str) and entry_type and entry_type not in types:
                    types.append(entry_type)
    return types


def _merge_context_types(tool_types: List[str], mention_types: List[str]) -> List[str]:
    output: List[str] = []
    for item in tool_types + mention_types:
        if item not in output:
            output.append(item)
    return output


def _context_types_from_entries(entries: List[Dict[str, Any]]) -> List[str]:
    types: List[str] = []
    for entry in entries or []:
        entry_type = (entry or {}).get("type")
        if isinstance(entry_type, str) and entry_type and entry_type not in types:
            types.append(entry_type)
    return types


def _contains_token(text: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


def _should_enable_layer5(
    request: ChatRequest,
    mentions_payload: List[Dict[str, str]],
    task_context: Dict[str, Any],
) -> Dict[str, Any]:
    message = (request.message or "").lower()
    matched_entity_tokens = [t for t in sorted(ENTITY_TYPE_TOKENS) if _contains_token(message, t)]
    matched_context_tokens = [t for t in sorted(CONTEXT_TYPE_TOKENS) if _contains_token(message, t)]
    has_at_mention = "@" in (request.message or "")
    action_tool_hint = _contains_any_phrase(request.message, ACTION_TOOL_HINT_TOKENS)
    detected_entities = [d for d in (request.detected_entities or []) if str(d).strip()]
    state_entity_keys = [k for k in sorted(ENTITY_STATE_KEYS) if task_context.get(k)]

    reasons: List[str] = []
    if mentions_payload:
        reasons.append("explicit_mentions")
    if has_at_mention:
        reasons.append("at_mention_syntax")
    if matched_entity_tokens:
        reasons.append("entity_type_tokens")
    if matched_context_tokens:
        reasons.append("context_type_tokens")
    if action_tool_hint:
        reasons.append("action_tool_intent")
    if detected_entities:
        reasons.append("detected_entities")
    if state_entity_keys:
        reasons.append("task_state_entity_keys")

    enabled = bool(reasons)
    return {
        "enabled": enabled,
        "reasons": reasons,
        "matched_entity_tokens": matched_entity_tokens,
        "matched_context_tokens": matched_context_tokens,
        "state_entity_keys": state_entity_keys,
        "detected_entities": detected_entities,
    }


def _normalized_message(message: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (message or "").lower()).strip()


def _is_no_context_message(message: str) -> bool:
    normalized = " ".join(_normalized_message(message).split())
    return normalized in NO_CONTEXT_MESSAGES


def _contains_any_phrase(message: str, phrases: set[str]) -> bool:
    lowered = (message or "").lower()
    return any(phrase in lowered for phrase in phrases)


def _is_continue_intent_by_rules(message: str) -> Optional[bool]:
    normalized = " ".join(_normalized_message(message).split())
    if not normalized:
        return False
    if normalized in CONTINUE_EXACT_MESSAGES:
        return True

    tokens = normalized.split()
    if any(token in CONTINUE_TOKEN_HINTS for token in tokens):
        return True

    if len(tokens) <= 4 and normalized in {"sounds good", "got it"}:
        return True

    if len(tokens) > 7:
        return False

    return None


def _should_continue_deferred_actions(message: str, has_deferred: bool) -> Optional[bool]:
    if not has_deferred:
        return False
    rules = _is_continue_intent_by_rules(message)
    return rules


def _execute_deferred_actions(
    registry: ChatToolRegistry,
    deferred_actions: List[Dict[str, Any]],
    action_budget: int,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    executed_outputs: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = []
    executed_count = 0

    for item in deferred_actions:
        name = (item.get("name") or "").strip()
        arguments = item.get("arguments") or {}

        if not name:
            continue
        if not registry.is_action_tool(name):
            continue
        if executed_count >= action_budget:
            remaining.append({"name": name, "arguments": arguments, "reason": "auto_action_limit"})
            continue

        result = registry.execute_tool(ToolCall(name=name, arguments=arguments))
        executed_outputs.append(
            {
                "name": name,
                "arguments": arguments,
                "success": result.success,
                "data": result.data if result.success else None,
                "error": result.error,
                "deferred": False,
                "continued": True,
            }
        )
        executed_count += 1

    return executed_outputs, remaining, executed_count


def _merge_deferred_actions(
    existing: List[Dict[str, Any]],
    new: List[Dict[str, Any]],
    max_items: int = 20,
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()
    for item in (existing or []) + (new or []):
        name = (item.get("name") or "").strip()
        arguments = item.get("arguments") or {}
        try:
            arg_key = json.dumps(arguments, sort_keys=True)
        except Exception:
            arg_key = str(arguments)
        key = f"{name}:{arg_key}"
        if not name or key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "name": name,
                "arguments": arguments,
                "reason": item.get("reason") or "auto_action_limit",
            }
        )
        if len(merged) >= max_items:
            break
    return merged


def _build_layer_assembly_policy(
    request: ChatRequest,
    task_context: Dict[str, Any],
    layer5_gate: Dict[str, Any],
) -> Dict[str, Any]:
    no_context = _is_no_context_message(request.message)
    layer5_enabled = bool(layer5_gate.get("enabled"))
    has_task_payload = bool(task_context)
    structured_hint = _contains_any_phrase(request.message, STRUCTURED_MEMORY_HINT_TOKENS)

    include_task = has_task_payload and not no_context
    include_session = (not no_context) or layer5_enabled
    include_structured = layer5_enabled or (structured_hint and not no_context) or has_task_payload

    reasons: List[str] = []
    if no_context:
        reasons.append("smalltalk_or_ack")
    if layer5_enabled:
        reasons.append("layer5_enabled")
    if structured_hint and not layer5_enabled:
        reasons.append("structured_hint_tokens")
    if has_task_payload:
        reasons.append("task_payload_present")

    return {
        "include_task": include_task,
        "include_session": include_session,
        "include_structured": include_structured,
        "no_context_message": no_context,
        "reasons": reasons,
    }


def _empty_mention_prefetch(mentions_payload: List[Dict[str, str]], reason: str) -> Dict[str, Any]:
    return {
        "mentions_received": len(mentions_payload),
        "resolved_mentions": [],
        "unresolved_mentions": [],
        "entities": [],
        "selected_entries": [],
        "selected_count": 0,
        "dropped_count": 0,
        "context_types": [],
        "budgets": {
            "max_items_per_entity": 5,
            "max_items_total": 25,
            "max_mentions_per_message": 8,
        },
        "skipped": True,
        "skip_reason": reason,
    }


def _normalize_action_title(value: Optional[str]) -> str:
    text = " ".join((value or "").replace('"', "").split())
    return text.strip()


def _action_title_from_output(item: Dict[str, Any]) -> str:
    name = (item.get("name") or "").strip()
    args = item.get("arguments") or {}
    data = item.get("data") or {}

    if name == "draft_email":
        subject = _normalize_action_title(data.get("subject") or args.get("subject"))
        recipient = _normalize_action_title(data.get("recipient") or args.get("recipient"))
        if subject and recipient:
            return f"draft email for {subject} to {recipient}"
        if subject:
            return f"draft email for {subject}"
        return "draft email"

    if name == "generate_meeting_brief":
        subject = _normalize_action_title(data.get("meeting_subject") or args.get("meeting_subject"))
        event_id = _normalize_action_title(data.get("event_id") or args.get("event_id"))
        if subject:
            return f"meeting brief for {subject}"
        if event_id:
            return f"meeting brief for {event_id}"
        return "meeting brief"

    if name == "generate_thread_intelligence":
        thread_id = _normalize_action_title(data.get("thread_id") or args.get("thread_id") or args.get("thread"))
        if thread_id:
            return f"thread intelligence for {thread_id}"
        return "thread intelligence"

    return _normalize_action_title(name) or "action"


def _format_action_followup(
    reply: str,
    tool_outputs: List[Dict[str, Any]],
    deferred_actions: List[Dict[str, Any]],
) -> str:
    completed: List[str] = []
    failed: List[str] = []
    deferred: List[str] = []

    def _append_unique(bucket: List[str], value: str) -> None:
        if value and value not in bucket:
            bucket.append(value)

    for item in tool_outputs:
        name = (item.get("name") or "").strip()
        if name not in ACTION_TOOL_NAMES:
            continue
        label = _action_title_from_output(item)
        if item.get("deferred"):
            _append_unique(deferred, label)
            continue
        if item.get("success"):
            _append_unique(completed, label)
            continue
        error = _normalize_action_title(item.get("error")) or "couldn't complete"
        _append_unique(failed, f"{label} ({error})")

    for item in deferred_actions:
        name = (item.get("name") or "").strip()
        if name not in ACTION_TOOL_NAMES:
            continue
        label = _action_title_from_output(item)
        _append_unique(deferred, label)

    clauses: List[str] = []
    if completed:
        done = ", ".join([f'"{item}"' for item in completed])
        clauses.append(f"I've completed {done}.")
    if failed:
        failed_text = ", ".join([f'"{item}"' for item in failed])
        clauses.append(f'I hit an issue with {failed_text}.')
    if deferred:
        deferred_text = ", ".join([f'"{item}"' for item in deferred])
        clauses.append(f"I can continue with {deferred_text} if you'd like.")

    if not clauses:
        return reply

    base = (reply or "").strip()
    if base:
        if base[-1] not in {".", "!", "?"}:
            base = f"{base}."
        return f"{base} {' '.join(clauses)}"
    return " ".join(clauses)


def _friendly_llm_error(request: ChatRequest) -> str:
    message = (request.message or "").lower()
    if _contains_any_phrase(message, {"draft", "reply", "email"}):
        return "I can't draft a reply right now."
    if _contains_any_phrase(message, {"brief", "prep", "meeting"}):
        return "I can't prepare a meeting brief right now."
    if _contains_any_phrase(message, {"recap", "summary", "decisions", "commitments"}):
        return "I can't summarize that right now."
    return "I'm having trouble reaching the model right now."


def _fallback_actions_without_llm(
    request: ChatRequest,
    registry: ChatToolRegistry,
    mentions_payload: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    message = (request.message or "").lower()
    outputs: List[Dict[str, Any]] = []

    mention_by_kind: Dict[str, List[Dict[str, str]]] = {"contact": [], "thread": [], "event": [], "message": []}
    for mention in mentions_payload:
        kind = (mention.get("kind") or "").strip().lower()
        if kind in mention_by_kind:
            mention_by_kind[kind].append(mention)

    if "draft" in message and ("reply" in message or "email" in message):
        thread = mention_by_kind["thread"][0] if mention_by_kind["thread"] else None
        contact = mention_by_kind["contact"][0] if mention_by_kind["contact"] else None
        source_message = mention_by_kind["message"][0] if mention_by_kind["message"] else None
        subject_hint = (thread or {}).get("label") or (source_message or {}).get("label") or "Draft reply"
        args = {
            "subject": subject_hint,
            "intent": request.message,
            "recipient": (contact or {}).get("ref"),
            "thread_id": (thread or {}).get("ref"),
            "message_id": (source_message or {}).get("ref"),
            "thread": (thread or {}).get("label"),
            "message": (source_message or {}).get("label"),
        }
        result = registry.execute_tool(ToolCall(name="draft_email", arguments=args))
        outputs.append(
            {
                "name": "draft_email",
                "arguments": args,
                "success": result.success,
                "data": result.data if result.success else None,
                "error": result.error,
                "deferred": False,
            }
        )

    if any(token in message for token in {"meeting brief", "brief", "prep", "prepare"}) and mention_by_kind["event"]:
        event = mention_by_kind["event"][0]
        args = {
            "event_id": event.get("ref"),
            "meeting_subject": event.get("label"),
            "include_recent_context": True,
        }
        result = registry.execute_tool(ToolCall(name="generate_meeting_brief", arguments=args))
        outputs.append(
            {
                "name": "generate_meeting_brief",
                "arguments": args,
                "success": result.success,
                "data": result.data if result.success else None,
                "error": result.error,
                "deferred": False,
            }
        )

    return outputs


@router.post("", response_model=Dict[str, Any])
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    tenant_header: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    tenant_id = request.tenant_id or tenant_header or "default"
    user_id = request.user_id or "anonymous"
    session_id = request.session_id or "default"
    task_context = request.task_context or request.current_state or {}
    logger.info(
        "chat_request tenant=%s user=%s session=%s message_len=%s mentions=%s",
        tenant_id,
        user_id,
        session_id,
        len(request.message or ""),
        len(request.mentions or []),
    )

    hot_cache = get_hot_context_cache_service()
    hot_cache.append_message(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        role="user",
        content=request.message,
    )
    pending_deferred_actions = hot_cache.get_deferred_actions(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
    )
    continue_deferred = _should_continue_deferred_actions(
        message=request.message,
        has_deferred=bool(pending_deferred_actions),
    )

    registry = ChatToolRegistry(db=db, tenant_id=tenant_id, user_id=user_id, session_id=session_id)
    if continue_deferred and pending_deferred_actions:
        continued_outputs, remaining_deferred, executed_count = _execute_deferred_actions(
            registry=registry,
            deferred_actions=pending_deferred_actions,
            action_budget=MAX_AUTO_ACTIONS,
        )
        persisted_deferred = hot_cache.set_deferred_actions(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            actions=remaining_deferred,
            max_items=20,
        )
        reply = _format_action_followup(
            reply="",
            tool_outputs=continued_outputs,
            deferred_actions=persisted_deferred,
        ) or "Ready. What should I handle next?"
        hot_cache.append_message(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=reply,
        )

        context_types = _context_types_from_tool_outputs(continued_outputs)
        use_context = bool(continued_outputs)
        context_level = "full" if len(continued_outputs) >= 2 else ("light" if continued_outputs else "none")
        mention_prefetch = _empty_mention_prefetch([], reason="continuation_turn")

        logger.info(
            "chat_continued_deferred tenant=%s user=%s session=%s executed_action_count=%s deferred_remaining=%s",
            tenant_id,
            user_id,
            session_id,
            executed_count,
            len(persisted_deferred),
        )

        return {
            "reply": reply,
            "session_id": session_id,
            "gate": {
                "use_context": use_context,
                "context_level": context_level,
                "context_types": context_types,
                "reason": "continued deferred actions",
            },
            "tool_calls": [
                {"name": t.get("name"), "arguments": t.get("arguments", {})}
                for t in continued_outputs
            ],
            "tool_outputs": continued_outputs,
            "deferred_actions": persisted_deferred,
            "has_more_actions": bool(persisted_deferred),
            "mention_prefetch": mention_prefetch,
            "timestamp": datetime.utcnow().isoformat(),
        }

    if continue_deferred is None and pending_deferred_actions:
        reply = "Do you want me to continue the remaining items, or handle this new request first?"
        hot_cache.append_message(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=reply,
        )
        mention_prefetch = _empty_mention_prefetch([], reason="continuation_ambiguity")
        return {
            "reply": reply,
            "session_id": session_id,
            "gate": {
                "use_context": False,
                "context_level": "none",
                "context_types": [],
                "reason": "continuation intent ambiguous",
            },
            "tool_calls": [],
            "tool_outputs": [],
            "deferred_actions": pending_deferred_actions,
            "has_more_actions": bool(pending_deferred_actions),
            "mention_prefetch": mention_prefetch,
            "timestamp": datetime.utcnow().isoformat(),
        }

    warm_cache = get_warm_cache_service()
    mention_service = MentionContextService(
        db=db,
        warm_cache=warm_cache,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
    )
    mentions_payload = [m.dict() for m in (request.mentions or [])]
    layer5_gate = _should_enable_layer5(
        request=request,
        mentions_payload=mentions_payload,
        task_context=task_context,
    )
    assembly_policy = _build_layer_assembly_policy(
        request=request,
        task_context=task_context,
        layer5_gate=layer5_gate,
    )
    if layer5_gate["enabled"]:
        mention_prefetch = mention_service.prefetch_for_mentions(mentions_payload)
    else:
        mention_prefetch = _empty_mention_prefetch(
            mentions_payload,
            reason="no_entity_or_context_reference",
        )
    mention_entries = mention_prefetch.get("selected_entries", [])
    if mention_entries:
        hot_cache.merge_context_entries(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            entries=mention_entries,
        )

    assembler = ContextAssembler(
        db=db,
        hot_cache=hot_cache,
        warm_cache=warm_cache,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        assistant_name=request.assistant_name,
        user_name=request.user_name,
    )
    layers, context_trace = assembler.build_layers_with_trace(
        task_context=task_context,
        include_task=assembly_policy["include_task"],
        include_session=assembly_policy["include_session"],
        include_structured=assembly_policy["include_structured"],
    )
    context_trace["assembly_policy"] = assembly_policy
    context_trace["retrieval"] = {
        "layer5_enabled": layer5_gate["enabled"],
        "layer5_reasons": layer5_gate["reasons"],
        "matched_entity_tokens": layer5_gate["matched_entity_tokens"],
        "matched_context_tokens": layer5_gate["matched_context_tokens"],
        "state_entity_keys": layer5_gate["state_entity_keys"],
        "detected_entities": layer5_gate["detected_entities"],
        "mentions_received": mention_prefetch.get("mentions_received", 0),
        "resolved_mentions": mention_prefetch.get("resolved_mentions", []),
        "unresolved_mentions": mention_prefetch.get("unresolved_mentions", []),
        "selected_count": mention_prefetch.get("selected_count", 0),
    }
    assembler.log_context_trace(context_trace, request.message)

    tool_outputs: List[Dict[str, Any]] = []
    deferred_actions: List[Dict[str, Any]] = []
    executed_action_count = 0
    llm_error_message: Optional[str] = None

    reply = "Ready. What should I run?"

    client = get_client()
    if client is not None:
        model_name = "gemini-2.5-flash-lite"
        extra_instruction = SYSTEM_CONTEXT_TOOL_USAGE
        if not layer5_gate["enabled"]:
            extra_instruction = (
                f"{SYSTEM_CONTEXT_TOOL_USAGE}\n\n"
                "Layer 5 deep retrieval is disabled for this turn because the request does not reference "
                "an entity type or context type. Do not call context tools."
            )
        config_kwargs: Dict[str, Any] = {
            "system_instruction": assembler.build_instruction(extra_instruction),
            "max_output_tokens": 220,
            "automatic_function_calling": genai_types.AutomaticFunctionCallingConfig(disable=True),
        }
        if layer5_gate["enabled"]:
            config_kwargs["tools"] = [
                genai_types.Tool(function_declarations=registry.list_function_declarations())
            ]
        config = genai_types.GenerateContentConfig(**config_kwargs)

        user_prompt = assembler.render_user_prompt(
            layers,
            request.message,
            retrieved_context=mention_entries,
        )
        contents: List[genai_types.Content] = [
            genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=user_prompt)])
        ]

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )

            max_tool_rounds = 4
            rounds = 0
            while rounds < max_tool_rounds:
                function_calls = list(response.function_calls or []) if layer5_gate["enabled"] else []
                if not function_calls:
                    break

                # Keep model turn in conversation before tool responses.
                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)
                elif response.text:
                    contents.append(
                        genai_types.Content(
                            role="model",
                            parts=[genai_types.Part.from_text(text=response.text)],
                        )
                    )

                remaining_budget = max(0, MAX_AUTO_ACTIONS - executed_action_count)
                current_outputs, tool_contents, deferred_now, executed_now = _execute_function_calls(
                    registry,
                    function_calls,
                    remaining_action_budget=remaining_budget,
                )
                tool_outputs.extend(current_outputs)
                deferred_actions.extend(deferred_now)
                executed_action_count += executed_now
                contents.extend(tool_contents)

                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                rounds += 1

            if response.text:
                reply = response.text.strip()
        except Exception as exc:
            logger.exception(
                "chat_generation_failed tenant=%s user=%s session=%s",
                tenant_id,
                user_id,
                session_id,
            )
            llm_error_message = _friendly_llm_error(request)
            fallback_outputs = _fallback_actions_without_llm(
                request=request,
                registry=registry,
                mentions_payload=mentions_payload,
            )
            if fallback_outputs:
                tool_outputs.extend(fallback_outputs)
                reply = ""
    else:
        logger.warning(
            "chat_generation_skipped_missing_api_key tenant=%s user=%s session=%s",
            tenant_id,
            user_id,
            session_id,
        )
        tool_outputs = _fallback_actions_without_llm(
            request=request,
            registry=registry,
            mentions_payload=mentions_payload,
        )
        if tool_outputs:
            reply = ""
        elif _is_no_context_message(request.message):
            reply = "Hi. What should I handle?"
        else:
            reply = "I can run this, but language generation is unavailable right now. Set GOOGLE_API_KEY to enable full chat."

    if request.message.strip().lower() in {"hi", "hello", "hey"} and not tool_outputs and not mention_entries:
        reply = "Hi. What should I handle?"

    if not tool_outputs and not mention_entries and llm_error_message:
        reply = llm_error_message

    persisted_deferred_actions = hot_cache.set_deferred_actions(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        actions=_merge_deferred_actions(pending_deferred_actions, deferred_actions, max_items=20),
        max_items=20,
    )

    if (tool_outputs or deferred_actions) and reply == "Ready. What should I run?":
        reply = ""

    action_outputs_this_turn = [
        item for item in tool_outputs if (item.get("name") in ACTION_TOOL_NAMES and not item.get("deferred"))
    ]
    followup_deferred = persisted_deferred_actions if action_outputs_this_turn else deferred_actions
    reply = _format_action_followup(
        reply=reply,
        tool_outputs=tool_outputs,
        deferred_actions=followup_deferred,
    )

    hot_cache.append_message(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        role="assistant",
        content=reply,
    )

    tool_types = _context_types_from_tool_outputs(tool_outputs)
    mention_types = _context_types_from_entries(mention_entries)
    context_types = _merge_context_types(tool_types, mention_types)
    use_context = bool(tool_outputs or mention_entries)
    context_level = "none"
    if use_context:
        if len(tool_outputs) >= 2 or len(mention_entries) >= 10:
            context_level = "full"
        else:
            context_level = "light"

    logger.info(
        "chat_context_usage tenant=%s user=%s session=%s layer5_enabled=%s include_structured=%s include_session=%s context_level=%s tool_calls=%s mention_resolved=%s context_types=%s layer5_reasons=%s assembly_reasons=%s executed_action_count=%s deferred_action_count=%s",
        tenant_id,
        user_id,
        session_id,
        layer5_gate["enabled"],
        assembly_policy["include_structured"],
        assembly_policy["include_session"],
        context_level,
        [t.get("name") for t in tool_outputs],
        len(mention_prefetch.get("resolved_mentions", [])),
        context_types,
        layer5_gate["reasons"],
        assembly_policy["reasons"],
        executed_action_count,
        len(persisted_deferred_actions),
    )
    logger.info(
        "chat_response tenant=%s user=%s session=%s reply_len=%s",
        tenant_id,
        user_id,
        session_id,
        len(reply or ""),
    )

    return {
        "reply": reply,
        "session_id": session_id,
        "gate": {
            "use_context": use_context,
            "context_level": context_level,
            "context_types": context_types,
            "reason": (
                "Layer5 enabled: "
                + (", ".join(layer5_gate["reasons"]) if layer5_gate["reasons"] else "none")
            ),
        },
        "tool_calls": [
            {"name": t.get("name"), "arguments": t.get("arguments", {})}
            for t in tool_outputs
        ],
        "tool_outputs": tool_outputs,
        "deferred_actions": persisted_deferred_actions,
        "has_more_actions": bool(persisted_deferred_actions),
        "mention_prefetch": mention_prefetch,
        "timestamp": datetime.utcnow().isoformat(),
    }

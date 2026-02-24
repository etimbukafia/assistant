"""
Tool family policy and turn-level gating for chat orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Set

from .planner_models import ToolFamily


NO_TOOL_MESSAGES = {
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank you",
    "ok",
    "okay",
    "got it",
    "sounds good",
    "noted",
}


ACTION_HINT_TOKENS = {
    "draft",
    "reply",
    "respond",
    "compose",
    "write",
    "prep",
    "brief",
    "schedule",
    "reschedule",
    "book",
    "plan",
    "summarize",
    "recap",
    "extract",
    "search",
    "find",
}

# Multi-word phrases that signal a context-retrieval question about a mentioned entity.
# Single-word tokens (e.g. "what", "how") are intentionally excluded to avoid false
# positives like "@Alice what is the capital of France?".
# These unlock READ_CONTEXT tools only - not artifact generation or writes.
CONTEXT_QUERY_PHRASES = {
    "what changed",
    "what happened",
    "what's new",
    "whats new",
    "any updates",
    "any news",
    "anything new",
    "latest on",
    "catch me up",
    "fill me in",
    "tell me about",
    "update me on",
    "status of",
    "status on",
    "how is",
    "how has",
    "what do you know",
    "what do we know",
    "what have",
    "anything on",
    "anything about",
    "remind me about",
    "what was decided",
    "what did",
    "what were",
}

TASK_WRITE_HINT_TOKENS = {
    "create task",
    "add task",
    "new task",
    "update task",
    "close task",
    "complete task",
    "mark done",
}


TOOL_FAMILY_BY_NAME = {
    # Read context
    "search_emails": ToolFamily.READ_CONTEXT,
    "search_tasks": ToolFamily.READ_CONTEXT,
    "get_calendar": ToolFamily.READ_CONTEXT,
    "get_email_details": ToolFamily.READ_CONTEXT,
    "get_thread_summary": ToolFamily.READ_CONTEXT,
    "get_contact_context": ToolFamily.READ_CONTEXT,
    "get_thread_history": ToolFamily.READ_CONTEXT,
    "get_user_preferences": ToolFamily.READ_CONTEXT,
    "get_event_context": ToolFamily.READ_CONTEXT,
    "get_message_context": ToolFamily.READ_CONTEXT,
    "get_task_context": ToolFamily.READ_CONTEXT,
    "search_vault": ToolFamily.READ_CONTEXT,
    "get_vault_note": ToolFamily.READ_CONTEXT,
    # Artifact generation
    "draft_email": ToolFamily.GENERATE_ARTIFACT,
    "generate_meeting_brief": ToolFamily.GENERATE_ARTIFACT,
    # Task writes
    "create_task": ToolFamily.WRITE_TASK,
    # External actions (future/approval gated)
    "draft_reply": ToolFamily.EXTERNAL_ACTION,
    "add_to_calendar": ToolFamily.EXTERNAL_ACTION,
    "cancel_meeting": ToolFamily.EXTERNAL_ACTION,
    "reschedule_meeting": ToolFamily.EXTERNAL_ACTION,
    # Not allowed in chat write path per current product decision.
    "update_principal_memory": ToolFamily.EXTERNAL_ACTION,
}


@dataclass(frozen=True)
class ToolPolicyDecision:
    tools_allowed: bool
    allowed_families: Set[ToolFamily] = field(default_factory=set)
    reason: str = ""

    def allows_family(self, family: ToolFamily) -> bool:
        return self.tools_allowed and family in self.allowed_families

    def allows_tool(self, tool_name: str, family_map: Optional[Dict[str, ToolFamily]] = None) -> bool:
        mapping = family_map or TOOL_FAMILY_BY_NAME
        family = mapping.get((tool_name or "").strip())
        return bool(family and self.allows_family(family))


class ToolPolicyEngine:
    """
    Fast deterministic gate for tool usage.
    """

    def __init__(self, family_map: Optional[Dict[str, ToolFamily]] = None):
        self.family_map = family_map or TOOL_FAMILY_BY_NAME

    def decide(self, user_message: str, mention_context: Optional[Dict] = None) -> ToolPolicyDecision:
        text = " ".join((user_message or "").lower().split())
        entities = (mention_context or {}).get("entities") or []
        has_mentions = bool(entities)
        has_action_hint = any(token in text for token in ACTION_HINT_TOKENS)
        has_task_write_hint = any(token in text for token in TASK_WRITE_HINT_TOKENS)
        has_context_query = any(phrase in text for phrase in CONTEXT_QUERY_PHRASES)

        if text in NO_TOOL_MESSAGES:
            return ToolPolicyDecision(
                tools_allowed=False,
                allowed_families=set(),
                reason="smalltalk_or_ack",
            )

        if not has_mentions:
            return ToolPolicyDecision(
                tools_allowed=False,
                allowed_families=set(),
                reason="requires_explicit_mentions",
            )
        
        # Context-query phrases (e.g. "what changed", "any updates") with a mention
        # unlock read-only tools but not artifact generation or write tools.
        if not has_action_hint and not has_task_write_hint:
            if has_context_query:
                return ToolPolicyDecision(
                    tools_allowed=True,
                    allowed_families={ToolFamily.READ_CONTEXT},
                    reason="context_query_with_mention",
                )
            return ToolPolicyDecision(
                tools_allowed=False,
                allowed_families=set(),
                reason="mentions_without_action_intent",
            )

        families: Set[ToolFamily] = {ToolFamily.READ_CONTEXT, ToolFamily.GENERATE_ARTIFACT}
        if has_task_write_hint:
            families.add(ToolFamily.WRITE_TASK)

        return ToolPolicyDecision(
            tools_allowed=True,
            allowed_families=families,
            reason="mentions_and_action_intent",
        )

    def filter_tools(self, tool_names: Iterable[str], decision: ToolPolicyDecision) -> Set[str]:
        if not decision.tools_allowed:
            return set()
        return {name for name in tool_names if decision.allows_tool(name, self.family_map)}



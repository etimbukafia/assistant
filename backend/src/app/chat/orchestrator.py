"""
Chat Orchestrator

Main orchestration layer for AI Chat.
Routes messages through LLM, executes tools, manages state.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import uuid
import hashlib
import json
import logging
import os
import re
import time

from google.genai import types as genai_types
from sqlalchemy.orm import Session

from app.data.models import ChatSession, ChatPendingAction
from .context import ChatContextManager, ConversationState
from .tools import ChatToolRegistry, ToolResult
from app.services.genai_client import get_genai_client
from app.services.context_assembler import ContextAssembler
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.telemetry_writer import get_telemetry_writer
from app.services.warm_cache import get_warm_cache_service
from app.security.prompt_sanitizer import detect_injection_patterns
from app.security.security_logger import log_injection_attempt
from .dag_executor import DependencyAwareExecutor, NodeRunStatus
from .planner_parser import PlanParseError, parse_execution_plan
from .tool_policy import TOOL_FAMILY_BY_NAME, ToolPolicyDecision, ToolPolicyEngine

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4
MAX_ACTION_TOOLS_PER_TURN = 5
MAX_DEFERRED_ACTIONS = 20
ACTION_TOOL_NAMES = {"draft_email", "generate_meeting_brief"}
NO_CONTEXT_MESSAGES = {
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
STRUCTURED_HINT_TOKENS = {
    "decision",
    "decisions",
    "commitment",
    "commitments",
    "risk",
    "risks",
    "relationship",
    "relationships",
    "remember",
    "recap",
    "summary",
    "what changed",
    "tone",
    "preference",
    "preferences",
}
DEEP_DETAIL_HINTS = {
    "detailed",
    "detail",
    "comprehensive",
    "thorough",
    "in-depth",
    "in depth",
    "full",
    "complete",
    "step by step",
}
SHORT_DETAIL_HINTS = {
    "short",
    "brief",
    "quick",
    "one line",
    "concise",
}
CHAT_METRICS_SAMPLE_RATE = max(0.0, min(1.0, float(os.getenv("CHAT_METRICS_SAMPLE_RATE", "1.0"))))
CHAT_METRICS_PROMPT_MAX_MESSAGES = max(1, int(os.getenv("CHAT_METRICS_PROMPT_MAX_MESSAGES", "6")))
CHAT_METRICS_PROMPT_MAX_TOTAL_CHARS = max(512, int(os.getenv("CHAT_METRICS_PROMPT_MAX_TOTAL_CHARS", "4096")))
CHAT_METRICS_PROMPT_MAX_CONTENT_CHARS = max(120, int(os.getenv("CHAT_METRICS_PROMPT_MAX_CONTENT_CHARS", "420")))

# Module-level cached LLM orchestrator (avoids re-init per request)
_chat_llm = None


def _get_chat_llm():
    """Get or create a cached LLM orchestrator for chat."""
    global _chat_llm
    if _chat_llm is None:
        from core.llm.orchestrator import LLMOrchestrator
        from core.llm.config import LLMConfig
        _chat_llm = LLMOrchestrator(config=LLMConfig.for_chat())
    return _chat_llm

# Prompts directory (backend/prompts/)
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"

# Prompt template cache (loaded once per process)
_prompt_cache: Dict[str, str] = {}


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory (cached)."""
    if name not in _prompt_cache:
        prompt_path = PROMPTS_DIR / f"{name}.md"
        try:
            _prompt_cache[name] = prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_path}")
            _prompt_cache[name] = ""
    return _prompt_cache[name]


_PLANNER_HIDDEN_TOOLS = {
    "get_contact_context",
    "get_thread_history",
    "get_user_preferences",
    "get_event_context",
    "get_message_context",
    "get_task_context",
}


# =========================================================================
# Mode Configuration
# =========================================================================

@dataclass
class ModeConfig:
    """Resolved configuration for a chat mode. No branching needed downstream."""
    system_prompt: str
    context_type: str
    tools: List[Dict[str, Any]] = field(default_factory=list)
    use_tools: bool = False


@dataclass
class ResponseProfile:
    """Adaptive output profile selected per user turn."""
    task_type: str
    artifact: str
    depth: str
    format_style: str
    max_output_tokens: int
    retry_max_output_tokens: int
    enable_richness_retry: bool


def resolve_mode(
    session_type: str,
    assistant_name: str,
    user_name: Optional[str],
    context: str,
    tool_registry: ChatToolRegistry,
) -> ModeConfig:
    """
    Resolve all mode-specific config upfront.

    Returns a ModeConfig that the orchestrator can use without
    checking session_type again.
    """
    # Identity preamble — tells the LLM its name and who it's talking to
    identity = f"Your name is {assistant_name}."
    if user_name:
        identity += f" You are speaking with {user_name}."

    if session_type == "reflection":
        base_prompt = _load_prompt("chat_reflection")
        return ModeConfig(
            system_prompt=f"{identity}\n\n{base_prompt}\n\n## Current Context\n{context}",
            context_type="task_review",
            tools=[],
            use_tools=False,
        )

    # Action / command mode
    base_prompt = _load_prompt("chat_system").format(
        assistant_name=assistant_name,
        user_name=user_name or "the user",
    )
    tool_names = ", ".join(tool_registry._tools.keys())
    tools = tool_registry.get_tool_definitions()
    return ModeConfig(
        system_prompt=f"{identity}\n\n{base_prompt}\n\n## Current Context\n{context}\n\nAvailable tools: {tool_names}",
        context_type="drafting",
        tools=tools,
        use_tools=True,
    )


# =========================================================================
# Orchestrator
# =========================================================================

class ChatOrchestrator:
    """
    Orchestrates chat conversations.

    Responsibilities:
    - Build prompts with context
    - Route to LLM
    - Execute tool calls
    - Create pending actions for approval-gated tools
    - Persist state after each turn
    """

    def __init__(
        self,
        db: Session,
        user_id: str,
        assistant_name: str = "Teeks",
        user_name: Optional[str] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.assistant_name = assistant_name
        self.user_name = user_name
        self.context_manager = ChatContextManager(db, user_id)
        self.tool_registry = ChatToolRegistry(db, user_id)
        self.tool_policy = ToolPolicyEngine()

    def _release_db_connection(self) -> None:
        """
        Release any checked-out DB connection before long LLM work.

        We only use rollback here to end implicit read transactions and
        return the connection to the pool. This keeps DB access short and
        avoids holding connections while waiting on LLMs.
        """
        try:
            if self.db.in_transaction():
                self.db.rollback()
        except Exception:
            logger.debug("chat_db_release_failed", exc_info=True)

    async def process_message(
        self,
        session: ChatSession,
        user_message: str,
        mention_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and generate a response.

        Returns:
            Dict with 'response', 'pending_actions', 'state_updates'
        """
        return await self._process_message_internal(session, user_message, mention_context=mention_context or {})

    async def _process_message_internal(
        self,
        session: ChatSession,
        user_message: str,
        mention_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal message processing with full error context."""
        orchestrator_started = time.perf_counter()
        injection_patterns = detect_injection_patterns(user_message)
        if injection_patterns:
            log_injection_attempt(
                user_id=self.user_id,
                source="user_message",
                pattern_matched=", ".join(injection_patterns),
                content_preview=user_message[:100]
            )

        state = self.context_manager.get_session_state(session)
        history = self.context_manager.get_recent_messages(session.id)

        context = self.context_manager.build_prompt_context(
            session=session,
            state=state,
            context_type="drafting" if session.session_type == "command" else "task_review"
        )
        mode = resolve_mode(
            session_type=session.session_type,
            assistant_name=self.assistant_name,
            user_name=self.user_name,
            context=context,
            tool_registry=self.tool_registry,
        )
        policy_decision = self.tool_policy.decide(user_message, mention_context or {})
        tools_allowed_this_turn = bool(mode.use_tools and policy_decision.tools_allowed)
        response_profile = self._select_response_profile(user_message)

        no_context_message = self._is_no_context_message(user_message)
        include_task_layer = not no_context_message
        include_structured_layer = (
            not no_context_message
            and self._should_include_structured_memory(user_message, mention_context or {})
        )

        assembler = ContextAssembler(
            db=self.db,
            hot_cache=get_hot_context_cache_service(),
            warm_cache=get_warm_cache_service(),
            tenant_id="default",
            user_id=self.user_id,
            session_id=session.id,
            assistant_name=self.assistant_name,
            user_name=self.user_name,
        )
        task_context = self._build_task_context_from_state(state)
        assembly_started = time.perf_counter()
        layers, context_trace = assembler.build_layers_with_trace(
            task_context=task_context,
            include_task=include_task_layer,
            include_session=False,  # Chat history is already injected from DB messages.
            include_structured=include_structured_layer,
        )
        context_assembly_ms = int((time.perf_counter() - assembly_started) * 1000)
        context_trace["assembly_policy"] = {
            "include_task": include_task_layer,
            "include_structured": include_structured_layer,
            "skip_reason": "smalltalk_or_ack" if no_context_message else "n/a",
        }
        context_trace["retrieval"] = {
            "mentions_present": bool((mention_context or {}).get("entities")),
            "mention_entities_count": len((mention_context or {}).get("entities", []) or []),
            "structured_hints_present": include_structured_layer,
        }
        context_trace["tool_policy"] = {
            "tools_allowed_this_turn": tools_allowed_this_turn,
            "reason": policy_decision.reason,
        }
        context_trace["response_policy"] = {
            "task_type": response_profile.task_type,
            "artifact": response_profile.artifact,
            "depth": response_profile.depth,
            "format_style": response_profile.format_style,
            "max_output_tokens": response_profile.max_output_tokens,
            "retry_max_output_tokens": response_profile.retry_max_output_tokens,
        }
        assembler.log_context_trace(context_trace, user_message)

        messages = []
        if self._is_smalltalk_minimal(user_message, mention_context or {}):
            # Ultra-lean prompt for short, no-context smalltalk to cut latency.
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are {self.assistant_name}, a personal assistant for {self.user_name or 'the user'}. "
                        "Reply naturally and warmly in one short sentence. "
                        "Do not mention tools, policies, or internal details."
                    ),
                },
                {"role": "user", "content": user_message},
            ]
            response_profile = ResponseProfile(
                task_type="chat",
                artifact="none",
                depth="micro",
                format_style="paragraph",
                max_output_tokens=80,
                retry_max_output_tokens=80,
                enable_richness_retry=False,
            )
            tools_allowed_this_turn = False
        else:
            messages = [
                {"role": "system", "content": layers.instruction},
                {
                    "role": "system",
                    "content": self._system_prompt_for_turn(mode.system_prompt, tools_allowed_this_turn),
                },
            ]
            layered_payload = {
                "task": layers.task,
                "structured": layers.structured,
            }
            if layered_payload["task"] or layered_payload["structured"]:
                messages.append(
                    {
                        "role": "system",
                        "content": f"Layered memory JSON: {json.dumps(layered_payload, ensure_ascii=True, separators=(',', ':'))}",
                    }
                )
            if mention_context:
                safe_context = json.dumps(mention_context, ensure_ascii=True, separators=(",", ":"))
                messages.append({"role": "system", "content": f"Resolved mention context JSON: {safe_context}"})
                if tools_allowed_this_turn:
                    batch_instruction = self._build_batch_action_instruction(
                        user_message=user_message,
                        mention_context=mention_context or {},
                    )
                    if batch_instruction:
                        messages.append({"role": "system", "content": batch_instruction})
            if tools_allowed_this_turn:
                planner_hint = self._build_planner_hint(user_message, mention_context or {})
                if planner_hint:
                    messages.append({"role": "system", "content": planner_hint})
            if not tools_allowed_this_turn:
                messages.append(
                    {
                        "role": "system",
                        "content": "Do not call tools on this turn. Respond directly using only the conversation text.",
                    }
                )
            messages.append({"role": "system", "content": self._build_response_profile_instruction(response_profile)})
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": user_message})

        # Release DB connection before LLM work to avoid holding pool slots.
        self._release_db_connection()

        pending_actions: List[Dict[str, Any]] = []
        tool_execution_records: List[Dict[str, Any]] = []
        tool_results: List[ToolResult] = []
        llm_prompt_ms_total = 0
        llm_ms_total = 0
        llm_calls_total = 0

        deferred_from_state = list(state.deferred_actions or [])
        deferred_remaining = list(deferred_from_state)
        assistant_message = ""

        if deferred_from_state and self._is_continue_intent(user_message):
            deferred_records, deferred_remaining, deferred_pending, deferred_state_updates = self._execute_deferred_actions(
                deferred_from_state,
                action_budget=MAX_ACTION_TOOLS_PER_TURN,
            )
            tool_execution_records.extend(deferred_records)
            pending_actions.extend(deferred_pending)
            for key, value in deferred_state_updates.items():
                setattr(state, key, value)
        else:
            try:
                llm_messages = list(messages)
                rounds = 0
                action_count = 0
                newly_deferred: List[Dict[str, Any]] = []
                active_tools = (
                    self._filter_tools_by_policy(mode.tools, policy_decision)
                    if tools_allowed_this_turn
                    else []
                )
                if tools_allowed_this_turn and active_tools:
                    planned = await self._run_planned_tool_execution(
                        user_message=user_message,
                        mention_context=mention_context or {},
                        active_tools=active_tools,
                        policy_decision=policy_decision,
                        session_id=session.id,
                    )
                    if planned is not None:
                        llm_prompt_ms_total += int(planned.get("llm_prompt_ms", 0) or 0)
                        llm_ms_total += int(planned.get("llm_ms", 0) or 0)
                        llm_calls_total += int(planned.get("llm_calls", 0) or 0)
                        assistant_message = str(planned.get("assistant_message") or "").strip()
                        tool_results.extend(planned.get("tool_results", []))
                        tool_execution_records.extend(planned.get("tool_execution_records", []))
                        pending_actions.extend(planned.get("pending_actions", []))
                        newly_deferred.extend(planned.get("deferred_actions", []))
                    else:
                        logger.info(
                            "planner_execution_fallback user=%s session=%s reason=planner_parse_or_validation_failed",
                            self.user_id,
                            session.id,
                        )

                if not tools_allowed_this_turn or not assistant_message:
                    attempted_richness_retry = False
                    attempted_batch_recovery = False

                    while rounds < MAX_TOOL_ROUNDS:
                        response = await self._call_llm(
                            llm_messages,
                            active_tools,
                            session_id=session.id,
                            max_output_tokens=response_profile.max_output_tokens,
                        )
                        llm_timing = response.get("timing", {})
                        llm_prompt_ms_total += int(llm_timing.get("prompt_ms", 0) or 0)
                        llm_ms_total += int(llm_timing.get("llm_ms", 0) or 0)
                        llm_calls_total += 1
                        response_text = (response.get("content") or "").strip()
                        if response_text:
                            assistant_message = response_text
                            llm_messages.append({"role": "assistant", "content": response_text})

                        tool_calls = response.get("tool_calls", [])
                        if not tools_allowed_this_turn or not tool_calls:
                            if (
                                tools_allowed_this_turn
                                and not tool_calls
                                and mention_context
                                and not attempted_batch_recovery
                            ):
                                recovery_prompt = self._build_batch_recovery_instruction(
                                    user_message=user_message,
                                    mention_context=mention_context or {},
                                    assistant_text=response_text,
                                )
                                if recovery_prompt:
                                    attempted_batch_recovery = True
                                    llm_messages.append({"role": "system", "content": recovery_prompt})
                                    continue
                            if (
                                not tools_allowed_this_turn
                                and response_text
                                and response_profile.enable_richness_retry
                                and not attempted_richness_retry
                                and self._is_under_detailed_response(response_text, response_profile)
                            ):
                                attempted_richness_retry = True
                                llm_messages.append(
                                    {
                                        "role": "system",
                                        "content": (
                                            "Rewrite your last answer as a complete, polished draft. "
                                            "Keep it practical and natural. Do not explain your reasoning."
                                        ),
                                    }
                                )
                                retry_response = await self._call_llm(
                                    llm_messages,
                                    [],
                                    session_id=session.id,
                                    max_output_tokens=response_profile.retry_max_output_tokens,
                                )
                                retry_llm_timing = retry_response.get("timing", {})
                                llm_prompt_ms_total += int(retry_llm_timing.get("prompt_ms", 0) or 0)
                                llm_ms_total += int(retry_llm_timing.get("llm_ms", 0) or 0)
                                llm_calls_total += 1
                                retry_text = (retry_response.get("content") or "").strip()
                                if retry_text:
                                    assistant_message = retry_text
                                    llm_messages.append({"role": "assistant", "content": retry_text})
                            break

                        parsed_calls: List[Dict[str, Any]] = []
                        for tool_call in tool_calls:
                            tool_name = (tool_call.get("function", {}) or {}).get("name")
                            tool_args = self._parse_tool_args((tool_call.get("function", {}) or {}).get("arguments", "{}"))
                            if not tool_name:
                                continue
                            parsed_calls.append({"name": tool_name, "arguments": tool_args})

                        if not parsed_calls:
                            break

                        llm_messages.append(
                            {
                                "role": "assistant",
                                "content": "",
                                "function_calls": parsed_calls,
                            }
                        )

                        for call in parsed_calls:
                            tool_name = call["name"]
                            tool_args = call["arguments"]
                            is_action_tool = bool(self.tool_registry.is_action_tool(tool_name))
                            if tool_name == "draft_email" and self.user_name and not tool_args.get("sender_name"):
                                tool_args["sender_name"] = self.user_name

                            if is_action_tool and action_count >= MAX_ACTION_TOOLS_PER_TURN:
                                record = {
                                    "name": tool_name,
                                    "arguments": tool_args,
                                    "success": False,
                                    "data": None,
                                    "error": "deferred_due_to_auto_action_limit",
                                    "deferred": True,
                                    "action_tool": True,
                                }
                                tool_execution_records.append(record)
                                newly_deferred.append(
                                    {
                                        "name": tool_name,
                                        "arguments": tool_args,
                                        "reason": "auto_action_limit",
                                    }
                                )
                                llm_messages.append(
                                    {
                                        "role": "tool",
                                        "name": tool_name,
                                        "response": {
                                            "success": False,
                                            "data": None,
                                            "error": "deferred_due_to_auto_action_limit",
                                        },
                                    }
                                )
                                continue

                            result = self.tool_registry.execute_tool(tool_name, tool_args)
                            tool_results.append(result)
                            if is_action_tool:
                                action_count += 1

                            if result.state_updates:
                                for key, value in result.state_updates.items():
                                    setattr(state, key, value)

                            if result.pending_action:
                                pending_actions.append(result.pending_action)

                            record = {
                                "name": tool_name,
                                "arguments": tool_args,
                                "success": result.success,
                                "data": result.data if result.success else None,
                                "error": result.error,
                                "deferred": False,
                                "action_tool": is_action_tool,
                            }
                            tool_execution_records.append(record)
                            llm_messages.append(
                                {
                                    "role": "tool",
                                    "name": tool_name,
                                    "response": {
                                        "success": result.success,
                                        "data": result.data,
                                        "error": result.error,
                                    },
                                }
                            )

                        rounds += 1

                deferred_remaining = self._merge_deferred_actions(deferred_remaining, newly_deferred)
            except Exception as exc:
                logger.error("chat_orchestrator_llm_failed user=%s session=%s", self.user_id, session.id, exc_info=True)
                return {
                    "response": self._friendly_llm_error(user_message),
                    "pending_actions": [],
                    "error": str(exc),
                }

        if not assistant_message:
            if tool_results:
                assistant_message = self._format_tool_results(tool_results)
            else:
                assistant_message = self._friendly_llm_error(user_message)

        has_action_activity = any(bool(item.get("action_tool")) for item in tool_execution_records)
        assistant_message = self._format_action_followup(
            reply=assistant_message,
            tool_outputs=tool_execution_records,
            deferred_actions=deferred_remaining if has_action_activity else [],
        )
        assistant_message = self._sanitize_plain_artifact_text(assistant_message, replace_sender=False)
        assistant_message = self._sanitize_user_facing_response(assistant_message)
        assistant_message, had_placeholders = self._strip_placeholder_lines(assistant_message)
        if had_placeholders and len(assistant_message) < 40:
            assistant_message = self._friendly_llm_error(user_message)
        action_intent = self._detect_primary_action_intent(user_message)
        if action_intent and (mention_context or {}).get("entities") and not tool_execution_records:
            assistant_message = self._friendly_llm_error(user_message)

        state.deferred_actions = list(deferred_remaining)[:MAX_DEFERRED_ACTIONS]
        logger.info(
            "chat_context_trace user=%s session=%s mode=%s mention_context=%s tool_records=%s action_records=%s deferred=%s",
            self.user_id,
            session.id,
            session.session_type,
            bool((mention_context or {}).get("entities")),
            len(tool_execution_records),
            sum(1 for item in tool_execution_records if bool(item.get("action_tool"))),
            len(state.deferred_actions),
        )
        self.context_manager.save_session_state(session, state)

        return {
            "response": assistant_message,
            "pending_actions": pending_actions,
            "state": state.to_dict(),
            "timing": {
                "context_assembly_ms": context_assembly_ms,
                "llm_prompt_ms": llm_prompt_ms_total,
                "llm_ms": llm_ms_total,
                "llm_calls": llm_calls_total,
                "orchestration_ms": int((time.perf_counter() - orchestrator_started) * 1000),
            },
        }

    async def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        max_output_tokens: int = 300,
    ) -> Dict[str, Any]:
        """
        Call the LLM with messages and optional tools.

        Primary path uses native Gemini function-calling.
        Fallback path uses existing text generation + JSON extraction.
        """
        call_started = time.perf_counter()
        tool_definitions_count = len(tools or [])
        safe_session_id = session_id or "unknown"
        record_metrics = self._should_record_chat_metrics(
            session_id=safe_session_id,
            messages=messages,
            tools=tools or [],
        )
        metrics_messages = self._prepare_metrics_messages(messages) if record_metrics else []

        client = get_genai_client()
        if client is not None:
            model_name = "gemini-2.5-flash-lite"
            system_content = ""
            contents: List[genai_types.Content] = []

            for msg in messages:
                role = (msg.get("role") or "").strip().lower()
                text = msg.get("content", "")

                if role == "system":
                    text = str(text or "")
                    system_content = f"{system_content}\n\n{text}".strip() if system_content else text
                    continue

                if role == "assistant":
                    parts: List[genai_types.Part] = []
                    if text:
                        parts.append(genai_types.Part.from_text(text=str(text)))
                    for function_call in msg.get("function_calls", []) or []:
                        fn_name = (function_call.get("name") or "").strip()
                        fn_args = function_call.get("arguments") or {}
                        if not fn_name:
                            continue
                        if not isinstance(fn_args, dict):
                            fn_args = self._parse_tool_args(fn_args)
                        parts.append(genai_types.Part.from_function_call(name=fn_name, args=fn_args))
                    if parts:
                        contents.append(genai_types.Content(role="model", parts=parts))
                    continue

                if role == "tool":
                    tool_name = (msg.get("name") or "").strip()
                    tool_response = msg.get("response") or {}
                    if tool_name:
                        if not isinstance(tool_response, dict):
                            tool_response = {"value": str(tool_response)}
                        part = genai_types.Part.from_function_response(
                            name=tool_name,
                            response=tool_response,
                        )
                        contents.append(genai_types.Content(role="tool", parts=[part]))
                    continue

                if not isinstance(text, str):
                    text = json.dumps(text, ensure_ascii=True)
                contents.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=text)]))

            config_kwargs: Dict[str, Any] = {
                "system_instruction": system_content,
                "max_output_tokens": max(120, min(int(max_output_tokens or 300), 1200)),
            }
            if tools:
                config_kwargs["automatic_function_calling"] = genai_types.AutomaticFunctionCallingConfig(disable=True)
                declarations = self._to_genai_function_declarations(tools)
                if declarations:
                    config_kwargs["tools"] = [genai_types.Tool(function_declarations=declarations)]

            llm_started = time.perf_counter()
            prompt_ms = int((llm_started - call_started) * 1000)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(**config_kwargs),
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - llm_started) * 1000)
                if record_metrics:
                    self._enqueue_chat_metric(
                        session_id=safe_session_id,
                        model=model_name,
                        provider="genai",
                        path="native",
                        messages=metrics_messages,
                        latency_ms=latency_ms,
                        input_tokens=0,
                        output_tokens=0,
                        tool_definitions_count=tool_definitions_count,
                        tool_calls_count=0,
                        success=False,
                        error_type=exc.__class__.__name__,
                        response_chars=0,
                    )
                raise

            latency_ms = int((time.perf_counter() - llm_started) * 1000)

            tool_calls: List[Dict[str, Any]] = []
            for fc in list(response.function_calls or []):
                tool_calls.append(
                    {
                        "function": {
                            "name": fc.name,
                            "arguments": json.dumps(dict(fc.args or {})),
                        }
                    }
                )

            usage = getattr(response, "usage_metadata", None)
            input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
            output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
            if input_tokens > 0 or output_tokens > 0:
                self._enqueue_token_usage(
                    user_id=self.user_id,
                    model=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    operation="chat",
                )

            if record_metrics:
                self._enqueue_chat_metric(
                    session_id=safe_session_id,
                    model=model_name,
                    provider="genai",
                    path="native",
                    messages=metrics_messages,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    tool_definitions_count=tool_definitions_count,
                    tool_calls_count=len(tool_calls),
                    success=True,
                    error_type=None,
                    response_chars=len((response.text or "").strip()),
                )

            return {
                "content": (response.text or "").strip(),
                "tool_calls": tool_calls,
                "timing": {
                    "prompt_ms": prompt_ms,
                    "llm_ms": latency_ms,
                    "total_ms": int((time.perf_counter() - call_started) * 1000),
                },
            }

        orchestrator = _get_chat_llm()
        prompt_parts = []
        system_content = ""

        for msg in messages:
            role = msg.get("role")
            if role == "system":
                system_content = msg.get("content", "")
            elif role == "user":
                prompt_parts.append(f"User: {msg.get('content', '')}")
            elif role == "assistant":
                assistant_text = msg.get("content", "")
                if assistant_text:
                    prompt_parts.append(f"Assistant: {assistant_text}")
                for function_call in msg.get("function_calls", []) or []:
                    prompt_parts.append(
                        f"Assistant tool call: {function_call.get('name')} {json.dumps(function_call.get('arguments', {}))}"
                    )
            elif role == "tool":
                prompt_parts.append(
                    f"Tool ({msg.get('name', 'unknown')}): {json.dumps(msg.get('response', {}), ensure_ascii=True)}"
                )

        prompt = "\n\n".join(prompt_parts)
        if tools:
            tool_desc = self._build_tool_prompt(tools)
            prompt = tool_desc + "\n\n" + prompt

        llm_started = time.perf_counter()
        prompt_ms = int((llm_started - call_started) * 1000)
        try:
            raw_text = await orchestrator.agenerate_text(
                prompt=prompt,
                system_prompt=system_content
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - llm_started) * 1000)
            if record_metrics:
                self._enqueue_chat_metric(
                    session_id=safe_session_id,
                    model="llm_orchestrator",
                    provider="orchestrator",
                    path="fallback",
                    messages=metrics_messages,
                    latency_ms=latency_ms,
                    input_tokens=0,
                    output_tokens=0,
                    tool_definitions_count=tool_definitions_count,
                    tool_calls_count=0,
                    success=False,
                    error_type=exc.__class__.__name__,
                    response_chars=0,
                )
            raise

        latency_ms = int((time.perf_counter() - llm_started) * 1000)

        usage = orchestrator.get_token_usage()
        input_tokens = int(usage["input_tokens"] or 0)
        output_tokens = int(usage["output_tokens"] or 0)
        if usage['input_tokens'] > 0 or usage['output_tokens'] > 0:
            self._enqueue_token_usage(
                user_id=self.user_id,
                model=usage['model'],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation="chat",
            )
        orchestrator.reset_token_usage()

        tool_calls = self._extract_tool_calls_from_response({}, raw_text)
        content = raw_text
        if tool_calls:
            import re as _re
            content = _re.sub(r'```json\s*.*?\s*```', '', content, flags=_re.DOTALL).strip()
            content = _re.sub(r'\{"tool_call"\s*:\s*\{[^}]+\}\s*\}', '', content).strip()

        if record_metrics:
            self._enqueue_chat_metric(
                session_id=safe_session_id,
                model=usage.get("model") or "llm_orchestrator",
                provider="orchestrator",
                path="fallback",
                messages=metrics_messages,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_definitions_count=tool_definitions_count,
                tool_calls_count=len(tool_calls),
                success=True,
                error_type=None,
                response_chars=len(content or ""),
            )

        return {
            "content": content,
            "tool_calls": tool_calls,
            "timing": {
                "prompt_ms": prompt_ms,
                "llm_ms": latency_ms,
                "total_ms": int((time.perf_counter() - call_started) * 1000),
            },
        }

    def _should_record_chat_metrics(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> bool:
        if tools:
            return True
        last_user_message = ""
        for msg in reversed(messages or []):
            if (msg.get("role") or "").strip().lower() == "user":
                last_user_message = str(msg.get("content") or "")
                break
        if last_user_message and len(last_user_message.strip()) <= 24 and self._is_no_context_message(last_user_message):
            return False
        if CHAT_METRICS_SAMPLE_RATE >= 1.0:
            return True
        if CHAT_METRICS_SAMPLE_RATE <= 0.0:
            return False
        seed = f"{self.user_id}:{session_id}:{len(messages)}:{len(last_user_message)}"
        bucket = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        return bucket < CHAT_METRICS_SAMPLE_RATE

    def _prepare_metrics_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        total_chars = 0
        for msg in list(messages or [])[-CHAT_METRICS_PROMPT_MAX_MESSAGES:]:
            role = str(msg.get("role") or "user").strip().lower()
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=True, separators=(",", ":"))
            content = content[:CHAT_METRICS_PROMPT_MAX_CONTENT_CHARS]
            line_size = len(role) + 1 + len(content)
            if total_chars + line_size > CHAT_METRICS_PROMPT_MAX_TOTAL_CHARS:
                break
            prepared.append({"role": role, "content": content})
            total_chars += line_size
            if total_chars >= CHAT_METRICS_PROMPT_MAX_TOTAL_CHARS:
                break
        return prepared

    def _enqueue_chat_metric(
        self,
        *,
        session_id: str,
        model: str,
        provider: str,
        path: str,
        messages: List[Dict[str, Any]],
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        tool_definitions_count: int,
        tool_calls_count: int,
        success: bool,
        error_type: Optional[str],
        response_chars: int,
    ) -> None:
        try:
            get_telemetry_writer().enqueue_chat_metric(
                user_id=self.user_id,
                session_id=session_id,
                model=model,
                provider=provider,
                path=path,
                messages=messages,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_definitions_count=tool_definitions_count,
                tool_calls_count=tool_calls_count,
                success=success,
                error_type=error_type,
                response_chars=response_chars,
            )
        except Exception:
            logger.warning("chat_metrics_enqueue_failed user=%s", self.user_id, exc_info=True)

    def _enqueue_token_usage(
        self,
        *,
        user_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str,
    ) -> None:
        try:
            get_telemetry_writer().enqueue_token_usage(
                user_id=user_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation=operation,
            )
        except Exception:
            logger.warning("token_usage_enqueue_failed user=%s", self.user_id, exc_info=True)

    def _to_genai_function_declarations(self, tools: List[Dict[str, Any]]) -> List[genai_types.FunctionDeclaration]:
        declarations: List[genai_types.FunctionDeclaration] = []
        for tool in tools or []:
            fn = tool.get("function", {})
            name = fn.get("name")
            if not name:
                continue
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=name,
                    description=fn.get("description", ""),
                    parameters_json_schema=fn.get("parameters", {"type": "object", "properties": {}}),
                )
            )
        return declarations

    def _build_tool_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """Build the tool description prompt with JSON schema."""
        lines = [
            "You have access to the following tools. To use a tool, include a JSON block in your response:",
            "",
            "```json",
            '{"tool_call": {"name": "tool_name", "arguments": {"arg1": "value1"}}}',
            "```",
            "",
            "Available tools:"
        ]
        
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", {}).get("properties", {})
            required = func.get("parameters", {}).get("required", [])
            
            lines.append(f"\n**{name}**: {desc}")
            if params:
                lines.append("  Arguments:")
                for param_name, param_def in params.items():
                    req_marker = " (required)" if param_name in required else ""
                    param_type = param_def.get("type", "string")
                    param_desc = param_def.get("description", "")
                    lines.append(f"    - {param_name}: {param_type}{req_marker} - {param_desc}")
        
        lines.append("\n\nIf you don't need to use a tool, respond normally with text only.")
        return "\n".join(lines)
    
    def _extract_tool_calls_from_response(
        self,
        result: Dict[str, Any],
        content: str
    ) -> List[Dict[str, Any]]:
        """Extract tool calls from LLM response."""
        tool_calls = []
        
        # Method 1: Check if result dict contains tool_call directly
        if isinstance(result.get("tool_call"), dict):
            tc = result["tool_call"]
            tool_calls.append({
                "function": {
                    "name": tc.get("name"),
                    "arguments": json.dumps(tc.get("arguments", {}))
                }
            })
            return tool_calls
        
        # Method 2: Extract JSON blocks from content
        import re
        
        # Look for ```json ... ``` blocks
        json_blocks = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        for block in json_blocks:
            try:
                parsed = json.loads(block)
                if "tool_call" in parsed:
                    tc = parsed["tool_call"]
                    tool_calls.append({
                        "function": {
                            "name": tc.get("name"),
                            "arguments": json.dumps(tc.get("arguments", {}))
                        }
                    })
            except json.JSONDecodeError:
                continue
        
        # Method 3: Look for inline JSON {"tool_call": ...}
        if not tool_calls:
            try:
                # Find JSON-like pattern for tool_call
                pattern = r'\{"tool_call"\s*:\s*\{[^}]+\}\s*\}'
                matches = re.findall(pattern, content)
                for match in matches:
                    parsed = json.loads(match)
                    if "tool_call" in parsed:
                        tc = parsed["tool_call"]
                        tool_calls.append({
                            "function": {
                                "name": tc.get("name"),
                                "arguments": json.dumps(tc.get("arguments", {}))
                            }
                        })
            except (json.JSONDecodeError, re.error):
                pass
        
        return tool_calls

    def _parse_tool_args(self, raw_args: Any) -> Dict[str, Any]:
        if isinstance(raw_args, dict):
            return raw_args
        if raw_args is None:
            return {}
        if not isinstance(raw_args, str):
            return {}
        try:
            parsed = json.loads(raw_args)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            logger.warning("tool_args_parse_failed user=%s raw=%s", self.user_id, raw_args[:120])
            return {}

    def _select_response_profile(self, message: str) -> ResponseProfile:
        lowered = (message or "").lower()

        artifact = "none"
        if any(token in lowered for token in {"email", "reply", "message"}):
            artifact = "email"
        elif any(token in lowered for token in {"presentation", "slide", "slides", "deck"}):
            artifact = "presentation"
        elif any(token in lowered for token in {"memo", "brief", "document", "doc"}):
            artifact = "document"

        if self._is_no_context_message(message):
            task_type = "chat"
        elif artifact != "none" and any(token in lowered for token in {"draft", "write", "compose", "create", "prepare", "build"}):
            task_type = "draft"
        elif any(token in lowered for token in {"plan", "roadmap", "checklist", "steps"}):
            task_type = "plan"
        elif any(token in lowered for token in {"analyze", "analysis", "compare", "tradeoff", "why", "explain"}):
            task_type = "analysis"
        elif any(token in lowered for token in {"recap", "summary", "summarize", "what changed"}):
            task_type = "recap"
        else:
            task_type = "chat"

        if any(hint in lowered for hint in SHORT_DETAIL_HINTS):
            depth = "micro"
        elif any(hint in lowered for hint in DEEP_DETAIL_HINTS):
            depth = "deep"
        elif task_type in {"draft", "plan", "analysis"}:
            depth = "standard"
        else:
            depth = "micro"

        format_style = "paragraph"
        if task_type in {"plan", "analysis", "recap"}:
            format_style = "sections"
        if artifact in {"presentation", "document"}:
            format_style = "sections"

        max_tokens = 220
        retry_tokens = 320
        if depth == "standard":
            max_tokens = 520
            retry_tokens = 720
        elif depth == "deep":
            max_tokens = 850
            retry_tokens = 1000

        if task_type == "draft":
            max_tokens = max(max_tokens, 500)
            retry_tokens = max(retry_tokens, 760)

        return ResponseProfile(
            task_type=task_type,
            artifact=artifact,
            depth=depth,
            format_style=format_style,
            max_output_tokens=max_tokens,
            retry_max_output_tokens=retry_tokens,
            enable_richness_retry=depth == "deep",
        )

    def _is_smalltalk_minimal(self, message: str, mention_context: Dict[str, Any]) -> bool:
        """Detect very short, no-context smalltalk to force a tiny prompt."""
        if not message:
            return False
        if len(message.strip()) > 32:
            return False
        if mention_context.get("entities") or mention_context.get("memory"):
            return False
        return self._is_no_context_message(message)

    def _build_response_profile_instruction(self, profile: ResponseProfile) -> str:
        lines = [
            "Adaptive response policy:",
            f"- task_type: {profile.task_type}",
            f"- artifact: {profile.artifact}",
            f"- depth: {profile.depth}",
            f"- format: {profile.format_style}",
            "- Be concise when the ask is simple.",
            "- Expand only when the ask needs a usable artifact, plan, or deeper analysis.",
            "- Never mention internal policy names or decision logic.",
        ]

        if profile.task_type == "draft":
            lines.extend(
                [
                    "- Return a complete first draft, not notes about a draft.",
                    "- Keep language natural and polished.",
                ]
            )
            if profile.artifact == "email":
                lines.extend(
                    [
                        "- Include a clear subject line and the full email body.",
                        "- Use plain text only; do not use markdown formatting.",
                        "- If a key detail is missing, make one reasonable assumption and proceed.",
                    ]
                )
            elif profile.artifact in {"presentation", "document"}:
                lines.extend(
                    [
                        "- Return a complete draft structure that can be used immediately.",
                    ]
                )
        elif profile.task_type in {"plan", "analysis"}:
            lines.extend(
                [
                    "- Use clear sections with concrete next actions.",
                ]
            )

        return "\n".join(lines)

    def _system_prompt_for_turn(self, system_prompt: str, tools_allowed: bool) -> str:
        """Drop tool instructions on turns where tools are explicitly disabled."""
        if tools_allowed:
            return system_prompt
        marker = "\n\nAvailable tools:"
        marker_index = (system_prompt or "").find(marker)
        if marker_index < 0:
            return system_prompt
        return system_prompt[:marker_index].rstrip()

    def _is_under_detailed_response(self, response_text: str, profile: ResponseProfile) -> bool:
        if profile.task_type not in {"draft", "plan", "analysis"}:
            return False
        text = (response_text or "").strip()
        if not text:
            return True

        word_count = len(text.split())
        min_words = 55 if profile.task_type == "draft" else 40
        if profile.depth == "deep":
            min_words = max(min_words, 90)
        if word_count < min_words:
            return True

        if profile.task_type == "draft" and profile.artifact == "email":
            lowered = text.lower()
            has_subject = "subject:" in lowered
            if not has_subject and word_count < 80:
                return True

        return False

    def _is_no_context_message(self, message: str) -> bool:
        cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in (message or ""))
        normalized = " ".join(cleaned.split())
        return normalized in NO_CONTEXT_MESSAGES

    def _should_include_structured_memory(self, message: str, mention_context: Dict[str, Any]) -> bool:
        lowered = (message or "").lower()
        if mention_context.get("entities"):
            return True
        return any(token in lowered for token in STRUCTURED_HINT_TOKENS)

    def _build_task_context_from_state(self, state: ConversationState) -> Dict[str, Any]:
        task_context: Dict[str, Any] = {}
        if state.current_thread_id:
            task_context["current_thread_id"] = state.current_thread_id
        if state.current_contact_id is not None:
            task_context["current_contact_id"] = state.current_contact_id
        if state.current_email_id is not None:
            task_context["current_email_id"] = state.current_email_id
        if state.current_task_id is not None:
            task_context["task"] = {"task_id": state.current_task_id}
        if state.active_workflow:
            task_context["goal"] = state.active_workflow
        if state.workflow_data:
            task_context["constraints"] = state.workflow_data
        return task_context

    def _is_continue_intent(self, message: str) -> bool:
        normalized = " ".join("".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in (message or "")).split())
        if not normalized:
            return False
        exact = {
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
        if normalized in exact:
            return True
        tokens = set(normalized.split())
        return bool(tokens.intersection({"continue", "proceed", "next", "resume"}))

    def _execute_deferred_actions(
        self,
        deferred_actions: List[Dict[str, Any]],
        action_budget: int,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        executed_records: List[Dict[str, Any]] = []
        remaining: List[Dict[str, Any]] = []
        pending_actions: List[Dict[str, Any]] = []
        state_updates: Dict[str, Any] = {}
        executed_count = 0

        for item in deferred_actions:
            name = (item.get("name") or "").strip()
            arguments = item.get("arguments") or {}
            if not name:
                continue
            if executed_count >= action_budget:
                remaining.append({"name": name, "arguments": arguments, "reason": "auto_action_limit"})
                continue
            if not self.tool_registry.is_action_tool(name):
                continue

            result = self.tool_registry.execute_tool(name, arguments)
            executed_records.append(
                {
                    "name": name,
                    "arguments": arguments,
                    "success": result.success,
                    "data": result.data if result.success else None,
                    "error": result.error,
                    "deferred": False,
                    "continued": True,
                    "action_tool": True,
                }
            )
            if result.pending_action:
                pending_actions.append(result.pending_action)
            if result.state_updates:
                state_updates.update(result.state_updates)
            executed_count += 1

        return executed_records, remaining, pending_actions, state_updates

    def _merge_deferred_actions(
        self,
        existing: List[Dict[str, Any]],
        new: List[Dict[str, Any]],
        max_items: int = MAX_DEFERRED_ACTIONS,
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen = set()
        for item in (existing or []) + (new or []):
            name = (item.get("name") or "").strip()
            arguments = item.get("arguments") or {}
            if not name:
                continue
            try:
                arg_key = json.dumps(arguments, sort_keys=True)
            except Exception:
                arg_key = str(arguments)
            key = f"{name}:{arg_key}"
            if key in seen:
                continue
            seen.add(key)
            merged.append({"name": name, "arguments": arguments, "reason": item.get("reason") or "auto_action_limit"})
            if len(merged) >= max_items:
                break
        return merged

    def _friendly_llm_error(self, message: str) -> str:
        lowered = (message or "").lower()
        if any(token in lowered for token in {"draft", "reply", "email"}):
            return "I can't draft that reply right now."
        if any(token in lowered for token in {"meeting brief", "brief", "prep", "prepare"}):
            return "I can't prepare that meeting brief right now."
        if any(token in lowered for token in {"recap", "summary", "decisions", "commitments"}):
            return "I can't summarize that right now."
        return "I can't complete that right now."

    def _normalize_action_title(self, value: Optional[str]) -> str:
        text = " ".join((value or "").replace('"', "").split())
        return text.strip()

    def _action_title_from_output(self, item: Dict[str, Any]) -> str:
        name = (item.get("name") or "").strip()
        args = item.get("arguments") or {}
        data = item.get("data") or {}

        if name == "draft_email":
            subject = self._normalize_action_title(data.get("subject") or args.get("subject"))
            recipient = self._normalize_action_title(data.get("recipient") or args.get("recipient"))
            if subject and recipient:
                return f"draft email for {subject} to {recipient}"
            if subject:
                return f"draft email for {subject}"
            return "draft email"

        if name == "generate_meeting_brief":
            subject = self._normalize_action_title(data.get("meeting_subject") or args.get("meeting_subject"))
            event_id = self._normalize_action_title(data.get("event_id") or args.get("event_id"))
            if subject:
                return f"meeting brief for {subject}"
            if event_id:
                return f"meeting brief for {event_id}"
            return "meeting brief"

        return self._normalize_action_title(name) or "action"

    def _format_action_followup(
        self,
        reply: str,
        tool_outputs: List[Dict[str, Any]],
        deferred_actions: List[Dict[str, Any]],
    ) -> str:
        # For a single successful action, return the artifact as-is.
        single_action = [item for item in tool_outputs if (item.get("action_tool") or item.get("name") in ACTION_TOOL_NAMES)]
        if len(single_action) == 1 and not deferred_actions:
            return self._normalize_single_action_reply(reply, tool_outputs)

        # For multi-action turns, return the action outputs only (no meta summary).
        base = (reply or "").strip()
        if deferred_actions:
            deferred = []
            for item in deferred_actions:
                name = (item.get("name") or "").strip()
                if not (name in ACTION_TOOL_NAMES or self.tool_registry.is_action_tool(name)):
                    continue
                label = self._action_title_from_output(item)
                if label:
                    deferred.append(label)
            if deferred:
                deferred_text = ", ".join([f'"{value}"' for value in deferred])
                return f"{base}\n\nWould you like me to continue with {deferred_text}?" if base else f"Would you like me to continue with {deferred_text}?"
        return base

    def _sanitize_plain_artifact_text(self, text: str, replace_sender: bool = False) -> str:
        """Normalize lightweight markdown/styling into plain chat-safe text."""
        out = text or ""
        # Markdown heading markers
        out = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", out)
        # Bold/underline emphasis
        out = re.sub(r"\*\*(.*?)\*\*", r"\1", out, flags=re.DOTALL)
        out = re.sub(r"__(.*?)__", r"\1", out, flags=re.DOTALL)
        # Inline code markers
        out = re.sub(r"`([^`]+)`", r"\1", out)
        # Normalize markdown star bullets into plain hyphen bullets
        out = re.sub(r"(?m)^\s*\*\s+", "- ", out)

        if replace_sender:
            replacement_name = (self.user_name or "").strip()
            if replacement_name:
                out = re.sub(r"\[(?:your\s*name)\]", replacement_name, out, flags=re.IGNORECASE)
            else:
                out = re.sub(r"\[(?:your\s*name)\]", "", out, flags=re.IGNORECASE)

        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()

    def _strip_placeholder_lines(self, text: str) -> Tuple[str, bool]:
        """Remove placeholder/filler content that should never reach users."""
        if not text:
            return "", False

        placeholder_re = re.compile(
            r"\[(?:your\s*name|your\s*email|list\s+of|insert|tbd|to\s+be\s+decided|"
            r"link|date|time|attendee|attendees|recipient|assignee|name|title|company|"
            r"phone|location|agenda|pre-reads?|attachments?|notes?|commitment|"
            r"suggest)\b[^\]]*\]",
            flags=re.IGNORECASE,
        )
        extracted_re = re.compile(r"\bcommitment\s+\d+\s+extracted\b", flags=re.IGNORECASE)

        lines: List[str] = []
        had_placeholders = False
        for raw in str(text).splitlines():
            line = raw.rstrip()
            if not line.strip():
                lines.append("")
                continue

            if placeholder_re.search(line):
                had_placeholders = True
                # Remove placeholder segments; drop the line if it becomes empty/label-only.
                cleaned = placeholder_re.sub("", line).strip()
                if extracted_re.search(cleaned):
                    had_placeholders = True
                    continue
                if not cleaned:
                    continue
                if re.match(r"^[A-Za-z0-9 /_-]+:\s*$", cleaned):
                    continue
                lines.append(cleaned)
                continue

            if extracted_re.search(line):
                had_placeholders = True
                continue

            lines.append(line)

        cleaned_text = "\n".join(lines).strip()
        return cleaned_text, had_placeholders

    def _sanitize_user_facing_response(self, text: str) -> str:
        """Remove internal/process wording that should never surface to users."""
        out = (text or "").strip()
        if not out:
            return out
        replacements = [
            (r"\bi need to access the context for\b", "I don't have enough details yet for"),
            (r"\bi need (more|additional) context\b", "I need one more detail"),
            (r"\bcontext is not available to me right now\b", "I don't have those details yet"),
            (r"\bi can'?t access context\b", "I can't verify those details yet"),
            (r"\bi can access context\b", "I can verify those details"),
        ]
        for pattern, repl in replacements:
            out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
        return out

    def _normalize_referenced_entities(self, mention_context: Dict[str, Any]) -> List[Dict[str, str]]:
        entities = mention_context.get("entities") or []
        normalized: List[Dict[str, str]] = []
        seen: set[str] = set()
        for item in entities:
            kind = (item.get("kind") or item.get("type") or "").strip().lower()
            if kind not in {"thread", "event", "contact", "task"}:
                continue
            ref = " ".join(str(item.get("ref") or "").split()).strip()
            label = " ".join(str(item.get("label") or ref).split()).strip()
            key = f"{kind}:{(ref or label).lower()}"
            if not (ref or label) or key in seen:
                continue
            seen.add(key)
            normalized.append({"kind": kind, "ref": ref, "label": label})
        return normalized

    def _build_batch_action_instruction(self, user_message: str, mention_context: Dict[str, Any]) -> str:
        """Instruct the model to treat explicit multi-entity requests as batch actions."""
        lowered = (user_message or "").lower()
        action_hint = ""
        target_kinds: set[str] = set()
        if any(token in lowered for token in {"draft", "reply", "respond", "compose", "write", "email"}):
            action_hint = "draft_email"
            target_kinds = {"thread", "contact"}
        elif any(token in lowered for token in {"meeting brief", "prep", "prepare", "brief"}):
            action_hint = "generate_meeting_brief"
            target_kinds = {"event"}

        if not action_hint:
            return ""

        entities_all = [
            item for item in self._normalize_referenced_entities(mention_context)
            if item.get("kind") in target_kinds
        ]
        entities = entities_all
        if action_hint == "draft_email":
            # For drafts, prefer thread-scoped batching.
            # Use contact batching only when there are no thread references.
            thread_entities = [item for item in entities_all if item.get("kind") == "thread"]
            contact_entities = [item for item in entities_all if item.get("kind") == "contact"]
            if len(thread_entities) >= 2:
                entities = thread_entities
            elif len(thread_entities) == 0 and len(contact_entities) >= 2:
                entities = contact_entities
            else:
                return ""

        if len(entities) < 2:
            return ""

        visible = entities[:MAX_ACTION_TOOLS_PER_TURN]
        return (
            "Batch action instruction:\n"
            f"- The user explicitly referenced {len(entities)} entities for a single repeated action.\n"
            f"- Treat this as a batch request for {action_hint}.\n"
            f"- Execute one {action_hint} tool call per referenced entity now (up to {MAX_ACTION_TOOLS_PER_TURN}).\n"
            "- If there are more entities beyond the limit, defer the rest and ask to continue naturally.\n"
            "- Do not ask the user to choose one entity when references are explicit and resolvable.\n"
            f"- Entity references: {json.dumps(visible, ensure_ascii=True)}"
        )

    def _looks_like_single_target_clarification(self, assistant_text: str) -> bool:
        text = " ".join((assistant_text or "").lower().split())
        if not text:
            return False
        patterns = [
            "which thread",
            "which one",
            "pick one",
            "choose one",
            "specify which",
            "cannot draft replies for multiple",
            "can't draft replies for multiple",
            "one at a time",
        ]
        return any(p in text for p in patterns)

    def _build_batch_recovery_instruction(
        self,
        user_message: str,
        mention_context: Dict[str, Any],
        assistant_text: str,
    ) -> str:
        """Retry hint when model tries to force single-target clarification."""
        if not self._looks_like_single_target_clarification(assistant_text):
            return ""
        batch_prompt = self._build_batch_action_instruction(user_message, mention_context)
        if not batch_prompt:
            return ""
        return (
            "Correction for previous response:\n"
            "- Do not ask the user to pick one item.\n"
            "- Execute the batch now with tool calls based on explicit references.\n"
            "- Return concise outputs for completed items.\n\n"
            f"{batch_prompt}"
        )

    def _build_planner_hint(self, user_message: str, mention_context: Dict[str, Any]) -> str:
        """Lightweight planner hint to nudge intent extraction + ordered execution."""
        lowered = (user_message or "").lower()
        has_action_word = any(
            token in lowered
            for token in [
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
                "create task",
                "update task",
                "remember",
                "set preference",
                "search",
                "find",
            ]
        )
        if not has_action_word:
            return ""
        entities = self._normalize_referenced_entities(mention_context)
        explicit_multi_target = len(entities) >= 2
        likely_multi_intent = any(token in lowered for token in {" and ", " also ", ","})
        if not explicit_multi_target and not likely_multi_intent:
            return ""
        return (
            "Planner hint:\n"
            "- Keep an internal ordered plan for this turn.\n"
            "- If multiple intents or explicit targets are present, execute up to 5 actions now.\n"
            "- Ask at most one concise question only if truly blocking; otherwise proceed with assumptions.\n"
            "- Prefer partial completion over blocking; defer extras politely.\n"
            "- Keep the final reply concise and user-facing; do not expose this hint."
        )

    def _detect_primary_action_intent(self, user_message: str) -> str:
        lowered = (user_message or "").lower()
        if any(token in lowered for token in {"meeting brief", "brief", "prep", "prepare"}):
            return "generate_meeting_brief"
        if any(token in lowered for token in {"draft", "reply", "respond", "compose", "write", "email"}):
            return "draft_email"
        return ""

    async def _run_planned_tool_execution(
        self,
        user_message: str,
        mention_context: Dict[str, Any],
        active_tools: List[Dict[str, Any]],
        policy_decision: ToolPolicyDecision,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Build a structured execution plan, then run it through dependency-aware executor.

        Returns None when planning cannot be validated so caller can fall back.
        """
        planner_messages = self._build_plan_builder_messages(
            user_message=user_message,
            mention_context=mention_context,
            active_tools=active_tools,
        )
        planner_response = await self._call_llm(
            planner_messages,
            tools=[],
            session_id=session_id,
            max_output_tokens=760,
        )
        planner_timing = planner_response.get("timing", {}) or {}
        raw_plan = (planner_response.get("content") or "").strip()
        if not raw_plan:
            return None

        try:
            plan = parse_execution_plan(raw_plan)
        except PlanParseError:
            logger.warning(
                "plan_parse_failed user=%s session=%s raw_preview=%s",
                self.user_id,
                session_id,
                raw_plan[:220],
            )
            repaired = await self._repair_planner_output(
                raw_plan=raw_plan,
                user_message=user_message,
                mention_context=mention_context,
                active_tools=active_tools,
                session_id=session_id,
            )
            if repaired is None:
                return None
            plan = repaired

        if plan.clarification.needed and plan.clarification.question:
            return {
                "assistant_message": str(plan.clarification.question).strip(),
                "pending_actions": [],
                "tool_results": [],
                "tool_execution_records": [],
                "deferred_actions": [],
                "llm_prompt_ms": int(planner_timing.get("prompt_ms", 0) or 0),
                "llm_ms": int(planner_timing.get("llm_ms", 0) or 0),
                "llm_calls": 1,
            }

        node_by_id = {node.id: node for node in plan.nodes}
        allowed_tool_names = {
            ((item.get("function") or {}).get("name") or "").strip()
            for item in active_tools
            if isinstance(item, dict)
        }

        action_count = 0
        deferred_actions: List[Dict[str, Any]] = []
        execution_records: List[Dict[str, Any]] = []
        tool_results: List[ToolResult] = []
        pending_actions: List[Dict[str, Any]] = []

        executor = DependencyAwareExecutor()

        def _execute_node(node) -> ToolResult:
            nonlocal action_count
            tool_name = (node.tool or "").strip()
            tool_args = dict(node.args or {})

            if tool_name == "draft_email":
                # Ensure the raw user ask is available to the drafting tool for completeness.
                tool_args.setdefault("user_request", user_message)

            if tool_name not in allowed_tool_names:
                raise ValueError("tool_not_allowed_by_catalog")
            if not policy_decision.allows_tool(tool_name):
                raise ValueError("tool_not_allowed_by_policy")

            is_action_tool = bool(self.tool_registry.is_action_tool(tool_name))
            if tool_name == "draft_email" and self.user_name and not tool_args.get("sender_name"):
                tool_args["sender_name"] = self.user_name

            if is_action_tool and action_count >= MAX_ACTION_TOOLS_PER_TURN:
                deferred_actions.append(
                    {
                        "name": tool_name,
                        "arguments": tool_args,
                        "reason": "auto_action_limit",
                    }
                )
                return ToolResult(success=False, error="deferred_due_to_auto_action_limit")

            result = self.tool_registry.execute_tool(tool_name, tool_args)
            if is_action_tool and result.success:
                action_count += 1
            self._release_db_connection()
            return result

        dag_result = await executor.execute(
            plan=plan,
            execute_node=_execute_node,
            approved_node_ids={node.id for node in plan.nodes},  # write tools stay approval-gated by ToolRegistry.
        )

        for rec in dag_result.records:
            node = node_by_id.get(rec.node_id)
            tool_name = (node.tool or "") if node else ""
            tool_args = dict(node.args or {}) if node else {}
            is_action_tool = bool(tool_name and self.tool_registry.is_action_tool(tool_name))

            if rec.status == NodeRunStatus.SUCCESS and isinstance(rec.output, ToolResult):
                result = rec.output
                tool_results.append(result)
                if result.pending_action:
                    pending_actions.append(result.pending_action)
                execution_records.append(
                    {
                        "name": tool_name,
                        "arguments": tool_args,
                        "success": result.success,
                        "data": result.data if result.success else None,
                        "error": result.error,
                        "deferred": bool(result.error == "deferred_due_to_auto_action_limit"),
                        "action_tool": is_action_tool,
                    }
                )
                continue

            execution_records.append(
                {
                    "name": tool_name,
                    "arguments": tool_args,
                    "success": False,
                    "data": None,
                    "error": rec.error or rec.status.value,
                    "deferred": False,
                    "action_tool": is_action_tool,
                }
            )

        assistant_message = ""
        if tool_results:
            assistant_message = self._format_tool_results(tool_results)
        elif pending_actions:
            assistant_message = "I prepared actions for your approval."

        return {
            "assistant_message": assistant_message,
            "pending_actions": pending_actions,
            "tool_results": tool_results,
            "tool_execution_records": execution_records,
            "deferred_actions": deferred_actions,
            "llm_prompt_ms": int(planner_timing.get("prompt_ms", 0) or 0),
            "llm_ms": int(planner_timing.get("llm_ms", 0) or 0),
            "llm_calls": 1,
        }

    async def _repair_planner_output(
        self,
        raw_plan: str,
        user_message: str,
        mention_context: Dict[str, Any],
        active_tools: List[Dict[str, Any]],
        session_id: str,
    ) -> Optional["ExecutionPlan"]:
        """
        Attempt to repair planner output into a valid ExecutionPlan.

        This reduces fallbacks to freeform LLM responses that can hallucinate
        placeholders or generic templates.
        """
        catalog: List[Dict[str, Any]] = []
        for tool in active_tools:
            fn = tool.get("function") or {}
            name = (fn.get("name") or "").strip()
            if not name:
                continue
            if name in _PLANNER_HIDDEN_TOOLS:
                continue
            family = TOOL_FAMILY_BY_NAME.get(name)
            catalog.append(
                {
                    "name": name,
                    "family": family.value if family else "read_context",
                    "description": str(fn.get("description") or ""),
                }
            )

        repair_system = (
            "You fix planner JSON. Return ONLY valid JSON (no markdown) matching: "
            "{plan_id, sub_requests[], nodes[], clarification}. "
            "Do not add prose."
        )
        repair_user = (
            f"User message: {user_message}\n"
            f"Resolved mention context JSON: {json.dumps(mention_context or {}, ensure_ascii=True, separators=(',', ':'))}\n"
            f"Tool catalog JSON: {json.dumps(catalog, ensure_ascii=True, separators=(',', ':'))}\n"
            f"Broken planner output:\n{raw_plan}\n"
            "Return corrected JSON only."
        )
        repair_response = await self._call_llm(
            [{"role": "system", "content": repair_system}, {"role": "user", "content": repair_user}],
            tools=[],
            session_id=session_id,
            max_output_tokens=520,
        )
        repaired_raw = (repair_response.get("content") or "").strip()
        if not repaired_raw:
            return None
        try:
            return parse_execution_plan(repaired_raw)
        except PlanParseError:
            logger.warning(
                "plan_repair_failed user=%s session=%s raw_preview=%s",
                self.user_id,
                session_id,
                repaired_raw[:220],
            )
            return None

    def _build_plan_builder_messages(
        self,
        user_message: str,
        mention_context: Dict[str, Any],
        active_tools: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Build planner prompt messages for strict JSON ExecutionPlan output."""
        catalog: List[Dict[str, Any]] = []
        for tool in active_tools:
            fn = tool.get("function") or {}
            name = (fn.get("name") or "").strip()
            if not name:
                continue
            if name in _PLANNER_HIDDEN_TOOLS:
                continue
            family = TOOL_FAMILY_BY_NAME.get(name)
            catalog.append(
                {
                    "name": name,
                    "family": family.value if family else "read_context",
                    "description": str(fn.get("description") or ""),
                }
            )

        planner_system = (
            "You are a strict planning engine for Teeks chat. "
            "Return ONLY a valid JSON object (no markdown, no prose) matching this contract: "
            "{plan_id, sub_requests[], nodes[], clarification}. "
            "Each node must include: id, sub_request_id, family, tool, args, depends_on[]. "
            "Use only tools from the provided catalog. "
            "Prefer unified tools (entity_search, context_search) over deprecated get_* context tools. "
            "Use context_search when the user asks to retrieve decisions, commitments, preferences, relationships, risks, or history "
            "about an entity (contact/thread/event/message/task), or when they ask for updates/recaps/status/what-changed."
            "Prefer minimal plans. "
            "If the request is blocked, set clarification.needed=true with one concise question. "
            "If not blocked, clarification.needed=false."
        )
        planner_user = (
            f"User message: {user_message}\n"
            f"Resolved mention context JSON: {json.dumps(mention_context or {}, ensure_ascii=True, separators=(',', ':'))}\n"
            f"Tool catalog JSON: {json.dumps(catalog, ensure_ascii=True, separators=(',', ':'))}\n"
            "Constraints:\n"
            f"- Max {MAX_ACTION_TOOLS_PER_TURN} action nodes for this turn.\n"
            "- For independent reads, keep dependencies empty so they can run in parallel.\n"
            "- Keep args concrete and executable.\n"
            "- Never include tools outside catalog."
        )
        return [
            {"role": "system", "content": planner_system},
            {"role": "user", "content": planner_user},
        ]

    def _filter_tools_by_policy(
        self,
        tools: List[Dict[str, Any]],
        decision: ToolPolicyDecision,
    ) -> List[Dict[str, Any]]:
        """Filter function declarations by tool-family policy decision."""
        filtered: List[Dict[str, Any]] = []
        for tool_def in tools:
            function_decl = tool_def.get("function") or {}
            name = (function_decl.get("name") or "").strip()
            if decision.allows_tool(name):
                filtered.append(tool_def)
        return filtered

    def _normalize_single_action_reply(self, reply: str, tool_outputs: List[Dict[str, Any]]) -> str:
        text = (reply or "").strip()
        if not text:
            return text

        action_tools = [
            item for item in tool_outputs
            if bool(item.get("action_tool")) or (item.get("name") in ACTION_TOOL_NAMES)
        ]
        if len(action_tools) != 1:
            return text

        only = action_tools[0]
        action_name = (only.get("name") or "").strip()
        if action_name not in {"draft_email", "generate_meeting_brief"}:
            return text

        if action_name == "generate_meeting_brief":
            payload = only.get("data") or {}
            if isinstance(payload, dict):
                return self._render_meeting_brief(payload)

        return self._sanitize_plain_artifact_text(
            text=text,
            replace_sender=(action_name == "draft_email"),
        )
    
    def _format_tool_results(self, results: List[ToolResult]) -> str:
        """Format tool results into a human-readable response."""
        parts = []
        
        for result in results:
            if not result.success:
                parts.append(self._humanize_tool_error(result.error))
            elif result.data:
                # Format based on data type
                if "emails" in result.data:
                    count = result.data.get("count", 0)
                    if count == 0:
                        parts.append("I didn't find any matching emails.")
                    else:
                        parts.append(f"I found {count} email(s):")
                        for email in result.data["emails"][:3]:
                            parts.append(f"- \"{email['subject']}\" from {email['sender']}")
                
                elif "tasks" in result.data:
                    count = result.data.get("count", 0)
                    if count == 0:
                        parts.append("I didn't find any matching tasks.")
                    else:
                        parts.append(f"I found {count} task(s):")
                        for task in result.data["tasks"][:3]:
                            parts.append(f"- {task['title']} ({task['status']})")
                
                elif "events" in result.data:
                    count = result.data.get("count", 0)
                    if count == 0:
                        parts.append("No upcoming events found.")
                    else:
                        parts.append(f"You have {count} upcoming event(s):")
                        for event in result.data["events"][:3]:
                            parts.append(f"- {event['title']} at {event['start_time']}")
                
                elif "message" in result.data:
                    parts.append(result.data["message"])
                elif "body" in result.data and "subject" in result.data:
                    parts.append(self._render_email_draft(result.data))
                elif "agenda" in result.data and "meeting_subject" in result.data:
                    parts.append(self._render_meeting_brief(result.data))
                elif "summary" in result.data:
                    parts.append(str(result.data.get("summary")))
        
        if parts:
            rendered = "\n".join(parts)
            rendered = self._sanitize_plain_artifact_text(rendered, replace_sender=False)
            rendered, had_placeholders = self._strip_placeholder_lines(rendered)
            if had_placeholders and len(rendered) < 40:
                return "I couldn't complete that action yet."
            return rendered
        # Avoid empty generic fallback when tools ran but returned no renderable payload.
        return "I completed that step, but there wasn't any displayable output yet."

    def _humanize_tool_error(self, error: Optional[str]) -> str:
        text = " ".join(str(error or "").split()).strip().lower()
        if not text:
            return "I couldn't finish that action."
        if "not found" in text and "thread" in text:
            return "I couldn't find that thread. Please reselect it from references and try again."
        if "not found" in text and "event" in text:
            return "I couldn't find that event. Please reselect it from references and try again."
        if "not found" in text and "task" in text:
            return "I couldn't find that task. Please reselect it from references and try again."
        if "missing required field" in text:
            return "I need one more detail to complete that action."
        if "invalid parameter" in text or "validation" in text:
            return "I couldn't run that because one detail was invalid. Please adjust and resend."
        if "draft" in text or "email" in text or "reply" in text:
            return "I couldn't draft that email yet."
        if "meeting" in text or "brief" in text or "prep" in text:
            return "I couldn't prepare that meeting brief yet."
        if "task" in text:
            return "I couldn't complete that task action yet."
        if "calendar" in text or "event" in text:
            return "I couldn't complete that calendar action yet."
        return "I couldn't complete that action yet."

    def _render_email_draft(self, payload: Dict[str, Any]) -> str:
        subject = " ".join(str(payload.get("subject") or "").split()).strip()
        body = str(payload.get("body") or "").strip()
        recipient = " ".join(str(payload.get("recipient") or "").split()).strip()

        if body:
            if self.user_name:
                body = re.sub(r"\[(?:your\s*name)\]", self.user_name, body, flags=re.IGNORECASE)
            else:
                body = re.sub(r"\[(?:your\s*name)\]", "", body, flags=re.IGNORECASE)

        lines: List[str] = []
        if subject:
            lines.append(f"Subject: {subject}")
        if recipient:
            lines.append(f"To: {recipient}")
        if body:
            if lines:
                lines.append("")
            lines.append(body)

        if lines:
            return "\n".join(lines).strip()
        return "I drafted that email, but the content came back empty."

    def _format_meeting_time(self, start_at: Optional[str], end_at: Optional[str]) -> str:
        if not start_at and not end_at:
            return ""

        def _parse(value: Optional[str]) -> Optional[datetime]:
            raw = (value or "").strip()
            if not raw:
                return None
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                return None

        start_dt = _parse(start_at)
        end_dt = _parse(end_at)

        if start_dt and end_dt:
            same_day = start_dt.date() == end_dt.date()
            if same_day:
                return (
                    f"{start_dt.strftime('%b %d, %Y')} "
                    f"{start_dt.strftime('%I:%M %p').lstrip('0')} - {end_dt.strftime('%I:%M %p').lstrip('0')}"
                )
            return (
                f"{start_dt.strftime('%b %d, %Y %I:%M %p').lstrip('0')} - "
                f"{end_dt.strftime('%b %d, %Y %I:%M %p').lstrip('0')}"
            )
        if start_dt:
            return start_dt.strftime("%b %d, %Y %I:%M %p").lstrip("0")
        if end_dt:
            return end_dt.strftime("%b %d, %Y %I:%M %p").lstrip("0")

        if start_at and end_at:
            return f"{start_at} - {end_at}"
        return start_at or end_at or ""

    def _render_meeting_brief(self, payload: Dict[str, Any]) -> str:
        subject = (payload.get("meeting_subject") or payload.get("event_id") or "Meeting").strip()
        summary = (payload.get("summary") or "").strip()
        start_at = payload.get("start_at")
        end_at = payload.get("end_at")
        location = (payload.get("location") or "").strip()
        participants_raw = payload.get("participants")

        def _clean_lines(values: Any, limit: int) -> List[str]:
            if not isinstance(values, list):
                return []
            out: List[str] = []
            for value in values:
                text = " ".join(str(value or "").split()).strip()
                if not text:
                    continue
                out.append(text)
                if len(out) >= limit:
                    break
            return out

        agenda = _clean_lines(payload.get("agenda"), 8)
        decisions = _clean_lines(payload.get("decisions"), 8)
        commitments = _clean_lines(payload.get("commitments"), 8)
        risks = _clean_lines(payload.get("risks"), 6)
        open_items = _clean_lines(payload.get("open_items"), 8)
        participants = _clean_lines(participants_raw, 8)

        lines: List[str] = [f"Meeting brief: {subject}"]
        when_line = self._format_meeting_time(start_at, end_at)
        if when_line:
            lines.append(f"When: {when_line}")
        if location:
            lines.append(f"Location: {location}")
        if participants:
            lines.append(f"Participants: {', '.join(participants)}")

        has_context_sections = any([decisions, commitments, risks, open_items])
        zero_counts_summary = bool(
            re.search(r"\b0\s+decisions?\b", summary.lower())
            and re.search(r"\b0\s+commitments?\b", summary.lower())
            and re.search(r"\b0\s+(active\s+)?risks?\b", summary.lower())
        )
        if summary and not zero_counts_summary:
            lines.append("")
            lines.append(summary)
        elif not has_context_sections:
            lines.append("")
            lines.append("No prior linked decisions, commitments, or risks found for this meeting yet.")

        def _append_section(title: str, items: List[str]) -> None:
            if not items:
                return
            lines.append("")
            lines.append(f"{title}:")
            for item in items:
                lines.append(f"- {item}")

        _append_section("Agenda", agenda)
        _append_section("Decisions", decisions)
        _append_section("Commitments", commitments)
        _append_section("Risks", risks)
        _append_section("Open items", open_items)

        return "\n".join(lines).strip()
    
    def create_pending_action(
        self,
        session_id: str,
        message_id: int,
        action_type: str,
        action_data: Dict[str, Any]
    ) -> ChatPendingAction:
        """Create a pending action for user approval."""
        action = ChatPendingAction(
            id=str(uuid.uuid4()),
            session_id=session_id,
            message_id=message_id,
            action_type=action_type,
            action_data=action_data,
            status="pending",
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action

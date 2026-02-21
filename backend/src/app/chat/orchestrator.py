"""
Chat Orchestrator

Main orchestration layer for AI Chat.
Routes messages through LLM, executes tools, manages state.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import uuid
import json
import logging
import time

from google.genai import types as genai_types
from sqlalchemy.orm import Session

from app.data.models import ChatSession, ChatPendingAction
from .context import ChatContextManager, ConversationState
from .tools import ChatToolRegistry, ToolResult
from app.services.genai_client import get_genai_client
from app.services.context_assembler import ContextAssembler
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.warm_cache import get_warm_cache_service
from app.services.chat_metrics import build_prompt_text, record_chat_model_metric
from app.security.prompt_sanitizer import detect_injection_patterns
from app.security.security_logger import log_injection_attempt
from core.llm.token_tracking import record_token_usage

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
    base_prompt = _load_prompt("chat_system").format(assistant_name=assistant_name)
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
        try:
            return await self._process_message_internal(session, user_message, mention_context=mention_context or {})
        except Exception as e:
            logger.error(f"Unexpected error in process_message: {e}", exc_info=True)
            return {
                "response": "I apologize, but I encountered an unexpected error. Please try again.",
                "pending_actions": [],
                "state": {}
            }

    async def _process_message_internal(
        self,
        session: ChatSession,
        user_message: str,
        mention_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal message processing with full error context."""
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
        has_explicit_entity_mentions = bool((mention_context or {}).get("entities"))
        tools_allowed_this_turn = bool(mode.use_tools and has_explicit_entity_mentions)
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
        layers, context_trace = assembler.build_layers_with_trace(
            task_context=task_context,
            include_task=include_task_layer,
            include_session=False,  # Chat history is already injected from DB messages.
            include_structured=include_structured_layer,
        )
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
            "reason": "requires_explicit_mentions" if not tools_allowed_this_turn else "mentions_present",
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

        messages = [{"role": "system", "content": mode.system_prompt}]
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

        pending_actions: List[Dict[str, Any]] = []
        tool_execution_records: List[Dict[str, Any]] = []
        tool_results: List[ToolResult] = []

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
                active_tools = mode.tools if tools_allowed_this_turn else []
                attempted_richness_retry = False

                while rounds < MAX_TOOL_ROUNDS:
                    response = await self._call_llm(
                        llm_messages,
                        active_tools,
                        session_id=session.id,
                        max_output_tokens=response_profile.max_output_tokens,
                    )
                    response_text = (response.get("content") or "").strip()
                    if response_text:
                        assistant_message = response_text
                        llm_messages.append({"role": "assistant", "content": response_text})

                    tool_calls = response.get("tool_calls", [])
                    if not tools_allowed_this_turn or not tool_calls:
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
                assistant_message = "I've handled what I can right now."

        has_action_activity = any(bool(item.get("action_tool")) for item in tool_execution_records)
        assistant_message = self._format_action_followup(
            reply=assistant_message,
            tool_outputs=tool_execution_records,
            deferred_actions=deferred_remaining if has_action_activity else [],
        )

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
            "state": state.to_dict()
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
        prompt_text = build_prompt_text(messages)
        tool_definitions_count = len(tools or [])
        safe_session_id = session_id or "unknown"

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
                "automatic_function_calling": genai_types.AutomaticFunctionCallingConfig(disable=True),
            }
            if tools:
                declarations = self._to_genai_function_declarations(tools)
                if declarations:
                    config_kwargs["tools"] = [genai_types.Tool(function_declarations=declarations)]

            started_at = time.perf_counter()
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(**config_kwargs),
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                try:
                    record_chat_model_metric(
                        db=self.db,
                        user_id=self.user_id,
                        session_id=safe_session_id,
                        model=model_name,
                        provider="genai",
                        path="native",
                        prompt_text=prompt_text,
                        latency_ms=latency_ms,
                        input_tokens=0,
                        output_tokens=0,
                        tool_definitions_count=tool_definitions_count,
                        tool_calls_count=0,
                        success=False,
                        error_type=exc.__class__.__name__,
                        response_chars=0,
                    )
                except Exception:
                    logger.warning("chat_metrics_record_failed user=%s", self.user_id, exc_info=True)
                raise

            latency_ms = int((time.perf_counter() - started_at) * 1000)

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
                record_token_usage(
                    db=self.db,
                    user_id=self.user_id,
                    model=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    operation="chat",
                )

            try:
                record_chat_model_metric(
                    db=self.db,
                    user_id=self.user_id,
                    session_id=safe_session_id,
                    model=model_name,
                    provider="genai",
                    path="native",
                    prompt_text=prompt_text,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    tool_definitions_count=tool_definitions_count,
                    tool_calls_count=len(tool_calls),
                    success=True,
                    response_chars=len((response.text or "").strip()),
                )
            except Exception:
                logger.warning("chat_metrics_record_failed user=%s", self.user_id, exc_info=True)

            return {
                "content": (response.text or "").strip(),
                "tool_calls": tool_calls,
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

        started_at = time.perf_counter()
        try:
            raw_text = await orchestrator.agenerate_text(
                prompt=prompt,
                system_prompt=system_content
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            try:
                record_chat_model_metric(
                    db=self.db,
                    user_id=self.user_id,
                    session_id=safe_session_id,
                    model="llm_orchestrator",
                    provider="orchestrator",
                    path="fallback",
                    prompt_text=prompt_text,
                    latency_ms=latency_ms,
                    input_tokens=0,
                    output_tokens=0,
                    tool_definitions_count=tool_definitions_count,
                    tool_calls_count=0,
                    success=False,
                    error_type=exc.__class__.__name__,
                    response_chars=0,
                )
            except Exception:
                logger.warning("chat_metrics_record_failed user=%s", self.user_id, exc_info=True)
            raise

        latency_ms = int((time.perf_counter() - started_at) * 1000)

        usage = orchestrator.get_token_usage()
        input_tokens = int(usage["input_tokens"] or 0)
        output_tokens = int(usage["output_tokens"] or 0)
        if usage['input_tokens'] > 0 or usage['output_tokens'] > 0:
            record_token_usage(
                db=self.db,
                user_id=self.user_id,
                model=usage['model'],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation="chat"
            )
        orchestrator.reset_token_usage()

        tool_calls = self._extract_tool_calls_from_response({}, raw_text)
        content = raw_text
        if tool_calls:
            import re as _re
            content = _re.sub(r'```json\s*.*?\s*```', '', content, flags=_re.DOTALL).strip()
            content = _re.sub(r'\{"tool_call"\s*:\s*\{[^}]+\}\s*\}', '', content).strip()

        try:
            record_chat_model_metric(
                db=self.db,
                user_id=self.user_id,
                session_id=safe_session_id,
                model=usage.get("model") or "llm_orchestrator",
                provider="orchestrator",
                path="fallback",
                prompt_text=prompt_text,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_definitions_count=tool_definitions_count,
                tool_calls_count=len(tool_calls),
                success=True,
                response_chars=len(content or ""),
            )
        except Exception:
            logger.warning("chat_metrics_record_failed user=%s", self.user_id, exc_info=True)

        return {
            "content": content,
            "tool_calls": tool_calls
        }

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
            return "I can't draft a reply right now."
        if any(token in lowered for token in {"meeting brief", "brief", "prep", "prepare"}):
            return "I can't prepare a meeting brief right now."
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
        completed: List[str] = []
        failed: List[str] = []
        deferred: List[str] = []

        def _append_unique(items: List[str], value: str) -> None:
            if value and value not in items:
                items.append(value)

        for item in tool_outputs:
            name = (item.get("name") or "").strip()
            is_action = bool(item.get("action_tool")) or name in ACTION_TOOL_NAMES
            if not is_action:
                continue

            label = self._action_title_from_output(item)
            if item.get("deferred"):
                _append_unique(deferred, label)
                continue
            if item.get("success"):
                _append_unique(completed, label)
                continue
            _append_unique(failed, label)

        for item in deferred_actions:
            name = (item.get("name") or "").strip()
            is_action = name in ACTION_TOOL_NAMES or self.tool_registry.is_action_tool(name)
            if not is_action:
                continue
            _append_unique(deferred, self._action_title_from_output(item))

        clauses: List[str] = []
        if completed:
            done = ", ".join([f'"{value}"' for value in completed])
            clauses.append(f"I've completed {done}.")
        if failed:
            failed_text = ", ".join([f'"{value}"' for value in failed])
            clauses.append(f"I hit an issue with {failed_text}.")
        if deferred:
            deferred_text = ", ".join([f'"{value}"' for value in deferred])
            clauses.append(f"Would you like me to continue with {deferred_text}?")

        if not clauses:
            return reply

        base = (reply or "").strip()
        if base:
            if base[-1] not in {".", "!", "?"}:
                base = f"{base}."
            return f"{base} {' '.join(clauses)}"
        return " ".join(clauses)
    
    def _format_tool_results(self, results: List[ToolResult]) -> str:
        """Format tool results into a human-readable response."""
        parts = []
        
        for result in results:
            if not result.success:
                parts.append(f"I encountered an issue: {result.error}")
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
                    parts.append(f"Draft ready: {result.data.get('subject')}")
                elif "agenda" in result.data and "meeting_subject" in result.data:
                    parts.append(f"Meeting brief ready: {result.data.get('meeting_subject')}")
                elif "summary" in result.data:
                    parts.append(str(result.data.get("summary")))
        
        return "\n".join(parts) if parts else "Done."
    
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

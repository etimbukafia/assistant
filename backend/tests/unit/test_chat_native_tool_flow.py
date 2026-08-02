import asyncio
import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_chat_orchestrator(monkeypatch):
    context_mod = types.ModuleType("app.chat.context")

    class ConversationState:
        def __init__(self):
            self.deferred_actions = []

        def to_dict(self):
            return {"deferred_actions": list(self.deferred_actions)}

    class ChatContextManager:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        def save_session_state(self, session, state):
            return None

    context_mod.ChatContextManager = ChatContextManager
    context_mod.ConversationState = ConversationState
    monkeypatch.setitem(sys.modules, "app.chat.context", context_mod)

    tools_mod = types.ModuleType("app.chat.tools")

    class ChatToolRegistry:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id
            self._tools = {}

    class ToolResult:
        def __init__(self, success=True, data=None, error=None, state_updates=None, pending_action=None):
            self.success = success
            self.data = data
            self.error = error
            self.state_updates = state_updates
            self.pending_action = pending_action

    tools_mod.ChatToolRegistry = ChatToolRegistry
    tools_mod.ToolResult = ToolResult
    monkeypatch.setitem(sys.modules, "app.chat.tools", tools_mod)

    models_mod = types.ModuleType("app.data.models")
    models_mod.ChatSession = type("ChatSession", (), {})
    models_mod.ChatPendingAction = type("ChatPendingAction", (), {})
    monkeypatch.setitem(sys.modules, "app.data.models", models_mod)

    context_assembler_mod = types.ModuleType("app.services.context_assembler")
    context_assembler_mod.ContextAssembler = type("ContextAssembler", (), {})
    monkeypatch.setitem(sys.modules, "app.services.context_assembler", context_assembler_mod)

    hot_cache_mod = types.ModuleType("app.services.hot_context_cache")
    hot_cache_mod.get_hot_context_cache_service = lambda: None
    monkeypatch.setitem(sys.modules, "app.services.hot_context_cache", hot_cache_mod)

    warm_cache_mod = types.ModuleType("app.services.warm_cache")
    warm_cache_mod.get_warm_cache_service = lambda: None
    monkeypatch.setitem(sys.modules, "app.services.warm_cache", warm_cache_mod)

    telemetry_mod = types.ModuleType("app.services.telemetry_writer")

    class _TelemetryWriter:
        def enqueue_chat_metric(self, **kwargs):
            return None

        def enqueue_token_usage(self, **kwargs):
            return None

    telemetry_mod.get_telemetry_writer = lambda: _TelemetryWriter()
    monkeypatch.setitem(sys.modules, "app.services.telemetry_writer", telemetry_mod)

    sanitizer_mod = types.ModuleType("app.security.prompt_sanitizer")
    sanitizer_mod.detect_injection_patterns = lambda text: []
    monkeypatch.setitem(sys.modules, "app.security.prompt_sanitizer", sanitizer_mod)

    security_logger_mod = types.ModuleType("app.security.security_logger")
    security_logger_mod.log_injection_attempt = lambda **kwargs: None
    monkeypatch.setitem(sys.modules, "app.security.security_logger", security_logger_mod)

    dag_mod = types.ModuleType("app.chat.dag_executor")
    dag_mod.DependencyAwareExecutor = type("DependencyAwareExecutor", (), {})
    dag_mod.NodeRunStatus = type("NodeRunStatus", (), {})
    monkeypatch.setitem(sys.modules, "app.chat.dag_executor", dag_mod)

    parser_mod = types.ModuleType("app.chat.planner_parser")
    parser_mod.PlanParseError = type("PlanParseError", (Exception,), {})
    parser_mod.parse_execution_plan = lambda raw: None
    monkeypatch.setitem(sys.modules, "app.chat.planner_parser", parser_mod)

    planner_models_mod = types.ModuleType("app.chat.planner_models")

    class ToolFamily:
        GENERATE_ARTIFACT = "generate_artifact"
        WRITE_TASK = "write_task"
        EXTERNAL_ACTION = "external_action"

    planner_models_mod.ToolFamily = ToolFamily
    monkeypatch.setitem(sys.modules, "app.chat.planner_models", planner_models_mod)

    tool_policy_mod = types.ModuleType("app.chat.tool_policy")
    tool_policy_mod.TOOL_FAMILY_BY_NAME = {}
    tool_policy_mod.ToolPolicyDecision = type("ToolPolicyDecision", (), {})
    tool_policy_mod.ToolPolicyEngine = type("ToolPolicyEngine", (), {})
    monkeypatch.setitem(sys.modules, "app.chat.tool_policy", tool_policy_mod)

    orchestrator_module = importlib.import_module("app.chat.orchestrator")
    orchestrator_module = importlib.reload(orchestrator_module)
    return orchestrator_module.ChatOrchestrator, orchestrator_module


class _FakeNativeToolLLM:
    def __init__(self, provider: str, model: str):
        self.config = SimpleNamespace(
            provider=provider,
            gemini_model=model if provider == "gemini" else None,
            anthropic_model=model if provider == "anthropic" else None,
            hf_model_id=None,
        )
        self.last_call = None
        self.reset_called = False

    def supports_tools(self) -> bool:
        return True

    async def agenerate_with_tools(self, messages, tools=None, system_prompt=None, max_output_tokens=300):
        self.last_call = {
            "messages": messages,
            "tools": tools,
            "system_prompt": system_prompt,
            "max_output_tokens": max_output_tokens,
        }
        return {
            "content": "Searching now.",
            "tool_calls": [
                {
                    "id": "tool-1",
                    "type": "function",
                    "function": {
                        "name": "search_emails",
                        "arguments": '{"query":"from:boss","limit":3}',
                    },
                }
            ],
        }

    async def agenerate_text(self, prompt, system_prompt=None):
        raise AssertionError("Native tool path should not fall back to agenerate_text")

    def get_token_usage(self):
        return {"input_tokens": 120, "output_tokens": 45, "model": self.config.gemini_model or self.config.anthropic_model}

    def reset_token_usage(self):
        self.reset_called = True


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("gemini", "gemini-2.5-flash-lite"),
        ("anthropic", "claude-sonnet-4-20250514"),
    ],
)
def test_call_llm_uses_native_tool_provider_flow(monkeypatch, provider, model):
    ChatOrchestrator, orchestrator_module = _load_chat_orchestrator(monkeypatch)
    fake_llm = _FakeNativeToolLLM(provider=provider, model=model)
    monkeypatch.setattr(orchestrator_module, "_get_chat_llm", lambda: fake_llm)

    orchestrator = ChatOrchestrator(db=MagicMock(), user_id="user-1", user_name="Etimbuk")
    orchestrator._enqueue_chat_metric = MagicMock()
    orchestrator._enqueue_token_usage = MagicMock()

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Find recent emails from my boss."},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_emails",
                "description": "Search emails",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    result = asyncio.run(
        orchestrator._call_llm(
            messages=messages,
            tools=tools,
            session_id="session-1",
            max_output_tokens=250,
        )
    )

    assert result["content"] == "Searching now."
    assert result["tool_calls"][0]["function"]["name"] == "search_emails"
    assert fake_llm.last_call is not None
    assert fake_llm.last_call["messages"] == messages
    assert fake_llm.last_call["tools"] == tools
    assert fake_llm.last_call["max_output_tokens"] == 250
    assert fake_llm.reset_called is True
    orchestrator._enqueue_token_usage.assert_called_once_with(
        user_id="user-1",
        model=model,
        input_tokens=120,
        output_tokens=45,
        operation="chat",
    )


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("gemini", "gemini-2.5-flash-lite"),
        ("anthropic", "claude-sonnet-4-20250514"),
    ],
)
def test_call_llm_native_tool_flow_is_generic_for_contact_tools(monkeypatch, provider, model):
    ChatOrchestrator, orchestrator_module = _load_chat_orchestrator(monkeypatch)
    fake_llm = _FakeNativeToolLLM(provider=provider, model=model)
    monkeypatch.setattr(orchestrator_module, "_get_chat_llm", lambda: fake_llm)

    orchestrator = ChatOrchestrator(db=MagicMock(), user_id="user-1", user_name="Etimbuk")
    orchestrator._enqueue_chat_metric = MagicMock()
    orchestrator._enqueue_token_usage = MagicMock()

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "What matters about Sarah right now?"},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_contact_brief",
                "description": "Get relationship brief",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "integer"},
                    },
                },
            },
        }
    ]
    fake_llm.last_call = None

    result = asyncio.run(
        orchestrator._call_llm(
            messages=messages,
            tools=tools,
            session_id="session-1",
            max_output_tokens=220,
        )
    )

    assert result["content"] == "Searching now."
    assert fake_llm.last_call is not None
    assert fake_llm.last_call["tools"] == tools

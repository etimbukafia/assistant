import asyncio
import importlib
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock


def _load_chat_orchestrator(monkeypatch, *, layers, tools_allowed=False, tool_result_data=None):
    context_mod = types.ModuleType("app.chat.context")

    class ConversationState:
        def __init__(self):
            self.deferred_actions = []
            self.current_contact_id = None
            self.current_thread_id = None
            self.current_event_id = None
            self.current_email_id = None
            self.current_task_id = None
            self.active_workflow = None
            self.workflow_data = None

        def to_dict(self):
            return {"deferred_actions": list(self.deferred_actions)}

    class ChatContextManager:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        def get_session_state(self, session):
            return ConversationState()

        def get_recent_messages(self, session_id):
            return []

        def build_prompt_context(self, session, state, context_type):
            return "Current context"

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
            self._tools = {"context_search": {}} if tools_allowed else {}

        def get_tool_definitions(self):
            if not tools_allowed:
                return []
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "context_search",
                        "description": "Search structured memory",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                            },
                        },
                    },
                }
            ]

        def execute_tool(self, tool_name, tool_args):
            return ToolResult(success=True, data=tool_result_data or {})

        def is_action_tool(self, tool_name):
            return False

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

    class ContextAssembler:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def build_layers_with_trace(self, **kwargs):
            return layers, {}

        def log_context_trace(self, trace, message):
            return None

    context_assembler_mod.ContextAssembler = ContextAssembler
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
        READ_CONTEXT = "read_context"
        GENERATE_ARTIFACT = "generate_artifact"
        WRITE_TASK = "write_task"
        EXTERNAL_ACTION = "external_action"

    planner_models_mod.ToolFamily = ToolFamily
    monkeypatch.setitem(sys.modules, "app.chat.planner_models", planner_models_mod)

    tool_policy_mod = types.ModuleType("app.chat.tool_policy")
    tool_policy_mod.TOOL_FAMILY_BY_NAME = {}

    class ToolPolicyDecision:
        def __init__(self, tools_allowed=False, allowed_families=None, reason="unit_test"):
            self.tools_allowed = tools_allowed
            self.allowed_families = set(allowed_families or [])
            self.reason = reason

        def allows_tool(self, tool_name):
            return self.tools_allowed

        def allows_family(self, family):
            return family in self.allowed_families

    class ToolPolicyEngine:
        def decide(self, user_message, mention_context):
            allowed_families = {ToolFamily.READ_CONTEXT} if tools_allowed else set()
            return ToolPolicyDecision(tools_allowed=tools_allowed, allowed_families=allowed_families)

    tool_policy_mod.ToolPolicyDecision = ToolPolicyDecision
    tool_policy_mod.ToolPolicyEngine = ToolPolicyEngine
    monkeypatch.setitem(sys.modules, "app.chat.tool_policy", tool_policy_mod)

    orchestrator_module = importlib.import_module("app.chat.orchestrator")
    orchestrator_module = importlib.reload(orchestrator_module)
    return orchestrator_module.ChatOrchestrator


def _make_layers(*, structured=None, contact=None):
    return SimpleNamespace(
        instruction="Layer instruction",
        task={},
        contact=contact or {},
        profile={},
        structured=structured or [],
    )


def _freshness_messages(messages):
    return [
        msg["content"]
        for msg in messages
        if msg.get("role") == "system" and "Freshness rule for this turn:" in str(msg.get("content") or "")
    ]


def _tool_messages(messages):
    return [msg for msg in messages if msg.get("role") == "tool"]


def test_process_message_includes_old_context_freshness_rule_for_old_structured_memory(monkeypatch):
    old_created_at = (datetime.now(timezone.utc) - timedelta(days=240)).isoformat()
    ChatOrchestrator = _load_chat_orchestrator(
        monkeypatch,
        layers=_make_layers(
            structured=[
                {
                    "type": "decision",
                    "content": "Approved the prior vendor workflow",
                    "created_at": old_created_at,
                    "status": "active",
                }
            ]
        ),
    )

    orchestrator = ChatOrchestrator(db=MagicMock(), user_id="user-1", user_name="Etimbuk")
    orchestrator.db.in_transaction.return_value = False
    orchestrator._enqueue_chat_metric = MagicMock()
    orchestrator._enqueue_token_usage = MagicMock()

    captured = {}

    async def _fake_call_llm(messages, tools=None, session_id=None, max_output_tokens=300):
        captured["messages"] = messages
        return {"content": "Based on the prior approval, this may have changed.", "tool_calls": [], "timing": {}}

    monkeypatch.setattr(orchestrator, "_call_llm", _fake_call_llm)

    session = SimpleNamespace(id="session-1", session_type="reflection")
    result = asyncio.run(orchestrator.process_message(session, "What should I keep in mind about that vendor?"))

    freshness = _freshness_messages(captured["messages"])
    assert result["response"] == "Based on the prior approval, this may have changed."
    assert len(freshness) == 1
    lowered = freshness[0].lower()
    assert "only add an age disclaimer" in lowered
    assert "approved the prior vendor workflow" in lowered


def test_process_message_skips_old_context_freshness_rule_for_recent_structured_memory(monkeypatch):
    recent_created_at = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    ChatOrchestrator = _load_chat_orchestrator(
        monkeypatch,
        layers=_make_layers(
            structured=[
                {
                    "type": "decision",
                    "content": "Approved the current vendor workflow",
                    "created_at": recent_created_at,
                    "status": "active",
                }
            ]
        ),
    )

    orchestrator = ChatOrchestrator(db=MagicMock(), user_id="user-2", user_name="Etimbuk")
    orchestrator.db.in_transaction.return_value = False
    orchestrator._enqueue_chat_metric = MagicMock()
    orchestrator._enqueue_token_usage = MagicMock()

    captured = {}

    async def _fake_call_llm(messages, tools=None, session_id=None, max_output_tokens=300):
        captured["messages"] = messages
        return {"content": "The current workflow was approved recently.", "tool_calls": [], "timing": {}}

    monkeypatch.setattr(orchestrator, "_call_llm", _fake_call_llm)

    session = SimpleNamespace(id="session-2", session_type="reflection")
    asyncio.run(orchestrator.process_message(session, "What should I keep in mind about that vendor?"))

    assert _freshness_messages(captured["messages"]) == []


def test_process_message_includes_old_context_freshness_rule_for_old_selected_entries(monkeypatch):
    ChatOrchestrator = _load_chat_orchestrator(monkeypatch, layers=_make_layers())

    orchestrator = ChatOrchestrator(db=MagicMock(), user_id="user-3", user_name="Etimbuk")
    orchestrator.db.in_transaction.return_value = False
    orchestrator._enqueue_chat_metric = MagicMock()
    orchestrator._enqueue_token_usage = MagicMock()

    captured = {}

    async def _fake_call_llm(messages, tools=None, session_id=None, max_output_tokens=300):
        captured["messages"] = messages
        return {"content": "Based on an older preference, this may have changed.", "tool_calls": [], "timing": {}}

    monkeypatch.setattr(orchestrator, "_call_llm", _fake_call_llm)

    session = SimpleNamespace(id="session-3", session_type="reflection")
    mention_context = {
        "mention_prefetch": {
            "selected_entries": [
                {
                    "type": "preference",
                    "content": "Prefers terse board updates",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=220)).isoformat(),
                }
            ]
        }
    }
    asyncio.run(orchestrator.process_message(session, "How should I phrase the update?", mention_context=mention_context))

    freshness = _freshness_messages(captured["messages"])
    assert len(freshness) == 1
    lowered = freshness[0].lower()
    assert "prefers terse board updates" in lowered
    assert "do not mention age" in lowered


def test_process_message_surfaces_missing_source_note_in_provenance_answer_path(monkeypatch):
    ChatOrchestrator = _load_chat_orchestrator(
        monkeypatch,
        layers=_make_layers(),
        tools_allowed=True,
        tool_result_data={
            "entries": [
                {
                    "type": "decision",
                    "content": "Approved the Q1 budget.",
                    "source_resolved": False,
                    "source_availability_note": "The source thread is no longer present in the inbox.",
                }
            ]
        },
    )

    orchestrator = ChatOrchestrator(db=MagicMock(), user_id="user-4", user_name="Etimbuk")
    orchestrator.db.in_transaction.return_value = False
    orchestrator._enqueue_chat_metric = MagicMock()
    orchestrator._enqueue_token_usage = MagicMock()

    captured_calls = []

    async def _fake_call_llm(messages, tools=None, session_id=None, max_output_tokens=300):
        captured_calls.append(messages)
        if len(captured_calls) == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tool-1",
                        "type": "function",
                        "function": {
                            "name": "context_search",
                            "arguments": '{"query":"where did that decision come from"}',
                        },
                    }
                ],
                "timing": {},
            }
        return {
            "content": "It came from a thread that's no longer present in your inbox.",
            "tool_calls": [],
            "timing": {},
        }

    monkeypatch.setattr(orchestrator, "_call_llm", _fake_call_llm)

    session = SimpleNamespace(id="session-4", session_type="reflection")
    mention_context = {
        "entities": [{"kind": "thread", "ref": "thread-1", "label": "Budget thread"}],
    }
    result = asyncio.run(
        orchestrator.process_message(
            session,
            "Where did that decision come from?",
            mention_context=mention_context,
        )
    )

    assert result["response"] == "It came from a thread that's no longer present in your inbox."
    assert len(captured_calls) == 2
    system_messages = [msg["content"] for msg in captured_calls[0] if msg.get("role") == "system"]
    assert any("source thread or message is no longer present" in str(msg).lower() for msg in system_messages)
    tool_messages = _tool_messages(captured_calls[1])
    assert any(
        "The source thread is no longer present in the inbox."
        in str(msg.get("response", {}).get("data", {}))
        for msg in tool_messages
    )

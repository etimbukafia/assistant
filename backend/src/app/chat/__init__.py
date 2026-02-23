"""
Chat package exports (lazy-loaded to avoid import-time side effects).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ChatContextManager",
    "ConversationState",
    "ChatOrchestrator",
    "ApprovalIntent",
    "ApprovalIntentKind",
    "PendingActionRef",
    "parse_approval_intent",
    "DependencyAwareExecutor",
    "DAGExecutionResult",
    "NodeExecutionRecord",
    "NodeRunStatus",
    "ExecutionPlan",
    "PlanNode",
    "PlanSubRequest",
    "ToolFamily",
    "PlanParseError",
    "parse_execution_plan",
    "ChatService",
    "ChatToolRegistry",
]


def __getattr__(name: str) -> Any:
    if name in {"ChatContextManager", "ConversationState"}:
        mod = import_module(".context", __name__)
        return getattr(mod, name)
    if name == "ChatOrchestrator":
        mod = import_module(".orchestrator", __name__)
        return getattr(mod, name)
    if name in {"ApprovalIntent", "ApprovalIntentKind", "PendingActionRef", "parse_approval_intent"}:
        mod = import_module(".approval_intent", __name__)
        return getattr(mod, name)
    if name in {"DependencyAwareExecutor", "DAGExecutionResult", "NodeExecutionRecord", "NodeRunStatus"}:
        mod = import_module(".dag_executor", __name__)
        return getattr(mod, name)
    if name in {"ExecutionPlan", "PlanNode", "PlanSubRequest", "ToolFamily"}:
        mod = import_module(".planner_models", __name__)
        return getattr(mod, name)
    if name in {"PlanParseError", "parse_execution_plan"}:
        mod = import_module(".planner_parser", __name__)
        return getattr(mod, name)
    if name == "ChatService":
        mod = import_module(".service", __name__)
        return getattr(mod, name)
    if name == "ChatToolRegistry":
        mod = import_module(".tools", __name__)
        return getattr(mod, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

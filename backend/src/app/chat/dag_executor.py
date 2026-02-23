"""
Dependency-aware execution runner for structured chat plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import inspect
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from .planner_models import ExecutionPlan, PlanNode


class NodeRunStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"


@dataclass
class NodeExecutionRecord:
    node_id: str
    status: NodeRunStatus
    output: Any = None
    error: Optional[str] = None


@dataclass
class DAGExecutionResult:
    records: List[NodeExecutionRecord] = field(default_factory=list)
    completed_node_ids: Set[str] = field(default_factory=set)
    failed_node_ids: Set[str] = field(default_factory=set)
    waiting_approval_node_ids: Set[str] = field(default_factory=set)
    blocked_node_ids: Set[str] = field(default_factory=set)

    @property
    def success(self) -> bool:
        return not self.failed_node_ids and not self.blocked_node_ids


NodeExecutor = Callable[[PlanNode], Any]


class DependencyAwareExecutor:
    """
    Execute ExecutionPlan nodes respecting DAG dependencies and approval state.
    """

    async def execute(
        self,
        plan: ExecutionPlan,
        execute_node: NodeExecutor,
        approved_node_ids: Optional[Set[str]] = None,
    ) -> DAGExecutionResult:
        approved = set(approved_node_ids or set())
        result = DAGExecutionResult()
        status_by_node: Dict[str, NodeRunStatus] = {}

        for layer in plan.topological_layers():
            for node in layer:
                dep_statuses = [status_by_node.get(dep) for dep in node.depends_on]
                if any(status != NodeRunStatus.SUCCESS for status in dep_statuses):
                    status_by_node[node.id] = NodeRunStatus.BLOCKED
                    result.blocked_node_ids.add(node.id)
                    result.records.append(
                        NodeExecutionRecord(
                            node_id=node.id,
                            status=NodeRunStatus.BLOCKED,
                            error="dependency_not_satisfied",
                        )
                    )
                    continue

                if node.requires_approval and node.id not in approved:
                    status_by_node[node.id] = NodeRunStatus.WAITING_APPROVAL
                    result.waiting_approval_node_ids.add(node.id)
                    result.records.append(
                        NodeExecutionRecord(
                            node_id=node.id,
                            status=NodeRunStatus.WAITING_APPROVAL,
                            error="approval_required",
                        )
                    )
                    continue

                try:
                    maybe_awaitable = execute_node(node)
                    output = await maybe_awaitable if inspect.isawaitable(maybe_awaitable) else maybe_awaitable
                    status_by_node[node.id] = NodeRunStatus.SUCCESS
                    result.completed_node_ids.add(node.id)
                    result.records.append(
                        NodeExecutionRecord(
                            node_id=node.id,
                            status=NodeRunStatus.SUCCESS,
                            output=output,
                        )
                    )
                except Exception as exc:  # pragma: no cover - covered by tests via error path
                    status_by_node[node.id] = NodeRunStatus.FAILED
                    result.failed_node_ids.add(node.id)
                    result.records.append(
                        NodeExecutionRecord(
                            node_id=node.id,
                            status=NodeRunStatus.FAILED,
                            error=str(exc),
                        )
                    )

        return result

"""
Structured planning models for dependency-aware chat execution.
"""

from __future__ import annotations

from collections import defaultdict, deque
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ToolFamily(str, Enum):
    """Controlled tool families for planner output."""

    READ_CONTEXT = "read_context"
    GENERATE_ARTIFACT = "generate_artifact"
    WRITE_TASK = "write_task"
    EXTERNAL_ACTION = "external_action"


class PlanClarification(BaseModel):
    """Clarification request emitted by planner when execution is blocked."""

    needed: bool = False
    question: Optional[str] = None

    @model_validator(mode="after")
    def _validate_question(self) -> "PlanClarification":
        if self.needed and not (self.question or "").strip():
            raise ValueError("clarification.question is required when clarification.needed=true")
        if not self.needed:
            self.question = None
        return self


class PlanSubRequest(BaseModel):
    """Atomic user ask split from original message."""

    id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    text: str = Field(min_length=1)
    blocking: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlanNode(BaseModel):
    """Executable node in the dependency graph."""

    id: str = Field(min_length=1)
    sub_request_id: str = Field(min_length=1)
    family: ToolFamily
    tool: str = Field(min_length=1)
    args: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    requires_approval: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize_approval(self) -> "PlanNode":
        # Write families require explicit approval by design.
        if self.family in {ToolFamily.WRITE_TASK, ToolFamily.EXTERNAL_ACTION}:
            self.requires_approval = True
        return self


class ExecutionPlan(BaseModel):
    """
    Structured plan used by the dependency-aware executor.
    """

    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    sub_requests: List[PlanSubRequest] = Field(min_length=1)
    nodes: List[PlanNode] = Field(min_length=1)
    clarification: PlanClarification = Field(default_factory=PlanClarification)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_graph(self) -> "ExecutionPlan":
        sub_request_ids = [item.id for item in self.sub_requests]
        if len(sub_request_ids) != len(set(sub_request_ids)):
            raise ValueError("sub_requests contains duplicate ids")
        sub_request_set = set(sub_request_ids)

        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("nodes contains duplicate ids")
        node_id_set = set(node_ids)

        for node in self.nodes:
            if node.sub_request_id not in sub_request_set:
                raise ValueError(
                    f"node '{node.id}' references unknown sub_request_id '{node.sub_request_id}'"
                )
            for dep in node.depends_on:
                if dep not in node_id_set:
                    raise ValueError(f"node '{node.id}' depends_on unknown node '{dep}'")
                if dep == node.id:
                    raise ValueError(f"node '{node.id}' cannot depend on itself")

        self._assert_acyclic()
        return self

    def _assert_acyclic(self) -> None:
        adjacency: Dict[str, List[str]] = defaultdict(list)
        indegree: Dict[str, int] = {node.id: 0 for node in self.nodes}

        for node in self.nodes:
            for dep in node.depends_on:
                adjacency[dep].append(node.id)
                indegree[node.id] += 1

        queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
        visited = 0

        while queue:
            current = queue.popleft()
            visited += 1
            for nxt in adjacency.get(current, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        if visited != len(self.nodes):
            raise ValueError("nodes dependency graph contains a cycle")

    def topological_layers(self) -> List[List[PlanNode]]:
        """
        Return DAG execution layers where each inner list can run in parallel.
        """
        node_by_id = {node.id: node for node in self.nodes}
        dependents: Dict[str, List[str]] = defaultdict(list)
        indegree: Dict[str, int] = {node.id: 0 for node in self.nodes}

        for node in self.nodes:
            for dep in node.depends_on:
                dependents[dep].append(node.id)
                indegree[node.id] += 1

        ready = sorted([node_id for node_id, degree in indegree.items() if degree == 0])
        layers: List[List[PlanNode]] = []
        visited = 0

        while ready:
            current_layer_ids = list(ready)
            ready = []
            layer_nodes = [node_by_id[node_id] for node_id in current_layer_ids]
            layers.append(layer_nodes)
            visited += len(current_layer_ids)

            for node_id in current_layer_ids:
                for dep in dependents.get(node_id, []):
                    indegree[dep] -= 1
                    if indegree[dep] == 0:
                        ready.append(dep)
            ready.sort()

        if visited != len(self.nodes):
            raise ValueError("dependency cycle detected")

        return layers

    def approval_node_ids(self) -> List[str]:
        """Return node ids that require approval before execution."""
        return [node.id for node in self.nodes if node.requires_approval]

    def has_write_actions(self) -> bool:
        """Whether the plan contains any write/external nodes."""
        return bool(self.approval_node_ids())

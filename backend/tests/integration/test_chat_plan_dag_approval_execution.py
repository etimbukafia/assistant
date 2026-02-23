import asyncio
import json

import pytest

from app.chat.approval_intent import PendingActionRef, parse_approval_intent, ApprovalIntentKind
from app.chat.dag_executor import DependencyAwareExecutor, NodeRunStatus
from app.chat.planner_parser import parse_execution_plan


@pytest.mark.integration
def test_multi_intent_plan_to_dag_to_text_approval_to_execution():
    """
    End-to-end integration of orchestration primitives:
    planner output -> validated plan -> DAG run -> approval intent -> resumed execution.
    """
    raw_plan = json.dumps(
        {
            "plan_id": "plan-e2e-1",
            "sub_requests": [
                {"id": "sr1", "intent": "search_tasks", "text": "Check existing tasks", "blocking": False},
                {"id": "sr2", "intent": "create_task", "text": "Create follow-up task", "blocking": False},
                {"id": "sr3", "intent": "draft_email", "text": "Draft email summary", "blocking": False},
            ],
            "nodes": [
                {
                    "id": "n1",
                    "sub_request_id": "sr1",
                    "family": "read_context",
                    "tool": "search_tasks",
                    "args": {"query": "forecast", "limit": 5},
                    "depends_on": [],
                },
                {
                    "id": "n2",
                    "sub_request_id": "sr2",
                    "family": "write_task",
                    "tool": "create_task",
                    "args": {"title": "Send revised forecast to Sarah"},
                    "depends_on": ["n1"],
                },
                {
                    "id": "n3",
                    "sub_request_id": "sr3",
                    "family": "generate_artifact",
                    "tool": "draft_email",
                    "args": {"intent": "share revised forecast status"},
                    "depends_on": ["n2"],
                },
            ],
            "clarification": {"needed": False, "question": None},
        }
    )

    plan = parse_execution_plan(raw_plan)
    executor = DependencyAwareExecutor()
    execution_log = []
    created_tasks = []

    def run_node(node):
        execution_log.append(node.id)
        if node.tool == "search_tasks":
            return {"count": 0, "tasks": []}
        if node.tool == "create_task":
            created_tasks.append(node.args.get("title"))
            return {
                "pending_action": {
                    "action_type": "create_task",
                    "action_data": {"title": node.args.get("title")},
                }
            }
        if node.tool == "draft_email":
            return {"subject": "Forecast update", "body": "Draft body"}
        return {"ok": True}

    # Pass 1: execute without approvals -> write node should wait, dependent should block.
    first = asyncio.run(executor.execute(plan=plan, execute_node=run_node, approved_node_ids=set()))
    first_status = {record.node_id: record.status for record in first.records}
    assert first_status["n1"] == NodeRunStatus.SUCCESS
    assert first_status["n2"] == NodeRunStatus.WAITING_APPROVAL
    assert first_status["n3"] == NodeRunStatus.BLOCKED
    assert created_tasks == []

    # User approves pending write actions via text.
    pending_refs = [PendingActionRef(id="n2", index=1, action_type="create_task")]
    approval = parse_approval_intent("approve all", pending_refs)
    assert approval.kind == ApprovalIntentKind.APPROVE_ALL
    assert approval.approve_ids == {"n2"}

    # Pass 2: resume with approved node ids.
    second = asyncio.run(executor.execute(plan=plan, execute_node=run_node, approved_node_ids=set(approval.approve_ids)))
    second_status = {record.node_id: record.status for record in second.records}
    assert second_status["n1"] == NodeRunStatus.SUCCESS
    assert second_status["n2"] == NodeRunStatus.SUCCESS
    assert second_status["n3"] == NodeRunStatus.SUCCESS

    assert created_tasks == ["Send revised forecast to Sarah"]
    assert second.success

import asyncio

from app.chat.dag_executor import DependencyAwareExecutor, NodeRunStatus
from app.chat.planner_models import ExecutionPlan


def _sample_plan():
    return ExecutionPlan.model_validate(
        {
            "sub_requests": [{"id": "sr1", "intent": "mixed", "text": "do things"}],
            "nodes": [
                {
                    "id": "n1",
                    "sub_request_id": "sr1",
                    "family": "read_context",
                    "tool": "get_contact_context",
                    "args": {},
                    "depends_on": [],
                },
                {
                    "id": "n2",
                    "sub_request_id": "sr1",
                    "family": "write_task",
                    "tool": "create_task",
                    "args": {},
                    "depends_on": ["n1"],
                },
                {
                    "id": "n3",
                    "sub_request_id": "sr1",
                    "family": "generate_artifact",
                    "tool": "draft_email",
                    "args": {},
                    "depends_on": ["n2"],
                },
            ],
        }
    )


def test_executor_waits_for_approval_and_blocks_dependents():
    plan = _sample_plan()
    executor = DependencyAwareExecutor()

    async def run_node(node):
        return {"node": node.id}

    result = asyncio.run(executor.execute(plan, run_node, approved_node_ids=set()))

    status = {record.node_id: record.status for record in result.records}
    assert status["n1"] == NodeRunStatus.SUCCESS
    assert status["n2"] == NodeRunStatus.WAITING_APPROVAL
    assert status["n3"] == NodeRunStatus.BLOCKED
    assert "n2" in result.waiting_approval_node_ids
    assert "n3" in result.blocked_node_ids


def test_executor_runs_after_approval():
    plan = _sample_plan()
    executor = DependencyAwareExecutor()

    def run_node(node):
        return {"ok": node.id}

    result = asyncio.run(executor.execute(plan, run_node, approved_node_ids={"n2"}))
    status = {record.node_id: record.status for record in result.records}

    assert status["n1"] == NodeRunStatus.SUCCESS
    assert status["n2"] == NodeRunStatus.SUCCESS
    assert status["n3"] == NodeRunStatus.SUCCESS
    assert result.success


def test_executor_marks_failures():
    plan = _sample_plan()
    executor = DependencyAwareExecutor()

    def run_node(node):
        if node.id == "n1":
            raise RuntimeError("boom")
        return {"ok": node.id}

    result = asyncio.run(executor.execute(plan, run_node, approved_node_ids={"n2"}))
    status = {record.node_id: record.status for record in result.records}
    assert status["n1"] == NodeRunStatus.FAILED
    assert status["n2"] == NodeRunStatus.BLOCKED
    assert status["n3"] == NodeRunStatus.BLOCKED

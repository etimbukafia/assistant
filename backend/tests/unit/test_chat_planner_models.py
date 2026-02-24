import json

import pytest

from app.chat.planner_models import ExecutionPlan, ToolFamily
from app.chat.planner_parser import PlanParseError, parse_execution_plan


def _valid_plan_dict():
    return {
        "sub_requests": [
            {"id": "sr1", "intent": "draft_email", "text": "Draft a reply for Sarah"}
        ],
        "nodes": [
            {
                "id": "n1",
                "sub_request_id": "sr1",
                "family": "read_context",
                "tool": "get_contact_context",
                "args": {"contact_ref": "@Sarah"},
                "depends_on": [],
            },
            {
                "id": "n2",
                "sub_request_id": "sr1",
                "family": "generate_artifact",
                "tool": "draft_email",
                "args": {"intent": "confirm timeline"},
                "depends_on": ["n1"],
            },
        ],
        "clarification": {"needed": False},
    }


def test_execution_plan_validates_and_builds_layers():
    plan = ExecutionPlan.model_validate(_valid_plan_dict())
    layers = plan.topological_layers()

    assert len(layers) == 2
    assert [node.id for node in layers[0]] == ["n1"]
    assert [node.id for node in layers[1]] == ["n2"]
    assert not plan.has_write_actions()


def test_write_family_auto_requires_approval():
    payload = _valid_plan_dict()
    payload["nodes"].append(
        {
            "id": "n3",
            "sub_request_id": "sr1",
            "family": ToolFamily.WRITE_TASK.value,
            "tool": "create_task",
            "args": {"title": "Follow up"},
            "depends_on": ["n2"],
        }
    )
    plan = ExecutionPlan.model_validate(payload)

    assert plan.has_write_actions()
    assert "n3" in plan.approval_node_ids()


def test_execution_plan_rejects_unknown_dependency():
    payload = _valid_plan_dict()
    payload["nodes"][1]["depends_on"] = ["missing"]

    with pytest.raises(Exception):
        ExecutionPlan.model_validate(payload)


def test_execution_plan_rejects_cycle():
    payload = _valid_plan_dict()
    payload["nodes"][0]["depends_on"] = ["n2"]  # creates n2 -> n1 -> n2 cycle

    with pytest.raises(Exception):
        ExecutionPlan.model_validate(payload)


def test_parse_execution_plan_from_json_fence():
    payload = _valid_plan_dict()
    raw = f"```json\n{json.dumps(payload)}\n```"
    plan = parse_execution_plan(raw)
    assert isinstance(plan, ExecutionPlan)
    assert plan.sub_requests[0].id == "sr1"


def test_parse_execution_plan_extracts_embedded_json():
    payload = _valid_plan_dict()
    raw = f"Planner result follows:\n{json.dumps(payload)}\nDone."
    plan = parse_execution_plan(raw)
    assert isinstance(plan, ExecutionPlan)
    assert len(plan.nodes) == 2


def test_parse_execution_plan_raises_on_invalid_payload():
    with pytest.raises(PlanParseError):
        parse_execution_plan("not-json and no object")


def test_parse_execution_plan_repairs_missing_sub_requests_from_nodes():
    payload = _valid_plan_dict()
    payload["sub_requests"] = []
    raw = f"```json\n{json.dumps(payload)}\n```"
    plan = parse_execution_plan(raw)

    assert isinstance(plan, ExecutionPlan)
    assert len(plan.sub_requests) == 1
    assert plan.sub_requests[0].id == "sr1"
    assert plan.nodes[0].sub_request_id == "sr1"

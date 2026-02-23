from app.chat.planner_models import ToolFamily
from app.chat.tool_policy import ToolPolicyEngine


def test_tool_policy_blocks_smalltalk():
    engine = ToolPolicyEngine()
    decision = engine.decide("hi", {"entities": [{"kind": "contact", "ref": "x"}]})
    assert not decision.tools_allowed
    assert decision.reason == "smalltalk_or_ack"


def test_tool_policy_requires_mentions():
    engine = ToolPolicyEngine()
    decision = engine.decide("draft an email for Sarah", {"entities": []})
    assert not decision.tools_allowed
    assert decision.reason == "requires_explicit_mentions"


def test_tool_policy_allows_relevant_families():
    engine = ToolPolicyEngine()
    decision = engine.decide(
        "draft a reply for @Sarah",
        {"entities": [{"kind": "contact", "ref": "Sarah"}]},
    )
    assert decision.tools_allowed
    assert ToolFamily.READ_CONTEXT in decision.allowed_families
    assert ToolFamily.GENERATE_ARTIFACT in decision.allowed_families
    assert decision.allows_tool("draft_email")
    assert decision.allows_tool("get_contact_context")
    assert not decision.allows_tool("create_task")


def test_tool_policy_adds_write_task_on_task_write_intent():
    engine = ToolPolicyEngine()
    decision = engine.decide(
        "create task for @Sarah to send revised forecast",
        {"entities": [{"kind": "contact", "ref": "Sarah"}]},
    )
    assert decision.tools_allowed
    assert ToolFamily.WRITE_TASK in decision.allowed_families
    assert decision.allows_tool("create_task")

from app.chat.orchestrator import ChatOrchestrator
from app.chat.planner_models import ToolFamily
from app.chat.tool_policy import ToolPolicyDecision
from datetime import datetime, timedelta, timezone


def test_memory_retrieval_instruction_prefers_resolved_contact_context(db_session):
    orchestrator = ChatOrchestrator(db_session, user_id="user-orch-1")
    decision = ToolPolicyDecision(
        tools_allowed=True,
        allowed_families={ToolFamily.READ_CONTEXT},
        reason="memory_reflection_context_query",
    )

    instruction = orchestrator._build_memory_retrieval_instruction(
        user_message="When last did we discuss the budget with Sarah Chen?",
        mention_context={
            "entities": [{"kind": "contact", "ref": "sarah@example.com", "label": "Sarah Chen"}],
            "entity_resolution": {"status": "resolved", "candidate": "Sarah Chen"},
        },
        policy_decision=decision,
    )

    lowered = instruction.lower()
    assert "retrieve before answering" in lowered
    assert "resolved anchors already in view" in lowered
    assert "contact brief, timeline, and signals" in lowered
    assert "authoritative" in lowered


def test_memory_retrieval_instruction_handles_unresolved_entities_with_fallback(db_session):
    orchestrator = ChatOrchestrator(db_session, user_id="user-orch-2")
    decision = ToolPolicyDecision(
        tools_allowed=True,
        allowed_families={ToolFamily.READ_CONTEXT},
        reason="memory_reflection_context_query",
    )

    instruction = orchestrator._build_memory_retrieval_instruction(
        user_message="Did we approve vendor X?",
        mention_context={
            "entity_resolution": {"status": "unresolved", "candidate": "vendor X"},
        },
        policy_decision=decision,
    )

    lowered = instruction.lower()
    assert "entity_search first" in lowered
    assert "topic/context retrieval" in lowered
    assert "vendor x" in lowered
    assert "do not pretend a direct match exists" in lowered
    assert "get_approval_history first" in lowered


def test_plan_builder_messages_prefer_memory_grounding_before_actions(db_session):
    orchestrator = ChatOrchestrator(db_session, user_id="user-orch-3")

    messages = orchestrator._build_plan_builder_messages(
        user_message="Draft a reply to Sarah about the vendor approval.",
        mention_context={"entity_resolution": {"status": "unresolved", "candidate": "Sarah"}},
        active_tools=[
            {"function": {"name": "entity_search", "description": "Resolve entities"}},
            {"function": {"name": "context_search", "description": "Search context"}},
            {"function": {"name": "get_approval_history", "description": "Retrieve approval history"}},
            {"function": {"name": "draft_email", "description": "Draft email"}},
            {"function": {"name": "get_contact_brief", "description": "Get contact brief"}},
            {"function": {"name": "get_contact_timeline", "description": "Get contact timeline"}},
            {"function": {"name": "get_contact_signals", "description": "Get contact signals"}},
        ],
    )

    planner_system = messages[0]["content"]
    planner_user = messages[1]["content"]

    assert "start with entity_search" in planner_system
    assert "prefer get_contact_brief, get_contact_timeline, and get_contact_signals" in planner_system
    assert "use get_approval_history for approval-status or approval-history questions" in planner_system.lower()
    assert "place read-context retrieval before any write or action node" in planner_system.lower()
    assert "unresolved entity" in planner_system.lower()
    assert "schedule retrieval nodes before action nodes" in planner_user.lower()


def test_memory_retrieval_instruction_uses_all_resolved_anchor_kinds(db_session):
    orchestrator = ChatOrchestrator(db_session, user_id="user-orch-4")
    decision = ToolPolicyDecision(
        tools_allowed=True,
        allowed_families={ToolFamily.READ_CONTEXT},
        reason="memory_reflection_mentions_read_context",
    )

    instruction = orchestrator._build_memory_retrieval_instruction(
        user_message="When last did we discuss board prep with Sarah Chen?",
        mention_context={
            "entities": [
                {"kind": "thread", "ref": "thread-1", "label": "Board Prep"},
                {"kind": "contact", "ref": "sarah@example.com", "label": "Sarah Chen"},
            ],
            "entity_resolution": {"status": "resolved", "candidate": "Sarah Chen"},
        },
        policy_decision=decision,
    )

    lowered = instruction.lower()
    assert "contact history question" in lowered
    assert "thread is already resolved" in lowered


def test_context_freshness_instruction_requires_old_retrieved_memory(db_session):
    orchestrator = ChatOrchestrator(db_session, user_id="user-orch-5")

    assert (
        orchestrator._build_context_freshness_instruction(
            mention_context={},
            contact_layer=None,
            structured_layer=None,
        )
        == ""
    )

    assert (
        orchestrator._build_context_freshness_instruction(
            mention_context={"entities": [{"kind": "contact", "ref": "1", "label": "Sarah Chen"}]},
            contact_layer=None,
            structured_layer=None,
        )
        == ""
    )

    recent_instruction = orchestrator._build_context_freshness_instruction(
        mention_context={"entities": [{"kind": "contact", "ref": "1", "label": "Sarah Chen"}]},
        contact_layer=None,
        structured_layer=[
            {
                "type": "decision",
                "content": "Approved the current budget",
                "created_at": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
            }
        ],
    )

    assert recent_instruction == ""

    instruction = orchestrator._build_context_freshness_instruction(
        mention_context={
            "mention_prefetch": {
                "selected_entries": [
                    {
                        "type": "preference",
                        "content": "Prefers terse vendor updates",
                        "created_at": (datetime.now(timezone.utc) - timedelta(days=240)).isoformat(),
                    }
                ]
            }
        },
        contact_layer={"name": "Sarah Chen"},
        structured_layer=None,
    )

    lowered = instruction.lower()
    assert "only add an age disclaimer" in lowered
    assert "do not mention age" in lowered
    assert "may have changed" in lowered
    assert "preference:prefers terse vendor updates" in lowered


def test_memory_retrieval_instruction_covers_provenance_for_missing_sources(db_session):
    orchestrator = ChatOrchestrator(db_session, user_id="user-orch-6")
    decision = ToolPolicyDecision(
        tools_allowed=True,
        allowed_families={ToolFamily.READ_CONTEXT},
        reason="memory_reflection_context_query",
    )

    instruction = orchestrator._build_memory_retrieval_instruction(
        user_message="Where did that decision come from?",
        mention_context={},
        policy_decision=decision,
    )

    lowered = instruction.lower()
    assert "asks where a memory came from" in lowered
    assert "source thread or message is no longer present" in lowered

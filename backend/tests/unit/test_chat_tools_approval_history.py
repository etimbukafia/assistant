from datetime import datetime, timezone
import importlib
import sys
import types

from app.data.models import ChatPendingAction, ChatSession, Message, Task, VaultProposal


def _load_chat_tool_registry():
    security_pkg = types.ModuleType("app.security")
    security_pkg.__path__ = []
    sys.modules["app.security"] = security_pkg

    tool_validator = types.ModuleType("app.security.tool_validator")

    class _ValidationResult:
        def __init__(self, sanitized_args):
            self.valid = True
            self.errors = []
            self.sanitized_args = sanitized_args

    tool_validator.validate_tool_args = lambda name, parameters, schema: _ValidationResult(parameters)
    sys.modules["app.security.tool_validator"] = tool_validator

    prompt_sanitizer = types.ModuleType("app.security.prompt_sanitizer")
    prompt_sanitizer.sanitize_with_detection = lambda value, **kwargs: (value, [])
    sys.modules["app.security.prompt_sanitizer"] = prompt_sanitizer

    security_logger = types.ModuleType("app.security.security_logger")
    security_logger.log_validation_failure = lambda **kwargs: None
    sys.modules["app.security.security_logger"] = security_logger

    module = importlib.import_module("app.chat.tools")
    return module.ChatToolRegistry


def test_get_approval_history_returns_structured_matches_for_tasks_and_actions(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-approval-1"
    message = Message(
        message_id="gmail-approval-1",
        thread_id="thread-approval-1",
        user_id=user_id,
        subject="Vendor X approval",
        sender="ops@example.com",
        recipient="me@example.com",
        body="Please approve Vendor X for onboarding.",
    )
    db_session.add(message)
    db_session.flush()

    task = Task(
        user_id=user_id,
        message_id=message.id,
        thread_id=message.thread_id,
        title="Approve Vendor X onboarding",
        description="Decision made to approve Vendor X.",
        status="approved",
        approved_at=datetime.now(timezone.utc),
    )
    db_session.add(task)

    session = ChatSession(id="session-approval-1", user_id=user_id, session_type="reflection", state={})
    db_session.add(session)
    db_session.flush()

    action = ChatPendingAction(
        id="action-approval-1",
        session_id=session.id,
        action_type="create_task",
        action_data={"title": "Vendor X legal review"},
        status="approved",
    )
    db_session.add(action)
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool("get_approval_history", {"query": "Vendor X"})

    assert result.success is True
    assert result.data["count"] >= 2
    assert result.data["approved_count"] >= 2
    assert any(item["source"] == "task" for item in result.data["items"])
    assert any(item["source"] == "chat_action" for item in result.data["items"])


def test_get_approval_history_includes_pending_and_rejected_when_requested(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-approval-2"
    session = ChatSession(id="session-approval-2", user_id=user_id, session_type="reflection", state={})
    db_session.add(session)
    db_session.flush()

    db_session.add(
        ChatPendingAction(
            id="action-approval-2",
            session_id=session.id,
            action_type="draft_reply",
            action_data={"email_subject": "Vendor Y follow-up"},
            status="pending",
        )
    )
    db_session.add(
        VaultProposal(
            user_id=user_id,
            proposal_type="update_note",
            proposed_data={"title": "Vendor Y"},
            diff_summary="Mark Vendor Y as rejected",
            status="rejected",
        )
    )
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool(
        "get_approval_history",
        {"query": "Vendor Y", "include_pending": True, "include_rejected": True},
    )

    assert result.success is True
    statuses = {item["status"] for item in result.data["items"]}
    assert "pending" in statuses
    assert "rejected" in statuses
    assert result.data["pending_count"] >= 1
    assert result.data["rejected_count"] >= 1


def test_get_approval_history_ignores_approval_stopwords_in_query(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-approval-3"
    db_session.add(
        VaultProposal(
            user_id=user_id,
            proposal_type="create_note",
            proposed_data={"title": "Vendor Z"},
            diff_summary="Approved Vendor Z note creation",
            status="approved",
        )
    )
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool("get_approval_history", {"query": "Did we approve Vendor Z?"})

    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["items"][0]["title"] == "Vendor Z"


def test_get_approval_history_rejects_vague_subjectless_queries(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-approval-4"
    db_session.add(
        VaultProposal(
            user_id=user_id,
            proposal_type="create_note",
            proposed_data={"title": "Vendor Q"},
            diff_summary="Approved Vendor Q note creation",
            status="approved",
        )
    )
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool("get_approval_history", {"query": "Did we approve this?"})

    assert result.success is False
    assert "specific approval subject" in result.error


def test_get_approval_history_preserves_single_character_disambiguators(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-approval-5"
    db_session.add(
        VaultProposal(
            user_id=user_id,
            proposal_type="create_note",
            proposed_data={"title": "Vendor X"},
            diff_summary="Approved Vendor X onboarding",
            status="approved",
        )
    )
    db_session.add(
        VaultProposal(
            user_id=user_id,
            proposal_type="create_note",
            proposed_data={"title": "Vendor Y"},
            diff_summary="Approved Vendor Y onboarding",
            status="approved",
        )
    )
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool("get_approval_history", {"query": "Vendor X"})

    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["items"][0]["title"] == "Vendor X"


def test_get_approval_history_orders_chat_actions_by_reviewed_at(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-approval-6"
    session = ChatSession(id="session-approval-6", user_id=user_id, session_type="reflection", state={})
    db_session.add(session)
    db_session.flush()

    db_session.add(
        ChatPendingAction(
            id="action-approval-6a",
            session_id=session.id,
            action_type="create_task",
            action_data={"title": "Vendor R approval"},
            status="approved",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            reviewed_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
    )
    db_session.add(
        ChatPendingAction(
            id="action-approval-6b",
            session_id=session.id,
            action_type="create_task",
            action_data={"title": "Vendor R approval"},
            status="approved",
            created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            reviewed_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool("get_approval_history", {"query": "Vendor R"})

    assert result.success is True
    assert result.data["latest_match"]["ref"] == "action-approval-6a"
    assert result.data["items"][0]["ref"] == "action-approval-6a"

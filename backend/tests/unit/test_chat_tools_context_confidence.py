import importlib
import sys
import types
from datetime import datetime, timedelta, timezone

from app.data.models import ContextEntry


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


def test_context_search_excludes_low_confidence_entries_unless_user_corrected(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-context-confidence-1"
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="decision",
            content="Low-confidence board decision",
            entity_type="global",
            entity_id=None,
            created_by="Teeks",
            status="active",
            classification_confidence=0.2,
            user_corrected=False,
        )
    )
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="decision",
            content="Corrected board decision",
            entity_type="global",
            entity_id=None,
            created_by="Teeks",
            status="active",
            classification_confidence=0.2,
            user_corrected=True,
        )
    )
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="decision",
            content="High-confidence board decision",
            entity_type="global",
            entity_id=None,
            created_by="Teeks",
            status="active",
            classification_confidence=0.9,
            user_corrected=False,
        )
    )
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool(
        "context_search",
        {"query": "board decision", "entity_type": "global", "types": ["decision"], "limit": 10},
    )

    assert result.success is True
    contents = [item["content"] for item in result.data["entries"]]
    assert "Low-confidence board decision" not in contents
    assert "Corrected board decision" in contents
    assert "High-confidence board decision" in contents


def test_context_search_includes_missing_source_metadata_for_thread_entries(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-context-confidence-2"
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="decision",
            content="Approved in the missing thread.",
            entity_type="thread",
            entity_id="thread-missing-1",
            created_by="You",
            status="active",
        )
    )
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool(
        "context_search",
        {"query": "approved", "entity_type": "thread", "entity_id": "thread-missing-1", "types": ["decision"], "limit": 10},
    )

    assert result.success is True
    entry = result.data["entries"][0]
    assert entry["source_resolved"] is False
    assert entry["source_availability_note"] == "The source thread is no longer present in the inbox."


def test_context_search_keeps_expired_decision_history_when_directly_relevant(db_session):
    ChatToolRegistry = _load_chat_tool_registry()
    user_id = "user-context-confidence-3"
    now = datetime.now(timezone.utc)
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="decision",
            content="Approved the board deck delay.",
            entity_type="global",
            entity_id=None,
            created_by="You",
            status="active",
            expires_at=now - timedelta(days=30),
            created_at=now - timedelta(days=240),
            updated_at=now - timedelta(days=240),
        )
    )
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="commitment",
            content="Send the board deck by Friday.",
            entity_type="global",
            entity_id=None,
            created_by="You",
            status="active",
            expires_at=now - timedelta(days=1),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
        )
    )
    db_session.commit()

    registry = ChatToolRegistry(db_session, user_id=user_id)
    result = registry.execute_tool(
        "context_search",
        {"query": "board deck delay", "entity_type": "global", "types": ["decision"], "limit": 10},
    )

    assert result.success is True
    contents = [item["content"] for item in result.data["entries"]]
    assert "Approved the board deck delay." in contents
    assert "Send the board deck by Friday." not in contents

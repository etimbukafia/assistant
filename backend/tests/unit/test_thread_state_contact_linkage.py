from datetime import datetime, timezone

import pytest

from app.data.models import Message, ThreadState
from app.services.thread_state import ThreadStateService


class _FakeBatchAIProcessor:
    def init_thread_state_batch(self, messages_data):
        return [
            {
                "summary": item["subject"],
                "needs_reply": True,
                "tasks": [],
                "decisions": [],
                "action_points": [],
            }
            for item in messages_data
        ]

    def update_thread_state_batch(self, batch_items):
        return [
            {
                "summary_update": item["thread_state"].get("summary") or "Updated thread",
                "needs_reply": False,
                "new_tasks": [],
                "new_decisions": [],
                "action_points": [],
            }
            for item in batch_items
        ]

    def record_and_reset_tokens(self, db, user_id, operation):
        return None


def test_process_messages_batch_sets_contact_and_participants_for_new_thread(db_session):
    message = Message(
        message_id="msg-batch-1",
        thread_id="thread-batch-1",
        user_id="user-batch-1",
        subject="Prep notes",
        sender="Sarah Chen <sarah@example.com>",
        recipient="EA <ea@example.com>, Exec <exec@example.com>",
        contact_id=42,
        body="Body",
        received_at=datetime.now(timezone.utc),
        processed=False,
    )
    db_session.add(message)
    db_session.commit()

    service = ThreadStateService(db_session, ai_processor=_FakeBatchAIProcessor())
    results = service.process_messages_batch([message])

    assert len(results) == 1
    thread_state = db_session.query(ThreadState).filter(ThreadState.thread_id == "thread-batch-1").first()
    assert thread_state is not None
    assert thread_state.user_id == "user-batch-1"
    assert thread_state.contact_id == 42
    assert thread_state.message_count == 1
    emails = {participant["email"] for participant in (thread_state.participants or [])}
    assert emails == {"sarah@example.com", "ea@example.com", "exec@example.com"}


def test_process_messages_batch_updates_existing_thread_metadata(db_session):
    db_session.add(
        ThreadState(
            thread_id="thread-batch-2",
            user_id="user-batch-2",
            summary="Open thread",
            message_count=1,
            participants=[{"email": "sarah@example.com", "name": "Sarah", "role": "sender", "contact_id": 7}],
        )
    )
    message = Message(
        message_id="msg-batch-2",
        thread_id="thread-batch-2",
        user_id="user-batch-2",
        subject="Re: Open thread",
        sender="Sarah Chen <sarah@example.com>",
        recipient="Chief of Staff <cos@example.com>",
        contact_id=7,
        body="Body",
        received_at=datetime.now(timezone.utc),
        processed=False,
    )
    db_session.add(message)
    db_session.commit()

    service = ThreadStateService(db_session, ai_processor=_FakeBatchAIProcessor())
    results = service.process_messages_batch([message])

    assert len(results) == 1
    thread_state = db_session.query(ThreadState).filter(ThreadState.thread_id == "thread-batch-2").first()
    assert thread_state.message_count == 2
    assert thread_state.last_message_id == message.id
    assert thread_state.contact_id == 7
    emails = {participant["email"] for participant in (thread_state.participants or [])}
    assert "cos@example.com" in emails


def test_get_or_create_thread_state_rejects_cross_user_thread_collision(db_session):
    db_session.add(
        ThreadState(
            thread_id="shared-thread-id",
            user_id="user-a",
            summary="Existing thread",
            message_count=1,
        )
    )
    db_session.commit()

    service = ThreadStateService(db_session, ai_processor=_FakeBatchAIProcessor())

    with pytest.raises(RuntimeError, match="ownership mismatch"):
        service.get_or_create_thread_state("shared-thread-id", user_id="user-b")

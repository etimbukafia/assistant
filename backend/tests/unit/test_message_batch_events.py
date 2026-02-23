from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.data.models import Base, Message
from app.processors.message import process_messages_batch


def _build_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return testing_session_local(), engine


def test_process_messages_batch_emits_message_processed_per_message():
    db, engine = _build_session()
    try:
        user_id = "user-123"
        m1 = Message(
            message_id="m-1",
            thread_id="thread-1",
            user_id=user_id,
            subject="Subject 1",
            sender="a@example.com",
            recipient="u@example.com",
            body="Body 1",
            received_at=datetime.now(timezone.utc),
            processed=False,
        )
        m2 = Message(
            message_id="m-2",
            thread_id="thread-2",
            user_id=user_id,
            subject="Subject 2",
            sender="b@example.com",
            recipient="u@example.com",
            body="Body 2",
            received_at=datetime.now(timezone.utc),
            processed=False,
        )
        db.add_all([m1, m2])
        db.commit()

        batch_results = [
            {
                "summary": "Summary 1",
                "needs_reply": True,
                "extracted_tasks": [{"title": "Task 1"}],
                "extracted_dates": [],
                "extracted_people": [],
                "extracted_decisions": [],
                "scheduling_intent": False,
            },
            {
                "summary": "Summary 2",
                "needs_reply": False,
                "extracted_tasks": [],
                "extracted_dates": [],
                "extracted_people": [],
                "extracted_decisions": [{"decision": "Dec"}],
                "scheduling_intent": False,
            },
        ]

        enqueue_calls = []

        class FakeThreadStateService:
            def __init__(self, _db, assistant_name="Donna"):
                self._db = _db
                self.assistant_name = assistant_name

            def process_messages_batch(self, _messages):
                return batch_results

        def capture_enqueue_task(*, task_type, payload, correlation_id=None, db=None):
            enqueue_calls.append(
                {
                    "task_type": task_type,
                    "payload": payload,
                    "correlation_id": correlation_id,
                    "db_is_set": db is not None,
                }
            )

        with patch("app.processors.message.ThreadStateService", FakeThreadStateService):
            with patch("app.processors.message.enqueue_task", side_effect=capture_enqueue_task):
                results = process_messages_batch(
                    message_ids=[m1.id, m2.id],
                    db=db,
                    user_id=user_id,
                    correlation_id="corr-1",
                )

        assert len(results) == 2
        db.refresh(m1)
        db.refresh(m2)
        assert m1.processed is True
        assert m2.processed is True

        processed_events = [
            c for c in enqueue_calls
            if c["task_type"] == "emit_event" and c["payload"].get("event_name") == "message_processed"
        ]
        assert len(processed_events) == 2
        emitted_ids = {evt["payload"]["event_payload"]["message_id"] for evt in processed_events}
        assert emitted_ids == {m1.id, m2.id}
    finally:
        db.close()
        engine.dispose()

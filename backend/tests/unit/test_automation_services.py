from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.automation.inbox_copilot import InboxCopilotService
from app.automation.meeting_prep import MeetingPrepService
from app.data.models import Base, CalendarEvent, ContextEntry, GmailAccount, Message, Task, ThreadState, UserSettings


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _make_settings(db, *, user_id: str = "user-1", calendar_connected: bool = False) -> UserSettings:
    settings = UserSettings(
        user_id=user_id,
        user_email="user@example.com",
        notification_email="user@example.com",
        calendar_ids=["primary"] if calendar_connected else [],
        connected_provider="google" if calendar_connected else "none",
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def test_inbox_copilot_needs_gmail_connection():
    db = _make_session()
    settings = _make_settings(db)

    service = InboxCopilotService(db=db, user_id=settings.user_id, settings=settings)

    summary = service.get_summary()

    assert summary["status"] == "needs_connection"
    assert summary["connectors"]["required"][0]["id"] == "gmail"
    assert summary["connectors"]["required"][0]["connected"] is False


def test_inbox_copilot_run_records_history():
    db = _make_session()
    settings = _make_settings(db)
    db.add(
        GmailAccount(
            email="user@example.com",
            user_id=settings.user_id,
            access_token="token",
            refresh_token="refresh",
        )
    )
    db.add(
        Message(
            message_id="m-1",
            thread_id="t-1",
            user_id=settings.user_id,
            subject="Board update",
            sender="ceo@example.com",
            recipient="user@example.com",
            body="Need a reply",
            received_at=datetime.now(timezone.utc),
            status="inbox",
        )
    )
    db.commit()
    message = db.query(Message).filter(Message.message_id == "m-1").first()
    db.add(
        ThreadState(
            thread_id="t-1",
            user_id=settings.user_id,
            subject="Board update",
            summary="Need reply on board update",
            needs_reply=True,
            message_count=1,
        )
    )
    db.add(
        Task(
            message_id=message.id,
            thread_id="t-1",
            user_id=settings.user_id,
            title="Reply to board update",
            status="approved",
        )
    )
    db.commit()

    service = InboxCopilotService(db=db, user_id=settings.user_id, settings=settings)
    service.update(enabled=True)

    summary = service.get_summary()
    run_result = service.run()

    assert summary["status"] == "drafts_only"
    assert summary["workload"]["reply_needed_threads"] == 1
    assert run_result["run"]["summary"]
    assert run_result["preview"]["next_thread"]["thread_id"] == "t-1"


def test_meeting_prep_running_and_uses_event_memory():
    db = _make_session()
    settings = _make_settings(db, calendar_connected=True)
    event = CalendarEvent(
        user_id=settings.user_id,
        title="Board prep",
        start_time=datetime.now(timezone.utc) + timedelta(hours=2),
        end_time=datetime.now(timezone.utc) + timedelta(hours=3),
        participants=[{"email": "sarah@example.com", "name": "Sarah"}],
        status="upcoming",
        external_event_id="evt-1",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    db.add(
        ContextEntry(
            user_id=settings.user_id,
            type="decision",
            content="We decided to delay the board deck.",
            entity_type="event",
            entity_id="evt-1",
            status="active",
        )
    )
    db.commit()

    service = MeetingPrepService(db=db, user_id=settings.user_id, settings=settings)
    service.update(enabled=True)

    summary = service.get_summary()
    run_result = service.run(event_id=str(event.id))

    assert summary["status"] == "running"
    assert summary["next_event"]["id"] == event.id
    assert run_result["brief"]["meeting_subject"] == "Board prep"
    assert "delay the board deck" in " ".join(run_result["brief"]["decisions"]).lower()

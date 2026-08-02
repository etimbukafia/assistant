from datetime import datetime, timedelta, timezone

from app.data.models import CalendarEvent, Contact, ContextEntry, Message, Task, ThreadState
from app.services.contact_brief import ContactBriefService
from app.services.contact_timeline import ContactTimelineService


def test_contact_brief_marks_recent_interaction_thread_resolution(db_session):
    user_id = "user-contact-source-1"
    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id=user_id,
        name="Sarah Chen",
        email="sarah@example.com",
        created_at=now,
        updated_at=now,
    )
    db_session.add(contact)
    db_session.flush()
    db_session.add(
        Message(
            user_id=user_id,
            message_id="gmail-contact-source-1",
            thread_id="thread-contact-source-1",
            sender="sarah@example.com",
            recipient="ea@example.com",
            subject="Board prep",
            body="Can you send the revised board prep summary?",
            summary="Board prep summary request.",
            received_at=now - timedelta(hours=2),
            contact_id=contact.id,
        )
    )
    db_session.commit()

    brief = ContactBriefService(db_session, user_id=user_id).get_contact_brief(contact.id)

    assert brief is not None
    assert brief["recent_interactions"][0]["thread_id"] == "thread-contact-source-1"
    assert brief["recent_interactions"][0]["thread_resolved"] is True


def test_contact_brief_thread_resolution_returns_false_for_missing_thread(db_session):
    service = ContactBriefService(db_session, user_id="user-contact-source-2")

    assert service._thread_ref_resolved("missing-thread") is False
    assert service._thread_ref_resolved(None) is None


def test_contact_timeline_marks_resolved_sources(db_session):
    user_id = "user-contact-source-3"
    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id=user_id,
        name="Mina Ade",
        email="mina@example.com",
        created_at=now,
        updated_at=now,
    )
    db_session.add(contact)
    db_session.flush()

    message = Message(
        user_id=user_id,
        message_id="gmail-contact-source-3",
        thread_id="thread-contact-source-3",
        sender="mina@example.com",
        recipient="ea@example.com",
        subject="Launch review",
        body="Let's review the launch timing.",
        summary="Launch timing review.",
        received_at=now - timedelta(days=1),
        contact_id=contact.id,
    )
    db_session.add(message)
    db_session.flush()

    db_session.add(
        ThreadState(
            user_id=user_id,
            thread_id="thread-contact-source-3",
            contact_id=contact.id,
            decisions=[{"decision": "Delay launch note.", "made_at": (now - timedelta(hours=12)).isoformat()}],
            updated_at=now - timedelta(hours=12),
            created_at=now - timedelta(days=2),
        )
    )
    db_session.add(
        Task(
            user_id=user_id,
            message_id=message.id,
            thread_id="thread-contact-source-3",
            title="Send revised plan",
            status="approved",
            deadline=now + timedelta(days=2),
            created_at=now - timedelta(hours=4),
            updated_at=now - timedelta(hours=4),
        )
    )
    db_session.add(
        CalendarEvent(
            user_id=user_id,
            title="Launch review sync",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
            participants=[{"email": "mina@example.com", "name": "Mina Ade"}],
            organizer="owner@example.com",
            status="upcoming",
            external_event_id="evt-contact-source-3",
        )
    )
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="insight",
            entity_type="contact",
            entity_id="mina@example.com",
            content="Trusted launch partner.",
            status="active",
            created_by="You",
            updated_at=now - timedelta(hours=3),
            created_at=now - timedelta(hours=3),
        )
    )
    db_session.commit()

    timeline = ContactTimelineService(db_session, user_id=user_id).get_contact_timeline(contact.id, limit=10)

    assert timeline is not None
    interaction = next(item for item in timeline if item["kind"] == "interaction")
    decision = next(item for item in timeline if item["kind"] == "decision")
    task = next(item for item in timeline if item["kind"] == "task")
    meeting = next(item for item in timeline if item["kind"] == "meeting")
    context_entry = next(item for item in timeline if item["kind"] == "insight")

    assert interaction["source_resolved"] is True
    assert decision["source_resolved"] is True
    assert task["source_resolved"] is True
    assert meeting["source_resolved"] is True
    assert context_entry["source_resolved"] is None


def test_contact_timeline_keeps_expired_decision_history(db_session):
    user_id = "user-contact-source-4"
    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id=user_id,
        name="Lena Hart",
        email="lena@example.com",
        created_at=now,
        updated_at=now,
    )
    db_session.add(contact)
    db_session.flush()
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="decision",
            entity_type="contact",
            entity_id="lena@example.com",
            content="Approved the original venue change.",
            status="active",
            created_by="You",
            expires_at=now - timedelta(days=15),
            updated_at=now - timedelta(days=220),
            created_at=now - timedelta(days=220),
        )
    )
    db_session.commit()

    timeline = ContactTimelineService(db_session, user_id=user_id).get_contact_timeline(contact.id, limit=10)

    assert timeline is not None
    decisions = [item["title"] for item in timeline if item["kind"] == "decision"]
    assert "Approved the original venue change." in decisions

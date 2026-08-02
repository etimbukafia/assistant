from datetime import datetime, timedelta, timezone

from app.data.models import CalendarEvent, Contact, ContextEntry, Message, Task, ThreadState
from app.services.contact_timeline import ContactTimelineService


def test_contact_timeline_service_normalizes_and_sorts_items(db_session):
    user_id = "user-contact-timeline-1"
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

    message = Message(
        user_id=user_id,
        message_id="gmail-contact-timeline-1",
        thread_id="thread-contact-timeline-1",
        sender="sarah@example.com",
        recipient="ea@example.com",
        subject="Launch update",
        body="Here is the latest launch update.",
        decrypted_body="Here is the latest launch update.",
        summary="Latest launch update shared.",
        needs_reply=True,
        received_at=now - timedelta(days=1),
        contact_id=contact.id,
    )
    db_session.add(message)
    db_session.flush()

    db_session.add(
        ThreadState(
            user_id=user_id,
            thread_id="thread-contact-timeline-1",
            contact_id=contact.id,
            decisions=[{"decision": "Delay the launch announcement.", "made_at": (now - timedelta(hours=12)).isoformat()}],
            updated_at=now - timedelta(hours=12),
            created_at=now - timedelta(days=2),
        )
    )
    db_session.add(
        Task(
            user_id=user_id,
            message_id=message.id,
            thread_id="thread-contact-timeline-1",
            title="Send revised deck",
            description="Send the updated deck before Friday.",
            status="approved",
            deadline=now + timedelta(days=2),
            created_at=now - timedelta(hours=6),
            updated_at=now - timedelta(hours=6),
        )
    )
    db_session.add(
        CalendarEvent(
            user_id=user_id,
            title="Prep sync",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
            participants=[{"email": "sarah@example.com", "name": "Sarah Chen"}],
            status="upcoming",
            external_event_id="evt-contact-timeline-1",
        )
    )
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="relationships",
            entity_type="contact",
            entity_id="sarah@example.com",
            content="High-trust operating partner.",
            importance_level="high",
            status="active",
            updated_at=now - timedelta(hours=2),
            created_at=now - timedelta(hours=2),
        )
    )
    db_session.commit()

    timeline = ContactTimelineService(db_session, user_id=user_id).get_contact_timeline(contact.id, limit=10)

    assert timeline is not None
    assert [item["kind"] for item in timeline[:3]] == ["task", "meeting", "relationships"]
    assert {item["kind"] for item in timeline} >= {"interaction", "decision", "task", "meeting", "relationships"}
    assert timeline[0]["title"] == "Send revised deck"
    interaction = next(item for item in timeline if item["kind"] == "interaction")
    task = next(item for item in timeline if item["kind"] == "task")
    decision = next(item for item in timeline if item["kind"] == "decision")
    meeting = next(item for item in timeline if item["kind"] == "meeting")
    assert interaction["detail"] == "Latest launch update shared."
    assert "Here is the latest launch update." not in (interaction["detail"] or "")
    assert task["detail"] and task["detail"].startswith("Due ")
    assert interaction["source_resolved"] is True
    assert task["source_resolved"] is True
    assert decision["source_resolved"] is True
    assert meeting["source_resolved"] is True


def test_contact_timeline_service_filters_risky_context_details(db_session):
    user_id = "user-contact-timeline-2"
    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id=user_id,
        name="Alex Morgan",
        email="alex@example.com",
        created_at=now,
        updated_at=now,
    )
    db_session.add(contact)
    db_session.flush()
    db_session.add_all(
        [
            ContextEntry(
                user_id=user_id,
                type="preferences",
                entity_type="contact",
                entity_id="alex@example.com",
                content="Raw preference text should not be exposed here.",
                importance_level="normal",
                status="active",
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            ),
            ContextEntry(
                user_id=user_id,
                type="relationships",
                entity_type="contact",
                entity_id="alex@example.com",
                content="Trusted partner on finance work.",
                linked_to="Sensitive linked detail that should not leave the service.",
                importance_level="high",
                status="active",
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(hours=1),
            ),
        ]
    )
    db_session.commit()

    timeline = ContactTimelineService(db_session, user_id=user_id).get_contact_timeline(contact.id, limit=10)

    assert timeline is not None
    assert {item["kind"] for item in timeline} == {"relationships"}
    assert timeline[0]["detail"] is None

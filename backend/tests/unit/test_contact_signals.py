from datetime import datetime, timedelta, timezone

from app.data.models import CalendarEvent, Contact, ContextEntry, Message
from app.services.contact_signals import ContactSignalsService


def test_contact_signals_service_builds_deterministic_signals(db_session):
    user_id = "user-contact-signals-1"
    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id=user_id,
        name="Priya Shah",
        email="priya@example.com",
        category="vip",
        created_at=now,
        updated_at=now,
    )
    db_session.add(contact)
    db_session.flush()

    db_session.add(
        Message(
            user_id=user_id,
            message_id="gmail-contact-signals-1",
            thread_id="thread-contact-signals-1",
            sender="priya@example.com",
            recipient="ea@example.com",
            subject="Board prep",
            body="Can you send the pre-read?",
            decrypted_body="Can you send the pre-read?",
            summary="Asked for the board pre-read.",
            needs_reply=True,
            received_at=now - timedelta(days=20),
            contact_id=contact.id,
        )
    )
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="commitment",
            entity_type="contact",
            entity_id="priya@example.com",
            content="Send Priya the pre-read.",
            importance_level="high",
            status="active",
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
        )
    )
    db_session.add(
        ContextEntry(
            user_id=user_id,
            type="decision",
            entity_type="contact",
            entity_id="priya@example.com",
            content="Lead with the investor update.",
            importance_level="normal",
            status="active",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
    )
    db_session.add(
        CalendarEvent(
            user_id=user_id,
            title="Past board sync",
            start_time=now - timedelta(days=10, hours=1),
            end_time=now - timedelta(days=10),
            participants=[{"email": "priya@example.com", "name": "Priya Shah"}],
            status="completed",
            external_event_id="evt-contact-signals-past",
        )
    )
    db_session.add(
        CalendarEvent(
            user_id=user_id,
            title="Upcoming board sync",
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, hours=1),
            participants=[{"email": "priya@example.com", "name": "Priya Shah"}],
            status="upcoming",
            external_event_id="evt-contact-signals-upcoming",
        )
    )
    db_session.commit()

    signals = ContactSignalsService(db_session, user_id=user_id).get_contact_signals(contact.id)

    assert signals is not None
    keys = {item["key"] for item in signals}
    assert keys >= {
        "overdue_follow_up",
        "unresolved_commitment",
        "upcoming_meeting_without_recent_interaction",
        "new_decision_since_last_meeting",
        "priority_marker",
    }


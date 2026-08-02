import os
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.data.models import CalendarEvent, Contact, ContactContext, ContextEntry, Message, Task, ThreadState
from app.services.contact_brief import ContactBriefService


def test_contact_brief_service_aggregates_contact_memory_and_evidence(db_session):
    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id="user-1",
        name="Sarah Chen",
        email="sarah@example.com",
        role="Chief of Staff",
        organization="Acme",
        notes="Executive sponsor for the Q2 launch.",
        category="vip",
        created_at=now,
        updated_at=now,
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    message = Message(
        message_id="msg-1",
        thread_id="thread-1",
        user_id="user-1",
        subject="Q2 launch timing",
        sender="Sarah Chen <sarah@example.com>",
        recipient="ea@example.com",
        contact_id=contact.id,
        body="Can we confirm launch timing this week?",
        received_at=now - timedelta(days=1),
        summary="Sarah wants launch timing confirmed.",
        needs_reply=True,
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    db_session.add(
        ThreadState(
            thread_id="thread-1",
            user_id="user-1",
            summary="Launch coordination thread",
            decisions=[{"decision": "Keep launch in late May", "made_at": (now - timedelta(days=2)).isoformat()}],
            needs_reply=True,
            message_count=3,
            contact_id=contact.id,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=1),
        )
    )
    db_session.add(
        Task(
            thread_id="thread-1",
            message_id=message.id,
            user_id="user-1",
            title="Confirm launch timing with Sarah",
            description="Send proposed launch date options.",
            task_type="follow_up",
            priority="high",
            status="approved",
            deadline=now + timedelta(days=2),
            created_at=now - timedelta(hours=20),
            updated_at=now - timedelta(hours=12),
        )
    )
    db_session.add(
        ContextEntry(
            user_id="user-1",
            type="preferences",
            content="Keep updates concise and include the exact decision needed.",
            entity_type="contact",
            entity_id="sarah@example.com",
            linked_to="Sarah Chen",
            created_by="You",
            importance_level="high",
            status="active",
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(days=4),
        )
    )
    db_session.add(
        ContextEntry(
            user_id="user-1",
            type="relationships",
            content="Primary executive partner for launch planning and board prep.",
            entity_type="contact",
            entity_id="sarah@example.com",
            linked_to="Sarah Chen",
            created_by="You",
            importance_level="high",
            status="active",
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
        )
    )
    db_session.add(
        ContextEntry(
            user_id="user-1",
            type="commitment",
            content="Share final launch date options by Thursday.",
            entity_type="contact",
            entity_id="sarah@example.com",
            linked_to="Sarah Chen",
            created_by="You",
            importance_level="normal",
            status="active",
            expires_at=now + timedelta(days=3),
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        )
    )
    db_session.add(
        CalendarEvent(
            user_id="user-1",
            title="Launch planning sync",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
            participants=[{"email": "sarah@example.com", "name": "Sarah Chen"}],
            organizer="sarah@example.com",
            status="upcoming",
            source="synced",
            provider="google",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        ContactContext(
            user_id="user-1",
            contact_email="sarah@example.com",
            contact_name="Sarah Chen",
            preferred_tone="formal",
            contact_metadata={
                "message_count": 12,
                "last_interaction_at": (now - timedelta(days=1)).isoformat(),
                "primary_channel": "email",
                "reply_rate": 0.75,
                "avg_response_latency_hours": 6.0,
            },
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=1),
        )
    )
    db_session.commit()

    brief = ContactBriefService(db_session, user_id="user-1").get_contact_brief(contact.id)

    assert brief is not None
    assert brief["contact"].name == "Sarah Chen"
    assert brief["summary"]["category"] == "vip"
    assert "Primary executive partner" in brief["summary"]["headline"]
    assert brief["stats"]["total_messages"] >= 1
    assert brief["stats"]["needs_reply_threads"] == 1
    assert brief["stats"]["reply_rate"] == 0.75
    assert brief["preferences"][0]["content"].startswith("Preferred tone:")
    assert any(item["source_type"] == "task" for item in brief["commitments"])
    assert any(item["decision"] == "Keep launch in late May" for item in brief["decisions"])
    assert brief["upcoming_events"][0]["title"] == "Launch planning sync"
    assert any(signal["key"] == "needs_reply" for signal in brief["signals"])
    assert brief["recent_interactions"][0]["thread_resolved"] is True


def test_contact_brief_service_returns_none_for_missing_contact(db_session):
    brief = ContactBriefService(db_session, user_id="user-1").get_contact_brief(99999)
    assert brief is None


def test_contact_brief_service_does_not_match_messages_by_email_substring(db_session):
    now = datetime.now(timezone.utc)
    target = Contact(
        user_id="user-1",
        name="Ann Lee",
        email="ann@example.com",
        created_at=now,
        updated_at=now,
    )
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    db_session.add_all(
        [
            Message(
                message_id="msg-exact",
                thread_id="thread-exact",
                user_id="user-1",
                subject="For Ann",
                sender="Ann <ann@example.com>",
                recipient="ea@example.com",
                contact_id=target.id,
                body="Exact contact message",
                received_at=now - timedelta(hours=3),
                created_at=now - timedelta(hours=3),
                updated_at=now - timedelta(hours=3),
            ),
            Message(
                message_id="msg-false-positive",
                thread_id="thread-other",
                user_id="user-1",
                subject="For Joann",
                sender="Joann <joann@example.com>",
                recipient="ea@example.com",
                body="Should not leak into Ann's brief",
                received_at=now - timedelta(hours=2),
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            ),
        ]
    )
    db_session.commit()

    brief = ContactBriefService(db_session, user_id="user-1").get_contact_brief(target.id)

    subjects = [item["subject"] for item in brief["recent_interactions"]]
    assert "For Ann" in subjects
    assert "For Joann" not in subjects
    assert brief["stats"]["total_messages"] == 1


def test_contact_brief_service_does_not_match_events_by_partial_name_or_mismatched_legacy_context(db_session):
    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id="user-1",
        name="Ann Lee",
        email="ann@example.com",
        created_at=now,
        updated_at=now,
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    db_session.add_all(
        [
            CalendarEvent(
                user_id="user-1",
                title="Exact attendee match",
                start_time=now + timedelta(days=1),
                end_time=now + timedelta(days=1, hours=1),
                participants=[{"email": "ann@example.com", "name": "Ann Lee"}],
                organizer="owner@example.com",
                status="upcoming",
                source="synced",
                provider="google",
                created_at=now,
                updated_at=now,
            ),
            CalendarEvent(
                user_id="user-1",
                title="Partial name false positive",
                start_time=now + timedelta(days=2),
                end_time=now + timedelta(days=2, hours=1),
                participants=[{"email": "other@example.com", "name": "Joann Lee"}],
                organizer="owner@example.com",
                status="upcoming",
                source="synced",
                provider="google",
                created_at=now,
                updated_at=now,
            ),
            ContactContext(
                user_id="user-1",
                contact_email="ann@example.com",
                contact_name="Different Person",
                notes="Legacy notes that should not attach.",
                preferred_tone="casual",
                contact_metadata={"primary_channel": "email"},
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=2),
            ),
        ]
    )
    db_session.commit()

    brief = ContactBriefService(db_session, user_id="user-1").get_contact_brief(contact.id)

    event_titles = [item["title"] for item in brief["upcoming_events"]]
    assert "Exact attendee match" in event_titles
    assert "Partial name false positive" not in event_titles
    assert brief["summary"]["manual_notes"] is None
    assert brief["summary"]["preferred_tone"] is None


def test_contact_brief_service_keeps_expired_decision_history_visible(db_session):
    now = datetime.now(timezone.utc)
    contact = Contact(
        user_id="user-1",
        name="Sarah Chen",
        email="sarah@example.com",
        created_at=now,
        updated_at=now,
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    db_session.add(
        ContextEntry(
            user_id="user-1",
            type="decision",
            content="Approved the older board deck delay.",
            entity_type="contact",
            entity_id="sarah@example.com",
            linked_to="Sarah Chen",
            created_by="You",
            status="active",
            expires_at=now - timedelta(days=20),
            created_at=now - timedelta(days=220),
            updated_at=now - timedelta(days=220),
        )
    )
    db_session.add(
        ContextEntry(
            user_id="user-1",
            type="commitment",
            content="Send the updated deck tomorrow.",
            entity_type="contact",
            entity_id="sarah@example.com",
            linked_to="Sarah Chen",
            created_by="You",
            status="active",
            expires_at=now - timedelta(days=1),
            created_at=now - timedelta(days=15),
            updated_at=now - timedelta(days=15),
        )
    )
    db_session.commit()

    brief = ContactBriefService(db_session, user_id="user-1").get_contact_brief(contact.id)

    assert brief is not None
    decisions = [item["decision"] for item in brief["decisions"]]
    commitments = [item["title"] for item in brief["commitments"]]
    assert "Approved the older board deck delay." in decisions
    assert "Send the updated deck tomorrow." not in commitments

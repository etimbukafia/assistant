from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.data.models import Contact, ContextEntry, DiaryEntryLink, Message
from app.superpowers.email_drafting import EmailDraftingService


def test_draft_includes_contact_brief_context_for_known_recipient(db_session):
    user_id = "user-draft-contact-1"
    contact = Contact(
        user_id=user_id,
        name="Sarah Chen",
        email="sarah@example.com",
        role="Chief of Staff",
        organization="Acme",
    )
    db_session.add(contact)
    db_session.flush()
    db_session.add_all(
        [
            ContextEntry(
                user_id=user_id,
                type="relationships",
                entity_type="contact",
                entity_id="sarah@example.com",
                content="Sarah expects concise executive-ready updates.",
                importance_level="high",
                status="active",
            ),
            ContextEntry(
                user_id=user_id,
                type="preferences",
                entity_type="contact",
                entity_id="sarah@example.com",
                content="Keep replies under five sentences.",
                importance_level="normal",
                status="active",
            ),
            ContextEntry(
                user_id=user_id,
                type="commitment",
                entity_type="contact",
                entity_id="sarah@example.com",
                content="Send the revised deck by Friday.",
                importance_level="normal",
                status="active",
            ),
            ContextEntry(
                user_id=user_id,
                type="decision",
                entity_type="contact",
                entity_id="sarah@example.com",
                content="We agreed to delay the launch announcement.",
                importance_level="normal",
                status="active",
            ),
            Message(
                user_id=user_id,
                message_id="gmail-draft-1",
                thread_id="thread-draft-1",
                sender="sarah@example.com",
                recipient="ea@example.com",
                subject="Launch update",
                body="Can you send me the revised deck by Friday?",
                decrypted_body="Can you send me the revised deck by Friday?",
                received_at=datetime.now(timezone.utc),
                contact_id=contact.id,
            ),
        ]
    )
    db_session.commit()

    service = EmailDraftingService(db_session, user_id=user_id)
    fake_llm = MagicMock()
    fake_llm.generate_text.return_value = "Hi Sarah,\n\nSharing the revised deck shortly.\n\nBest,\nEtimbuk"

    with patch("app.superpowers.email_drafting._get_drafting_llm", return_value=fake_llm):
        result = service.draft(
            subject="Launch update",
            recipient="sarah@example.com",
            thread_id="thread-draft-1",
            sender_name="Etimbuk",
            user_request="confirm the revised deck will arrive by Friday",
        )

    prompt = fake_llm.generate_text.call_args.kwargs["prompt"]
    assert "contact_briefs" not in result
    assert all(entry.get("entity_type") != "contact" for entry in result["context_entries"])
    assert "Known contact briefs" in prompt
    assert "Send the revised deck by Friday." in prompt
    assert "We agreed to delay the launch announcement." in prompt


def test_recent_awareness_entries_exclude_forgotten_memories(db_session):
    user_id = "user-draft-contact-2"
    db_session.add_all(
        [
            ContextEntry(
                user_id=user_id,
                type="decision",
                entity_type="thread",
                entity_id="thread-aware-1",
                content="Forgotten recent decision",
                status="forgotten",
                created_by="You",
            ),
            ContextEntry(
                user_id=user_id,
                type="commitment",
                entity_type="thread",
                entity_id="thread-aware-1",
                content="Active recent commitment",
                status="active",
                created_by="You",
            ),
        ]
    )
    db_session.commit()

    service = EmailDraftingService(db_session, user_id=user_id)
    rows = service._query_recent_awareness_entries(thread_ref="thread-aware-1", message_ref=None)

    contents = [row.content for row in rows]
    assert "Active recent commitment" in contents
    assert "Forgotten recent decision" not in contents


def test_thread_entity_discovery_ignores_forgotten_thread_memory_links(db_session):
    user_id = "user-draft-contact-3"
    entry = ContextEntry(
        user_id=user_id,
        type="decision",
        entity_type="thread",
        entity_id="thread-forgotten-1",
        content="Old thread memory",
        status="forgotten",
        created_by="You",
    )
    db_session.add(entry)
    db_session.flush()
    db_session.add_all(
        [
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="thread",
                entity_id="thread-forgotten-1",
                display_name="Thread forgotten",
                source="user",
            ),
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="contact",
                entity_id="ally@example.com",
                display_name="Ally",
                source="user",
            ),
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="event",
                entity_id="event-1",
                display_name="Board Review",
                source="user",
            ),
        ]
    )
    db_session.commit()

    service = EmailDraftingService(db_session, user_id=user_id)
    related = service._discover_one_hop_entities(
        thread_ref="thread-forgotten-1",
        source_message=None,
        recipient_email=None,
    )

    assert related["contacts"] == []
    assert related["events"] == []

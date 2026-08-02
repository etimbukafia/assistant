from datetime import datetime, timezone

from app.data.models import Contact, ContactContext, ThreadState
from app.services.contact_linking import ContactLinker


def test_contact_linker_does_not_resolve_from_recipient_when_sender_unknown(db_session):
    contact = Contact(
        user_id="user-link-1",
        name="Sarah Chen",
        email="sarah@example.com",
    )
    db_session.add(contact)
    db_session.commit()

    linker = ContactLinker(db_session, user_id="user-link-1")
    resolved = linker.resolve_message_contact_id(
        sender_value="Unknown Sender <unknown@example.com>",
        recipient_value="Sarah Chen <sarah@example.com>",
    )

    assert resolved is None


def test_contact_linker_does_not_resolve_exact_name_without_email_match(db_session):
    contact = Contact(
        user_id="user-link-2",
        name="Sarah Chen",
        email=None,
    )
    db_session.add(contact)
    db_session.commit()

    linker = ContactLinker(db_session, user_id="user-link-2")
    resolved = linker.resolve_message_contact_id(
        sender_value="Sarah Chen",
        recipient_value=None,
    )

    assert resolved is None


def test_contact_linker_does_not_resolve_legacy_alias_to_canonical_contact(db_session):
    contact = Contact(
        user_id="user-link-3",
        name="Sarah Chen",
        email="sarah@example.com",
    )
    db_session.add(contact)
    db_session.flush()
    db_session.add(
        ContactContext(
            user_id="user-link-3",
            contact_email="sarah@example.com",
            contact_name="Sarah Chen",
            aliases=["sc", "Sarah C"],
        )
    )
    db_session.commit()

    linker = ContactLinker(db_session, user_id="user-link-3")
    resolved = linker.resolve_message_contact_id(
        sender_value="Sarah C",
        recipient_value=None,
    )

    assert resolved is None


def test_contact_linker_rejects_spoofed_display_name_when_email_mismatches(db_session):
    contact = Contact(
        user_id="user-link-3b",
        name="Sarah Chen",
        email="sarah@example.com",
    )
    db_session.add(contact)
    db_session.commit()

    linker = ContactLinker(db_session, user_id="user-link-3b")
    resolved = linker.resolve_message_contact_id(
        sender_value="Sarah Chen <evil@example.com>",
        recipient_value=None,
    )

    assert resolved is None


def test_contact_linker_scopes_thread_link_to_user(db_session):
    contact = Contact(
        user_id="user-link-4",
        name="Jordan Lee",
        email="jordan@example.com",
    )
    db_session.add(contact)
    db_session.flush()
    thread_state = ThreadState(
        thread_id="thread-link-1",
        user_id="user-link-4",
        subject="Status",
        message_count=1,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(thread_state)
    db_session.commit()

    linker = ContactLinker(db_session, user_id="different-user")
    linker.link_thread_state("thread-link-1", contact.id)

    stored = db_session.query(ThreadState).filter(ThreadState.thread_id == "thread-link-1").first()
    assert stored.contact_id is None

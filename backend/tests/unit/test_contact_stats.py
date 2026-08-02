from app.data.models import Contact, ContactContext
from app.services.contact_stats import increment_message_count


def test_increment_message_count_does_not_create_legacy_context_without_canonical_contact(db_session):
    increment_message_count(
        db_session,
        user_id="user-stats-1",
        contact_email="unknown@example.com",
    )

    stored = db_session.query(ContactContext).filter(
        ContactContext.user_id == "user-stats-1",
        ContactContext.contact_email == "unknown@example.com",
    ).first()
    assert stored is None


def test_increment_message_count_creates_legacy_context_for_existing_canonical_contact(db_session):
    db_session.add(
        Contact(
            user_id="user-stats-2",
            name="Known Contact",
            email="known@example.com",
        )
    )
    db_session.commit()

    increment_message_count(
        db_session,
        user_id="user-stats-2",
        contact_email="known@example.com",
    )

    stored = db_session.query(ContactContext).filter(
        ContactContext.user_id == "user-stats-2",
        ContactContext.contact_email == "known@example.com",
    ).first()
    assert stored is not None
    assert stored.contact_metadata["message_count"] == 1

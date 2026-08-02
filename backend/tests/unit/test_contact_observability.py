import logging

from app.data.models import Contact
from app.services.contact_brief import ContactBriefService
from app.services.contact_linking import ContactLinker
from app.services.contact_signals import ContactSignalsService


def test_contact_brief_logs_metric_with_consumer(db_session, caplog):
    contact = Contact(user_id="user-obsv-1", name="Alice", email="alice@example.com")
    db_session.add(contact)
    db_session.commit()

    with caplog.at_level(logging.INFO, logger="app.services.contact_observability"):
        brief = ContactBriefService(db_session, user_id="user-obsv-1").get_contact_brief(contact.id, consumer="chat")

    assert brief is not None
    assert "contact_brief_metric" in caplog.text
    assert "consumer=chat" in caplog.text
    assert f"contact_id={contact.id}" in caplog.text


def test_contact_linker_logs_exact_email_resolution(db_session, caplog):
    contact = Contact(user_id="user-obsv-2", name="Alice", email="alice@example.com")
    db_session.add(contact)
    db_session.commit()

    linker = ContactLinker(db_session, user_id="user-obsv-2")
    with caplog.at_level(logging.INFO, logger="app.services.contact_observability"):
        resolved = linker.resolve_message_contact_id(
            sender_value="Alice <alice@example.com>",
            recipient_value="ea@example.com",
            source="gmail_backfill",
        )

    assert resolved == contact.id
    assert "contact_linkage_metric" in caplog.text
    assert "source=gmail_backfill" in caplog.text
    assert "matched=True" in caplog.text
    assert "resolution_method=email_exact" in caplog.text


def test_contact_signals_logs_signal_counts(db_session, caplog):
    contact = Contact(user_id="user-obsv-3", name="VIP Contact", email="vip@example.com", category="vip")
    db_session.add(contact)
    db_session.commit()

    with caplog.at_level(logging.INFO, logger="app.services.contact_observability"):
        signals = ContactSignalsService(db_session, user_id="user-obsv-3").get_contact_signals(contact.id, consumer="contacts_api")

    assert signals is not None
    assert any(item.get("key") == "priority_marker" for item in signals)
    assert "contact_signals_metric" in caplog.text
    assert "consumer=contacts_api" in caplog.text

import asyncio
from datetime import datetime, timezone

from app.data.models import Contact, ContextEntry, DiaryEntryLink, Message, Notification
from app.jobs.worker import handle_classify_context_capture


def test_handle_classify_context_capture_applies_low_confidence_fallback(db_session, monkeypatch):
    from app.infra import database as database_module
    from sqlalchemy.orm import sessionmaker

    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.flush()

    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Possible risk with vendor timing.",
        raw_text="Possible risk with vendor timing.",
        entity_type="contact",
        entity_id=str(contact.id),
        linked_to="Sarah",
        classification_status="pending",
        user_corrected=False,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add(entry)
    db_session.commit()

    class _Result:
        category = "risk"
        confidence = 0.42
        rationale = "Potential issue, but wording is tentative."
        uncertain = True

    invalidations = {"count": 0}

    monkeypatch.setattr(
        "app.services.context_capture_classifier.classify_context_capture",
        lambda entry: _Result(),
    )
    monkeypatch.setattr(
        "app.jobs.worker.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: invalidations.__setitem__("count", invalidations["count"] + 1),
    )
    session_factory = sessionmaker(bind=db_session.bind, autocommit=False, autoflush=False)
    monkeypatch.setattr(database_module, "SessionLocal", session_factory)

    asyncio.run(
        handle_classify_context_capture(
            task_id=1,
            task_type="classify_context_capture",
            payload={"entry_id": entry.id, "user_id": "user-capture-1"},
            correlation_id="corr-1",
        )
    )

    db_session.refresh(entry)
    notification = db_session.query(Notification).filter(Notification.user_id == "user-capture-1").first()

    assert entry.type == "insight"
    assert entry.classification_status == "classified"
    assert entry.classification_confidence == 0.42
    assert entry.classification_suggested_type == "risk"
    assert notification is not None
    assert notification.title == "Saved as Insight for Sarah"
    assert invalidations["count"] == 1


def test_handle_classify_context_capture_does_not_override_user_correction(db_session, monkeypatch):
    from app.infra import database as database_module
    from sqlalchemy.orm import sessionmaker

    entry = ContextEntry(
        user_id="user-capture-1",
        type="decision",
        content="Sarah approved vendor X.",
        raw_text="Sarah approved vendor X.",
        entity_type="global",
        entity_id=None,
        linked_to=None,
        classification_status="user_corrected",
        user_corrected=True,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add(entry)
    db_session.commit()

    called = {"count": 0}

    def _unexpected(_entry):
        called["count"] += 1
        raise AssertionError("classifier should not run")

    monkeypatch.setattr("app.services.context_capture_classifier.classify_context_capture", _unexpected)
    session_factory = sessionmaker(bind=db_session.bind, autocommit=False, autoflush=False)
    monkeypatch.setattr(database_module, "SessionLocal", session_factory)

    asyncio.run(
        handle_classify_context_capture(
            task_id=1,
            task_type="classify_context_capture",
            payload={"entry_id": entry.id, "user_id": "user-capture-1"},
            correlation_id="corr-2",
        )
    )

    db_session.refresh(entry)
    assert called["count"] == 0
    assert entry.type == "decision"


def test_handle_classify_context_capture_attaches_high_confidence_secondary_links(db_session, monkeypatch):
    from app.infra import database as database_module
    from sqlalchemy.orm import sessionmaker

    contact = Contact(user_id="user-capture-1", name="Priya", email="priya@example.com")
    message = Message(
        user_id="user-capture-1",
        message_id="msg-456",
        thread_id="thread-456",
        sender="priya@example.com",
        recipient="ea@example.com",
        subject="Vendor follow-up",
        body="Please follow up.",
        received_at=datetime.now(timezone.utc),
        processed=False,
    )
    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Need to follow up with Priya on vendor X.",
        raw_text="Need to follow up with Priya on vendor X.",
        entity_type="global",
        entity_id=None,
        linked_to=None,
        classification_status="pending",
        user_corrected=False,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add_all([contact, message, entry])
    db_session.commit()

    class _Result:
        category = "commitment"
        confidence = 0.93
        rationale = "Explicit follow-up obligation."
        uncertain = False
        secondary_links = [
            {"entity_type": "contact", "entity_id": str(contact.id), "display_name": "Priya"},
            {"entity_type": "message", "entity_id": "msg-456", "display_name": "Vendor follow-up"},
        ]

    monkeypatch.setattr(
        "app.services.context_capture_classifier.classify_context_capture",
        lambda entry: _Result(),
    )
    monkeypatch.setattr("app.jobs.worker.cache_coordinator.invalidate_from_context_entry", lambda *args, **kwargs: None)
    session_factory = sessionmaker(bind=db_session.bind, autocommit=False, autoflush=False)
    monkeypatch.setattr(database_module, "SessionLocal", session_factory)

    asyncio.run(
        handle_classify_context_capture(
            task_id=2,
            task_type="classify_context_capture",
            payload={"entry_id": entry.id, "user_id": "user-capture-1"},
            correlation_id="corr-3",
        )
    )

    db_session.refresh(entry)
    links = db_session.query(DiaryEntryLink).filter(DiaryEntryLink.entry_id == entry.id).all()
    assert entry.type == "commitment"
    assert entry.classification_suggested_type is None
    assert {(link.entity_type, link.entity_id) for link in links} == {
        ("contact", str(contact.id)),
        ("message", "msg-456"),
    }
    assert {link.source for link in links} == {"teeks"}

from datetime import datetime, timezone, timedelta

from app.data.models import CalendarEvent, Contact, ContextEntry, DiaryEntryLink, Message, Task, TaskQueue
from app.routes.v1.vault import (
    _to_context_capture_response,
    create_context_capture,
    update_context_entry,
    delete_context_capture_link,
    delete_context_entry,
)
from app.data.schemas import ContextCaptureCreate, ContextCaptureScopeType, ContextEntryStatus, DiaryEntryLinkSchema, ContextCaptureUpdate, ContextType
from app.security.auth import AuthenticatedUser


def _user():
    return AuthenticatedUser(
        user_id="user-capture-1",
        email="ea@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={},
    )


def test_create_context_capture_defaults_to_pending_insight_for_contact_scope(db_session, monkeypatch):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.commit()

    queued = {}

    def _fake_enqueue(task_type, payload, **kwargs):
        queued["task_type"] = task_type
        queued["payload"] = payload
        return None

    monkeypatch.setattr("app.jobs.queue.enqueue_task", _fake_enqueue)
    invalidations = {"count": 0}
    monkeypatch.setattr(
        "app.routes.v1.vault.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: invalidations.__setitem__("count", invalidations["count"] + 1),
    )

    response = create_context_capture(
        payload=ContextCaptureCreate(
            text="Sarah approved vendor X for Q3 expansion",
            scope_type=ContextCaptureScopeType.contact,
            scope_id="sarah@example.com",
            linked_to="Sarah",
        ),
        user=_user(),
        db=db_session,
    )
    stored = db_session.query(ContextEntry).filter(ContextEntry.id == response.id).first()
    assert stored is not None
    assert stored.type == "insight"
    assert stored.raw_text == "Sarah approved vendor X for Q3 expansion"
    assert stored.classification_status == "pending"
    assert stored.entity_type == "contact"
    assert stored.entity_id == str(contact.id)
    assert queued["task_type"] == "classify_context_capture"
    assert queued["payload"]["entry_id"] == response.id
    assert queued["payload"]["user_id"] == "user-capture-1"
    assert invalidations["count"] == 1


def test_create_context_capture_accepts_explicit_global_scope(db_session):
    response = create_context_capture(
        payload=ContextCaptureCreate(
            text="Board prefers short Monday briefings",
            scope_type=ContextCaptureScopeType.global_,
            scope_id=None,
            linked_to=None,
        ),
        user=_user(),
        db=db_session,
    )

    stored = db_session.query(ContextEntry).filter(ContextEntry.id == response.id).first()
    assert stored is not None
    assert stored.entity_type == "global"
    assert stored.entity_id is None
    assert stored.classification_status == "pending"


def test_create_context_capture_rejects_missing_non_global_scope_id(db_session):
    try:
        create_context_capture(
            payload=ContextCaptureCreate(
                text="Follow up on this",
                scope_type=ContextCaptureScopeType.task,
                scope_id=None,
            ),
            user=_user(),
            db=db_session,
        )
        assert False, "Expected scope validation error"
    except Exception as exc:
        assert "scope_id is required" in str(exc)


def test_create_context_capture_accepts_task_scope(db_session):
    task = Task(
        user_id="user-capture-1",
        thread_id=None,
        message_id=1,
        title="Reply to vendor",
        status="approved",
    )
    db_session.add(task)
    db_session.commit()

    response = create_context_capture(
        payload=ContextCaptureCreate(
            text="Need legal signoff before sending",
            scope_type=ContextCaptureScopeType.task,
            scope_id=str(task.id),
            linked_to="Reply to vendor",
        ),
        user=_user(),
        db=db_session,
    )

    stored = db_session.query(ContextEntry).filter(ContextEntry.id == response.id).first()
    assert stored is not None
    assert stored.entity_type == "task"
    assert stored.entity_id == str(task.id)


def test_create_context_capture_accepts_event_scope(db_session, monkeypatch):
    event = CalendarEvent(
        user_id="user-capture-1",
        title="Q3 Planning",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        external_event_id="evt-123",
        source="synced",
    )
    db_session.add(event)
    db_session.commit()
    monkeypatch.setattr("app.jobs.queue.enqueue_task", lambda *args, **kwargs: None)

    response = create_context_capture(
        payload=ContextCaptureCreate(
            text="Sarah approved the vendor in the Q3 planning meeting.",
            scope_type=ContextCaptureScopeType.event,
            scope_id="evt-123",
        ),
        user=_user(),
        db=db_session,
    )

    stored = db_session.query(ContextEntry).filter(ContextEntry.id == response.id).first()
    assert stored is not None
    assert stored.entity_type == "event"
    assert stored.entity_id == "evt-123"


def test_create_context_capture_canonicalizes_message_scope_and_persists_links(db_session):
    message = Message(
        user_id="user-capture-1",
        message_id="msg-123",
        thread_id="thread-1",
        sender="sarah@example.com",
        recipient="ea@example.com",
        subject="Vendor approval",
        body="Approved",
        received_at=datetime.now(timezone.utc),
        processed=False,
    )
    db_session.add(message)
    db_session.commit()

    response = create_context_capture(
        payload=ContextCaptureCreate(
            text="Sarah approved vendor X.",
            scope_type=ContextCaptureScopeType.message,
            scope_id=str(message.id),
            links=[
                DiaryEntryLinkSchema(
                    entity_type="thread",
                    entity_id="thread-1",
                    display_name="Vendor approval thread",
                )
            ],
        ),
        user=_user(),
        db=db_session,
    )

    stored = db_session.query(ContextEntry).filter(ContextEntry.id == response.id).first()
    links = db_session.query(DiaryEntryLink).filter(DiaryEntryLink.entry_id == response.id).all()
    assert stored is not None
    assert stored.entity_type == "message"
    assert stored.entity_id == "msg-123"
    assert stored.linked_to == "Vendor approval"
    assert len(links) == 1
    assert links[0].source == "user"


def test_create_context_capture_drops_invalid_unowned_links(db_session, monkeypatch):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    other_contact = Contact(user_id="other-user", name="Mallory", email="mallory@example.com")
    db_session.add_all([contact, other_contact])
    db_session.commit()

    monkeypatch.setattr("app.jobs.queue.enqueue_task", lambda *args, **kwargs: None)

    response = create_context_capture(
        payload=ContextCaptureCreate(
            text="Sarah approved vendor X for Q3 expansion",
            scope_type=ContextCaptureScopeType.contact,
            scope_id="sarah@example.com",
            links=[
                DiaryEntryLinkSchema(
                    entity_type="contact",
                    entity_id=str(contact.id),
                    display_name="Sarah",
                ),
                DiaryEntryLinkSchema(
                    entity_type="contact",
                    entity_id=str(other_contact.id),
                    display_name="Mallory",
                ),
                DiaryEntryLinkSchema(
                    entity_type="bogus",
                    entity_id="x",
                    display_name="Bogus",
                ),
            ],
        ),
        user=_user(),
        db=db_session,
    )

    links = db_session.query(DiaryEntryLink).filter(DiaryEntryLink.entry_id == response.id).all()
    assert len(links) == 1
    assert links[0].display_name == "Sarah"
    assert links[0].entity_id == str(contact.id)


def test_create_context_capture_rejects_oversized_text(db_session):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.commit()

    try:
        create_context_capture(
            payload=ContextCaptureCreate(
                text="x" * 2001,
                scope_type=ContextCaptureScopeType.contact,
                scope_id=str(contact.id),
            ),
            user=_user(),
            db=db_session,
        )
        assert False, "Expected validation error"
    except Exception as exc:
        assert "at most 2000 characters" in str(exc)


def test_create_context_capture_throttles_classifier_enqueue(db_session, monkeypatch):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.flush()
    now = datetime.utcnow()
    db_session.add_all(
        [
            TaskQueue(
                task_type="classify_context_capture",
                user_id="user-capture-1",
                payload={"entry_id": idx},
                status="completed",
                created_at=now - timedelta(minutes=1),
                updated_at=now - timedelta(minutes=1),
            )
            for idx in range(10)
        ]
    )
    db_session.commit()

    queued = {"count": 0}
    monkeypatch.setattr(
        "app.jobs.queue.enqueue_task",
        lambda *args, **kwargs: queued.__setitem__("count", queued["count"] + 1),
    )

    create_context_capture(
        payload=ContextCaptureCreate(
            text="Board prefers short Monday briefings",
            scope_type=ContextCaptureScopeType.contact,
            scope_id=str(contact.id),
        ),
        user=_user(),
        db=db_session,
    )

    assert queued["count"] == 0


def test_update_context_entry_manual_correction_sets_user_corrected_and_replaces_links(db_session, monkeypatch):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    other = Contact(user_id="user-capture-1", name="Priya", email="priya@example.com")
    db_session.add_all([contact, other])
    db_session.flush()
    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Sarah approved vendor X.",
        raw_text="Sarah approved vendor X.",
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
    db_session.flush()
    db_session.add(
        DiaryEntryLink(
            entry_id=entry.id,
            entity_type="contact",
            entity_id=str(contact.id),
            display_name="Sarah",
        )
    )
    db_session.commit()

    invalidations = {"count": 0}
    monkeypatch.setattr(
        "app.routes.v1.vault.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: invalidations.__setitem__("count", invalidations["count"] + 1),
    )

    response = update_context_entry(
        entry_id=entry.id,
        payload=ContextCaptureUpdate(
            type=ContextType.decision,
            links=[
                DiaryEntryLinkSchema(
                    entity_type="contact",
                    entity_id=str(other.id),
                    display_name="Priya",
                )
            ],
        ),
        user=_user(),
        db=db_session,
    )

    db_session.refresh(entry)
    links = db_session.query(DiaryEntryLink).filter(DiaryEntryLink.entry_id == entry.id).all()
    assert response.type == ContextType.decision
    assert entry.classification_status == "user_corrected"
    assert entry.user_corrected is True
    assert len(links) == 1
    assert links[0].display_name == "Priya"
    assert links[0].source == "user"
    assert invalidations["count"] == 1


def test_update_context_entry_can_remove_all_links_via_patch(db_session, monkeypatch):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.flush()
    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Sarah approved vendor X.",
        raw_text="Sarah approved vendor X.",
        entity_type="contact",
        entity_id=str(contact.id),
        linked_to="Sarah",
        classification_status="classified",
        user_corrected=False,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add(entry)
    db_session.flush()
    db_session.add_all(
        [
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="contact",
                entity_id=str(contact.id),
                display_name="Sarah",
                source="user",
            ),
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="message",
                entity_id="msg-123",
                display_name="Vendor approval",
                source="teeks",
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.routes.v1.vault.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: None,
    )

    response = update_context_entry(
        entry_id=entry.id,
        payload=ContextCaptureUpdate(links=[]),
        user=_user(),
        db=db_session,
    )

    links = db_session.query(DiaryEntryLink).filter(DiaryEntryLink.entry_id == entry.id).all()
    assert response.links == []
    assert links == []


def test_update_context_entry_can_mark_entry_forgotten(db_session, monkeypatch):
    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Old vendor preference",
        raw_text="Old vendor preference",
        entity_type="global",
        entity_id=None,
        linked_to=None,
        classification_status="classified",
        user_corrected=False,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add(entry)
    db_session.commit()

    monkeypatch.setattr(
        "app.routes.v1.vault.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: None,
    )

    response = update_context_entry(
        entry_id=entry.id,
        payload=ContextCaptureUpdate(status=ContextEntryStatus.forgotten),
        user=_user(),
        db=db_session,
    )

    db_session.refresh(entry)
    assert entry.status == "forgotten"
    assert response.status == ContextEntryStatus.forgotten


def test_delete_context_entry_forgets_entry_instead_of_resolving_it(db_session, monkeypatch):
    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Outdated vendor preference",
        raw_text="Outdated vendor preference",
        entity_type="global",
        entity_id=None,
        linked_to=None,
        classification_status="classified",
        user_corrected=False,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add(entry)
    db_session.commit()

    monkeypatch.setattr(
        "app.routes.v1.vault.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.routes.v1.vault._prewarm_action_chips_cache",
        lambda *args, **kwargs: None,
    )

    response = delete_context_entry(
        entry_id=entry.id,
        user=_user(),
        db=db_session,
    )

    db_session.refresh(entry)
    assert entry.status == "forgotten"
    assert response == {"forgotten": True, "id": entry.id}


def test_context_capture_response_drops_orphaned_links_from_existing_entries(db_session):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.flush()
    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Sarah approved vendor X.",
        raw_text="Sarah approved vendor X.",
        entity_type="contact",
        entity_id=str(contact.id),
        linked_to="Sarah",
        classification_status="classified",
        user_corrected=False,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add(entry)
    db_session.flush()
    db_session.add_all(
        [
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="contact",
                entity_id=str(contact.id),
                display_name="Sarah",
                source="user",
            ),
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="message",
                entity_id="missing-message",
                display_name="Deleted message",
                source="teeks",
            ),
        ]
    )
    db_session.commit()

    response = _to_context_capture_response(db=db_session, user_id="user-capture-1", entry=entry)

    assert len(response.links) == 1
    assert response.links[0].entity_type == "contact"
    assert response.links[0].entity_id == str(contact.id)


def test_update_context_entry_preserves_existing_teeks_link_provenance(db_session, monkeypatch):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.flush()
    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Sarah approved vendor X.",
        raw_text="Sarah approved vendor X.",
        entity_type="contact",
        entity_id=str(contact.id),
        linked_to="Sarah",
        classification_status="classified",
        user_corrected=False,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add(entry)
    db_session.flush()
    db_session.add_all(
        [
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="contact",
                entity_id=str(contact.id),
                display_name="Sarah",
                source="user",
            ),
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="message",
                entity_id="msg-123",
                display_name="Vendor approval",
                source="teeks",
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.routes.v1.vault.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: None,
    )

    response = update_context_entry(
        entry_id=entry.id,
        payload=ContextCaptureUpdate(
            links=[
                DiaryEntryLinkSchema(
                    entity_type="contact",
                    entity_id=str(contact.id),
                    display_name="Sarah",
                ),
                DiaryEntryLinkSchema(
                    entity_type="message",
                    entity_id="msg-123",
                    display_name="Vendor approval",
                ),
            ]
        ),
        user=_user(),
        db=db_session,
    )

    links = (
        db_session.query(DiaryEntryLink)
        .filter(DiaryEntryLink.entry_id == entry.id)
        .order_by(DiaryEntryLink.entity_type.asc(), DiaryEntryLink.entity_id.asc())
        .all()
    )
    assert len(response.links) == 2
    assert [(link.entity_type, link.entity_id, link.source) for link in links] == [
        ("contact", str(contact.id), "user"),
        ("message", "msg-123", "teeks"),
    ]


def test_delete_context_capture_link_removes_only_target_and_preserves_other_provenance(db_session, monkeypatch):
    contact = Contact(user_id="user-capture-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.flush()
    entry = ContextEntry(
        user_id="user-capture-1",
        type="insight",
        content="Sarah approved vendor X.",
        raw_text="Sarah approved vendor X.",
        entity_type="contact",
        entity_id=str(contact.id),
        linked_to="Sarah",
        classification_status="classified",
        user_corrected=False,
        created_by="You",
        importance_level="normal",
        status="active",
    )
    db_session.add(entry)
    db_session.flush()
    db_session.add_all(
        [
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="contact",
                entity_id=str(contact.id),
                display_name="Sarah",
                source="user",
            ),
            DiaryEntryLink(
                entry_id=entry.id,
                entity_type="message",
                entity_id="msg-123",
                display_name="Vendor approval",
                source="teeks",
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.routes.v1.vault.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: None,
    )

    response = delete_context_capture_link(
        entry_id=entry.id,
        entity_type="contact",
        entity_id=str(contact.id),
        user=_user(),
        db=db_session,
    )

    links = db_session.query(DiaryEntryLink).filter(DiaryEntryLink.entry_id == entry.id).all()
    assert len(response.links) == 1
    assert len(links) == 1
    assert links[0].entity_type == "message"
    assert links[0].entity_id == "msg-123"
    assert links[0].source == "teeks"


def test_to_context_capture_response_keeps_expired_decision_active(db_session):
    now = datetime.now(timezone.utc)
    entry = ContextEntry(
        user_id="user-capture-1",
        type="decision",
        content="Approved the older venue change.",
        entity_type="global",
        entity_id=None,
        created_by="You",
        status="active",
        expires_at=now - timedelta(days=30),
        created_at=now - timedelta(days=200),
        updated_at=now - timedelta(days=200),
    )
    db_session.add(entry)
    db_session.commit()

    response = _to_context_capture_response(db=db_session, user_id="user-capture-1", entry=entry)

    assert response.status == ContextEntryStatus.active


def test_update_context_entry_keeps_expired_decision_active_but_ages_other_types(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    decision_entry = ContextEntry(
        user_id="user-capture-1",
        type="decision",
        content="Delay the board deck by one week.",
        entity_type="global",
        entity_id=None,
        created_by="You",
        status="active",
        created_at=now - timedelta(days=120),
        updated_at=now - timedelta(days=120),
    )
    preference_entry = ContextEntry(
        user_id="user-capture-1",
        type="preference",
        content="Prefers concise Monday updates.",
        entity_type="global",
        entity_id=None,
        created_by="You",
        status="active",
        created_at=now - timedelta(days=60),
        updated_at=now - timedelta(days=60),
    )
    db_session.add_all([decision_entry, preference_entry])
    db_session.commit()

    monkeypatch.setattr(
        "app.routes.v1.vault.cache_coordinator.invalidate_from_context_entry",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.routes.v1.vault._prewarm_action_chips_cache",
        lambda *args, **kwargs: None,
    )

    decision_response = update_context_entry(
        entry_id=decision_entry.id,
        payload=ContextCaptureUpdate(expires_at=now - timedelta(days=10)),
        user=_user(),
        db=db_session,
    )
    preference_response = update_context_entry(
        entry_id=preference_entry.id,
        payload=ContextCaptureUpdate(expires_at=now - timedelta(days=10)),
        user=_user(),
        db=db_session,
    )

    assert decision_response.status == ContextEntryStatus.active
    assert preference_response.status == ContextEntryStatus.stale

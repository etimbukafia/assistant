import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from core.cache.hot_cache import HotCache

from app.data.models import CalendarEvent, Contact, ContextEntry, Message, Task, ThreadState
from app.services.hot_context_cache import HotContextCacheService
from app.services.warm_cache import WarmCacheService


TENANT = "tenant-unit"
USER_ID = "user-cache-unit"


def _make_coordinator():
    namespace = f"coord-{uuid.uuid4().hex[:8]}"
    warm = WarmCacheService(namespace=namespace, default_ttl_seconds=3600, ttl_jitter_seconds=0)
    hot_ctx = HotContextCacheService(namespace=namespace, session_ttl_seconds=3600)
    hot_cache = HotCache(maxsize_per_user=64, max_stores=64)

    patches = [
        patch("app.services.entity_cache_coordinator.get_warm_cache_service", return_value=warm),
        patch("app.services.entity_cache_coordinator.get_hot_context_cache_service", return_value=hot_ctx),
        patch("core.cache.thread_cache.hot_cache", hot_cache),
        patch("core.cache.calendar_cache.hot_cache", hot_cache),
    ]
    for active in patches:
        active.start()

    from app.services.entity_cache_coordinator import EntityCacheCoordinator

    return EntityCacheCoordinator(), warm, hot_ctx, hot_cache, patches


def _stop_patches(patches):
    for active in reversed(patches):
        active.stop()


def test_invalidate_from_context_entry_follows_diary_links():
    coordinator, warm, _, _, patches = _make_coordinator()
    try:
        warm.set(TENANT, USER_ID, "contact:alice@example.com", {"cached": True}, ttl_seconds=3600)
        warm.set(TENANT, USER_ID, "thread:thread-1", {"cached": True}, ttl_seconds=3600)
        warm.set(TENANT, USER_ID, "event:42", {"cached": True}, ttl_seconds=3600)
        warm.set(TENANT, USER_ID, "message:msg-1", {"cached": True}, ttl_seconds=3600)

        entry = ContextEntry(
            user_id=USER_ID,
            type="decision",
            content="Track relationship change",
            entity_type="global",
            entity_id=None,
            created_by="You",
            importance_level="normal",
            status="active",
        )
        entry.links = [
            SimpleNamespace(entity_type="contact", entity_id="alice@example.com"),
            SimpleNamespace(entity_type="thread", entity_id="thread-1"),
            SimpleNamespace(entity_type="event", entity_id="42"),
            SimpleNamespace(entity_type="message", entity_id="msg-1"),
        ]

        coordinator.invalidate_from_context_entry(TENANT, entry)

        assert warm.get(TENANT, USER_ID, "contact:alice@example.com") is None
        assert warm.get(TENANT, USER_ID, "thread:thread-1") is None
        assert warm.get(TENANT, USER_ID, "event:42") is None
        assert warm.get(TENANT, USER_ID, "message:msg-1") is None
    finally:
        _stop_patches(patches)


def test_invalidate_task_related_contact_clears_related_contact_scope(db_session):
    coordinator, warm, _, _, patches = _make_coordinator()
    try:
        contact = Contact(user_id=USER_ID, name="Alice", email="alice@example.com")
        db_session.add(contact)
        db_session.flush()

        message = Message(
            message_id="msg-task-1",
            thread_id="thread-task-1",
            user_id=USER_ID,
            subject="Follow up",
            sender="alice@example.com",
            recipient="ea@example.com",
            contact_id=contact.id,
            body="Please follow up.",
            received_at=datetime.now(timezone.utc),
        )
        db_session.add(message)
        db_session.flush()

        thread_state = ThreadState(
            user_id=USER_ID,
            thread_id="thread-task-1",
            subject="Follow up",
            message_count=1,
            contact_id=contact.id,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(thread_state)
        db_session.flush()

        task = Task(
            user_id=USER_ID,
            thread_id="thread-task-1",
            message_id=message.id,
            title="Reply to Alice",
            status="approved",
        )
        db_session.add(task)
        db_session.commit()

        warm.set(TENANT, USER_ID, "contact:alice@example.com", {"cached": True}, ttl_seconds=3600)

        coordinator.invalidate_task_related_contact(
            db=db_session,
            tenant_id=TENANT,
            user_id=USER_ID,
            task_id=task.id,
        )

        assert warm.get(TENANT, USER_ID, "contact:alice@example.com") is None
    finally:
        _stop_patches(patches)


def test_invalidate_event_related_contacts_clears_only_matching_contact_scopes(db_session):
    coordinator, warm, _, _, patches = _make_coordinator()
    try:
        alice = Contact(user_id=USER_ID, name="Alice", email="alice@example.com")
        bob = Contact(user_id=USER_ID, name="Bob", email="bob@example.com")
        db_session.add_all([alice, bob])
        db_session.flush()

        event = CalendarEvent(
            user_id=USER_ID,
            title="Weekly sync",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            participants=[{"email": "alice@example.com", "name": "Alice"}],
            organizer="exec@example.com",
        )
        db_session.add(event)
        db_session.commit()

        warm.set(TENANT, USER_ID, "contact:alice@example.com", {"cached": True}, ttl_seconds=3600)
        warm.set(TENANT, USER_ID, "contact:bob@example.com", {"cached": True}, ttl_seconds=3600)

        coordinator.invalidate_event_related_contacts(
            db=db_session,
            tenant_id=TENANT,
            user_id=USER_ID,
            event_id=event.id,
        )

        assert warm.get(TENANT, USER_ID, "contact:alice@example.com") is None
        assert warm.get(TENANT, USER_ID, "contact:bob@example.com") is not None
    finally:
        _stop_patches(patches)

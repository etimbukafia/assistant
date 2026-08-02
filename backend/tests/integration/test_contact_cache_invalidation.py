import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.cache.hot_cache import HotCache

from app.data.models import CalendarEvent, Contact, Message, Task, ThreadState
from app.services.hot_context_cache import HotContextCacheService
from app.services.warm_cache import WarmCacheService


TENANT = "tenant-integration"
USER_ID = "user-contact-cache"


def _make_coordinator():
    namespace = f"contact-cache-{uuid.uuid4().hex[:8]}"
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

    return EntityCacheCoordinator(), warm, patches


def _stop_patches(patches):
    for active in reversed(patches):
        active.stop()


@pytest.mark.integration
def test_task_change_invalidates_cached_contact_scope(db_session):
    coordinator, warm, patches = _make_coordinator()
    try:
        contact = Contact(user_id=USER_ID, name="Alice", email="alice@example.com")
        db_session.add(contact)
        db_session.flush()

        message = Message(
            message_id="msg-cache-task",
            thread_id="thread-cache-task",
            user_id=USER_ID,
            subject="Task thread",
            sender="alice@example.com",
            recipient="ea@example.com",
            contact_id=contact.id,
            body="Need a response",
            received_at=datetime.now(timezone.utc),
        )
        db_session.add(message)
        db_session.flush()

        db_session.add(
            ThreadState(
                user_id=USER_ID,
                thread_id="thread-cache-task",
                subject="Task thread",
                message_count=1,
                contact_id=contact.id,
                created_at=datetime.now(timezone.utc),
            )
        )
        db_session.flush()

        task = Task(
            user_id=USER_ID,
            thread_id="thread-cache-task",
            message_id=message.id,
            title="Reply to Alice",
            status="approved",
        )
        db_session.add(task)
        db_session.commit()

        warm.set(TENANT, USER_ID, "contact:alice@example.com", {"brief": "stale"}, ttl_seconds=3600)

        coordinator.invalidate_task_related_contact(
            db=db_session,
            tenant_id=TENANT,
            user_id=USER_ID,
            task_id=task.id,
        )

        assert warm.get(TENANT, USER_ID, "contact:alice@example.com") is None
    finally:
        _stop_patches(patches)


@pytest.mark.integration
def test_new_linked_message_invalidates_cached_contact_scope(db_session):
    coordinator, warm, patches = _make_coordinator()
    try:
        contact = Contact(user_id=USER_ID, name="Alice", email="alice@example.com")
        db_session.add(contact)
        db_session.flush()

        message = Message(
            message_id="msg-cache-message",
            thread_id="thread-cache-message",
            user_id=USER_ID,
            subject="Fresh message",
            sender="alice@example.com",
            recipient="ea@example.com",
            contact_id=contact.id,
            body="Hello there",
            received_at=datetime.now(timezone.utc),
        )
        db_session.add(message)
        db_session.flush()
        db_session.add(
            ThreadState(
                user_id=USER_ID,
                thread_id="thread-cache-message",
                subject="Fresh message",
                message_count=1,
                contact_id=contact.id,
                created_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()

        warm.set(TENANT, USER_ID, "contact:alice@example.com", {"brief": "stale"}, ttl_seconds=3600)

        coordinator.invalidate_message_related_contact(
            db=db_session,
            tenant_id=TENANT,
            user_id=USER_ID,
            message_db_id=message.id,
        )

        assert warm.get(TENANT, USER_ID, "contact:alice@example.com") is None
    finally:
        _stop_patches(patches)


@pytest.mark.integration
def test_meeting_participant_update_invalidates_target_contact_and_preserves_other_contact(db_session):
    coordinator, warm, patches = _make_coordinator()
    try:
        alice = Contact(user_id=USER_ID, name="Alice", email="alice@example.com")
        bob = Contact(user_id=USER_ID, name="Bob", email="bob@example.com")
        db_session.add_all([alice, bob])
        db_session.flush()

        event = CalendarEvent(
            user_id=USER_ID,
            title="Relationship sync",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            participants=[{"email": "alice@example.com", "name": "Alice"}],
            organizer="exec@example.com",
        )
        db_session.add(event)
        db_session.commit()

        warm.set(TENANT, USER_ID, "contact:alice@example.com", {"brief": "stale-alice"}, ttl_seconds=3600)
        warm.set(TENANT, USER_ID, "contact:bob@example.com", {"brief": "fresh-bob"}, ttl_seconds=3600)

        coordinator.invalidate_event_related_contacts(
            db=db_session,
            tenant_id=TENANT,
            user_id=USER_ID,
            event_id=event.id,
        )

        assert warm.get(TENANT, USER_ID, "contact:alice@example.com") is None
        assert warm.get(TENANT, USER_ID, "contact:bob@example.com") == {"brief": "fresh-bob"}
    finally:
        _stop_patches(patches)

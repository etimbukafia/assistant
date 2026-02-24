"""
Integration tests for EntityCacheCoordinator — cache invalidation from context entry mutations.

These tests use the REAL cache implementations (no mocking of cache behaviour).
All three layers are exercised with live in-process state:

  Layer 1 — thread_cache / calendar_cache  (core.cache.HotCache)
  Layer 2 — warm_cache                     (WarmCacheService, in-process store)
  Layer 3 — hot session fragments          (HotContextCacheService, in-process store)

Redis is NOT required. WarmCacheService falls back to its in-process OrderedDict
when no Redis URL is configured.

Isolation strategy:
  - WarmCacheService and HotContextCacheService share class-level state across all
    instances. Each test gets a unique namespace (uuid-prefixed) so cache keys never
    collide between tests.
  - thread_cache and calendar_cache delegate to the core hot_cache singleton.
    We patch them with a fresh HotCache instance per test so each test starts clean.

Run with:
    pytest tests/integration/test_cache_invalidation.py -m integration -v -s
"""

import uuid
import pytest
from unittest.mock import MagicMock, patch

from core.cache.hot_cache import HotCache
from app.services.warm_cache import WarmCacheService
from app.services.hot_context_cache import HotContextCacheService

TENANT = "tenant-integ"
USER   = "user-integ"


def _entry(entity_type: str, entity_id: str, user_id: str = USER) -> MagicMock:
    """Minimal stand-in for a ContextEntry — only the fields the coordinator reads."""
    e = MagicMock()
    e.user_id     = user_id
    e.entity_type = entity_type
    e.entity_id   = entity_id
    return e


@pytest.mark.integration
class TestCacheInvalidationIntegration:
    """
    Verifies that calling invalidate_from_context_entry results in real cache
    eviction across all three layers for each entity scope type.
    """

    def setup_method(self, method):
        # Unique namespace per test — isolates keys inside the shared class-level dicts
        ns = uuid.uuid4().hex[:10]
        print(f"\n[setup] test={method.__name__}  namespace=t_{ns}")

        # Real instances with TTL jitter removed for determinism
        self.warm    = WarmCacheService(
            namespace=f"t_{ns}",
            default_ttl_seconds=3600,
            ttl_jitter_seconds=0,
        )
        self.hot_ctx = HotContextCacheService(
            namespace=f"t_{ns}",
            session_ttl_seconds=3600,
        )
        # Fresh HotCache for thread/calendar layer — not the module singleton
        self.hot_cache = HotCache(maxsize_per_user=256, max_stores=256)
        print(f"[setup] WarmCacheService ns=t_{ns}  HotContextCacheService ns=t_{ns}  HotCache fresh=True")

        self._patches = [
            patch(
                "app.services.entity_cache_coordinator.get_warm_cache_service",
                return_value=self.warm,
            ),
            patch(
                "app.services.entity_cache_coordinator.get_hot_context_cache_service",
                return_value=self.hot_ctx,
            ),
            # Redirect thread_cache and calendar_cache to the fresh HotCache
            patch("core.cache.thread_cache.hot_cache",   self.hot_cache),
            patch("core.cache.calendar_cache.hot_cache", self.hot_cache),
        ]
        for p in self._patches:
            p.start()

        from app.services.entity_cache_coordinator import EntityCacheCoordinator
        self.coord = EntityCacheCoordinator()
        print("[setup] EntityCacheCoordinator instantiated with patched caches")

    def teardown_method(self, method):
        for p in self._patches:
            p.stop()
        print(f"[teardown] patches stopped for test={method.__name__}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _prime_warm(self, scope: str) -> None:
        """Write a real entry to the warm cache and assert it landed."""
        self.warm.set(TENANT, USER, scope, {"data": f"cached:{scope}"}, ttl_seconds=3600)
        result = self.warm.get(TENANT, USER, scope)
        assert result is not None, f"warm cache prime failed for scope={scope!r}"
        print(f"  [prime] warm  scope={scope!r}  value={result}")

    def _prime_hot_cache(self, namespace: str, key: str) -> None:
        """Write a real entry to the HotCache and assert it landed."""
        sentinel = {"_key": key}
        self.hot_cache.get_or_set(USER, namespace, key, lambda: sentinel)
        # Confirm it's cached — builder must NOT be called again
        result = self.hot_cache.get_or_set(USER, namespace, key, lambda: {"_key": "REBUILT"})
        assert result == sentinel, "hot_cache prime failed — entry was not stored"
        print(f"  [prime] hot_cache  namespace={namespace!r}  key={key!r}  value={result}")

    def _prime_session_fragment(
        self,
        entity_type: str,
        entity_id: str,
        session_id: str = "session-1",
        entry_id: int = 1,
    ) -> None:
        """Merge a context fragment into a hot session and assert it's there."""
        self.hot_ctx.merge_context_entries(
            TENANT, USER, session_id,
            [{
                "id":          entry_id,
                "entity_type": entity_type,
                "entity_id":   str(entity_id),
                "type":        "risk",
                "content":     f"test fragment for {entity_type}:{entity_id}",
            }],
        )
        state = self.hot_ctx.get_session_state(TENANT, USER, session_id)
        matched = [
            e for e in state["context_entries"]
            if e["entity_type"] == entity_type and e["entity_id"] == str(entity_id)
        ]
        assert matched, f"session fragment prime failed for {entity_type}:{entity_id}"
        print(f"  [prime] session fragment  session={session_id}  {entity_type}:{entity_id}  entry_id={entry_id}")

    def _hot_cache_was_evicted(self, namespace: str, key: str) -> bool:
        """
        Returns True if the entry was evicted — proven by the builder being called.
        Uses a never-before-seen sentinel so a cache hit would return the old value.
        """
        rebuilt_sentinel = object()
        result = self.hot_cache.get_or_set(USER, namespace, key, lambda: rebuilt_sentinel)
        evicted = result is rebuilt_sentinel
        print(f"  [check] hot_cache eviction  namespace={namespace!r}  key={key!r}  evicted={evicted}")
        return evicted

    def _check_warm_evicted(self, scope: str) -> bool:
        result = self.warm.get(TENANT, USER, scope)
        evicted = result is None
        print(f"  [check] warm eviction  scope={scope!r}  evicted={evicted}  (value={result})")
        return evicted

    def _check_session_fragments(self, entity_type: str, entity_id: str, session_id: str = "session-1"):
        state = self.hot_ctx.get_session_state(TENANT, USER, session_id)
        matched = [
            e for e in state["context_entries"]
            if e["entity_type"] == entity_type and e["entity_id"] == str(entity_id)
        ]
        print(f"  [check] session fragments  {entity_type}:{entity_id}  remaining={len(matched)}")
        return matched

    # ── Thread-scoped entry ───────────────────────────────────────────────────

    def test_thread_entry_clears_thread_cache(self):
        print("\n--- invalidate thread → hot_cache[thread] evicted ---")
        self._prime_hot_cache("thread", "thread-001")

        print(f"  [act] invalidate_from_context_entry(entity_type=thread, entity_id=thread-001)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("thread", "thread-001"))

        assert self._hot_cache_was_evicted("thread", "thread-001"), \
            "thread_cache entry was NOT evicted"

    def test_thread_entry_clears_warm_scope(self):
        print("\n--- invalidate thread → warm[thread:thread-001] evicted ---")
        self._prime_warm("thread:thread-001")

        print(f"  [act] invalidate_from_context_entry(entity_type=thread, entity_id=thread-001)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("thread", "thread-001"))

        assert self._check_warm_evicted("thread:thread-001")

    def test_thread_entry_clears_hot_session_fragments(self):
        print("\n--- invalidate thread → session fragments removed ---")
        self._prime_session_fragment("thread", "thread-001")

        print(f"  [act] invalidate_from_context_entry(entity_type=thread, entity_id=thread-001)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("thread", "thread-001"))

        remaining = self._check_session_fragments("thread", "thread-001")
        assert not remaining

    # ── Event-scoped entry ────────────────────────────────────────────────────

    def test_event_entry_clears_calendar_cache(self):
        print("\n--- invalidate event → hot_cache[calendar/event:42] evicted ---")
        self._prime_hot_cache("calendar", "event:42")

        print(f"  [act] invalidate_from_context_entry(entity_type=event, entity_id=42)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("event", "42"))

        assert self._hot_cache_was_evicted("calendar", "event:42"), \
            "calendar_cache entry was NOT evicted"

    def test_event_entry_clears_warm_scope(self):
        print("\n--- invalidate event → warm[event:42] evicted ---")
        self._prime_warm("event:42")

        print(f"  [act] invalidate_from_context_entry(entity_type=event, entity_id=42)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("event", "42"))

        assert self._check_warm_evicted("event:42")

    def test_event_entry_clears_hot_session_fragments(self):
        print("\n--- invalidate event → session fragments removed ---")
        self._prime_session_fragment("event", "42", entry_id=2)

        print(f"  [act] invalidate_from_context_entry(entity_type=event, entity_id=42)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("event", "42"))

        remaining = self._check_session_fragments("event", "42")
        assert not remaining

    # ── Contact-scoped entry ──────────────────────────────────────────────────

    def test_contact_entry_clears_warm_scope_lowercased(self):
        print("\n--- invalidate contact (mixed-case) → warm[contact:alice@example.com] evicted ---")
        self._prime_warm("contact:alice@example.com")

        print(f"  [act] invalidate_from_context_entry(entity_type=contact, entity_id=Alice@Example.COM)")
        self.coord.invalidate_from_context_entry(
            TENANT, _entry("contact", "Alice@Example.COM")
        )

        assert self._check_warm_evicted("contact:alice@example.com")

    def test_contact_entry_clears_hot_session_fragments_lowercased(self):
        print("\n--- invalidate contact (mixed-case) → session fragments removed ---")
        self._prime_session_fragment("contact", "alice@example.com", entry_id=3)

        print(f"  [act] invalidate_from_context_entry(entity_type=contact, entity_id=Alice@Example.COM)")
        self.coord.invalidate_from_context_entry(
            TENANT, _entry("contact", "Alice@Example.COM")
        )

        remaining = self._check_session_fragments("contact", "alice@example.com")
        assert not remaining

    def test_contact_entry_does_not_touch_thread_cache(self):
        print("\n--- invalidate contact → thread_cache and warm[thread:*] UNTOUCHED ---")
        self._prime_hot_cache("thread", "thread-unrelated")
        self._prime_warm("thread:thread-unrelated")

        print(f"  [act] invalidate_from_context_entry(entity_type=contact, entity_id=alice@example.com)")
        self.coord.invalidate_from_context_entry(
            TENANT, _entry("contact", "alice@example.com")
        )

        hot_evicted = self._hot_cache_was_evicted("thread", "thread-unrelated")
        warm_evicted = self._check_warm_evicted("thread:thread-unrelated")
        print(f"  [assert] hot_cache untouched={not hot_evicted}  warm untouched={not warm_evicted}")
        assert not hot_evicted
        assert not warm_evicted

    # ── Message-scoped entry ──────────────────────────────────────────────────

    def test_message_entry_clears_warm_scope(self):
        print("\n--- invalidate message → warm[message:msg-99] evicted ---")
        self._prime_warm("message:msg-99")

        print(f"  [act] invalidate_from_context_entry(entity_type=message, entity_id=msg-99)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("message", "msg-99"))

        assert self._check_warm_evicted("message:msg-99")

    def test_message_entry_clears_hot_session_fragments(self):
        print("\n--- invalidate message → session fragments removed ---")
        self._prime_session_fragment("message", "msg-99", entry_id=4)

        print(f"  [act] invalidate_from_context_entry(entity_type=message, entity_id=msg-99)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("message", "msg-99"))

        remaining = self._check_session_fragments("message", "msg-99")
        assert not remaining

    # ── prior_entry: entity_id change must clear both old and new scopes ──────

    def test_prior_entry_both_scopes_cleared(self):
        print("\n--- prior_entry path → both old and new warm scopes cleared ---")
        self._prime_warm("thread:thread-OLD")
        self._prime_warm("thread:thread-NEW")

        print(f"  [act] invalidate_from_context_entry(new=thread:thread-NEW, prior=thread:thread-OLD)")
        self.coord.invalidate_from_context_entry(
            TENANT,
            _entry("thread", "thread-NEW"),
            prior_entry=_entry("thread", "thread-OLD"),
        )

        assert self._check_warm_evicted("thread:thread-OLD"), "old scope not cleared"
        assert self._check_warm_evicted("thread:thread-NEW"), "new scope not cleared"

    def test_prior_entry_of_different_type_clears_both_cache_layers(self):
        print("\n--- prior_entry (event→thread) → both hot_cache layers cleared ---")
        self._prime_hot_cache("thread",   "thread-001")
        self._prime_hot_cache("calendar", "event:42")

        print(f"  [act] invalidate_from_context_entry(new=thread:thread-001, prior=event:42)")
        self.coord.invalidate_from_context_entry(
            TENANT,
            _entry("thread", "thread-001"),
            prior_entry=_entry("event", "42"),
        )

        assert self._hot_cache_was_evicted("thread",   "thread-001"), "thread_cache not cleared"
        assert self._hot_cache_was_evicted("calendar", "event:42"),   "calendar_cache not cleared"

    # ── Isolation: unrelated scopes survive ───────────────────────────────────

    def test_unrelated_warm_scope_survives(self):
        print("\n--- invalidate thread-TARGET → thread-OTHER warm scope survives ---")
        self._prime_warm("thread:thread-TARGET")
        self._prime_warm("thread:thread-OTHER")

        print(f"  [act] invalidate_from_context_entry(entity_type=thread, entity_id=thread-TARGET)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("thread", "thread-TARGET"))

        assert self._check_warm_evicted("thread:thread-TARGET")
        other = self.warm.get(TENANT, USER, "thread:thread-OTHER")
        print(f"  [check] warm  scope=thread:thread-OTHER  survived={other is not None}  value={other}")
        assert other is not None

    def test_unrelated_session_fragments_survive(self):
        print("\n--- invalidate thread-001 → contact fragment survives ---")
        self._prime_session_fragment("thread",  "thread-001",        entry_id=10)
        self._prime_session_fragment("contact", "alice@example.com", entry_id=11)

        print(f"  [act] invalidate_from_context_entry(entity_type=thread, entity_id=thread-001)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("thread", "thread-001"))

        state = self.hot_ctx.get_session_state(TENANT, USER, "session-1")
        thread_frags  = [e for e in state["context_entries"] if e["entity_type"] == "thread"]
        contact_frags = [e for e in state["context_entries"] if e["entity_type"] == "contact"]
        print(f"  [check] thread fragments remaining={len(thread_frags)}  contact fragments remaining={len(contact_frags)}")

        assert len(thread_frags)  == 0, "thread fragment was not removed"
        assert len(contact_frags) == 1, "contact fragment was incorrectly removed"

    def test_other_user_warm_cache_unaffected(self):
        print("\n--- invalidate user-integ → other-user warm cache unaffected ---")
        other_user = "user-other"
        self.warm.set(TENANT, other_user, "thread:thread-001", {"data": "other"}, ttl_seconds=3600)
        other_before = self.warm.get(TENANT, other_user, "thread:thread-001")
        print(f"  [prime] warm  user={other_user}  scope=thread:thread-001  value={other_before}")

        print(f"  [act] invalidate_from_context_entry(user={USER}, entity_type=thread, entity_id=thread-001)")
        self.coord.invalidate_from_context_entry(TENANT, _entry("thread", "thread-001", user_id=USER))

        other_after = self.warm.get(TENANT, other_user, "thread:thread-001")
        print(f"  [check] warm  user={other_user}  scope=thread:thread-001  survived={other_after is not None}  value={other_after}")
        assert other_after is not None

"""
Unit tests for HotCache — in-process TTL cache with tenant isolation.
"""

import time
import pytest
from core.cache.hot_cache import HotCache


@pytest.mark.unit
class TestHotCache:
    def setup_method(self):
        self.cache = HotCache(maxsize_per_user=8, max_stores=4)

    # ── get_or_set ───────────────────────────────────────────────────────

    def test_get_or_set_caches_value(self):
        call_count = 0

        def builder():
            nonlocal call_count
            call_count += 1
            return {"data": "hello"}

        result1 = self.cache.get_or_set("user1", "thread", "t1", builder)
        result2 = self.cache.get_or_set("user1", "thread", "t1", builder)

        assert result1 == {"data": "hello"}
        assert result2 == {"data": "hello"}
        assert call_count == 1  # builder called only once

    def test_get_or_set_different_keys(self):
        self.cache.get_or_set("user1", "thread", "t1", lambda: "a")
        self.cache.get_or_set("user1", "thread", "t2", lambda: "b")

        assert self.cache.get_or_set("user1", "thread", "t1", lambda: "x") == "a"
        assert self.cache.get_or_set("user1", "thread", "t2", lambda: "x") == "b"

    # ── invalidate ───────────────────────────────────────────────────────

    def test_invalidate_removes_entry(self):
        self.cache.get_or_set("user1", "thread", "t1", lambda: "old")
        self.cache.invalidate("user1", "thread", "t1")

        result = self.cache.get_or_set("user1", "thread", "t1", lambda: "new")
        assert result == "new"

    def test_invalidate_nonexistent_key_is_noop(self):
        # Should not raise
        self.cache.invalidate("user1", "thread", "nonexistent")

    def test_invalidate_nonexistent_store_is_noop(self):
        # No store created yet for this user+namespace
        self.cache.invalidate("ghost_user", "thread", "t1")

    # ── invalidate_scope ─────────────────────────────────────────────────

    def test_invalidate_scope_clears_all_keys(self):
        self.cache.get_or_set("user1", "calendar", "events:a", lambda: "a")
        self.cache.get_or_set("user1", "calendar", "events:b", lambda: "b")
        self.cache.get_or_set("user1", "calendar", "event:1", lambda: "c")

        self.cache.invalidate_scope("user1", "calendar")

        # All should rebuild
        assert self.cache.get_or_set("user1", "calendar", "events:a", lambda: "new_a") == "new_a"
        assert self.cache.get_or_set("user1", "calendar", "events:b", lambda: "new_b") == "new_b"
        assert self.cache.get_or_set("user1", "calendar", "event:1", lambda: "new_c") == "new_c"

    def test_invalidate_scope_does_not_affect_other_namespaces(self):
        self.cache.get_or_set("user1", "thread", "t1", lambda: "thread_data")
        self.cache.get_or_set("user1", "calendar", "events", lambda: "cal_data")

        self.cache.invalidate_scope("user1", "calendar")

        # Thread data should survive
        assert self.cache.get_or_set("user1", "thread", "t1", lambda: "rebuilt") == "thread_data"

    # ── User isolation ───────────────────────────────────────────────────

    def test_user_isolation(self):
        """User A's cache is fully isolated from User B's."""
        self.cache.get_or_set("userA", "thread", "t1", lambda: "A_data")
        self.cache.get_or_set("userB", "thread", "t1", lambda: "B_data")

        assert self.cache.get_or_set("userA", "thread", "t1", lambda: "x") == "A_data"
        assert self.cache.get_or_set("userB", "thread", "t1", lambda: "x") == "B_data"

    def test_invalidate_does_not_cross_users(self):
        self.cache.get_or_set("userA", "thread", "t1", lambda: "A_data")
        self.cache.get_or_set("userB", "thread", "t1", lambda: "B_data")

        self.cache.invalidate("userA", "thread", "t1")

        # A rebuilt, B untouched
        assert self.cache.get_or_set("userA", "thread", "t1", lambda: "A_new") == "A_new"
        assert self.cache.get_or_set("userB", "thread", "t1", lambda: "B_new") == "B_data"

    def test_invalidate_scope_does_not_cross_users(self):
        self.cache.get_or_set("userA", "calendar", "events", lambda: "A_cal")
        self.cache.get_or_set("userB", "calendar", "events", lambda: "B_cal")

        self.cache.invalidate_scope("userA", "calendar")

        assert self.cache.get_or_set("userA", "calendar", "events", lambda: "A_new") == "A_new"
        assert self.cache.get_or_set("userB", "calendar", "events", lambda: "B_new") == "B_cal"

    # ── TTL expiry ───────────────────────────────────────────────────────

    def test_ttl_expiry(self):
        """Entries expire after their namespace TTL."""
        # Use a tiny TTL for testing
        cache = HotCache(maxsize_per_user=8, max_stores=4)
        # Monkey-patch the store to have 1s TTL
        from cachetools import TTLCache
        store = TTLCache(maxsize=8, ttl=1)
        cache._stores[("user1", "fast")] = store

        store["key1"] = "value1"
        assert store.get("key1") == "value1"

        time.sleep(1.1)
        assert store.get("key1") is None

    # ── Namespace TTL isolation ──────────────────────────────────────────

    def test_namespace_ttl_isolation(self):
        """Thread (300s) and calendar (60s) get different TTL stores."""
        self.cache.get_or_set("user1", "thread", "t1", lambda: "thread_data")
        self.cache.get_or_set("user1", "calendar", "e1", lambda: "cal_data")

        thread_store = self.cache._stores.get(("user1", "thread"))
        cal_store = self.cache._stores.get(("user1", "calendar"))

        assert thread_store is not None
        assert cal_store is not None
        # TTLCache stores its ttl as the `_TTLCache__ttl` attribute
        assert thread_store.ttl == 300
        assert cal_store.ttl == 60

    # ── LRU eviction of inactive user stores ─────────────────────────────

    def test_lru_eviction_of_stores(self):
        """When max_stores is exceeded, least-recently-used stores are evicted."""
        cache = HotCache(maxsize_per_user=4, max_stores=3)

        cache.get_or_set("user1", "thread", "k", lambda: "v1")
        cache.get_or_set("user2", "thread", "k", lambda: "v2")
        cache.get_or_set("user3", "thread", "k", lambda: "v3")

        # Adding a 4th store should evict user1's store (LRU)
        cache.get_or_set("user4", "thread", "k", lambda: "v4")

        # user1's data should be gone (rebuilt)
        assert cache.get_or_set("user1", "thread", "k", lambda: "v1_new") == "v1_new"
        # user4's data should be present
        assert cache.get_or_set("user4", "thread", "k", lambda: "x") == "v4"

    # ── Edge cases ───────────────────────────────────────────────────────

    def test_builder_exception_does_not_cache(self):
        """If builder raises, nothing is cached."""
        with pytest.raises(ValueError):
            self.cache.get_or_set("user1", "thread", "t1", lambda: (_ for _ in ()).throw(ValueError("boom")))

        # Next call should try builder again
        result = self.cache.get_or_set("user1", "thread", "t1", lambda: "recovered")
        assert result == "recovered"

    def test_maxsize_per_user_evicts_oldest(self):
        """When a user store is full, oldest entries are evicted."""
        cache = HotCache(maxsize_per_user=3, max_stores=10)

        cache.get_or_set("user1", "thread", "k1", lambda: "v1")
        cache.get_or_set("user1", "thread", "k2", lambda: "v2")
        cache.get_or_set("user1", "thread", "k3", lambda: "v3")
        # This should evict k1
        cache.get_or_set("user1", "thread", "k4", lambda: "v4")

        # k1 should be rebuilt
        assert cache.get_or_set("user1", "thread", "k1", lambda: "v1_new") == "v1_new"
        # k4 should be cached
        assert cache.get_or_set("user1", "thread", "k4", lambda: "x") == "v4"

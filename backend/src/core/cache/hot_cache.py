"""
Hot Cache — In-process TTL cache with per-user tenant isolation.

Each (user_id, namespace) pair gets its own TTLCache instance.
No shared eviction pressure between users. No data leakage.

Global store count bounded by LRU eviction of inactive user stores.
"""

import logging
from threading import Lock
from typing import Callable, TypeVar

from cachetools import TTLCache, LRUCache

T = TypeVar("T")

NAMESPACE_TTL = {"thread": 300, "calendar": 60}
DEFAULT_TTL = 300

logger = logging.getLogger(__name__)


class HotCache:
    def __init__(self, maxsize_per_user: int = 64, max_stores: int = 256):
        self._maxsize = maxsize_per_user
        self._stores: LRUCache = LRUCache(maxsize=max_stores)
        self._lock = Lock()

    def _get_store(self, user_id: str, namespace: str) -> TTLCache:
        store_key = (user_id, namespace)
        store = self._stores.get(store_key)
        if store is None:
            ttl = NAMESPACE_TTL.get(namespace, DEFAULT_TTL)
            store = TTLCache(maxsize=self._maxsize, ttl=ttl)
            self._stores[store_key] = store
        return store

    def get_or_set(self, user_id: str, namespace: str, key: str, builder: Callable[[], T]) -> T:
        """Return cached value or build, cache, and return it."""
        with self._lock:
            store = self._get_store(user_id, namespace)
            cached = store.get(key)
            if cached is not None:
                logger.debug("cache hit: %s/%s/%s", user_id[:8], namespace, key)
                return cached

        # Build outside the lock — don't hold it during DB queries
        value = builder()

        with self._lock:
            store = self._get_store(user_id, namespace)
            store[key] = value
            logger.debug("cache set: %s/%s/%s", user_id[:8], namespace, key)

        return value

    def invalidate(self, user_id: str, namespace: str, key: str):
        """Remove a single cache entry."""
        with self._lock:
            store_key = (user_id, namespace)
            store = self._stores.get(store_key)
            if store is not None:
                store.pop(key, None)
                logger.debug("cache invalidate: %s/%s/%s", user_id[:8], namespace, key)

    def invalidate_scope(self, user_id: str, namespace: str):
        """Drop all entries for a user+namespace. O(1)."""
        with self._lock:
            store_key = (user_id, namespace)
            self._stores.pop(store_key, None)
            logger.debug("cache invalidate_scope: %s/%s", user_id[:8], namespace)

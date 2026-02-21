"""Dual-mode warm cache: Redis primary with in-process fallback."""

from __future__ import annotations

from collections import OrderedDict
import json
import os
import random
import threading
import time
from typing import Any, Callable, Dict, Optional


_redis_lock = threading.Lock()
_redis_client_singleton = None
_redis_disabled_until = 0.0
_redis_failures = 0


def _get_redis_client():
    global _redis_client_singleton, _redis_disabled_until

    now = time.time()
    if _redis_disabled_until > now:
        return None

    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return None

    if _redis_client_singleton is not None:
        return _redis_client_singleton

    with _redis_lock:
        if _redis_client_singleton is not None:
            return _redis_client_singleton
        try:
            import redis  # type: ignore
            socket_connect_timeout = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", "0.2"))
            socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "0.2"))
            _redis_client_singleton = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=socket_connect_timeout,
                socket_timeout=socket_timeout,
                retry_on_timeout=False,
                health_check_interval=30,
            )
            return _redis_client_singleton
        except Exception:
            _mark_redis_failure()
            return None


def _mark_redis_failure() -> None:
    global _redis_failures, _redis_disabled_until, _redis_client_singleton
    _redis_failures = min(_redis_failures + 1, 8)
    backoff_seconds = min(30.0, float(2 ** _redis_failures))
    _redis_disabled_until = time.time() + backoff_seconds
    _redis_client_singleton = None


def _mark_redis_success() -> None:
    global _redis_failures, _redis_disabled_until
    _redis_failures = 0
    _redis_disabled_until = 0.0


class WarmCacheService:
    _lock = threading.RLock()
    _inproc_store: "OrderedDict[str, tuple[float, Dict[str, Any]]]" = OrderedDict()
    _inproc_user_index: Dict[str, "OrderedDict[str, float]"] = {}
    _inproc_key_owner: Dict[str, str] = {}

    def __init__(
        self,
        namespace: str = "warmctx",
        version: str = "v1",
        default_ttl_seconds: int = 900,
        ttl_jitter_seconds: int = 60,
        max_inproc_entries: int = 5000,
        per_user_scope_limit: int = 32,
    ) -> None:
        self.namespace = namespace
        self.version = version
        self.default_ttl_seconds = default_ttl_seconds
        self.ttl_jitter_seconds = ttl_jitter_seconds
        self.max_inproc_entries = max_inproc_entries
        self.per_user_scope_limit = per_user_scope_limit

    def _safe_part(self, value: str) -> str:
        return (value or "default").strip().replace(":", "_")

    def _cache_key(self, tenant_id: str, user_id: str, scope: str) -> str:
        tenant = self._safe_part(tenant_id)
        user = self._safe_part(user_id)
        safe_scope = self._safe_part(scope)
        return f"{self.namespace}:{self.version}:t:{tenant}:u:{user}:s:{safe_scope}"

    def _user_index_key(self, tenant_id: str, user_id: str) -> str:
        tenant = self._safe_part(tenant_id)
        user = self._safe_part(user_id)
        return f"{self.namespace}:{self.version}:idx:user:t:{tenant}:u:{user}"

    def _tenant_index_key(self, tenant_id: str) -> str:
        tenant = self._safe_part(tenant_id)
        return f"{self.namespace}:{self.version}:idx:tenant:t:{tenant}:users"

    def _compute_ttl(self, ttl_seconds: Optional[int]) -> int:
        base = ttl_seconds or self.default_ttl_seconds
        jitter = random.randint(0, max(0, self.ttl_jitter_seconds))
        return max(60, base + jitter)

    def _get_inproc(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            item = self._inproc_store.get(key)
            if not item:
                return None
            expires_at, payload = item
            if expires_at <= now:
                self._drop_inproc_key_unlocked(key)
                return None
            self._inproc_store.move_to_end(key)
            return payload

    def _set_inproc(self, key: str, user_index_key: str, payload: Dict[str, Any], ttl_seconds: int) -> None:
        now = time.time()
        expires_at = now + ttl_seconds
        with self._lock:
            self._inproc_store[key] = (expires_at, payload)
            self._inproc_store.move_to_end(key)

            if user_index_key not in self._inproc_user_index:
                self._inproc_user_index[user_index_key] = OrderedDict()
            user_scopes = self._inproc_user_index[user_index_key]
            user_scopes[key] = now
            user_scopes.move_to_end(key)
            self._inproc_key_owner[key] = user_index_key

            while len(user_scopes) > self.per_user_scope_limit:
                oldest_key, _ = user_scopes.popitem(last=False)
                self._drop_inproc_key_unlocked(oldest_key)

            while len(self._inproc_store) > self.max_inproc_entries:
                oldest_key, _ = self._inproc_store.popitem(last=False)
                owner = self._inproc_key_owner.pop(oldest_key, None)
                if owner and owner in self._inproc_user_index:
                    self._inproc_user_index[owner].pop(oldest_key, None)
                    if not self._inproc_user_index[owner]:
                        self._inproc_user_index.pop(owner, None)

    def _drop_inproc_key_unlocked(self, key: str) -> None:
        self._inproc_store.pop(key, None)
        owner = self._inproc_key_owner.pop(key, None)
        if owner and owner in self._inproc_user_index:
            self._inproc_user_index[owner].pop(key, None)
            if not self._inproc_user_index[owner]:
                self._inproc_user_index.pop(owner, None)

    def get(self, tenant_id: str, user_id: str, scope: str) -> Optional[Dict[str, Any]]:
        key = self._cache_key(tenant_id, user_id, scope)
        user_idx = self._user_index_key(tenant_id, user_id)

        # In-process first for fastest reads and to avoid network on hot paths.
        inproc = self._get_inproc(key)
        if inproc is not None:
            return inproc

        redis_client = _get_redis_client()
        if redis_client is not None:
            try:
                raw = redis_client.get(key)
                if raw:
                    payload = json.loads(raw)
                    self._set_inproc(key, user_idx, payload, ttl_seconds=self.default_ttl_seconds)
                    _mark_redis_success()
                    return payload
            except Exception:
                _mark_redis_failure()

        return None

    def set(
        self,
        tenant_id: str,
        user_id: str,
        scope: str,
        payload: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> None:
        key = self._cache_key(tenant_id, user_id, scope)
        user_idx = self._user_index_key(tenant_id, user_id)
        tenant_idx = self._tenant_index_key(tenant_id)
        ttl = self._compute_ttl(ttl_seconds)

        self._set_inproc(key, user_idx, payload, ttl)

        redis_client = _get_redis_client()
        if redis_client is None:
            return

        now = time.time()
        try:
            packed = json.dumps(payload)
            pipe = redis_client.pipeline()
            pipe.setex(key, ttl, packed)
            pipe.zadd(user_idx, {key: now})
            pipe.expire(user_idx, ttl * 2)
            pipe.sadd(tenant_idx, self._safe_part(user_id))
            pipe.expire(tenant_idx, ttl * 2)
            pipe.execute()
            _mark_redis_success()

            card = redis_client.zcard(user_idx)
            overflow = max(0, int(card) - self.per_user_scope_limit)
            if overflow > 0:
                old_keys = redis_client.zrange(user_idx, 0, overflow - 1)
                if old_keys:
                    pipe = redis_client.pipeline()
                    pipe.delete(*old_keys)
                    pipe.zrem(user_idx, *old_keys)
                    pipe.execute()
        except Exception:
            _mark_redis_failure()

    def get_or_build(
        self,
        tenant_id: str,
        user_id: str,
        scope: str,
        builder: Callable[[], Dict[str, Any]],
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        cached = self.get(tenant_id=tenant_id, user_id=user_id, scope=scope)
        if cached is not None:
            return cached
        built = builder()
        self.set(
            tenant_id=tenant_id,
            user_id=user_id,
            scope=scope,
            payload=built,
            ttl_seconds=ttl_seconds,
        )
        return built

    def invalidate_scope(self, tenant_id: str, user_id: str, scope: str) -> None:
        key = self._cache_key(tenant_id, user_id, scope)
        user_idx = self._user_index_key(tenant_id, user_id)

        with self._lock:
            self._drop_inproc_key_unlocked(key)

        redis_client = _get_redis_client()
        if redis_client is not None:
            try:
                redis_client.delete(key)
                redis_client.zrem(user_idx, key)
                _mark_redis_success()
            except Exception:
                _mark_redis_failure()

    def invalidate_user(self, tenant_id: str, user_id: str) -> None:
        user_idx = self._user_index_key(tenant_id, user_id)
        tenant_idx = self._tenant_index_key(tenant_id)
        with self._lock:
            user_scopes = self._inproc_user_index.pop(user_idx, OrderedDict())
            for key in list(user_scopes.keys()):
                self._drop_inproc_key_unlocked(key)

        redis_client = _get_redis_client()
        if redis_client is not None:
            try:
                keys = redis_client.zrange(user_idx, 0, -1)
                pipe = redis_client.pipeline()
                if keys:
                    pipe.delete(*keys)
                pipe.delete(user_idx)
                pipe.srem(tenant_idx, self._safe_part(user_id))
                pipe.execute()
                _mark_redis_success()
            except Exception:
                _mark_redis_failure()


_warm_cache_singleton: Optional[WarmCacheService] = None


def get_warm_cache_service() -> WarmCacheService:
    global _warm_cache_singleton
    if _warm_cache_singleton is None:
        _warm_cache_singleton = WarmCacheService(
            default_ttl_seconds=int(os.getenv("WARM_CACHE_TTL_SECONDS", "900")),
            ttl_jitter_seconds=int(os.getenv("WARM_CACHE_TTL_JITTER_SECONDS", "60")),
            max_inproc_entries=int(os.getenv("WARM_CACHE_MAX_INPROC_ENTRIES", "5000")),
            per_user_scope_limit=int(os.getenv("WARM_CACHE_PER_USER_SCOPE_LIMIT", "32")),
        )
    return _warm_cache_singleton

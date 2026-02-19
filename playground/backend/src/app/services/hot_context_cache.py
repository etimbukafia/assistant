"""In-process hot context cache for per-session conversation memory.

Design:
- per tenant/user/session isolation
- bounded global and per-user session counts
- bounded per-session message/context lists
- TTL expiry for inactive sessions
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import os
import threading
import time
from typing import Any, Dict, List, Optional


class HotContextCacheService:
    _lock = threading.RLock()
    _sessions: "OrderedDict[str, tuple[float, Dict[str, Any]]]" = OrderedDict()
    _user_index: Dict[str, "OrderedDict[str, float]"] = {}
    _session_owner: Dict[str, str] = {}

    def __init__(
        self,
        namespace: str = "hotctx",
        version: str = "v1",
        session_ttl_seconds: int = 900,
        max_sessions_global: int = 4000,
        max_sessions_per_user: int = 20,
        max_messages_per_session: int = 20,
        max_context_entries_per_session: int = 10,
    ) -> None:
        self.namespace = namespace
        self.version = version
        self.session_ttl_seconds = session_ttl_seconds
        self.max_sessions_global = max_sessions_global
        self.max_sessions_per_user = max_sessions_per_user
        self.max_messages_per_session = max_messages_per_session
        self.max_context_entries_per_session = max_context_entries_per_session

    def _safe_part(self, value: str) -> str:
        return (value or "default").strip().replace(":", "_")

    def _session_key(self, tenant_id: str, user_id: str, session_id: str) -> str:
        tenant = self._safe_part(tenant_id)
        user = self._safe_part(user_id)
        session = self._safe_part(session_id)
        return f"{self.namespace}:{self.version}:t:{tenant}:u:{user}:sess:{session}"

    def _user_key(self, tenant_id: str, user_id: str) -> str:
        tenant = self._safe_part(tenant_id)
        user = self._safe_part(user_id)
        return f"{self.namespace}:{self.version}:idx:t:{tenant}:u:{user}"

    def _new_session_payload(self, tenant_id: str, user_id: str, session_id: str) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "messages": [],
            "context_entries": [],
            "deferred_actions": [],
            "created_at": now_iso,
            "updated_at": now_iso,
        }

    def _drop_session_unlocked(self, session_key: str) -> None:
        self._sessions.pop(session_key, None)
        owner = self._session_owner.pop(session_key, None)
        if owner and owner in self._user_index:
            self._user_index[owner].pop(session_key, None)
            if not self._user_index[owner]:
                self._user_index.pop(owner, None)

    def _touch_session_unlocked(self, session_key: str, user_key: str, payload: Dict[str, Any]) -> None:
        expires_at = time.time() + self.session_ttl_seconds
        self._sessions[session_key] = (expires_at, payload)
        self._sessions.move_to_end(session_key)

        if user_key not in self._user_index:
            self._user_index[user_key] = OrderedDict()
        self._user_index[user_key][session_key] = time.time()
        self._user_index[user_key].move_to_end(session_key)
        self._session_owner[session_key] = user_key

        while len(self._user_index[user_key]) > self.max_sessions_per_user:
            oldest_key, _ = self._user_index[user_key].popitem(last=False)
            self._drop_session_unlocked(oldest_key)

        while len(self._sessions) > self.max_sessions_global:
            oldest_key, _ = self._sessions.popitem(last=False)
            owner = self._session_owner.pop(oldest_key, None)
            if owner and owner in self._user_index:
                self._user_index[owner].pop(oldest_key, None)
                if not self._user_index[owner]:
                    self._user_index.pop(owner, None)

    def _get_or_create_session_unlocked(self, tenant_id: str, user_id: str, session_id: str) -> Dict[str, Any]:
        session_key = self._session_key(tenant_id, user_id, session_id)
        user_key = self._user_key(tenant_id, user_id)
        now = time.time()

        item = self._sessions.get(session_key)
        if item is not None:
            expires_at, payload = item
            if expires_at > now:
                self._touch_session_unlocked(session_key, user_key, payload)
                return payload
            self._drop_session_unlocked(session_key)

        payload = self._new_session_payload(tenant_id, user_id, session_id)
        self._touch_session_unlocked(session_key, user_key, payload)
        return payload

    def get_session_state(self, tenant_id: str, user_id: str, session_id: str) -> Dict[str, Any]:
        with self._lock:
            payload = self._get_or_create_session_unlocked(tenant_id, user_id, session_id)
            return {
                "tenant_id": payload["tenant_id"],
                "user_id": payload["user_id"],
                "session_id": payload["session_id"],
                "messages": list(payload["messages"]),
                "context_entries": list(payload["context_entries"]),
                "deferred_actions": list(payload.get("deferred_actions", [])),
                "created_at": payload["created_at"],
                "updated_at": payload["updated_at"],
            }

    def append_message(self, tenant_id: str, user_id: str, session_id: str, role: str, content: str) -> Dict[str, Any]:
        with self._lock:
            payload = self._get_or_create_session_unlocked(tenant_id, user_id, session_id)
            payload["messages"].append(
                {
                    "role": role,
                    "content": content,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            if len(payload["messages"]) > self.max_messages_per_session:
                payload["messages"] = payload["messages"][-self.max_messages_per_session :]
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            return {
                "messages": list(payload["messages"]),
                "context_entries": list(payload["context_entries"]),
                "deferred_actions": list(payload.get("deferred_actions", [])),
            }

    def merge_context_entries(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str,
        entries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        with self._lock:
            payload = self._get_or_create_session_unlocked(tenant_id, user_id, session_id)
            existing = payload["context_entries"]
            by_key = OrderedDict()

            for item in existing:
                key = item.get("id") if item.get("id") is not None else f"anon:{item.get('type')}:{item.get('content')}"
                by_key[str(key)] = item

            for item in entries:
                key = item.get("id") if item.get("id") is not None else f"anon:{item.get('type')}:{item.get('content')}"
                k = str(key)
                if k in by_key:
                    by_key.pop(k)
                by_key[k] = item

            merged = list(by_key.values())[-self.max_context_entries_per_session :]
            payload["context_entries"] = merged
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()

            return {
                "messages": list(payload["messages"]),
                "context_entries": list(payload["context_entries"]),
                "deferred_actions": list(payload.get("deferred_actions", [])),
            }

    def get_deferred_actions(self, tenant_id: str, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            payload = self._get_or_create_session_unlocked(tenant_id, user_id, session_id)
            actions = payload.get("deferred_actions", [])
            return list(actions) if isinstance(actions, list) else []

    def set_deferred_actions(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str,
        actions: List[Dict[str, Any]],
        max_items: int = 20,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            payload = self._get_or_create_session_unlocked(tenant_id, user_id, session_id)
            capped = list(actions or [])[: max(0, max_items)]
            payload["deferred_actions"] = capped
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            return list(capped)

    def invalidate_session(self, tenant_id: str, user_id: str, session_id: str) -> None:
        with self._lock:
            self._drop_session_unlocked(self._session_key(tenant_id, user_id, session_id))

    def invalidate_user(self, tenant_id: str, user_id: str) -> None:
        user_key = self._user_key(tenant_id, user_id)
        with self._lock:
            sessions = self._user_index.pop(user_key, OrderedDict())
            for session_key in list(sessions.keys()):
                self._drop_session_unlocked(session_key)

    def clear_user_context_entries(self, tenant_id: str, user_id: str) -> None:
        user_key = self._user_key(tenant_id, user_id)
        with self._lock:
            sessions = self._user_index.get(user_key, OrderedDict())
            for session_key in list(sessions.keys()):
                item = self._sessions.get(session_key)
                if not item:
                    continue
                _, payload = item
                payload["context_entries"] = []
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._touch_session_unlocked(session_key, user_key, payload)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "sessions": len(self._sessions),
                "users": len(self._user_index),
                "max_sessions_global": self.max_sessions_global,
                "max_sessions_per_user": self.max_sessions_per_user,
                "max_messages_per_session": self.max_messages_per_session,
                "max_context_entries_per_session": self.max_context_entries_per_session,
                "session_ttl_seconds": self.session_ttl_seconds,
            }


_hot_cache_singleton: Optional[HotContextCacheService] = None


def get_hot_context_cache_service() -> HotContextCacheService:
    global _hot_cache_singleton
    if _hot_cache_singleton is None:
        _hot_cache_singleton = HotContextCacheService(
            session_ttl_seconds=int(os.getenv("HOT_CACHE_SESSION_TTL_SECONDS", "900")),
            max_sessions_global=int(os.getenv("HOT_CACHE_MAX_SESSIONS_GLOBAL", "4000")),
            max_sessions_per_user=int(os.getenv("HOT_CACHE_MAX_SESSIONS_PER_USER", "20")),
            max_messages_per_session=int(os.getenv("HOT_CACHE_MAX_MESSAGES_PER_SESSION", "20")),
            max_context_entries_per_session=int(os.getenv("HOT_CACHE_MAX_CONTEXT_ENTRIES_PER_SESSION", "10")),
        )
    return _hot_cache_singleton

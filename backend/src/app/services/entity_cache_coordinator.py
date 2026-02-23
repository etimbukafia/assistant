"""Central cache invalidation coordinator for entity and memory mutations."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

from core.cache import calendar_cache, thread_cache

from app.data.models import ContextEntry
from app.services.action_chips import prewarm_action_chips
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.warm_cache import get_warm_cache_service


logger = logging.getLogger(__name__)
MENTIONS_INDEX_SCOPE = "mentions_index_v1"


class EntityCacheCoordinator:
    """Coordinates invalidation across existing view cache + warm + hot layers."""

    _prewarm_lock = threading.Lock()
    _last_action_chip_prewarm_at: dict[str, float] = {}
    _action_chip_prewarm_inflight: set[str] = set()

    def __init__(self) -> None:
        self.warm_cache = get_warm_cache_service()
        self.hot_cache = get_hot_context_cache_service()

    def invalidate_thread(self, tenant_id: str, user_id: str, thread_id: str) -> None:
        if not user_id or not thread_id:
            return
        thread_cache.invalidate(user_id, thread_id)
        self.warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope=f"thread:{thread_id}")
        self.invalidate_action_chips(tenant_id=tenant_id, user_id=user_id)
        self.invalidate_mentions_index(tenant_id=tenant_id, user_id=user_id)
        self.hot_cache.invalidate_entity_fragments(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="thread",
            entity_id=thread_id,
        )

    def invalidate_event(self, tenant_id: str, user_id: str, event_id: str) -> None:
        if not user_id or not event_id:
            return
        try:
            calendar_cache.invalidate_event(user_id, int(event_id))
        except Exception:
            calendar_cache.invalidate_all(user_id)
        self.warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope=f"event:{event_id}")
        self.invalidate_action_chips(tenant_id=tenant_id, user_id=user_id)
        self.invalidate_mentions_index(tenant_id=tenant_id, user_id=user_id)
        self.hot_cache.invalidate_entity_fragments(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="event",
            entity_id=event_id,
        )

    def invalidate_contact(self, tenant_id: str, user_id: str, contact_id: str) -> None:
        if not user_id or not contact_id:
            return
        self.warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope=f"contact:{contact_id.lower()}")
        self.invalidate_action_chips(tenant_id=tenant_id, user_id=user_id)
        self.invalidate_mentions_index(tenant_id=tenant_id, user_id=user_id)
        self.hot_cache.invalidate_entity_fragments(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="contact",
            entity_id=contact_id.lower(),
        )

    def invalidate_message(self, tenant_id: str, user_id: str, message_id: str) -> None:
        if not user_id or not message_id:
            return
        self.warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope=f"message:{message_id}")
        self.invalidate_action_chips(tenant_id=tenant_id, user_id=user_id)
        self.invalidate_mentions_index(tenant_id=tenant_id, user_id=user_id)
        self.hot_cache.invalidate_entity_fragments(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="message",
            entity_id=message_id,
        )

    def invalidate_task(self, tenant_id: str, user_id: str, task_id: str) -> None:
        if not user_id or not task_id:
            return
        self.warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope=f"task:{task_id}")
        self.invalidate_action_chips(tenant_id=tenant_id, user_id=user_id)
        self.invalidate_mentions_index(tenant_id=tenant_id, user_id=user_id)
        self.hot_cache.invalidate_entity_fragments(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type="task",
            entity_id=task_id,
        )

    def invalidate_profile(self, tenant_id: str, user_id: str) -> None:
        if not user_id:
            return
        self.warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope="profile")
        self.invalidate_action_chips(tenant_id=tenant_id, user_id=user_id)
        self.invalidate_mentions_index(tenant_id=tenant_id, user_id=user_id)
        self.hot_cache.clear_user_context_entries(tenant_id=tenant_id, user_id=user_id)

    def invalidate_action_chips(self, tenant_id: str, user_id: str) -> None:
        if not user_id:
            return
        self.warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope="action_chips_v1")

    def invalidate_mentions_index(self, tenant_id: str, user_id: str) -> None:
        if not user_id:
            return
        self.warm_cache.invalidate_scope(tenant_id=tenant_id, user_id=user_id, scope=MENTIONS_INDEX_SCOPE)

    def prewarm_action_chips(self, db, tenant_id: str, user_id: str) -> None:
        if not user_id:
            return
        cache_key = f"{tenant_id}:{user_id}"
        enabled = (os.getenv("ACTION_CHIPS_MUTATION_PREWARM", "false").strip().lower() in {"1", "true", "yes", "on"})
        if not enabled:
            logger.debug(
                "action_chips_prewarm_skip user=%s reason=mutation_prewarm_disabled",
                user_id,
            )
            return

        min_interval = int(os.getenv("ACTION_CHIPS_PREWARM_MIN_INTERVAL_SECONDS", "60") or "60")
        now = time.time()
        with self._prewarm_lock:
            if cache_key in self._action_chip_prewarm_inflight:
                logger.debug(
                    "action_chips_prewarm_skip user=%s reason=inflight",
                    user_id,
                )
                return
            last_at = self._last_action_chip_prewarm_at.get(cache_key, 0.0)
            if now - last_at < max(5, min_interval):
                logger.debug(
                    "action_chips_prewarm_skip user=%s reason=debounced elapsed_s=%.2f min_interval_s=%s",
                    user_id,
                    now - last_at,
                    min_interval,
                )
                return
            self._action_chip_prewarm_inflight.add(cache_key)

        try:
            prewarm_action_chips(
                db=db,
                warm_cache=self.warm_cache,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            logger.debug("action_chips_prewarm_done user=%s", user_id)
        finally:
            with self._prewarm_lock:
                self._action_chip_prewarm_inflight.discard(cache_key)
                self._last_action_chip_prewarm_at[cache_key] = time.time()

    def invalidate_from_context_entry(self, tenant_id: str, entry: ContextEntry, prior_entry: Optional[ContextEntry] = None) -> None:
        """Invalidate scope based on current and optional prior state of a context entry."""
        self._invalidate_entry_scope(tenant_id, entry)
        if prior_entry is not None:
            self._invalidate_entry_scope(tenant_id, prior_entry)

    def _invalidate_entry_scope(self, tenant_id: str, entry: ContextEntry) -> None:
        entity_type = (entry.entity_type or "").strip()
        entity_id = (entry.entity_id or "").strip()
        user_id = entry.user_id

        if entity_type == "thread" and entity_id:
            self.invalidate_thread(tenant_id=tenant_id, user_id=user_id, thread_id=entity_id)
        elif entity_type == "event" and entity_id:
            self.invalidate_event(tenant_id=tenant_id, user_id=user_id, event_id=entity_id)
        elif entity_type == "contact" and entity_id:
            self.invalidate_contact(tenant_id=tenant_id, user_id=user_id, contact_id=entity_id)
        elif entity_type == "message" and entity_id:
            self.invalidate_message(tenant_id=tenant_id, user_id=user_id, message_id=entity_id)

        if entity_type == "global":
            self.invalidate_profile(tenant_id=tenant_id, user_id=user_id)

# In-Process Hot Cache for Thread Intelligence & Calendar

**Status**: Approved
**Date**: 2026-02-18
**Principle**: The user should never wait for data they've already seen.

---

## Why

Every thread intelligence view runs 4 DB queries (ThreadState, Messages, Tasks, SchedulingSuggestions). Calendar event lists hit the DB on every tab open. For items a user views repeatedly during triage, this is wasted work — the data hasn't changed between views.

## Design

Lightweight in-process `HotCache` using `cachetools.TTLCache`. Per-user isolated stores. Write-through not needed — frontend has optimistic updates via TanStack Query. The cache exists for the *return visit*, not the *current interaction*.

### Two namespaces, two TTLs

| Namespace  | TTL  | Rationale |
|------------|------|-----------|
| `thread`   | 300s | Thread intelligence only changes via processing or user actions. No external mutations. 5 min is safe. |
| `calendar` | 60s  | External calendars (Google/Outlook) can change anytime. 60s limits staleness while absorbing rapid tab/view switches. |

### Tenant Isolation

Stores are keyed by `(user_id, namespace)`. Each user gets their own `TTLCache` instance — no shared eviction pressure, no prefix scanning, no data leakage.

Global store count is bounded via `LRUCache(maxsize=256)`. Inactive users' stores evict naturally. Each user store holds up to 64 entries.

### The API — Three Methods

```python
class HotCache:
    get_or_set(user_id, namespace, key, builder_fn) -> value
    invalidate(user_id, namespace, key)
    invalidate_scope(user_id, namespace)
```

- `get_or_set`: The primary pattern. Pass a builder function, get cached or fresh. The caller doesn't think about cache state.
- `invalidate`: Surgical removal of one entry after a mutation.
- `invalidate_scope`: Drop all entries for a user+namespace. O(1) — drops the entire user store.

---

## Files to Create

### `backend/src/core/cache/__init__.py`

Singleton export:

```python
from .hot_cache import HotCache

hot_cache = HotCache()
```

### `backend/src/core/cache/hot_cache.py`

```python
from cachetools import TTLCache, LRUCache
from threading import Lock
from typing import Callable, TypeVar
import logging

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
        with self._lock:
            store_key = (user_id, namespace)
            store = self._stores.get(store_key)
            if store is not None:
                store.pop(key, None)
                logger.debug("cache invalidate: %s/%s/%s", user_id[:8], namespace, key)

    def invalidate_scope(self, user_id: str, namespace: str):
        with self._lock:
            store_key = (user_id, namespace)
            self._stores.pop(store_key, None)
            logger.debug("cache invalidate_scope: %s/%s", user_id[:8], namespace)
```

---

## Files to Modify

### 1. Thread Intelligence — Cache on Read

**`backend/src/app/routes/v1/messages.py`** — `get_thread_detail()`

- Add `user: AuthenticatedUser = Depends(get_current_user)` param
- Wrap existing query logic in a `build()` function
- Call `hot_cache.get_or_set(user.user_id, "thread", thread_id, build)`
- **Body exclusion**: Before caching, set `body=""` on all messages in the response. The intelligence view uses summary, action_points, decisions, participants, tasks — not the raw body. The `FormattedEmailBody` component in the frontend gets body from the full message query (`fetchMessage`), not from thread detail.

```python
def get_thread_detail(thread_id: str, db: Session = ..., user: AuthenticatedUser = ...):
    def build():
        # ... existing 4 queries ...
        response = build_thread_detail_response(thread_state, messages, tasks, suggestions)
        # Strip bodies before caching — no decrypted PII in memory
        for msg in response["messages"]:
            msg["body"] = ""
        return response

    return hot_cache.get_or_set(user.user_id, "thread", thread_id, build)
```

### 2. Thread Intelligence — Invalidate on Mutations

**`backend/src/app/routes/v1/messages.py`**:
- `update_message_status()` — after commit: `hot_cache.invalidate(user_id, "thread", message.thread_id)`
- `mark_message_done()` — same
- `archive_message()` — same
- `delete_message()` — same
- `send_reply()` — after `needs_reply` update
- `reprocess_message()` — after reprocessing

**`backend/src/app/routes/v1/tasks.py`**:
- `approve_task()`, `dismiss_task()`, `complete_task()`, `update_task()`, `create_task()` — after commit: `hot_cache.invalidate(user_id, "thread", task.thread_id)`

**`backend/src/app/routes/v1/scheduling.py`**:
- `send_suggestion()`, `dismiss_suggestion()` — after commit: `hot_cache.invalidate(user_id, "thread", suggestion.thread_id)`

**`backend/src/app/handlers/scheduling_handlers.py`**:
- `handle_scheduling_intent()` — invalidate after creating SchedulingSuggestion

**`backend/src/app/services/thread_state.py`**:
- After `process_message()` commit: `hot_cache.invalidate(user_id, "thread", thread_id)`

### 3. Calendar — Cache on Read

**`backend/src/app/routes/v1/calendar.py`**:

- `get_calendar_events()` — add `user` dependency
  - Cache key: `f"events:{status}:{limit}:{offset}"` (or whatever filter params the endpoint uses)
  - `hot_cache.get_or_set(user.user_id, "calendar", cache_key, build)`

- `get_calendar_event()` — add `user` dependency
  - Cache key: `f"event:{event_id}"`
  - `hot_cache.get_or_set(user.user_id, "calendar", cache_key, build)`

60s TTL. Rapid view switches and tab reopens are instant. External calendar changes visible within 1 minute.

### 4. Calendar — Invalidate on Mutations

**`backend/src/app/routes/v1/calendar.py`**:
- `create_event()`, `create_manual_event()`, `update_event()`, `delete_event()`, `sync_calendar()` — after commit: `hot_cache.invalidate_scope(user.user_id, "calendar")`
  - `invalidate_scope` because list queries depend on filters — creating/deleting an event affects every list permutation
- `generate_briefing()`, `generate_followups()` — `hot_cache.invalidate(user.user_id, "calendar", f"event:{event_id}")`

### 5. Dependency

**`backend/requirements.txt`** — Add `cachetools`

---

## What We're NOT Doing

- **No write-through**: Frontend has optimistic updates. The user sees instant changes regardless. Cache is for the return visit.
- **No distributed cache**: Single-process deployment. Redis adds operational cost for zero benefit.
- **No cache warming**: A cache miss costs ~20ms (4 indexed SELECTs). Not worth the complexity.
- **No cache headers/ETags**: Frontend manages staleness via TanStack Query `staleTime`. Backend cache is purely server-side.

---

## Verification

1. **Unit tests** — `HotCache`: get_or_set, invalidate, invalidate_scope, TTL expiry, namespace isolation, user isolation, LRU eviction of inactive user stores
2. **Manual — thread intelligence**:
   - Process an email via `/sync` → open thread view → verify DB hit (log: "cache set")
   - Open same thread again → verify cache hit (log: "cache hit")
   - Approve a task → reopen thread → verify cache miss (log: "cache invalidate" then "cache set")
3. **Manual — calendar**:
   - Fetch `GET /calendar/events` → verify DB hit
   - Fetch again within 60s → verify cache hit
   - Create event → fetch list → verify cache miss (scope invalidated)
   - Wait 60s → fetch again → verify TTL expiry and rebuild
4. **Regression**: `pytest -m "not slow and not live"` — no breakage

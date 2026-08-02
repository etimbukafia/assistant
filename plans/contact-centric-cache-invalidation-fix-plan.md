# Contact-Centric Cache Invalidation Fix Plan

## Objective
Make contact-facing caches correct when contacts, contact-scoped memory, messages, threads, tasks, and calendar events change.

## Current cache surfaces
- Warm cache scopes:
  - `contact:{email}` via `build_contact_snapshot(...)`
  - `thread:{thread_id}`
  - `event:{event_id}`
  - `message:{message_id}`
  - `mentions_index_v1`
  - `action_chips_v1`
- Hot cache entity fragments:
  - `contact`
  - `thread`
  - `event`
  - `message`
  - `task`

## Fixes by file

### 1. `backend/src/app/services/entity_cache_coordinator.py`
- Add bulk helpers:
  - `invalidate_contacts(...)`
  - `invalidate_contact_by_id(...)`
  - `invalidate_contact_related(...)`
- Add cross-entity invalidation helpers:
  - `invalidate_message_and_related_contact(...)`
  - `invalidate_thread_and_related_contact(...)`
  - `invalidate_event_and_related_contacts(...)`
  - `invalidate_task_and_related_contact(...)`
- Extend `invalidate_from_context_entry(...)` to invalidate linked entities from `DiaryEntryLink`, not just `entry.entity_type/entity_id`.

### 2. `backend/src/app/routes/v1/tasks.py`
- On create/update/approve/dismiss/complete/snooze:
  - keep `invalidate_thread(...)`
  - also invalidate related contact cache derived from:
    - `task.thread_id`
    - source `Message.contact_id`
    - linked `ThreadState.contact_id`
- Manual tasks should invalidate profile/action chips only, not arbitrary contacts.

### 3. `backend/src/app/routes/v1/messages.py`
- After message create/sync/reprocess/status/send/delete:
  - invalidate thread scope
  - invalidate message scope
  - invalidate related contact scope using `message.contact_id` and/or linked thread contact
- Initial sync, webhook sync, and delete paths should all share one helper for this.

### 4. `backend/src/app/services/thread_state.py`
- Replace bare `thread_cache.invalidate(...)` with coordinator-driven invalidation.
- When thread summary, `needs_reply`, decisions, participants, `contact_id`, or message counts change:
  - invalidate thread scope
  - invalidate related contact scope if `thread_state.contact_id` exists

### 5. `backend/src/app/routes/v1/calendar.py`
- On create/update/delete/sync/briefing/followups:
  - invalidate event scope
  - invalidate contact scopes for matching participants
- Add helper that resolves participant emails to canonical contacts before invalidation.

### 6. `backend/src/app/routes/v1/webhooks.py`
- After Gmail/Outlook ingestion:
  - invalidate related thread/message/contact scopes for affected records
- Current ingestion links contacts and thread state but relies mostly on TTL.

### 7. `backend/src/app/jobs/worker.py`
- After background email backfill / provider ingestion mutations:
  - invalidate contact + thread scopes for affected entities
- Background paths must match route-level invalidation behavior.

### 8. `backend/src/app/routes/v1/vault.py`
- When `ContextEntry` links change, invalidate all linked entity scopes, especially linked contacts.
- Current invalidation only follows `entry.entity_type/entity_id`.

### 9. `backend/src/app/services/contact_linking.py`
- When `link_thread_state(...)` assigns a `contact_id`, trigger contact + thread invalidation through caller-owned helpers.
- Do not keep linkage side effects cache-blind.

## Tests to add
- `backend/tests/unit/test_entity_cache_coordinator.py`
  - linked `DiaryEntryLink` invalidates contact scope
  - task/message/thread/event invalidation fans out to contact scope
- `backend/tests/integration/test_contact_cache_invalidation.py`
  - cached contact snapshot refreshes after task change
  - cached contact snapshot refreshes after new linked message
  - cached contact snapshot refreshes after meeting participant update
  - unrelated contact cache remains warm

## Acceptance criteria
- Contact brief/snapshot/mention preview is refreshed after any material linked change.
- Correctness does not depend on cache TTL.
- Invalidation remains user-scoped and contact-scoped, not global-by-default.

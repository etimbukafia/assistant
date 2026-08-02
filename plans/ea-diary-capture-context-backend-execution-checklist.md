# EA Diary: Capture Context Backend Execution Checklist

## Objective
Replace typed diary entry creation with a capture-first backend flow:
- assistant submits raw text + required scope
- backend saves immediately
- Gemma classifies asynchronously
- user can correct category later

## Phase 1: Data Model
### 1. Extend `ContextEntry`
- [x] Review `backend/src/app/data/models.py`
- [x] Add fields needed for capture-first flow:
  - `raw_text`
  - `classification_status`
  - `classification_confidence`
  - `user_corrected`
  - optional `classification_rationale`
- [x] Keep `type` as the canonical category used by retrieval
- [x] Default initial category to `insight` at save time

### 2. Add migration
- [x] Create migration under `backend/migrations/`
- [x] Backfill existing rows safely
- [x] Ensure null/default behavior works for legacy typed entries

## Phase 2: Schemas
### 3. Add capture-oriented request/response models
- [x] Update `backend/src/app/data/schemas.py`
- [x] Add:
  - `ContextCaptureCreate`
  - `ContextCaptureUpdate`
  - `ContextCaptureResponse`
- [x] Require:
  - `text`
  - `scope_type`
  - `scope_id`
- [x] Support explicit `global` scope

### 4. Keep compatibility for legacy typed create
- [x] Removed legacy typed create surface instead of preserving it
- [x] Canonical creation now flows through capture-first routes only

## Phase 3: Route Layer
### 5. Add capture endpoint
- [x] Update `backend/src/app/routes/v1/vault.py`
- [x] Add `POST /v1/context/captures`
- [x] Save immediately with:
  - raw text
  - explicit scope
  - initial `type="insight"`
  - `classification_status="pending"`
- [x] Validate scope:
  - contact
  - email/message
  - task
  - event
  - explicit global

### 6. Add correction/update endpoint
- [x] Add `PATCH /v1/context/captures/{id}`
- [x] Allow updating:
  - category
  - raw text
  - primary scope
  - secondary links
- [x] Set `user_corrected=True` on manual category change

### 7. Maintain cache invalidation
- [x] Reuse `EntityCacheCoordinator`
- [x] Invalidate relevant contact/thread/event/message scopes after:
  - capture save
  - classifier update
  - user correction

## Phase 4: Classification Pipeline
### 8. Add capture classification service
- [x] Create service under `backend/src/app/services/`
- [x] Input:
  - raw text
  - primary scope
  - linked contact/entity context if available
- [x] Output:
  - category
  - confidence
  - optional rationale
  - optional secondary links

### 9. Add queue worker task
- [x] Register `classify_context_capture` in `backend/src/app/jobs/worker.py`
- [x] Enqueue after save
- [x] Skip overwrite when `user_corrected=True`

### 10. Apply low-confidence rule
- [x] If confidence below threshold, store category as `insight`
- [x] Mark classification result as uncertain
- [x] Persist original classifier output if different

## Phase 5: Linking
### 11. Support explicit primary scope
- [x] Ensure new capture flow always stores one primary scope
- [x] Make `global` explicit rather than fallback

### 12. Add optional secondary linking
- [x] Store secondary links using `DiaryEntryLink`
- [x] Only add them automatically when confidence is high
- [x] Do not block save on secondary-link inference

## Phase 6: Notifications and Feedback
### 13. Add classification result event/notification
- [x] Emit result after async classification
- [x] Support messages like:
  - `Saved as Decision for Sarah`
  - `Saved as Insight for Sarah. Teeks was unsure, so it used Insight.`

### 14. Preserve correction UX support in response shape
- [x] Return enough data for the frontend to show:
  - current category
  - uncertainty state
  - change-category action

## Phase 7: Retrieval Compatibility
### 15. Keep downstream systems working
- [x] Verify `ContactBriefService` still uses `ContextEntry.type`
- [x] Verify contact timeline/signals still work with new entries
- [x] Verify chat/drafting/meeting-prep continue consuming categorized entries

## Phase 8: Security and Privacy
### 16. Scope validation
- [x] Ensure users can only save against their own contact/entity records
- [x] Prevent invalid or cross-user scope references

### 17. Classification safety
- [x] Preserve original text
- [x] Do not let classifier overwrite user corrections
- [x] Sanitize classification rationale/secondary-link labels before user-facing output if surfaced

## Phase 9: Observability
### 18. Add capture-flow observability
- [x] Log/measure:
  - capture save rate
  - classification latency
  - low-confidence fallback rate
  - correction rate
  - secondary-link attach rate

## Phase 10: Tests
### 19. Add model/schema tests
- [x] Verify default pending/insight behavior
- [x] Verify explicit global scope support

### 20. Add route tests
- [x] Capture save with contact scope
- [x] Capture save with event/task/message scope
- [x] Capture save with explicit global scope
- [x] Manual correction updates category and sets `user_corrected`

### 21. Add worker/classifier tests
- [x] High-confidence classification applies detected category
- [x] Low-confidence classification falls back to `insight`
- [x] User-corrected category is not overwritten
- [x] Secondary links only attach when confidence is high

### 22. Add cache invalidation tests
- [x] Capture save invalidates relevant scoped caches
- [x] Classifier update invalidates relevant scoped caches
- [x] Manual correction invalidates relevant scoped caches

## Current Status
- Phase 1 is implemented.
- Phase 2 is implemented in code, with runtime `pytest` still pending in the backend venv.
- Remaining open items are the unchecked entries above.

## Recommended Execution Order
1. `models.py`
2. migration
3. `schemas.py`
4. capture route
5. queue task + worker registration
6. classifier service
7. correction route
8. cache invalidation hooks
9. notification/result event
10. regression tests

## Definition Of Done
- assistants can save context without picking a category
- scope is always explicit
- classification runs asynchronously
- low-confidence results default to `insight`
- users can correct category
- downstream retrieval still works with the resulting entries

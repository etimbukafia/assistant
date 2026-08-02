# EA Diary: Capture Context Implementation Plan

## Objective
Transform the EA diary from a typed documentation system into a fast `Capture Context` workflow while preserving enough structure for retrieval, contact briefs, timeline, and signals.

## Product Decisions Locked
- category is not chosen during capture
- scope is required before save
- `global` must be explicit
- low-confidence classification falls back to `insight`
- users can always change category after classification
- primary scope is user-selected
- secondary links can be added automatically only when confidence is high

## Current System Reuse
Reuse:
- `Contact`
- `ContextEntry`
- `DiaryEntryLink`
- existing contact/entity retrieval
- existing worker/queue infrastructure
- Gemma-based classification path

Do not introduce a parallel memory system.

## Target Backend Model
Keep `ContextEntry` as the canonical stored record, but change how it is created.

Capture writes should support:
- `raw_text`
- `entity_type`
- `entity_id`
- placeholder/default `type="insight"` on initial save
- `classification_status`
  - `pending`
  - `classified`
  - `user_corrected`
- `classification_confidence`
- `user_corrected`

If existing schema cannot support these cleanly, add them with a migration rather than inventing a second table.

## Phase 1: API + Data Model
1. Update context-entry schema/input model
   - add a capture-oriented request shape
   - remove required manual category from the new capture endpoint
   - keep existing typed endpoint temporarily for compatibility

2. Add a new endpoint
   - `POST /v1/context/captures`
   - request:
     - `text`
     - `scope_type`
     - `scope_id`
   - response:
     - saved record
     - initial category=`insight`
     - classification status=`pending`

3. Add persistence fields
   - `classification_status`
   - `classification_confidence`
   - `user_corrected`

## Phase 2: Async Classification
1. Add a worker task
   - `classify_context_capture`

2. Gemma classifier output
   - `category`
   - `confidence`
   - optional short rationale
   - optional secondary links

3. Classification rules
   - if confidence < threshold -> `insight`
   - if confidence >= threshold -> detected category
   - never overwrite if `user_corrected=True`

4. Emit a notification/update payload
   - `Saved as Decision for Sarah`
   - or low-confidence `Saved as Insight... Teeks was unsure...`

## Phase 3: Editing + Correction
1. Add category correction endpoint
   - `PATCH /v1/context/captures/{id}`
   - allow:
     - category
     - scope
     - links
     - text

2. On manual correction
   - set `user_corrected=True`
   - preserve original classifier output for audit/debug

## Phase 4: UI Simplification
1. Replace diary typed form with one capture box
2. Require one scope picker
3. Preselect scope from current screen context
4. Save immediately
5. Show lightweight post-save classification toast/banner
6. Add one-click `Change category`

## Phase 5: Retrieval + Product Integration
1. Ensure contact briefs continue consuming `ContextEntry.type`
2. Ensure timeline/signals use corrected category, not only original classification
3. Make chat/drafting/meeting-prep consume the updated entries without code branching

## Phase 6: Migration
1. Keep legacy manual typed flow temporarily behind compatibility routes
   - status: done; compatibility routes remain deprecated-only
2. Migrate diary UI to new capture flow
   - status: done
3. Remove category selection from the primary UX
   - status: done
4. Deprecate the old typed-create experience after validation
   - status: in progress; canonical frontend now uses `/context/captures*` and `/contacts*`

## Backend Files Likely To Change
- `backend/src/app/data/models.py`
- `backend/src/app/data/schemas.py`
- `backend/src/app/routes/v1/vault.py`
- `backend/src/app/routes/v1/contacts.py` if capture is exposed there contextually
- `backend/src/app/jobs/worker.py`
- new classifier service, likely under `backend/src/app/services/`
- queue registration

## Frontend Files Likely To Change
- diary capture surfaces in `frontend/src/app/...`
- any diary/context composer component
- contact/event/task contextual capture entry points
- toast/notification UI for classification result

## Key Tradeoffs
1. Backend complexity increases
   - classification, retries, confidence handling, correction state

2. Temporary async mismatch
   - captured note may be saved before final category is known

3. Retrieval quality depends on classification quality
   - mitigated by low-confidence fallback to `insight`
   - mitigated by user correction

The tradeoff is worth it because it removes assistant-side cognitive load.

## Definition Of Done
- assistants can save context without selecting category
- scope is always explicit
- classification runs asynchronously
- low-confidence results default to `insight`
- users can correct category easily
- contact briefs/timeline/signals continue working from the resulting entries

# Plan: Split Task Type vs Task Signal

## Goal
Separate task “work category” from detection provenance, so `task_type` reflects what work it is, and a new `task_signal` reflects how it was inferred. Move `waiting_for` out of type into status/metadata.

## Scope
Backend model + schema + migrations, task creation pipeline, AI/pattern tracking, briefing/digest logic, and frontend task display/filters.

## Steps
1. **Model & Migration**
   - Add `task_signal` column to `Task` (enum/string: `explicit`, `implied`, `inferred_pattern`).
   - Normalize `task_type` to category values (e.g., `follow_up`, `scheduling`, `prep`, `decision`, `review`, `other`).
   - Data migration mapping:
     - `explicit` ? `task_signal=explicit`, `task_type=other` (or inferred category if available)
     - `implied_followup` ? `task_signal=implied`, `task_type=follow_up`
     - `meeting_prep` ? `task_signal=explicit|implied` (default explicit), `task_type=prep`
     - `waiting_for` ? `task_signal=explicit|implied` (default explicit), `task_type=follow_up` and keep `status=waiting_for`

2. **API & Schemas**
   - Update Task schemas to expose `task_type` + `task_signal`.
   - Update task create/update routes to accept `task_type` (category) and `task_signal` (optional, default explicit for manual).
   - Update validation + serialization aliases where needed.

3. **Task Creation Pipeline**
   - Update email processing / thread_state to emit both fields.
   - Update AI extraction output contract to include `task_type` and `task_signal` separately.

4. **Downstream Logic Updates**
   - Update `briefing`, `digest`, `follow_up` modules to use `task_type` categories.
   - Update `pattern_tracker` to use `task_signal` for explainability and `task_type` for action categories.

5. **Frontend**
   - Update Task type usage to display `task_type` category labels.
   - Adjust filters and tag mapping if they currently rely on old `task_type` values.

6. **Backfill + Verification**
   - Run migration on existing data and spot-check:
     - `waiting_for` tasks keep `status=waiting_for`
     - follow-up related tasks retain appropriate category
   - Confirm chat/briefing/digest outputs with updated field names.

## Acceptance Criteria
- No references to old mixed `task_type` values remain.
- Task API returns `task_type` (category) and `task_signal` (detection).
- Existing tasks migrated without loss of “waiting_for” behavior.
- UI filters and AI summaries behave as expected.

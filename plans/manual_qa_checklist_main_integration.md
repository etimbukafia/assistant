# Main Integration Manual QA Checklist

## 0) Setup
- [ ✅] Backend starts cleanly: `uvicorn main:app --reload` from `backend/`
- [ ✅] Frontend starts cleanly: `npm run dev` from `frontend/`
- [ ✅] Chat API reachable: `GET /v1/chat/sessions`
- [ ✅] Diary API reachable: `GET /v1/vault/diary/contacts`

## 1) Diary: Contacts
- [ ] Create contact with `name` + `email` succeeds
- [ ] Create duplicate contact with same `email` returns conflict and UI toast
- [ ] Create second contact with same `name` + different `email` succeeds
- [ ] Create same `name` without email when same-name already exists returns guided conflict message
- [ ] Update contact email invalidates mention resolution immediately
- [ ] Delete contact removes it from mention suggestions

## 2) Diary: Remember Entries
- [ ] Create `decision` for `executive` succeeds
- [ ] Create `preferences` for `assistant` succeeds
- [ ] Create `commitment` for `thread` with `entity_id` succeeds
- [ ] Create `relationships` for `contact` with email `entity_id` succeeds
- [ ] Create entry with `status=resolved` and `expires_at` in past saves correctly
- [ ] Update entry `status` from `active` -> `resolved` invalidates warm scope
- [ ] Delete entry invalidates related scope and removes from retrieval

## 3) Diary: Linked References
- [ ] Create `thread` reference appears in mention suggestions
- [ ] Create `event` reference appears in mention suggestions
- [ ] Create `message` reference appears in mention suggestions
- [ ] Update reference display name reflects in `@` picker
- [ ] Delete reference removes from `@` picker

## 4) Mentions
- [ ] Typing `@` opens suggestions
- [ ] Typing `@a` filters suggestions by prefix/substr
- [ ] Suggestions include `kind/ref/label` and render label correctly
- [ ] Selecting a suggestion inserts `@label` into input
- [ ] Sent payload includes structured mentions (`kind/ref/label`)
- [ ] Backend resolves mentions and logs `chat_mentions_resolved`

## 5) Chat: Tool Use + Gating
- [ ✅] Greeting (`hi`) does not trigger context tool calls
- [ ✅] Simple self-contained request avoids unnecessary retrieval
- [ ✅] Entity-referenced request (`@thread`) triggers relevant context tools
- [✅ ] Draft request triggers `draft_email`
- [ ] Meeting brief request triggers `generate_meeting_brief`
- [ ] Tool failures return human-safe response (no provider/internal wording)

## 6) Chat: Multi-Action Cap
- [ ] One message requesting 6+ actions executes up to 5 actions
- [ ] Response naturally confirms completed items and asks to continue remaining
- [ ] Follow-up (`continue`, `proceed`, `go on`) executes deferred actions
- [ ] Deferred actions persist in session state across turns
- [ ] Per-action failure does not fail whole request

## 7) Cache Invalidation
- [ ] Update thread-scoped entry invalidates:
- [ ] `thread_cache`
- [ ] warm scope `thread:*`
- [ ] hot session fragments for that thread
- [ ] Update event-scoped entry invalidates:
- [ ] `calendar_cache`
- [ ] warm scope `event:*`
- [ ] hot session fragments for that event
- [ ] Update contact-scoped entry invalidates warm/hot contact scopes
- [ ] Update message-scoped entry invalidates warm/hot message scopes
- [ ] Update assistant/executive preferences invalidates profile warm snapshot

## 8) Error Handling + Logs
- [ ] If Gemini unavailable (503), user sees task-specific natural fallback
- [ ] Async job failure message is human-safe
- [ ] Logs include:
- [ ] `chat_request` (route)
- [ ] `chat_mentions_resolved` (service)
- [ ] `chat_context_trace` (orchestrator)
- [ ] No raw stack traces returned in API response body

## 9) UI/UX Regression
- [ ] Chat page remains command-surface style and responsive (desktop/mobile)
- [ ] Inbox and Calendar tabs are unchanged and still functional
- [ ] Diary page is create-first (no dense entity browser list)
- [ ] Conflict and validation toasts appear for diary forms
- [ ] Mention dropdown keyboard navigation (up/down/enter/escape) works

## 10) Data Integrity
- [ ] `context_entries.entity_type` only uses allowed values
- [ ] `context_entries.status` only uses allowed values
- [ ] `contacts` uniqueness enforced on `(user_id, email)`
- [ ] `entity_references` uniqueness enforced on `(user_id, entity_type, display_name)` and `(user_id, entity_type, ref)`
- [ ] No cross-user data leakage in mentions, context tools, or diary endpoints

## 11) Smoke Scenarios
- [ ] Draft reply for `@thread` + `@contact`
- [ ] Generate meeting brief for `@event`
- [ ] Ask “What changed since yesterday for @contact?”
- [ ] Ask “What did we decide on @thread?”
- [ ] Create diary memory, then verify it is used by a follow-up chat request

---

## 12) Tasks

### 12a) Task Creation
- [ ] AI-detected task (from email) created via `POST /v1/tasks/` with valid `message_id` succeeds
- [✅] Manual task created via `POST /v1/tasks/manual` (no `message_id`) succeeds and uses placeholder message
- [ ✅] Manual task with `deadline` saves `deadline_source=explicit` and `deadline_user_confirmed=true`
- [ ] Manual task without `deadline` saves `deadline_user_confirmed=false`
- [✅ ] Creating a task removes it from `extracted_tasks` on the source message
- [✅ ] Creating a task with invalid `message_id` returns 404

### 12b) Task Lifecycle Transitions
- [ ] `approve` → moves `pending_approval` to `approved`, sets `approved_at`
- [ ] Approving a task with `scheduled_reminder_at` enqueues `evaluate_reminder` job
- [ ] `dismiss` → moves any status to `dismissed`, sets `dismissed_at`
- [ ] `start` → moves `waiting_for` to `in_progress`
- [ ] `complete` → sets `status=completed`, `completed_at`
- [ ] `snooze` → sets `status=snoozed`, `snoozed_until`
- [ ] Any action on a non-existent task returns 404

### 12c) Task Update (Edit)
- [ ] `PUT /v1/tasks/{id}` with `title` / `description` / `priority` updates those fields
- [ ] Setting `priority` explicitly clears `urgency_suggested_by_ai`
- [ ] Setting `deadline` stores `deadline_source=explicit` and `deadline_user_confirmed=true`
- [ ] Setting `deadline_confirmed=true` sets `deadline_user_confirmed=true` without overriding the deadline value
- [ ] Setting `mark_urgent=true` sets `priority=urgent` and clears `urgency_suggested_by_ai`
- [ ] Setting `clear_deadline=true` nulls `deadline`, `deadline_source`, and `deadline_confidence`
- [ ] Thread-linked task update triggers cache invalidation + prewarm of action chips

### 12d) Listing + Filtering
- [ ] Default sort returns tasks ranked urgent → high → normal → low, then `created_at DESC`
- [ ] `?status=approved` filters to a single status
- [ ] `?status=approved,in_progress` returns tasks matching either status
- [ ] `?priorities=urgent,high` filters by multiple priorities
- [ ] `?sort=created_at` returns tasks sorted by `created_at DESC`
- [ ] Pagination: `limit` + `offset` return the correct slice; `total` reflects the unfiltered count

### 12e) Task Stats
- [ ] `GET /v1/tasks/stats` returns counts for all statuses: `pending_approval`, `approved`, `in_progress`, `waiting_for`, `completed`, `dismissed`
- [ ] `overdue` count correctly reflects tasks with `scheduled_reminder_at` in the past and status `approved` or `pending_approval`

### 12f) UI — TaskItem Interactions
- [ ] `pending_approval` task renders with dashed border and Approve / Reject buttons
- [ ] Clicking Approve calls approve endpoint; task updates status optimistically in list
- [ ] Clicking Reject calls dismiss endpoint; task fades or is removed from list
- [ ] `waiting_for` task shows "Start" button; clicking transitions it to `in_progress`
- [ ] `approved` / `in_progress` task shows Complete button; clicking marks it done with strikethrough + opacity
- [ ] `completed` and `dismissed` tasks render at 50 % opacity with strikethrough title
- [ ] Deadline badge is visible for non-completed/dismissed tasks that have `deadline_at`
- [ ] Keyboard navigation: Enter / Space activates task open-details when `onOpenDetails` is set

---

## 13) Daily Focus

### 13a) Daily Focus API
- [ ] `GET /v1/focus/daily` with no `?date` returns today's focus, creating an empty row if none exists
- [ ] `GET /v1/focus/daily?date=YYYY-MM-DD` returns focus for the specified date
- [ ] `GET /v1/focus/daily?date=invalid` returns 400 with "Invalid date format. Use YYYY-MM-DD."
- [ ] `PUT /v1/focus/daily` with 1–3 goals saves and returns updated focus
- [ ] `PUT /v1/focus/daily` with 4+ goals returns 400 "Maximum 3 goals allowed"
- [ ] `PUT /v1/focus/daily` with `frog_task_id` of a valid, owned, non-completed task sets the frog
- [ ] `PUT /v1/focus/daily` with `frog_task_id` of a completed or dismissed task returns 400
- [ ] `PUT /v1/focus/daily` with `frog_task_id` of another user's task returns 404
- [ ] `PUT /v1/focus/daily` with `frog_task_id=null` (or `0`) clears the frog task
- [ ] `PUT /v1/focus/daily` with `weekly_target` propagates the value to all other rows in the same ISO week

### 13b) Weekly Summary API
- [ ] `GET /v1/focus/weekly-summary` returns focus rows for the current ISO week (Mon–Sun)
- [ ] `total_goals_set` equals the sum of `goals_total` across all returned days
- [ ] `total_goals_completed` equals the sum of `goals_completed` across all returned days
- [ ] `tasks_completed_this_week` counts tasks with `status=completed` and `completed_at` within the current week
- [ ] `weekly_target` reflects the shared weekly target text (drawn from the first row)

### 13c) Goals UI
- [ ] Adding a goal (up to 3) renders in the list without a page reload
- [ ] Toggling a goal's completed state updates `goals_completed` counter and visual indicator
- [ ] Completing all 3 goals shows progress at 3/3
- [ ] Removing a goal decrements `goals_total` and saves correctly

### 13d) Frog Task
- [ ] Selecting a frog task from the active task list links it to today's focus
- [ ] Frog task is rendered distinctly in Focus view (title visible, actionable)
- [ ] Completing the frog from Focus view marks it done and clears the frog slot gracefully
- [ ] Setting a completed task as the frog returns 400 (enforced server-side, not just client-side)

### 13e) Weekly Target
- [ ] Setting weekly target on any day of the week persists it to all 7 days in that ISO week
- [ ] Updating the weekly target on a later day retroactively updates earlier rows in the DB
- [ ] Weekly target text appears in both daily focus and weekly summary views

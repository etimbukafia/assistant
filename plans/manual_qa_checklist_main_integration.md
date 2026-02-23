# Main Integration Manual QA Checklist

## 0) Setup
- [ ✅] Backend starts cleanly: `uvicorn main:app --reload` from `backend/`
- [ ✅] Frontend starts cleanly: `npm run dev` from `frontend/`
- [ ✅] Chat API reachable: `GET /v1/chat/sessions`
- [ ✅] Diary API reachable: `GET /v1/vault/diary/contacts`

## 1) Diary: Contacts
- [ ✅] Create contact with `name` + `email` succeeds
- [ ✅] Create duplicate contact with same `email` returns conflict and UI toast
- [ ✅] Create second contact with same `name` + different `email` succeeds
- [ ✅] Create same `name` without email when same-name already exists returns guided conflict message
- [ ✅] Update contact email invalidates mention resolution immediately
- [ ✅] Delete contact removes it from mention suggestions

## 2) Diary: Remember Entries
- [ ✅] Create `decision` for `executive` succeeds. Note: not how it works
- [ ✅] Create `preferences` for `assistant` succeeds
- [ ✅] Create `commitment` for `thread` with `entity_id` succeeds
- [✅ ] Create `relationships` for `contact` with email `entity_id` succeeds
- [ ✅] Create entry with `status=resolved` and `expires_at` in past saves correctly
- [ ] Update entry `status` from `active` -> `resolved` invalidates warm scope
- [ ✅] Delete entry invalidates related scope and removes from retrieval

## 3) Diary: Linked References
- [ ✅] Create `thread` reference appears in mention suggestions
- [ ✅] Create `event` reference appears in mention suggestions
- [ ✅] Create `message` reference appears in mention suggestions
- [ ✅] Update reference display name reflects in `@` picker
- [ ✅] Delete reference removes from `@` picker

## 4) Mentions
- [✅ ] Typing `@` opens suggestions
- [✅ ] Typing `@a` filters suggestions by prefix/substr
- [✅ ] Suggestions include `kind/ref/label` and render label correctly
- [✅ ] Selecting a suggestion inserts `@label` into input
- [✅ ] Sent payload includes structured mentions (`kind/ref/label`)
- [✅ ] Backend resolves mentions and logs `chat_mentions_resolved`

## 5) Chat: Tool Use + Gating
- [✅ ] Greeting (`hi`) does not trigger context/tool calls
- [✅ ] Simple self-contained request avoids unnecessary retrieval
- [ ] Mention-referenced request (`@thread`, `@contact`, `@event`) allows tool use
- [ ] Mention presence does not force tool calls when response is already self-contained
- [ ] No-mention draft request returns a normal LLM draft (no tool path)
- [ ] `draft_email` tool is used only when references/context make it necessary
- [ ] `generate_meeting_brief` tool is used when meeting/event context is required
- [ ] Tool failures return human-safe response (no provider/internal wording)
- [ ] `chat_context_trace` logs accurate `tool_records` and `action_records`

## 6) Chat: Multi-Action + DAG Planner
- [ ] One message with 6+ action requests is decomposed into atomic sub-requests
- [ ] Mixed request with actions + trivial question handles both (actions executed, trivial answered)
- [ ] Up to 5 actions execute in current turn; overflow remains deferred
- [ ] Assistant response confirms completed actions and naturally asks whether to continue deferred ones
- [ ] Follow-up (`continue`, `proceed`, `go on`, `run`) executes deferred actions
- [ ] Deferred actions persist in session state across turns
- [ ] Dependency ordering is respected (downstream action runs only after prerequisite succeeds)
- [ ] Per-action failure does not fail the whole request
- [ ] Failed node is reported clearly while independent nodes still complete
- [ ] Re-running continuation does not duplicate already completed actions
- [ ] Truly blocking ambiguity asks one concise clarifying question
- [ ] Low-risk ambiguity proceeds without unnecessary blocking

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
- [✅ ] Manual task without `deadline` saves `deadline_user_confirmed=false`
- [✅ ] Creating a task removes it from `extracted_tasks` on the source message
- [✅ ] Creating a task with invalid `message_id` returns 404

### 12b) Task Lifecycle Transitions
- [✅ ] `approve` → moves `pending_approval` to `approved`, sets `approved_at`
- [ ] Approving a task with `scheduled_reminder_at` enqueues `evaluate_reminder` job
- [✅ ] `dismiss` → moves any status to `dismissed`, sets `dismissed_at`
- [ ✅] `start` → moves `waiting_for` to `in_progress`
- [✅ ] `complete` → sets `status=completed`, `completed_at`
- [✅ ] `snooze` → sets `status=snoozed`, `snoozed_until` - no "snooze"
- [ ✅] Any action on a non-existent task returns 404

### 12c) Task Update (Edit)
- [✅ ] `PUT /v1/tasks/{id}` with `title` / `description` / `priority` updates those fields
- [✅ ] Setting `priority` explicitly clears `urgency_suggested_by_ai`
- [✅ ] Setting `deadline` stores `deadline_source=explicit` and `deadline_user_confirmed=true`
- [✅ ] Setting `deadline_confirmed=true` sets `deadline_user_confirmed=true` without overriding the deadline value
- [✅ ] Setting `mark_urgent=true` sets `priority=urgent` and clears `urgency_suggested_by_ai`
- [✅ ] Setting `clear_deadline=true` nulls `deadline`, `deadline_source`, and `deadline_confidence`
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

---

## 14) Scheduling Intents

### 14a) Intent Detection (Email Processing)
- [ ] Email with scheduling language (e.g. "when are you free?") creates a `SchedulingIntent` row with `status=pending`
- [ ] Created intent has `intent_summary`, `meeting_title`, `meeting_date` populated from AI extraction
- [ ] Email below confidence threshold (< 0.6) does not create an intent
- [ ] Processing the same message twice does not create a duplicate intent (deduplication by `message_id`)
- [ ] New intent for a thread expires any previous `pending` intents for the same thread (`status=expired`)
- [ ] `meeting_reminder` intent where title + date matches a calendar event sets `matched_event_id`
- [ ] `meeting_reminder` intent with no calendar match has `matched_event_id = null`

### 14b) Intents API
- [ ] `GET /v1/scheduling/intents?status=pending` returns pending intents with all fields
- [ ] `GET /v1/scheduling/intents/{id}` returns a single intent; unknown id returns 404
- [ ] `POST /v1/scheduling/intents/{id}/run` returns `suggested_slots`, `draft_reply`, `reasoning`
- [ ] `POST /v1/scheduling/intents/{id}/run` with `user_note="prefer afternoons"` biases suggested slots to afternoon windows
- [ ] `POST /v1/scheduling/intents/{id}/send` with `edited_reply` sends Gmail reply, sets `status=sent`, creates follow-up task
- [ ] `POST /v1/scheduling/intents/{id}/send` without `edited_reply` returns 400
- [ ] `POST /v1/scheduling/intents/{id}/dismiss` sets `status=dismissed`
- [ ] `POST /v1/scheduling/intents/{id}/acknowledge` sets `status=acknowledged`
- [ ] `POST /v1/scheduling/intents/{id}/add-to-calendar` creates a `CalendarEvent`, sets `status=added`, sets `matched_event_id`
- [ ] `POST /v1/scheduling/intents/{id}/add-to-calendar` on intent without `meeting_date` returns 400
- [ ] All action endpoints on unknown intent id return 404
- [ ] `GET /v1/scheduling/suggestions` returns `{"suggestions": [], "total": 0}` (backwards compat stub)
- [ ] `POST /v1/scheduling/detect` returns deprecated message (backwards compat stub)

### 14c) Calendar Orchestrator
- [ ] Run result is not persisted — re-running the same intent returns a fresh result each time
- [ ] Slots respect working hours from `UserSettings` (no slots outside configured window)
- [ ] If no `UserSettings` exist, `/run` returns empty `suggested_slots` and a fallback draft reply
- [ ] Reasoning field summarises: events checked, urgent tasks noted, user note applied
- [ ] Orchestrator for `meeting_confirmation` or `meeting_reminder` type is not called by the run endpoint (the `/run` route still works but returns no slots for confirmation types)

### 14d) Frontend — SchedulingIntentsPanel
- [ ] Panel is hidden when there are no pending intents
- [ ] `availability_request` intent card shows primary button labelled "Suggest availability"
- [ ] `time_request` intent card shows primary button labelled "Suggest time"
- [ ] `reschedule_request` intent card shows primary button labelled "Suggest new times"
- [ ] `meeting_confirmation` intent card shows primary button labelled "Add to calendar"
- [ ] `meeting_reminder` with `matched_event_id` shows primary button labelled "Acknowledge"
- [ ] `meeting_reminder` without `matched_event_id` shows primary button labelled "Add to calendar"
- [ ] Every card has a "Dismiss" secondary button
- [ ] `intent_summary` is shown as card body text; falls back to `meeting_title` if summary is absent
- [ ] Clicking card body (summary text) opens OrchestratorPanel
- [ ] Clicking "Dismiss" calls dismiss endpoint; card disappears from panel
- [ ] Clicking "Acknowledge" calls acknowledge endpoint; card disappears from panel
- [ ] Clicking "Add to calendar" (direct action) calls add-to-calendar endpoint; card disappears and calendar events refresh

### 14e) Frontend — OrchestratorPanel
- [ ] Panel opens as a dialog with `meeting_title` as the heading (falls back to "Scheduling")
- [ ] Intent type label and sender name shown as overline
- [ ] `intent_summary` shown as context body text
- [ ] For `availability_request` / `time_request` / `reschedule_request`: user note textarea and "Get recommendations" button visible before running
- [ ] "Get recommendations" shows three-dot loader while request is in-flight
- [ ] After run: slot chips appear; clicking a chip selects it (highlighted in primary colour)
- [ ] Draft reply textarea is pre-filled with the orchestrator's `draft_reply` and is editable
- [ ] Reasoning text shown in italic above slot chips when present
- [ ] Clicking "Send reply" sends the (edited) reply, closes dialog, refreshes intents list
- [ ] "Send reply" disabled when draft reply textarea is empty
- [ ] Clicking "Re-run" clears results and restores the user-note input form
- [ ] For `meeting_confirmation` / `meeting_reminder`: only "Add to calendar" button shown (no orchestrator flow)
- [ ] "Add to calendar" from panel closes dialog, refreshes intents list and calendar events

---

## 15) Webhooks (Gmail + Polar)

### 15a) Gmail Webhook Security + Delivery (`POST /v1/webhooks/gmail`)
- [ ] Unauthorized request (missing/invalid token or auth) returns `401 unauthorized_webhook_source`
- [ ] If `GMAIL_PUBSUB_SUBSCRIPTION` is set and incoming subscription mismatches, request is rejected with `401`
- [ ] Malformed JSON body returns `200` with `{status: "ignored", reason: "invalid_json"}`
- [ ] Missing Pub/Sub `message.data` returns `200` with `{status: "ignored", reason: "no_data"}`
- [ ] Invalid base64 payload returns `200` with `{status: "ignored", reason: "decode_failed"}`
- [ ] Missing `emailAddress` in decoded payload returns `200` with `{status: "ignored", reason: "no_email"}`
- [ ] Unknown Gmail account (`emailAddress` not linked) returns `200` with `{status: "ignored", reason: "unknown_account"}`
- [ ] Duplicate Pub/Sub `messageId` is idempotent and returns `{status: "duplicate"}`
- [ ] First webhook for an account with empty `last_history_id` initializes cursor and returns `{status: "initialized"}`
- [ ] Webhook with no new messages updates `last_history_id` and returns `{status: "ok", new_messages: 0}`
- [ ] `last_history_id` never regresses when out-of-order/older `historyId` is received (monotonic cursor behavior)
- [ ] Processing failures return `500` with generic `gmail_webhook_processing_failed` (no internal stack/error details leaked)
- [ ] Successful processing inserts a row in `webhook_deliveries` for source `gmail`
- [ ] `webhook_logs` includes `source=gmail`, `event_type=gmail_push`, and correct `processed/error` values

### 15b) Polar Webhook Security + Idempotency (`POST /v1/webhooks/polar`)
- [ ] Invalid signature returns `400 Invalid webhook signature`
- [ ] Missing `POLAR_WEBHOOK_SECRET` returns `200` and `{handled: false, reason: "webhook_secret_not_configured"}`
- [ ] Unknown event type returns `200` and `{handled: false}` and is logged with `error=no_handler`
- [ ] Valid `subscription.created` activates user (`tier=pro`, `status=active`) and sets `polar_subscription_id`
- [ ] Valid `subscription.canceled` sets `subscription_status=canceled` without removing pro access immediately
- [ ] Valid `subscription.revoked` sets `tier=trial`, `status=expired`, clears `polar_subscription_id`
- [ ] Duplicate `webhook-id` is idempotent and returns `{duplicate: true}` without re-applying side effects
- [ ] Concurrent duplicate delivery (race) is safely handled (no crash; duplicate result returned)
- [ ] Payload shape with top-level `data.customer_id` is handled correctly
- [ ] Payload shape with nested `data.subscription.customer_id` is handled correctly
- [ ] Successful processing inserts a row in `webhook_deliveries` for source `polar`
- [ ] `webhook_logs` includes `source=polar`, correct `event_type`, and correct `processed/error` values

### 15c) Webhook Data Integrity
- [ ] `webhook_deliveries` enforces uniqueness on `(source, delivery_id)`
- [ ] Replaying the same delivery ID does not create duplicate rows in `webhook_deliveries`
- [ ] Webhook logs are append-only and do not block webhook request handling if logging fails

### 15d) Automated Test Coverage (must pass)
- [ ] `backend/tests/unit/test_gmail_webhook_route.py` passes
- [ ] `backend/tests/unit/test_polar_webhook_route.py` passes
- [ ] Existing Polar webhook tests in `backend/tests/unit/test_webhook_handlers.py` still pass
- [ ] Existing Polar integration tests in `backend/tests/integration/test_webhook_endpoint.py` still pass

---

## 16) Chat DAG Implementation (Planner + Executor + Approval)

### 16a) Planner Output Quality
- [ ] Multi-intent request is split into atomic steps with no missing user intent
- [ ] Planner marks read-only vs action steps correctly
- [ ] Planner assigns dependencies only when needed (no unnecessary chaining)
- [ ] Planner does not create cyclic dependencies
- [ ] Planner keeps trivial/small-talk items out of action DAG

### 16b) DAG Execution Semantics
- [ ] Execution order follows topological dependency order
- [ ] Independent nodes run without waiting on unrelated nodes
- [ ] Dependent node is skipped/held when prerequisite fails
- [ ] Partial completion is returned when one branch fails
- [ ] Retry/continue runs only pending or blocked nodes

### 16c) Approval Gate (Text + Chips)
- [ ] Approval-required actions are surfaced in approval step before execution
- [ ] Selecting one chip executes only selected action(s)
- [ ] Selecting multiple chips executes selected batch only
- [ ] User text approvals (`continue`, `proceed`, `run`) are interpreted correctly
- [ ] User text targeting a specific action (e.g., `run send email to Sarah`) executes only that matching action
- [ ] Reject/cancel text prevents execution of pending approval actions
- [ ] Approved actions are not re-requested for approval on next turn

### 16d) Tool Family + Gating Behavior
- [ ] Planning stage respects tool-family constraints (communication/scheduling/context)
- [ ] Disallowed tool family for a sub-task triggers fallback/clarification instead of unsafe execution
- [ ] No SQL write tool is exposed via chat where not intended
- [ ] Task write actions remain scoped to authorized user only

### 16e) Observability + Failure Handling
- [ ] Planner parse errors safely fallback to non-DAG path (no crash)
- [ ] Invalid plan node/tool schemas are rejected with user-safe fallback response
- [ ] Logs include planner summary, DAG step status, and approval decisions
- [ ] User-facing errors stay human-readable and avoid internal implementation jargon

### 16f) Automated Test Coverage (must pass)
- [ ] `backend/tests/unit/test_chat_planner_models.py` passes
- [ ] `backend/tests/unit/test_chat_tool_policy.py` passes
- [ ] `backend/tests/unit/test_chat_approval_intent.py` passes
- [ ] `backend/tests/unit/test_chat_dag_executor.py` passes
- [ ] `backend/tests/integration/test_chat_plan_dag_approval_execution.py` passes

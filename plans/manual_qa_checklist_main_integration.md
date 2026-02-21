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
- [ ] Simple self-contained request avoids unnecessary retrieval
- [ ] Entity-referenced request (`@thread`) triggers relevant context tools
- [ ] Draft request triggers `draft_email`
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

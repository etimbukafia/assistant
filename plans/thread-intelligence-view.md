---- IGNORE ----
Yes. Message cards should absolutely be clickable.

But not because “that’s standard UX.”

Because Teeks is a **context product**.
Cards = signal
Detail view = intelligence

If cards are not expandable, the product feels shallow.

---

# The Right Model

Think in layers:

**Card = scan**
**Detail view = understand**
**Action = decide**

If cards do too much → overwhelm
If they do too little → useless

Clickable solves that.

---

# What Happens When You Click a Card?

It should open a **Thread Intelligence View**, not just “email details.”

This is important.

You are not building Gmail.
You are building a decision surface.

---

# What the Detail View Should Contain

Here’s the ideal structure.

---

## 1. Full Thread Context (Top Section)

Show:

* Latest message expanded
* Collapsible older messages
* Sender avatars
* Clean formatting (not raw email dump)

Why:
Assistants need conversational flow.

---

## 2. AI Summary (Persistent, Top-Right or Top Block)

A refined version of the card summary.

Slightly richer than the card:

**Card:**

> Investor asking for coffee next week.

**Detail:**

> Casual reconnect. Sender available Mon afternoon or Wed morning. No urgency but relational.

This is your intelligence layer.

---

## 3. Extracted Actions (Core Section)

This is your superpower.

Structured blocks like:

### Tasks

* Reply with availability
* Suggest location

### Scheduling Signals

* Mon afternoon
* Wed morning

### Follow-ups

* No reply yet
* Friendly tone recommended

Make these editable.

Assistants love control.

---

## 4. Suggested Actions (CTA Layer)

Buttons like:

* Draft reply
* Propose times
* Add internal note
* Mark handled
* Snooze

This is where Teeks feels useful.

---

## 5. Thread Memory (If Available)

If you have memory:

* Past decisions
* Prior tone patterns
* Relationship signals

Example:

> Last interaction was 3 months ago. Casual tone historically.

This becomes addictive.

---

## 6. Internal Notes Panel

Private assistant notes.

* Editable inline
* Timestamped
* Never sent externally

This ties into your memory engine later.

---

## 7. Metadata (Subtle Footer)

Keep this light:

* Source (Gmail)
* Received time
* Labels
* AI confidence (optional later)

Don’t clutter.

Assistants don’t care about nerd stats early.

---

# What NOT to Show

Avoid:

❌ Raw headers
❌ AI technical scores
❌ Too many tags
❌ “Model confidence: 0.82”
❌ Over-structured dashboards

That makes it feel robotic.

You want:
Calm, intelligent, human.

---

# UX Pattern That Works Very Well

Use a **side panel** or **drawer**.

Not full page navigation.

Why:

Assistants think spatially.

They want:

* Inbox still visible
* Quick scanning
* Fast back-and-forth

So:

Click card → right-side panel opens
Press ESC → close
Arrow keys → move threads

This feels premium instantly.

---

# Mobile Variation

If mobile:

Card tap → full screen view
But keep same sections stacked vertically.

---

# The Emotional Test

Ask:

When an EA clicks a card, do they feel:
“Oh, this understands what matters”?

If yes, you nailed it.

If it feels like:
“Oh, just the email again”

Then you lost the magic.

---

# One-Line Guideline

Cards show signals.
Details show intelligence.

---

If you want, I can:

* Design the exact layout hierarchy (pixel-level)
* Tell you what to hide in v1 to avoid clutter
* Or design the “wow moment” interaction for first-time users

---- IGNORE ----

# Thread Intelligence View — Implementation Plan

## Context
Email cards in the inbox are not clickable. Users need to click a message to open a detail view that shows the full thread context, AI-extracted action points, tasks, scheduling signals, and suggested actions. This follows the "Logan Roy principle" — surface the action points immediately so an executive assistant knows exactly what needs to happen without reading the full email.

## Overview
- Make EmailCard clickable → opens a **Thread Detail Sheet** (right-side drawer)
- Add a new backend endpoint to fetch thread data (all messages + thread state)
- Add `action_points` to AI extraction (concise "what do I need to do" list)
- Build the Thread Detail UI with 5 sections

---

## 1. Backend: New Thread Endpoint

**File:** `backend/src/app/routes/v1/messages.py`

Add `GET /messages/thread/{thread_id}` that returns:
```python
{
    "thread_state": {  # From ThreadState model
        "summary", "open_tasks", "decisions", "participants",
        "needs_reply", "action_points", "message_count"
    },
    "messages": [  # All messages in thread, chronological
        { id, sender, subject, body (decrypted), summary, received_at,
          extracted_tasks, scheduling_intent, ... }
    ],
    "tasks": [  # Task model records linked to this thread
        { id, title, priority, status, deadline_at, ... }
    ],
    "scheduling_suggestions": [  # Pending suggestions for this thread
        { id, suggested_slots, draft_reply, ... }
    ]
}
```

**File:** `backend/src/app/data/schemas.py`

Add `ThreadDetailResponse` schema with the above shape.

---

## 2. Backend: Action Points Extraction

**File:** `backend/src/app/data/models.py`

Add to `ThreadState`:
```python
action_points = Column(JSON, default=list)  # ["Send Q3 report by Friday", "Confirm with Mike"]
```

**File:** `backend/migrations/035_add_action_points.sql`
```sql
ALTER TABLE thread_states ADD COLUMN action_points JSONB DEFAULT '[]';
```

**File:** `backend/prompts/init_thread_state.md`

Add to the extraction output:
```
"action_points": [
    "Send the Q3 report to finance by Friday",
    "Confirm meeting time with Sarah"
]
```
Rules: Short imperative sentences. Max 5. Only genuinely actionable items. No fluff.

**File:** `backend/prompts/update_thread_state.md`

Same — add action_points to the delta output. Remove completed ones, add new ones.

**File:** `backend/src/app/services/thread_state.py`

Apply `action_points` from AI result to ThreadState (same pattern as `open_tasks`).

---

## 3. Frontend: Thread Detail Service

**File:** `frontend/src/services/messages.ts`

Add:
```typescript
export async function fetchThreadDetail(threadId: string): Promise<ThreadDetailResponse>
```

Add types: `ThreadDetailResponse`, `ThreadMessage` (with decrypted body).

---

## 4. Frontend: Make EmailCard Clickable

**File:** `frontend/src/components/inbox/EmailCard.tsx`

- Add `onClick` prop to EmailCard
- Wrap card in clickable container (cursor-pointer)
- Pass `message.thread_id` up to parent

**File:** `frontend/src/components/inbox/InboxFeed.tsx`

- Track `selectedThreadId` state
- On card click → set selectedThreadId → open Sheet
- Render `<ThreadDetailSheet>` component

---

## 5. Frontend: Thread Detail Sheet Component

**New file:** `frontend/src/components/inbox/ThreadDetailSheet.tsx`

Uses the existing `Sheet` component (right-side drawer, matches app patterns).

### Section 1: AI Summary + Action Points (Top Block)
- Thread summary (richer than card — from ThreadState.summary)
- **Action Points** — bulleted list, bold, scannable. The Logan Roy section.
  - Each point is a short imperative sentence
  - Visual: checkmark-style bullets, prominent typography
- Needs reply indicator

### Section 2: Full Thread Context
- **Latest email** shown expanded with:
  - Sender avatar (initials circle, colored by sender)
  - Sender name + email
  - Timestamp
  - Clean HTML-stripped body (decrypted, formatted)
- **Older emails** in collapsible accordion
  - Each shows sender avatar, name, timestamp, snippet
  - Click to expand full body
  - Visual separator between messages

### Section 3: Extracted Tasks & Scheduling
- Tasks from the Task model (with approve/dismiss/complete actions)
- Scheduling suggestions if any exist for this thread
  - Show suggested time slots

### Section 4: Suggested Actions (CTA Layer)
- **Draft Reply** button → triggers draft-reply endpoint, shows result
- **Propose Times** button → if scheduling intent detected, link to calendar
- **Mark Done** / **Archive** buttons

### Section 5: Metadata Footer
- Source: Gmail icon + email account
- Received time (formatted)
- Thread message count
- Keep this subtle and light

---

## Files to Modify

### Backend
- `backend/src/app/routes/v1/messages.py` — add thread endpoint
- `backend/src/app/data/models.py` — add `action_points` to ThreadState
- `backend/src/app/data/schemas.py` — add ThreadDetailResponse
- `backend/src/app/services/thread_state.py` — apply action_points from AI
- `backend/prompts/init_thread_state.md` — add action_points to extraction
- `backend/prompts/update_thread_state.md` — add action_points to delta
- `backend/migrations/035_add_action_points.sql` — new migration

### Frontend
- `frontend/src/services/messages.ts` — add fetchThreadDetail + types
- `frontend/src/components/inbox/EmailCard.tsx` — add onClick
- `frontend/src/components/inbox/InboxFeed.tsx` — track selection, render Sheet
- `frontend/src/components/inbox/ThreadDetailSheet.tsx` — **new file**

---

## Verification
1. Click an email card in inbox → Sheet slides in from right
2. AI Summary + Action Points display at top (scannable, imperative)
3. Latest email shows with sender avatar, clean formatted body (decrypted)
4. Older thread messages collapsible
5. Tasks show with approve/dismiss actions
6. "Draft Reply" button generates and displays a draft
7. Metadata footer shows source + time, subtle
8. Close sheet → return to inbox feed

Thread Intelligence View — Performance & UX Fixes

 Context

 7 issues with the Thread Intelligence View. Core principles from design/principles.md: "Performance is Core UI", "executive assistants need responsiveness first", "sub-second interactions". From
 backend/principles.md: "Optimize for Speed Relentlessly", "Keep Architectures Simple", "Design Graceful Failure Paths".

 The user requires totally optimistic UI — every action is instant. If something fails, a broad rollback + refetch restores server truth. No spinners, no waiting.

 ---
 Fix 1: Optimistic Message Mutations (Fixes #2 + #3)

 File: frontend/src/hooks/useInbox.ts

 Add onMutate/onError/onSettled to markDone, archive, remove:

 - onMutate: Cancel queries → snapshot all messagesKeys.lists() cache → optimistically remove/update the message in the infinite query pages
 - onError: Restore from snapshot. Also invalidate tasksKeys.all and ["thread-detail"] for cross-cache consistency.
 - onSettled: Always invalidate messages list for eventual server truth.

 Helper function updateMessageInCache(messageId, updater) — mirrors updateTaskInCache pattern from useTasks.ts but for infinite query pages.

 For markDone: set status: "done", filter from inbox pages.
 For archive: set status: "archived", filter from inbox pages.
 For remove: remove from pages entirely.

 ---
 Fix 2: Cross-Cache Invalidation (Fixes #5)

 File: frontend/src/hooks/useTasks.ts

 In invalidateTaskLists(), add:
 queryClient.invalidateQueries({ queryKey: ["thread-detail"] });

 This ensures: approve task in inbox card → thread detail panel refreshes task status.

 In task mutation onError handlers, also invalidate messagesKeys.lists() (messages embed tasks).

 File: frontend/src/hooks/useInbox.ts

 In message mutation onError handlers, also invalidate tasksKeys.all.

 This gives broad rollback: any mutation failure restores truth across all related caches.

 ---
 Fix 3: Task Overflow — Show 2 + "Show More" (Fixes #4)

 File: frontend/src/components/inbox/EmailCard.tsx

 In non-compact mode, render max 2 tasks. If more exist, show a button:

 "Show {n} more" → expands remaining tasks inline


 Compact mode already shows badge count — no change needed.

 ---
 Fix 4: Frontend Caching / Speed (Fixes #1 + #6)

 File: frontend/src/hooks/useInbox.ts

 Add staleTime: 2 * 60_000 to useInfiniteQuery. Data stays fresh for 2 minutes — tab switches and navigations are instant.

 File: frontend/src/components/inbox/ThreadDetailPanel.tsx

 Add staleTime: 60_000 to thread-detail query. Switching between threads and back doesn't refetch within 1 minute.

 Add skeleton loading state instead of spinner — card-shaped shimmers for perceived speed.

 ---
 Fix 5: Reply Compose UI (Fixes #7)

 Backend: Send Reply Endpoint

 File: backend/src/app/data/schemas.py

 class SendReplyRequest(BaseModel):
     body: str
     to: str
     cc: Optional[List[str]] = None
     bcc: Optional[List[str]] = None
     subject: Optional[str] = None

 class SendReplyResponse(BaseModel):
     sent: bool
     message_id: Optional[str] = None
     thread_id: Optional[str] = None
     error: Optional[str] = None

 File: backend/src/app/routes/v1/messages.py

 Add POST /messages/{message_id}/send-reply:
 - Validate request
 - Use GmailClient.send_message() directly (simple, no module abstraction needed)
 - Pass in_reply_to from original message's message_id and thread_id for threading
 - After send: update ThreadState.needs_reply = False, last_outbound_at = now
 - Return SendReplyResponse
 - Graceful error: catch Gmail API errors, return sent: false with human-readable error

 Frontend: Compose Component

 File: frontend/src/services/messages.ts

 Add sendReply(messageId, data) service function.

 File: frontend/src/components/inbox/ReplyComposer.tsx (new)

 States: idle → composing → sending → sent → error

 Composing state layout (email-like):
 - From: Read-only, shows connected Gmail from settings.user_email (via AuthContext)
 - To: Input, pre-filled with original sender, editable
 - CC / BCC: Hidden by default, "CC BCC" link reveals fields
 - Subject: Input, pre-filled with Re: {original subject}, editable
 - Body: Textarea, pre-filled with AI draft (clean text, no markdown), editable
 - Send button (primary auburn) + Discard (ghost)

 Send flow:
 1. Click Send → confirmation modal: "Send reply to {to}?"
 2. Confirm → sending state (button shows spinner, fields disabled)
 3. Success → sent state, brief success indicator, invalidate thread-detail query (needs_reply clears)
 4. Failure → error state, error message inline (not toast — inline is more trustworthy per principles), fields re-enabled to retry

 After send: Panel stays open. Thread refreshes to reflect needs_reply: false.

 File: frontend/src/components/inbox/ThreadDetailPanel.tsx

 Replace the inline draft display + "Draft Reply" button with <ReplyComposer>. The composer:
 - On "Draft Reply" click: calls generateDraftReply(), then transitions to composing state with draft pre-filled
 - Shows the compose form inline in the panel (not a modal)

 ---
 Execution Order

 1. Fix 1 + Fix 2 — Optimistic mutations + cross-cache invalidation (unblocks everything)
 2. Fix 3 — Task overflow (quick, isolated)
 3. Fix 4 — Caching/speed (quick config changes)
 4. Fix 5 — Reply compose UI (backend endpoint + frontend component)

 Verification

 1. Approve task → shows approved instantly, no delay
 2. Approve task → switch to thread panel → task shows approved (no refresh needed)
 3. Delete email card → card disappears instantly
 4. If approval API fails → task rolls back to pending + error shown + message list refetched
 5. Email card with 5+ tasks → shows 2 + "Show 3 more" link
 6. Navigate away from inbox and back → instant (no loading spinner)
 7. Click different thread → panel switches instantly (cached 1 min)
 8. Draft Reply → compose form with From/To/CC/BCC/Subject/Body → Send → confirm → sent
 9. After send → thread shows needs_reply cleared
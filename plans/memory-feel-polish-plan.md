# Memory Feel Polish Plan

> Goal: Make Teeks feel like a "memory capture tool for moments that matter" — not a documentation system.
> No backend changes. No new features. Copy, chrome, and interaction patterns only.

---

## What we're changing

Three files carry almost all the user-facing language:

1. `frontend/src/components/vault/InlineContextCaptureCard.tsx`
2. `frontend/src/app/dashboard/vault/page.tsx`
3. `frontend/src/components/vault/VoiceCaptureButton.tsx`

Plus the contact capture widget copy already threaded into:

4. `frontend/src/app/dashboard/people/[id]/page.tsx` (heading already updated to "Add to memory")

---

## Phase 1 — Rewrite every string

### InlineContextCaptureCard

The card is used everywhere (inbox thread, task, event, contact). Its default props and
internal copy need to shift from filing-language to memory-language.

| Location | Current | New |
|---|---|---|
| Default `heading` prop | `"Capture Context"` | `"Remember this"` |
| Default `saveLabel` prop | `"Capture"` | `"Remember"` |
| Helper text | `"Teeks will organize this after you capture it."` | `"Teeks will hold onto this."` |
| Success toast | `"Saved. Organizing."` | `"Got it."` |
| Error toast | `"That didn't save. Try again."` | `"Didn't save. Try again."` |
| Pending label (badge) | `"Organizing"` | `"Remembering"` |
| Status line (pending) | `"Teeks is organizing this capture."` | `"Teeks is filing this away."` |
| Status line (classified) | `"Saved as {type}."` | `"Remembered as {type}."` |
| Status line (uncertain) | `"Teeks was unsure, so it saved this as Insight. Change it if needed."` | `"Teeks wasn't sure how to file this. Change it if you want."` |
| Revealed header label | `"Latest capture"` | `"Last remembered"` |
| Hidden header label | `"Latest saved context"` | `"Last remembered"` |
| Hidden status (pending) | `"Teeks is still organizing this capture."` | `"Teeks is still filing this away."` |
| Hidden status (uncertain) | `"Saved as Insight. Teeks was unsure."` | `"Filed as Insight — Teeks wasn't certain."` |
| Hidden status (classified) | `"Saved as {type}."` | `"Remembered as {type}."` |

### Category correction UI

Currently: 4 buttons staring at the user (all categories except current).

New pattern — one quiet line, correction on tap:

- Remove the row of pill buttons
- Replace with: `"Filed as Decision. Not right? →"` as a subtle text link
- Tapping opens an inline popover/dropdown with the 4 other category options
- `correctCategory` mutation fires on selection, popover closes

This removes the feeling that the user needs to audit Teeks's work. The correction
is available but doesn't demand attention.

### VoiceCaptureButton

| Location | Current | New |
|---|---|---|
| Pro gate toast | `"Voice capture requires Pro."` | `"Voice memory is a Pro feature."` |
| Success toast | `"Saved. Organizing."` | `"Got it."` |
| 429 error | `"Voice capture is temporarily busy. Try again in a moment."` | `"Voice memory is busy right now. Try again in a moment."` |
| 502 error | `"Teeks couldn't transcribe that recording right now. Try again."` | `"Teeks couldn't hear that clearly. Try again."` |
| Generic error | `"That recording didn't save. Try again."` | `"That didn't save. Try again."` |
| Pro gate title | `"Voice capture requires Pro"` | `"Voice memory requires Pro"` |

---

## Phase 2 — Vault page copy and chrome

### Section / heading copy

| Current | New |
|---|---|
| `"Context Timeline"` (section heading) | Remove the label entirely — the feed speaks for itself |
| `"Filter by category to focus. All captures show by default."` | `"Filter by type — or see everything."` |
| `"Capture a moment. Teeks will organize it for you."` (empty state) | `"The best insights disappear in hours. Capture one now — Teeks will hold onto it."` |
| `"No {type} captures yet."` (filtered empty state) | `"Nothing {type}-related yet."` |
| Composer helper text | `"Teeks will organize this after you capture it."` | `"Teeks will hold onto this."` |
| Composer char count area | keep as-is |

### Filter controls — move behind an icon

Currently the filter pills (All / Risk / Decision / Commitment / Preference / Insight)
are always visible above the feed, drawing the eye before the memories.

New pattern:
- Feed loads showing all entries, no filter controls visible
- A single icon button (SlidersHorizontal or Filter, 14px) sits in the feed header row,
  right-aligned, next to a minimal "Memory" or no label
- Clicking it reveals the filter pills inline (slide down or simple show/hide)
- Active filter is shown as a small badge on the icon button only
- Default state: filter hidden, feed visible immediately

This makes the first impression: *your memories* — not *controls for your memories*.

### Active entry type badge

The colored badge top-right of the Browse section (shows current filter) can be removed
once filters move behind the icon. The icon button itself indicates active filter via a dot.

---

## Phase 3 — Contact capture widget copy

The `InlineContextCaptureCard` on the contact page already has `heading="Add to memory"`.
Align placeholder and description to the new voice:

| Prop | Current | New |
|---|---|---|
| `description` | `"Capture something Teeks should remember about {name}."` | `"What do you want Teeks to remember about {name}?"` |
| `placeholder` | `"Capture something that matters about {name}."` | `"Something that matters about {name}…"` |

---

## Phase 4 — Inline capture cards on other surfaces

The `InlineContextCaptureCard` is also used on inbox threads, tasks, and events.
Each usage should pass a `heading` and `description` that fits the moment, not the filing system.

**Inbox thread:**
- `heading`: `"Remember something from this thread"`
- `description`: `"What came out of this conversation that Teeks should hold onto?"`
- `placeholder`: `"A decision, a preference, something said…"`

**Task:**
- `heading`: `"Remember something about this task"`
- `description`: `"Context Teeks should know when this comes up again."`
- `placeholder`: `"Why this matters, what was decided, what to watch out for…"`

**Calendar event:**
- `heading`: `"Remember something from this meeting"`
- `description`: `"What should Teeks know before or after this meeting?"`
- `placeholder`: `"Something said, agreed, or noticed…"`

Audit each usage site and update props accordingly.

---

## Files to change

| File | Changes |
|---|---|
| `frontend/src/components/vault/InlineContextCaptureCard.tsx` | All string rewrites + category correction UI redesign |
| `frontend/src/components/vault/VoiceCaptureButton.tsx` | Toast and title string rewrites |
| `frontend/src/app/dashboard/vault/page.tsx` | Section headings, empty states, filter chrome moved behind icon |
| `frontend/src/app/dashboard/people/[id]/page.tsx` | Description and placeholder props on capture card |
| Inbox thread component (wherever `InlineContextCaptureCard` is used) | Props update |
| Task detail component (wherever `InlineContextCaptureCard` is used) | Props update |
| Calendar event component (wherever `InlineContextCaptureCard` is used) | Props update |

---

## What stays the same

- All backend APIs, classification logic, categories — unchanged
- The five category types (Decision, Risk, Commitment, Preference, Insight) — kept, just styled quieter
- The timeline feed structure — kept
- The vault route — kept
- The `InlineContextCaptureCard` component structure — kept, only copy + correction UI changes

---

## Definition of done

- No screen uses "capture" as a noun (the action word is fine; the noun sounds like a form field)
- No screen uses "organize" to describe what Teeks does with memories
- Category correction is a quiet affordance, not a correction form
- The vault page opens showing memories first, controls second
- Every toast confirms with human language, not system language

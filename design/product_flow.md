# Teeks: Product Flow & User Journey

This document defines the end-to-end experience for an Executive Assistant using Teeks. Every flow is designed around a single constraint: **the EA is always short on time and long on judgment**.  Teeks handles the former to free the latter.

---

## 1. Onboarding — The First 90 Seconds

The onboarding does one job: get the EA from "account created" to "first useful thing seen" in under 90 seconds. That is it. No tutorial. No feature tour. No celebration screen.

| Step | Screen | What happens |
| :--- | :--- | :--- |
| 1 | **Landing** | Single CTA: "Connect your Gmail" — Ivory background, Playfair headline, Peony button |
| 2 | **OAuth** | Gmail permission screen — standard browser flow, no custom UI |
| 3 | **Sync** | Brass progress line at top. Copy: *"Syncing your inbox."* No percentage, no spinner. |
| 4 | **Today Feed** | First card appears. The product is already working. |

**No onboarding carousel.** If the product needs a slideshow to explain itself, the product is wrong.

---

## 2. The Daily Loop

### 08:00 — Morning orientation
EA opens Teeks. The Today feed shows cards ordered by urgency — Carmine-bordered items first, then chronological. The EA sees what needs attention, not a raw inbox.

### Mid-morning — The micro-intervention
An email arrives requiring action. Teeks has already prepared a draft. The EA sees an action card with a "Send" button — one tap. No composition. No formatting. Just approve or edit.

### Meeting time — Context ready
The EA taps a calendar event. Teeks surfaces relevant context: last interaction with attendees, outstanding items, anything that belongs in a briefing. The EA walks in informed.

### End of day — Reflection
The EA starts a Reflection session. Teeks switches to the Sage-accented mode. The tone changes. This is not a task mode — it is a thinking space. The input placeholder says: *"What's on your mind?"*

---

## 3. Core Interaction Flows

### Flow A: Draft Email Approval

```
[Action Card appears in chat]
      ↓
[EA reads draft — 3 lines, no more]
      ↓
    ┌──────────────────────────────┐
    │  [Send]        [Edit]        │
    │   Peony         Ghost        │
    └──────────────────────────────┘
         ↓                ↓
  [Sent. Thread        [Draft View
   archived.]           opens for
   Toast + archive.     inline edit]
```

**Design rules:**
- The draft is shown in full — not a preview. The EA must see exactly what will be sent.
- "Send" is Peony. Full width. No ambiguity about which button is primary.
- "Edit" is ghost text — it is an escape hatch, not a competing action.
- After send: toast message (*"Sent. Thread archived."*), not a modal.

### Flow B: Calendar Block Creation

```
[EA types: "Block my calendar Thursday 6am–10am, Vienna flight"]
      ↓
[Teeks creates action card]
      ↓
┌────────────────────────────────────┐
│  ✈ Vienna Flight                   │
│  Thursday, Feb 27 · 6:00–10:00 AM  │
│  Blocked — no notifications         │
│                                    │
│  [Confirm]          [Cancel]        │
└────────────────────────────────────┘
      ↓
[Event created. Calendar updated.]
```

**Design rule**: The action card shows the exact event that will be created — not "I'll create an event for you." The EA approves facts, not intentions.

### Flow C: Reflection Session

```
[EA taps new chat → Mode: Reflection]
      ↓
[Screen accent shifts: Brass → Sage]
[Placeholder: "What's on your mind?"]
      ↓
[Ephemeral session — no history kept after close]
[Bottom: "This conversation stays private."]
```

**Design rule**: Reflection sessions carry no action cards. No "approve" buttons. No tasks created. It is a thinking space. The design must communicate that difference visually — the Sage colour scheme does this work.

---

## 4. Interaction Pillars

### I. One tap to resolve
Every Teeks-generated action presents a single primary button. The EA should never need to think "what do I do with this?" — Teeks has already decided what the right action is and surfaced it.

### II. Prepare, not prompt
Teeks shows prepared work for approval, not open-ended questions. "Here's a draft" not "Would you like me to draft a reply?" The preparation happened before the EA opened the card.

### III. Transparent by default
Every action Teeks prepared is visible to the EA before execution. There are no background actions, no auto-sends, no autonomous behaviours. The EA's final tap is the authorisation.

### IV. The pattern is yours
If Teeks notices the EA consistently handles the same type of email the same way, it surfaces the pattern: *"You archive emails from this sender every time. Want me to do that automatically?"* — with a clearly reversible yes/no. The EA is always in control of what Teeks learns.

---

> [!IMPORTANT]
> **The product goal**: Teeks should feel like it is always 15 minutes ahead of the EA, who is 15 minutes ahead of the Executive. If either gap is missing, a feature is failing.

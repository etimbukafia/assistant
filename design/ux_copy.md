# Teeks: UX Copy Guide

> *Every word in the interface is a sentence the product says to a professional. Make it count.*

Teeks sounds like a sharp, discreet colleague. Not a cheerful assistant. Not a formal enterprise system. A person who knows what they are doing, gets to the point, and never wastes your time.

---

## 1. The Voice

**Calm. Direct. One degree warmer than clinical.**

| Quality | In practice |
| :--- | :--- |
| No exclamation marks | Anywhere. Ever. In any state. |
| Active voice | "I've drafted a reply." Not "A reply has been drafted." |
| Brevity | If a label needs a second sentence, the label is wrong. |
| Specific, not vague | "Sent. Thread archived." Not "Action completed successfully." |
| No apologies | "That didn't send. Try again." Not "Sorry! Something went wrong." |

---

## 2. Navigation Labels

| Element | Label | Why |
| :--- | :--- | :--- |
| Tab 1 | **Today** | Anchors the EA in now, not a general "Dashboard" |
| Tab 2 | **Chats** | What it is. Unambiguous. |
| Tab 3 | **Calendar** | Familiar, precise |
| Tab 4 | **Profile** | Settings + identity, one word |
| New chat button | `+` icon, no label | The icon is enough at this position |
| Mode: Action | **ACTION** | Uppercase overline — declares intent |
| Mode: Reflection | **REFLECTION** | Same treatment, different meaning |

---

## 3. Chat — Input Placeholders

| Mode | Placeholder |
| :--- | :--- |
| Action | `Ask Teeks` |
| Reflection | `What's on your mind?` |

Two modes. Two questions. The difference in tone is intentional.

---

## 4. Onboarding

| Moment | Copy |
| :--- | :--- |
| Landing headline | `Your inbox, handled.` |
| Landing subheadline | `Teeks drafts replies, creates events, and surfaces what matters — for your approval.` |
| Connect CTA | `Connect Gmail` |
| Syncing | `Syncing your inbox.` |
| First entry to Today feed | *(no splash copy — the content speaks)* |

**Rule**: No welcome message once the EA is inside the app. The content is the welcome.

---

## 5. Action Cards

### Draft Email

```
Draft Email
To: [Name]  ·  Re: [Subject]

[Body — 2–3 lines maximum. Never truncated.]

[Send]     [Edit]
```

- No "I" — the card is not speaking, it is showing
- Body is the exact text that will be sent — not a summary of it
- "Send" is the label. Not "Send Reply." Not "Approve & Send." Just **Send**.

### Create Event

```
Create Event
✈ Vienna Flight
Thursday, Feb 27 · 6:00 – 10:00 AM
Blocked — no notifications

[Confirm]     [Cancel]
```

### Create Task

```
Create Task
Follow up with Marcus re: Q1 numbers
Due: Friday

[Add to tasks]     [Dismiss]
```

---

## 6. Error States

| Error | Copy |
| :--- | :--- |
| Send failed | `That didn't send. Try again.` |
| Network lost | `No connection. Standing by.` |
| Auth expired | `Session expired. Sign in again.` |
| Sync failed | `Inbox sync failed. Pull to retry.` |
| Unknown | `Something went wrong. Try again.` |

**Rule**: Every error message has two parts — what happened, what to do. If you can't state both in one sentence, break it into two short ones. Never one without the other.

---

## 7. Empty States

| Screen | Copy | CTA |
| :--- | :--- | :--- |
| No sessions | `Your conversations appear here.` | `Start a chat` |
| No calendar events | `Nothing scheduled today.` | — |
| Search no results | `No results.` | — |
| Inbox clear | `All handled.` | — |

**Rule**: One line. Present tense. Statement, not question. No emoji.

---

## 8. Loading States

| Context | Copy |
| :--- | :--- |
| Inbox syncing | `Syncing your inbox.` |
| AI processing | `Thinking…` |
| Sending | *(no copy — send button shows spinner)* |
| Creating session | *(no copy — transition is immediate)* |

**Rule**: If it takes less than 800ms, no copy is needed — just the visual state. Copy is for waits the user might interpret as broken.

---

## 9. Interaction Toasts

Toasts appear at the bottom, disappear after 2.5 seconds, no close button.

| Action | Toast |
| :--- | :--- |
| Message sent | `Sent. Thread archived.` |
| Event created | `Added to your calendar.` |
| Task created | `Task added.` |
| Session deleted | `Conversation deleted.` |
| Action dismissed | `Dismissed.` |

Toasts confirm. They do not celebrate. They do not apologise. They state the fact.

---

## 10. Mode Switch

When switching between Action and Reflection:

- **Entering Reflection**: `Reflection mode. This conversation is private.`
- This appears as a thin inline note below the mode pill, grey, 12pt. Once only per session — not on every message.

---

> [!IMPORTANT]
> **The copy test**: Read every piece of UI copy out loud. If it sounds like a software product talking, rewrite it. It should sound like a person — specifically, a sharp, unhurried professional who knows exactly what they mean.

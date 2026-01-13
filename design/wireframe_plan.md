# Donna: Low-Fidelity Wireframe Plan

This document outlines the layout and hierarchy for Donna's core screens, focusing on structure before visual styling.

---

## 1. Dashboard (The Live Feed)
**Entry State**: App launch / authenticated landing.
**Primary Goal**: Synthesis of "Right Now."

```text
+-----------------------------------+
| [Avatar]      [Donna Pulse] [Sync]|
+-----------------------------------+
|  MORNING BRIEFING (Carousel)      |
|  [ Card: Synthesis of Day ]       |
+-----------------------------------+
|  [Filter: All/Urgent/FYI]         |
+-----------------------------------+
|  CORE FEED (Stack)                |
|  +---------------------------+    |
|  | [Red Dot] Urgent: Meeting |    |
|  | [Summary Snippet]         |    |
|  | [Action: Draft Reply]     |    |
|  +---------------------------+    |
|  | FYI: Budget Update        |    |
|  | [Summary Snippet]         |    |
|  +---------------------------+    |
+-----------------------------------+
| [DASH] [CAL] [TASKS] [SETTINGS]   |
+-----------------------------------+
```

### Dashboard States
- **Loading**: Shimmering grey blocks representing cards. "Cerulean Pulse" icon rotating in header.
- **Empty**: "The horizon is clear. I've archived 12 low-priority items for you." (Donna illustration).
- **Error**: "Connection to the executive brain lost. [Retry]"

---

## 2. Calendar (Executive Schedule)
**Primary Goal**: Context for the upcoming 24 hours.

```text
+-----------------------------------+
| < [Jan 12] >              [Sync]  |
+-----------------------------------+
| [ MINI CALENDAR - 1 Row ]         |
+-----------------------------------+
| 09:00 - Team Sync                 |
| [ Briefing Card: Context Tags ]   |
|                                   |
| 11:30 - Board Meeting             |
| [ Conflict Alert: 15m overlap ]   |
| [ Action: Propose Reschedule ]    |
|                                   |
| 14:00 - Deep Work (Hold)          |
+-----------------------------------+
```

### Calendar States
- **Empty**: "No meetings scheduled. Perfect time for the strategy work we discussed."

---

## 3. Task Hub (The Control Center)
**Primary Goal**: Tracking approved commitments.

```text
+-----------------------------------+
| [ Search ]              [ Filter ]|
+-----------------------------------+
| [Tab: TO DO]  [Tab: WAITING FOR]  |
+-----------------------------------+
| + Add Task Manually               |
+-----------------------------------+
| [!] High: Prep Budget (2h left)   |
| [ ] Normal: Reply to Sarah        |
| [ ] Implied: Follow up with Bob   |
+-----------------------------------+
```

---

## 4. Message Detail (The Deep Context)
**Primary Goal**: Rapid thread resolution.

```text
+-----------------------------------+
| [Back]                    [Action]|
+-----------------------------------+
| SUBJECT: Q4 Budget Review         |
+-----------------------------------+
| DONNA'S SYNTHESIS (Boxed)         |
| "John needs the breakdown by EOD" |
+-----------------------------------+
| EXTRACTED ENTITIES:               |
| [Date: Today] [Person: John]      |
+-----------------------------------+
| FULL THREAD (Collapsible)         |
| [Latest Message]                  |
| [...]                             |
+-----------------------------------+
| [DRAFT REPLY] [ARCHIVE] [SNOOZE]  |
+-----------------------------------+
```

---

## 5. Global Navigation Components

### Donna Pulse (The Voice)
- **Position**: Floating bottom right or persistent header element.
- **Layout**: Centered text input box with "Recent Commands" chips below.
- **State**: Translucent overlay.

### Shared States (IA-Wide)
- **Loading Overlay**: Used during heavy AI processing. Full-screen blur with "Donna is thinking..."
- **No Permissions**: "Gmail connection expired. Donna is blind until you [Reconnect]."

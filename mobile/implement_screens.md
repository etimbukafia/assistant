# Donna Mobile: Screen Implementation Guide

A step-by-step task list for implementing all mobile screens.

---

## Prerequisites

- [x] Theme system configured (`src/theme/Theme.ts`)
- [x] API client configured (`src/services/api.ts`)
- [x] Authentication context set up
- [x] Navigation structure in place (`app/_layout.tsx`)

---

## Phase 1: Authentication Flow

### 1.1 Splash Screen (`app/index.tsx`)
- [x] Animated logo entrance
- [ ] Check auth status via `GET /v1/auth/status`
- [ ] Route to Login, Auth Options, or Dashboard

### 1.2 Landing Screen (`app/login.tsx`)
- [x] DONNA wordmark with Oxblood accent
- [x] "Log in" button (navigates to `app/auth/welcome.tsx`)

### 1.3 Auth Options Screen (`app/auth/welcome.tsx`)
- [x] "Hi" / Google button
- [x] Navigates to `app/auth/google/choose-account.tsx`

### 1.4 Mock Google OAuth Flow
- [x] Choose Account Screen (`app/auth/google/choose-account.tsx`)
- [x] Consent Screen (`app/auth/google/consent.tsx`)
  - "Allow" button -> navigates to `app/(tabs)/inbox.tsx` (Demo Mode)

### 1.5 Activation Explanation (`app/auth/activation-explanation.tsx`)
- [x] [NEW] Explanation of 24-hr lookback & automated processing.
- [x] [NEW] Privacy guarantee (confirmation required).
- [x] [NEW] CTA: "Use Donna with my inbox" (starts sync).

### 1.6 Demo Inbox Experience (`app/(tabs)/inbox.tsx`)
- [x] [NEW] Demo banner: "See how Donna thinks" / "These are sample messages..."
- [x] [NEW] Demo Mode: Show sample messages if `inbox_status === 'demo'`.
- [x] [NEW] Clean transition: Demo -> "Processing..." -> Real.
- [x] [DELETE] `app/syncing.tsx`.

---

## Phase 2: Navigation & Profile Foundation

### 2.1 Tab Layout (`app/(tabs)/_layout.tsx`)
- [x] Bottom tab bar with 4 tabs (spacious, premium feel):
  - Inbox (mail icon)
  - Focus (checkmark icon)
  - Calendar (calendar icon)
  - Chat (message icon)
- [x] Apply `Colors.bgBase` to tab bar
- [x] Active tab: `Colors.accentSecondary` (Copper/Gold)

### 2.2 Global Header (`app/(tabs)/_layout.tsx`)
- [x] Implement `headerLeft` with **User Avatar/Monogram**:
  - Tapping opens `app/settings/profile.tsx` as a bottom sheet/modal.
- [x] Implement `headerRight` placeholders:
  - Notifications (bell)
  - Search (glass)
- [x] Center Title: "Donna" or Page Title in Serif font.

---

## Phase 3: Inbox Flow

### 3.1 Inbox List (`app/(tabs)/inbox.tsx`)
**Data:** `GET /v1/messages`

- [ ] FlatList/FlashList of message cards
- [ ] Each card shows: sender, subject, summary, time, priority badge
- [ ] Pull-to-refresh triggers sync
- [ ] Filter toggle: "Needs Reply" (`?needs_reply=true`)
- [ ] Empty state: "Inbox Zero" illustration
- [ ] Tap card → navigate to Message Detail

### 3.2 Message Detail (`app/details/message.tsx`)
**Data:** `GET /v1/messages/{id}`

- [ ] Header: Subject, Sender, Time
- [ ] Body: Summary (collapsible full body)
- [ ] Tasks section: List extracted tasks
- [ ] Action buttons:
  - "Draft Reply" → opens Draft Sheet
  - "Mark Done" → `POST /v1/messages/{id}/done`
  - "Archive" → `POST /v1/messages/{id}/archive`
- [ ] If `scheduling_intent_type` exists → show Scheduling CTA
- [ ] Thread context indicator

### 3.3 Draft Reply Sheet (`components/sheets/DraftReplySheet.tsx`)
**Data:** `POST /v1/messages/{id}/draft`

- [ ] BottomSheet modal
- [ ] Editable TextInput with AI-generated draft
- [ ] Tone selector: Professional, Friendly, Brief
- [ ] "Send" button → Gmail API
- [ ] "Cancel" button → dismiss

### 3.4 Scheduling Sheet (`components/sheets/SchedulingSheet.tsx`)
**Data:** `GET /v1/scheduling/suggestions?message_id=X`

- [ ] Display suggested time slots as selectable chips
- [ ] Editable reply text
- [ ] "Send Availability" → `POST /v1/scheduling/suggestions/{id}/send`
- [ ] "Dismiss" → `POST /v1/scheduling/suggestions/{id}/dismiss`

---

## Phase 4: Focus Hub (Tasks)

### 4.1 Task List (`app/(tabs)/focus.tsx`)
**Data:** `GET /v1/tasks`

- [ ] Segmented control: Pending | Approved | Completed
- [ ] Task cards with: title, priority, deadline, source snippet
- [ ] Swipe actions: Complete, Snooze
- [ ] FAB: "Add Task" → Create Task Modal
- [ ] Empty state per segment

### 4.2 Task Detail (`app/details/task.tsx`)
**Data:** `GET /v1/tasks/{id}`

- [ ] Full task info: title, description, priority, deadline
- [ ] Source message preview (if linked)
- [ ] Actions:
  - Approve (`POST /v1/tasks/{id}/approve`)
  - Dismiss (`POST /v1/tasks/{id}/dismiss`)
  - Complete (`POST /v1/tasks/{id}/complete`)
  - Snooze (`POST /v1/tasks/{id}/snooze`)
  - Edit → Update Modal

### 4.3 Create Task Modal (`components/modals/CreateTaskModal.tsx`)
**Data:** `POST /v1/tasks/manual`

- [ ] Title input (required)
- [ ] Description textarea
- [ ] Priority picker: Low, Normal, High, Urgent
- [ ] Deadline date picker
- [ ] "Create" button

---

## Phase 5: Calendar

### 5.1 Calendar View (`app/(tabs)/calendar.tsx`)
**Data:** `GET /v1/calendar/events`

- [ ] Weekly/Agenda view toggle
- [ ] Display events with time, title, participants
- [ ] Sync button → `POST /v1/calendar/sync`
- [ ] Tap event → Event Detail

### 5.2 Event Detail (`app/details/event.tsx`)
**Data:** `GET /v1/calendar/events/{id}`

- [ ] Event info: title, time, location, participants
- [ ] Briefing content (if available)
- [ ] Related emails section
- [ ] "Generate Follow-ups" → `POST /v1/calendar/events/{id}/generate-followups`

---

## Phase 6: AI Chat

### 6.1 Chat Sessions List (`app/(tabs)/chat.tsx`)
**Data:** `GET /v1/chat/sessions`

- [ ] List of sessions with title, last message preview, time
- [ ] "New Chat" FAB → `POST /v1/chat/sessions`
- [ ] Swipe to delete session
- [ ] Empty state: "Start a conversation"

### 6.2 Chat Session (`app/chat/[sessionId].tsx`)
**Data:** `GET /v1/chat/sessions/{id}`

- [ ] Message bubbles: user (right), assistant (left)
- [ ] Input bar with send button
- [ ] Send message → `POST /v1/chat/sessions/{id}/messages`
- [ ] Pending actions inline:
  - Approve → `POST /v1/chat/sessions/{id}/approve/{action_id}`
  - Reject → `POST /v1/chat/sessions/{id}/reject/{action_id}`
- [ ] Action types: `create_task`, `draft_reply`, `update_principal_memory`, `add_to_calendar`

---

## Phase 7: Settings

### 7.1 Settings Hub (`app/(tabs)/settings.tsx`)
- [ ] User info header (avatar, email)
- [ ] Sections:
  - General
  - Memory & Preferences
  - Calendar
  - Digests
  - Subscription
  - Data & Privacy

### 7.2 General Settings (`app/settings/general.tsx`)
**Data:** `GET/PUT /v1/settings`

- [ ] Toggle: Auto-approve tasks
- [ ] Textarea: Task detection instructions
- [ ] Toggle: Enable quick reply from task

### 7.3 Memory Screen (`app/settings/memory.tsx`)
**Data:** `GET /v1/memory/preferences`

- [ ] List preferences by context type
- [ ] Add/Edit/Delete preferences
- [ ] Pattern suggestions section → Approve/Reject

### 7.4 Contacts Screen (`app/settings/contacts.tsx`)
**Data:** `GET /v1/memory/contacts`

- [ ] List contacts with category badges
- [ ] Tap → Edit notes, category, preferred tone

### 7.5 Calendar Settings (`app/settings/calendar.tsx`)
**Data:** `GET/PATCH /v1/calendar/settings`

- [ ] Working hours start/end pickers
- [ ] Default meeting duration
- [ ] Buffer minutes
- [ ] Timezone selector
- [ ] Calendar ID multi-select

### 7.6 Digest Settings (`app/settings/digests.tsx`)
**Data:** `PUT /v1/digests/settings`

- [ ] Toggle: Morning Briefing
- [ ] Toggle: End of Day Summary
- [ ] Toggle: Weekly Review
- [ ] Time pickers for each

### 7.7 Subscription Screen (`app/settings/subscription.tsx`)
**Data:** `UserSettings.subscription_*` + Polar API

- [ ] Current plan display
- [ ] Trial countdown (if applicable)
- [ ] "Upgrade to Pro" button → Polar checkout
- [ ] "Manage Billing" → Polar portal

### 7.8 Data & Privacy (`app/settings/privacy.tsx`)
**Data:** `GET /v1/user/export`, `DELETE /v1/user/delete`

- [ ] "Export My Data" button → download JSON
- [ ] "Revoke Gmail Access" → confirm modal → `POST /v1/auth/gmail/revoke`
- [ ] "Delete All Data" → confirm modal → `DELETE /v1/user/delete?confirm=true`

---

## Phase 8: Edge Cases & Polish

### 8.1 Error States
- [ ] 401 → Redirect to Login
- [ ] 402 → Paywall modal
- [ ] 404 → Generic "Not Found" screen
- [ ] Network error → Banner or full-screen

### 8.2 Empty States
- [ ] Inbox: "Inbox Zero" illustration
- [ ] Tasks: "All done" illustration
- [ ] Chat: "Start a conversation" CTA
- [ ] Calendar: "No upcoming events"

### 8.3 Loading States
- [ ] Skeleton screens with shimmer
- [ ] Pull-to-refresh indicators
- [ ] Button loading states

### 8.4 Demo Mode
- [ ] Restricted action toast: "Restricted in Demo Mode"
- [ ] Visual indicator that demo mode is active

---

## Implementation Order (Recommended)

1. **Phase 2**: Tab structure (foundation)
2. **Phase 1**: Complete auth flow
3. **Phase 3**: Inbox (core value)
4. **Phase 4**: Focus Hub (core value)
5. **Phase 6**: Chat (differentiation)
6. **Phase 5**: Calendar (integration)
7. **Phase 7**: Settings (completion)
8. **Phase 8**: Polish

---

## File Structure

```
mobile/
├── app/
│   ├── (tabs)/
│   │   ├── _layout.tsx       # Tab navigator
│   │   ├── inbox.tsx
│   │   ├── focus.tsx
│   │   ├── calendar.tsx
│   │   ├── chat.tsx
│   │   └── settings.tsx
│   ├── details/
│   │   ├── message.tsx
│   │   ├── task.tsx
│   │   └── event.tsx
│   ├── chat/
│   │   └── [sessionId].tsx
│   ├── settings/
│   │   ├── general.tsx
│   │   ├── memory.tsx
│   │   ├── contacts.tsx
│   │   ├── calendar.tsx
│   │   ├── digests.tsx
│   │   ├── subscription.tsx
│   │   └── privacy.tsx
│   ├── index.tsx             # Splash
│   ├── login.tsx
│   └── syncing.tsx
├── src/
│   ├── components/
│   │   ├── cards/
│   │   ├── sheets/
│   │   ├── modals/
│   │   └── ui/
│   ├── services/
│   │   └── api.ts
│   ├── hooks/
│   └── theme/
└── instructions.md
```

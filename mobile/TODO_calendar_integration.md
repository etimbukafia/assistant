# Mobile Calendar Integration - TODO

## Calendar API Functions to Add (`src/services/calendar.ts`)

### 1. GET /calendar/calendars
- [x] Add `fetchUserCalendars()` function
- [x] Add `CalendarInfo` type

### 2. GET /calendar/availability  
- [x] Add `checkAvailability(startTime, endTime, calendarIds?)` function
- [x] Add `AvailabilityResponse` type with busy slots

### 3. POST /calendar/events
- [x] Add `createCalendarEvent(suggestionId, slotIndex, title?, description?, location?)` function

---

## UI Features to Build

### Calendar Settings (`app/settings/calendar.tsx`)
- [x] Add calendar selector section
- [x] Toggle calendars on/off
- [x] Persist `calendar_ids` to settings
- [x] Cache calendar list (rarely changes)

### Inbox Message Detail (future)
- [x] Scheduling suggestion card
- [x] Time slot picker with availability
- [x] Show free vs busy slots
- [x] Skeleton loading for time slots (API can be slow 2-3s)
- [x] "Confirm meeting" button

### Scheduling Flow
- [x] Confirmation screen before creating event
- [x] Success toast with "View in Calendar" link
- [x] Handle offline/no-OAuth gracefully

---

## UX Constraints (IMPORTANT)

### GET /calendar/availability
- ❌ Never call on app load
- ❌ Never call in background constantly
- ✅ Only when scheduling intent exists
- ✅ Only when user explicitly engages with scheduling

### POST /calendar/events
- ❌ Never auto-create events
- ❌ Never create as side effects of email processing
- ✅ Only after explicit user approval/confirmation

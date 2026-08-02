# Contact-Centric UI Mapping

## Objective
Shift the user experience from app-centric workflows (`Inbox`, `Calendar`, `Tasks`) to people-centric workflows without removing the current surfaces.

## New Primary UI Object
Add a first-class `Contact Intelligence` view for each important person.

Core page:
- `Contact Overview`
- `Relationship Brief`
- `Timeline`
- `Commitments`
- `Meetings`
- `Notes`

## New Screens / Views
### 1. Contact Intelligence Page
Entry point for a single person.

Sections:
- header: name, role, org, category, last interaction, next meeting
- relationship brief: summary, preferences, sensitivities, working style
- commitments: open promises, deadlines, owners
- decisions: notable decisions tied to this contact
- recent timeline: emails, meetings, tasks, notes, memory updates
- suggested actions: draft reply, prep for meeting, follow up, update memory

### 2. People Dashboard
A top-level dashboard module focused on:
- people who matter today
- people awaiting follow-up
- people with upcoming meetings
- people with unresolved commitments
- recent relationship changes

This should become more prominent than inbox triage over time.

### 3. Pre-Reply Context Card
Shown in:
- inbox thread detail
- draft reply flow
- chat drafting actions

Contents:
- who this person is
- last key interaction
- open commitments
- tone/preference reminders
- recent changes / risks

### 4. Pre-Meeting Brief Card
Shown in:
- calendar day view
- meeting brief action
- upcoming meetings modules

Contents:
- attendee relationship summary
- latest commitments and unresolved issues
- relevant thread history
- suggested talking points

## Changes To Existing Surfaces
### Inbox
Keep thread UI, but add:
- contact brief side panel
- “what matters before you reply” summary
- quick-save memory actions for decision / commitment / preference / risk

### Calendar
Keep event UI, but add:
- attendee relationship intelligence
- “relationship changes since last meeting”
- open items by attendee

### Chat
Bias chat results toward contacts:
- suggestions for `@contact`
- contact brief cards in responses
- prompts like “What should I remember about Sarah before replying?”

### Settings / Admin
Add configuration and reporting for:
- VIP contacts
- relationship health / follow-up signals
- contact-level usage and briefing metrics

## Navigation Changes
Recommended information architecture:
- `Today`
- `People`
- `Inbox`
- `Calendar`
- `Tasks`
- `Chat`

`People` should become a primary nav item.

## Reusable Components
- `ContactHeaderCard`
- `RelationshipBriefCard`
- `CommitmentList`
- `DecisionList`
- `RelationshipTimeline`
- `PreReplyContextCard`
- `PreMeetingContextCard`
- `PeoplePriorityRail`

## Rollout Order
1. Add contact intelligence page
2. Add pre-reply card in inbox and drafting
3. Add pre-meeting card in calendar
4. Add people dashboard / nav promotion

## UX Test
A user should be able to answer these from one screen:
- who is this person?
- what matters right now?
- what have we promised them?
- what should I remember before interacting?

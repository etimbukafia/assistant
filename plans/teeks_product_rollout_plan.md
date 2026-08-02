# Teeks Product Rollout Plan

## Product Direction
Teeks is `Automation powered by stored context`.

The product should be organized around:
- `Memory`: what Teeks knows
- `Automations`: what Teeks does with that knowledge

This rollout plan aligns product IA, backend architecture, connectors, pricing posture, and implementation order.

## Product Structure

### Top-Level UX
- `Memory`
- `Automations`
- `Settings`

Optional work surfaces may remain:
- `Inbox`
- `Calendar`
- `Tasks`
- `Contacts`

These should support the product, not define it.

### Product Surfaces
1. `Memory`
- Memory Reflection Space
- capture review
- correction
- forgetting
- provenance and trust handling

2. `Automations`
- productized automation catalog
- setup and connector flow
- status and recent runs
- automation detail pages

## Automation Catalog v1

### 1. Inbox Copilot
Promise:
- triage threads
- extract tasks
- identify reply-needed threads
- draft replies using stored relationship context

Required connector:
- Gmail

Includes:
- relationship-aware drafting
- thread processing
- task extraction

### 2. Meeting Prep
Promise:
- generate meeting briefs
- pull attendee context
- surface risks, commitments, decisions, and open prep items

Required connector:
- Calendar

Optional connector:
- Gmail

## What Is Not an Automation
- approval tracking
- memory capture
- generic memory retrieval
- relationship-aware drafting as a standalone product

These are supporting capabilities, not automation products.

## Connector Model
Connectors should be automation-scoped, not marketplace-scoped.

User flow:
1. User selects an automation
2. Teeks shows what connection is needed
3. User connects the required account
4. Automation becomes available with minimal settings

### Connector Requirements
- `Inbox Copilot`
  - required: Gmail
- `Meeting Prep`
  - required: Calendar
  - optional: Gmail

## Pricing Model
Price for outcomes, not plumbing.

### Recommended Packaging
1. `Core`
- Memory Reflection Space
- memory capture
- vault / memory review

2. `Inbox Copilot`
- automation add-on or included higher-tier plan

3. `Meeting Prep`
- automation add-on or included higher-tier plan

### Commercial Principle
- Users should feel they are paying for automation value
- Connector cost affects margin internally, but should not dominate user-facing pricing language

## Backend Rollout

### Memory Layer
Keep and harden:
- context capture
- retrieval
- entity resolution
- contact intelligence
- trust rules

### Automation Layer
Introduce first-class services:
- `InboxCopilotService`
- `MeetingPrepService`

Introduce first-class routes:
- `GET /v1/automations`
- `GET /v1/automations/inbox-copilot`
- `PATCH /v1/automations/inbox-copilot`
- `POST /v1/automations/inbox-copilot/run`
- `GET /v1/automations/meeting-prep`
- `PATCH /v1/automations/meeting-prep`
- `POST /v1/automations/meeting-prep/run`

### Data Model Additions
- automation definitions
- user automation settings
- required connector metadata
- automation run records
- execution mode / safety mode

## Safety Model
Supported modes:
- `read_only`
- `draft_only`
- `review_required`
- `auto_allowed`

Defaults:
- Meeting Prep: `read_only`
- Inbox drafting: `draft_only`
- any external execution: `review_required`

## Frontend Rollout

### Phase 1
- Add `Automations` top-level nav item
- Keep existing `Memory` surfaces under chat + vault
- Build automations index page with two cards only:
  - Inbox Copilot
  - Meeting Prep

### Phase 2
- Add automation detail pages
- Add connector requirement states
- Add enable / disable and safety mode UI

### Phase 3
- Reframe existing inbox/calendar entry points to connect back to automation detail pages
- Reduce top-level UI emphasis on legacy surface-first navigation

## Implementation Phases

### Phase A. Foundation
- finalize product naming
- add `Automations` page shell
- define automation config models and backend routes

### Phase B. Inbox Copilot
- wrap existing inbox/thread/drafting capabilities in `InboxCopilotService`
- add automation settings and status endpoint
- build setup UI and recent-runs UI

### Phase C. Meeting Prep
- wrap meeting-brief functionality in `MeetingPrepService`
- add automation settings and status endpoint
- build setup UI and recent-runs UI

### Phase D. Product Cleanup
- move remaining product language from feature surfaces to product pillars
- ensure memory and automations have clean boundaries
- keep chat as memory/reflection, not general automation identity

## Success Criteria
- Users understand Teeks in under 10 seconds:
  - Memory is the brain
  - Automations are the hands
- Inbox Copilot and Meeting Prep are understandable without explanation
- Connectors appear only when needed by an automation
- Existing backend capabilities are exposed as coherent product services, not scattered features

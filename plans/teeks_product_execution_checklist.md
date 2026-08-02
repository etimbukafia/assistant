# Teeks Product Execution Checklist

> Product thesis: Teeks is `Automation powered by stored context`.

## Status Legend
- `[x]` Done
- `[-]` Partial
- `[ ]` Not started

## Phase 1. Product Framing

### 1. Finalize product language
- [x] Standardize the core product thesis across docs and UI copy
- [x] Define canonical meanings for `Memory` and `Automations`
- [x] Remove conflicting generic-assistant language where it still appears
- [x] Ensure `Memory Reflection Space` remains the memory-first chat identity

### 2. Define top-level information architecture
- [x] Decide final top-level navigation structure
- [x] Position `Memory` and `Automations` as primary product pillars
- [x] Decide which legacy work surfaces remain top-level versus subordinate
- [x] Align dashboard entry points with the new hierarchy

## Phase 2. Frontend Product Structure

### 3. Introduce the Automations surface
- [x] Add top-level `Automations` navigation
- [x] Build an Automations index page shell
- [x] Add headline and positioning copy for the automations page
- [x] Show only productized automations, not a workflow builder

### 4. Launch automation catalog v1
- [x] Add `Inbox Copilot` card
- [x] Add `Meeting Prep` card
- [x] Show status, required connectors, and one primary CTA per automation
- [x] Exclude non-automation capabilities from the catalog

### 5. Build automation detail pages
- [x] Create `Inbox Copilot` detail page
- [x] Create `Meeting Prep` detail page
- [x] Add sections for `What Teeks will do`
- [x] Add `Required connections`
- [x] Add `Safety mode`
- [x] Add `Memory used`
- [x] Add `Recent runs`
- [x] Add enable / disable controls

## Phase 3. Connector and Setup Flow

### 6. Make connectors automation-scoped
- [x] Represent required connectors per automation
- [x] Represent optional connectors per automation
- [x] Build setup flow from automation to connector, not connector to automation
- [x] Show degraded behavior when optional connectors are missing

### 7. Connector states and onboarding
- [x] Add `Needs connection` state
- [x] Add `Ready` state
- [x] Add `Running` state
- [x] Add `Drafts only` state
- [x] Add `Off` state
- [x] Ensure onboarding makes automations feel outcome-first, not plumbing-first

## Phase 4. Backend Architecture

### 8. Formalize the memory layer
- [x] Document the memory layer as a first-class backend boundary
- [x] Keep memory trust rules centralized
- [x] Ensure automations consume memory only through the hardened memory layer
- [x] Confirm forgotten, provenance, confidence, and ambiguity rules are respected

### 9. Add first-class automation services
- [x] Introduce `InboxCopilotService`
- [x] Introduce `MeetingPrepService`
- [x] Move product orchestration into these services
- [x] Keep generic chat tools as infrastructure, not product architecture

### 10. Add automation API surface
- [x] Add `GET /v1/automations`
- [x] Add `GET /v1/automations/inbox-copilot`
- [x] Add `PATCH /v1/automations/inbox-copilot`
- [x] Add `POST /v1/automations/inbox-copilot/run`
- [x] Add `GET /v1/automations/meeting-prep`
- [x] Add `PATCH /v1/automations/meeting-prep`
- [x] Add `POST /v1/automations/meeting-prep/run`

### 11. Add automation models
- [x] Define automation definitions
- [x] Define user automation settings
- [x] Define required connector metadata
- [x] Define automation run history
- [x] Define safety / execution mode fields

## Phase 5. Productization of Existing Features

### 12. Package Inbox Copilot
- [ ] Wrap inbox/thread processing under `InboxCopilotService`
- [ ] Wrap task extraction under the automation
- [ ] Wrap context-aware drafting under the automation
- [ ] Expose recent runs and setup state
- [ ] Make relationship-aware drafting an internal capability of Inbox Copilot

### 13. Package Meeting Prep
- [ ] Wrap meeting brief generation under `MeetingPrepService`
- [ ] Wrap attendee context assembly under the automation
- [ ] Wrap decisions / commitments / risks under the automation
- [ ] Expose recent runs and setup state

## Phase 6. Safety and Execution Modes

### 14. Define automation safety defaults
- [ ] Mark meeting prep as `read_only`
- [ ] Mark inbox drafting as `draft_only`
- [ ] Keep risky outward actions as `review_required`
- [ ] Leave room for `auto_allowed` only where trust is earned

### 15. Reflect safety modes in product behavior
- [ ] Show safety mode in automation detail pages
- [ ] Ensure backend execution respects configured safety mode
- [ ] Prevent product/UI claims from overstating automation autonomy

## Phase 7. Pricing and Packaging

### 16. Define commercial packaging
- [ ] Define `Core` around memory
- [ ] Decide whether `Inbox Copilot` is add-on or higher-tier included
- [ ] Decide whether `Meeting Prep` is add-on or higher-tier included
- [ ] Ensure pricing language emphasizes outcomes, not connectors

## Phase 8. Cleanup and Migration

### 17. Reduce feature-sprawl in navigation and copy
- [ ] Reframe legacy dashboards under the new product model
- [ ] Reduce equal emphasis on old surface-first navigation
- [ ] Align inbox/calendar entry points back to automation pages where appropriate

### 18. Keep chat in its proper role
- [ ] Keep chat as the memory/reflection surface
- [ ] Allow chat to preview or launch automations where useful
- [ ] Do not let chat remain the primary system boundary for automations

## Phase 9. Verification

### 19. Product verification
- [ ] Verify users can explain Teeks as memory plus automations
- [ ] Verify automations are understandable without connector knowledge
- [ ] Verify the catalog stays constrained to true automations

### 20. Technical verification
- [ ] Verify automation services work independently of chat
- [ ] Verify automation routes return correct connector and status metadata
- [ ] Verify memory trust rules still govern automation inputs
- [ ] Verify recent runs, enable/disable state, and safety modes are persisted correctly

## Recommended Execution Order
1. Phase 1: product framing and IA
2. Phase 2: automations page and catalog v1
3. Phase 3: connector-aware setup flow
4. Phase 4: backend automation services and routes
5. Phase 5: package Inbox Copilot and Meeting Prep
6. Phase 6: safety modes
7. Phase 7: pricing and packaging
8. Phase 8: cleanup and migration
9. Phase 9: verification

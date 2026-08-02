# Teeks Backend Architecture Spec

## Product Thesis
Teeks is `Automation powered by stored context`.

The backend should reflect two primary product layers:
- `Memory`: capture, retrieval, trust, and reflection
- `Automations`: productized workflows powered by memory

Chat tools and internal orchestration may remain as infrastructure, but they should not define the product architecture.

## Core Backend Split

## 1. Memory Layer
Purpose:
- capture context
- classify and store memory
- resolve entities
- retrieve trusted context
- answer memory questions
- maintain provenance, ambiguity, confidence, and lifecycle rules

### Responsibilities
- Context capture and vault management
- Contact brief, contact timeline, and relationship signals
- Mention and entity resolution
- Approval history as memory lookup
- Provenance handling for missing sources
- Forgotten exclusion
- Confidence gating
- Orphan-safe memory shaping
- Memory reflection chat support

### Existing Modules That Fit Here
- [vault.py](/C:/Users/j/afiavana/assistant/backend/src/app/routes/v1/vault.py)
- [mention_context.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/mention_context.py)
- [contact_brief.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/contact_brief.py)
- [contact_timeline.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/contact_timeline.py)
- [context_memory_policy.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/context_memory_policy.py)
- [tools.py](/C:/Users/j/afiavana/assistant/backend/src/app/chat/tools.py)
- [service.py](/C:/Users/j/afiavana/assistant/backend/src/app/chat/service.py)

## 2. Automation Layer
Purpose:
- run opinionated workflows that use stored context to do work

Automations should be first-class backend services, not prompt accidents.

### Automation Catalog v1
1. `Inbox Copilot`
- thread processing
- reply-needed detection
- task extraction
- relationship-aware reply drafting

2. `Meeting Prep`
- meeting brief generation
- attendee context assembly
- risks, commitments, decisions, and prep warnings

### Existing Modules That Fit Here
- [thread_state.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/thread_state.py)
- [email_drafting.py](/C:/Users/j/afiavana/assistant/backend/src/app/superpowers/email_drafting.py)
- [meeting_brief.py](/C:/Users/j/afiavana/assistant/backend/src/app/superpowers/meeting_brief.py)
- [briefing.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/briefing.py)

## Architectural Rule
Automations must consume memory through the hardened memory layer.

They should never bypass:
- confidence gating
- forgotten exclusion
- provenance rules
- ambiguity handling
- orphan-safe shaping

## Recommended Package Structure
```text
backend/src/app/
  memory/
    capture/
    retrieval/
    entity_resolution/
    trust/
    contact_intelligence/
  automation/
    inbox_copilot.py
    meeting_prep.py
    models.py
    registry.py
  chat/
    reflection/
    planner/
    tools/
```

This does not require a full immediate move. It defines the target structure and product boundaries.

## First-Class Automation Services
Introduce explicit services:
- `InboxCopilotService`
- `MeetingPrepService`

Examples:
- `InboxCopilotService.run_for_thread(thread_id, user_id)`
- `InboxCopilotService.draft_reply(thread_id, user_id)`
- `MeetingPrepService.build_for_event(event_id, user_id)`

These services may call lower-level modules such as drafting, contact brief, thread state, and calendar services.

## API Shape
Add explicit automation routes:
- `GET /v1/automations`
- `GET /v1/automations/inbox-copilot`
- `PATCH /v1/automations/inbox-copilot`
- `POST /v1/automations/inbox-copilot/run`
- `GET /v1/automations/meeting-prep`
- `PATCH /v1/automations/meeting-prep`
- `POST /v1/automations/meeting-prep/run`

Each automation should expose:
- status
- required connectors
- safety mode
- recent runs
- enable / disable state

## Connector Model
Connectors are dependencies of automations, not primary backend products.

Each automation should declare:
- required connectors
- optional connectors
- degraded behavior when a connector is missing

Examples:
- `Inbox Copilot`
  - required: Gmail
- `Meeting Prep`
  - required: Calendar
  - optional: Gmail

## Safety Model
Automations should support explicit execution modes:
- `read_only`
- `draft_only`
- `review_required`
- `auto_allowed`

Suggested defaults:
- Meeting briefs: `read_only`
- Reply drafting: `draft_only`
- External actions: `review_required`

## Data Models
Introduce explicit automation models for:
- automation definitions
- user automation settings
- connector requirements
- automation run history
- last success / last failure

These models should be independent from chat session state.

## Role Of Chat
Chat should remain a reflection and interaction surface.

It may:
- explain automations
- preview automation outputs
- launch automations

It should not remain the primary architecture for automation execution.

## Migration Guidance
### Phase 1
- Keep existing services in place
- Add explicit automation service wrappers around current features
- Add automation routes and models

### Phase 2
- Move automation-specific orchestration out of generic chat pathways
- Keep chat as a consumer of automation services

### Phase 3
- Refactor package structure toward `memory/` and `automation/`

## Principle
The backend should make this product truth obvious:
- Memory is the foundation
- Automations are the productized outcomes
- Chat is an interface, not the system boundary

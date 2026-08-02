# Contact-Centric Relationship Intelligence Plan

## Goal
Reposition Teeks from an inbox/calendar assistant to a contact-centric relationship intelligence system for executive assistants without rewriting the current architecture.

Core framing:
- `Teeks is the relationship intelligence system for executive assistants.`
- `Teeks helps executive assistants remember everything that matters about the people their executives work with.`

## Product Shift
Do not remove email, calendar, tasks, or chat. Reframe them:
- email -> interaction evidence
- calendar -> meeting and timeline evidence
- tasks -> commitments and follow-ups
- chat -> access surface for relationship context

Primary object model:
- current: message/thread-first
- target: contact-first

## Existing Foundations To Reuse
- canonical contacts: [backend/src/app/data/models.py](/C:/Users/j/afiavana/assistant/backend/src/app/data/models.py)
- contact linking on ingestion: [backend/src/app/services/contact_linking.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/contact_linking.py)
- structured memory by entity: [backend/src/app/data/models.py](/C:/Users/j/afiavana/assistant/backend/src/app/data/models.py)
- contact snapshots: [backend/src/app/services/warm_context_snapshot.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/warm_context_snapshot.py)
- mention resolution and scoped retrieval: [backend/src/app/services/mention_context.py](/C:/Users/j/afiavana/assistant/backend/src/app/services/mention_context.py)
- contact-aware chat tools: [backend/src/app/chat/tools.py](/C:/Users/j/afiavana/assistant/backend/src/app/chat/tools.py)
- contact CRUD: [backend/src/app/routes/v1/vault.py](/C:/Users/j/afiavana/assistant/backend/src/app/routes/v1/vault.py)

## Target Backend Model
Make `Contact` the canonical relationship record. Everything else enriches it:
- `Contact`: identity, role, org, notes, category
- `ContextEntry(entity_type="contact")`: decisions, commitments, preferences, risks, relationships
- `Message` / `ThreadState`: evidence and interaction history
- `CalendarEvent`: meeting context
- `Task`: follow-up obligations tied to contact or thread

`ContactContext` should become derived/legacy metadata, not the primary product object.

## Flagship Feature
Build `Relationship Briefs`.

Each brief should aggregate:
- who this person is
- relationship summary
- active commitments
- key decisions
- preferences and sensitivities
- recent timeline
- upcoming meetings
- suggested handling notes

## Implementation Phases
### Phase 1: Canonical Contact Brief
- add `ContactBriefService`
- aggregate `Contact`, contact-scoped `ContextEntry`, recent threads/messages, events, tasks, legacy stats
- add `GET /contacts/{id}/brief`

### Phase 2: Contact-First Retrieval
- update chat/context assembly to prefer contact context before thread/event context
- use contact briefs in drafting and meeting-prep flows
- always fetch a relationship brief before reply drafting when a contact is known

### Phase 3: Relationship Timeline and Commitments
- build a normalized timeline per contact
- expose open commitments and unresolved risks
- add stale follow-up and “what changed” signals

### Phase 4: Contact-Centric Product Surfaces
- add a dedicated contact intelligence page
- add pre-reply and pre-meeting context cards
- shift dashboard emphasis from inbox/calendar to “people who matter today”

## API / Service Additions
- `ContactBriefService`
- `ContactTimelineService`
- `GET /contacts/{id}/brief`
- `GET /contacts/{id}/timeline`
- `GET /contacts/{id}/signals`

## Migration Strategy
- no destructive rewrite
- keep existing routes and models
- progressively route chat, drafting, and meeting briefing through contact briefs
- preserve thread/event/message retrieval as secondary supporting context

## Success Criteria
- Teeks can answer “what matters about this person?” before “what is in this thread?”
- replies and meeting briefs consistently include contact-specific context
- the product homepage and core UX can credibly lead with relationship intelligence, not generic productivity

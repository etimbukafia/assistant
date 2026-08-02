# Contact-Centric Backend Execution Checklist

## Objective
Turn the current message/thread-oriented backend into a contact-centric relationship intelligence backend without rewriting the existing ingestion, chat, drafting, and meeting flows.

## Phase 1: Contact Brief Read Model
### 1. Add contact brief schemas
- [x] Update `backend/src/app/data/schemas.py`
- [x] Add `ContactBriefResponse`
- [x] Add nested response blocks for:
  - `contact`
  - `relationship_summary`
  - `preferences`
  - `commitments`
  - `decisions`
  - `recent_interactions`
  - `upcoming_events`
  - `signals`
- [x] Keep response read-only; do not add write payloads yet

Done when:
- there is a stable API shape for a first-class contact brief

### 2. Add `ContactBriefService`
- [x] Create `backend/src/app/services/contact_brief.py`
- [x] Resolve contact by `contact_id`
- [x] Aggregate from:
  - `Contact`
  - `ContextEntry(entity_type="contact")`
  - `Message` rows linked by `contact_id`
  - `ThreadState` rows linked by `contact_id`
  - `CalendarEvent` rows associated through contact email/name when available
  - `Task` rows linked to related threads/messages
  - legacy `ContactContext` stats as derived metadata only
- [x] Build sections:
  - identity
  - relationship summary
  - active commitments
  - decisions
  - preferences / sensitivities
  - recent timeline
  - next meetings
  - simple signals
- [x] Keep service deterministic; no LLM calls in Phase 1

Done when:
- one service call returns a usable “relationship brief” from existing data

### 3. Add contact brief endpoint
- [x] Update `backend/src/app/routes/v1/vault.py` or add a dedicated `contacts.py` route module
- [x] Add `GET /contacts/{contact_id}/brief`
- [x] Require authenticated user and user-scoped lookup
- [x] Return `404` for missing contacts

Decision:
- preferred short-term path: add to `vault.py` to avoid route sprawl
- preferred long-term path: move contact-specific APIs into `routes/v1/contacts.py`

Done when:
- frontend/chat can fetch a canonical contact brief over HTTP

### 4. Add tests for the read model
- [x] Add `backend/tests/unit/test_contact_brief_service.py`
- [x] Add `backend/tests/integration/test_contact_brief_route.py`
- [x] Cover:
  - no memory entries
  - contact with decisions/commitments/preferences
  - contact linked to multiple threads
  - missing contact
  - legacy `ContactContext` data included as derived stats, not canonical notes

Done when:
- the brief is stable under both unit and route-level tests

## Phase 2: Contact-First Retrieval and Snapshotting
### 5. Extend warm snapshots to support full contact briefs
- [x] Update `backend/src/app/services/warm_context_snapshot.py`
- [x] Add a richer `build_contact_snapshot(...)` output:
  - top preferences
  - active commitments
  - recent decisions
  - high-importance risks
  - recent timeline summary
- [x] Keep existing snapshot callers backward-compatible

Done when:
- contact snapshots are useful enough to power chat/drafting context without recomputing every section

### 6. Bias mention retrieval toward contacts first
- [x] Update `backend/src/app/services/mention_context.py`
- [x] Prefer contact snapshot hydration before thread/event snapshot hydration
- [x] Ensure mention ranking favors contacts when the query is person-like
- [x] Add support for brief preview payloads in resolved mention context

Done when:
- `@contact` retrieval consistently surfaces relationship context before raw thread context

### 7. Promote contact context in chat assembly
- [x] Update `backend/src/app/services/context_assembler.py`
- [x] Add explicit contact layer support using `current_contact_id`
- [x] If a contact is active in task context, inject contact summary before generic structured memory
- [x] Keep thread/event context as secondary supporting layers

### 8. Update chat orchestrator to prefer contact context
- [x] Update `backend/src/app/chat/orchestrator.py`
- [x] When `state.current_contact_id` exists or a contact mention resolves, request contact-first context
- [x] Add response guidance so the assistant answers:
  - what matters about this person
  - what is open with them
  - what changed recently
- [x] Avoid regressing thread-specific answers

### 9. Update chat tools to expose first-class contact intelligence
- [x] Update `backend/src/app/chat/tools.py`
- [x] Add or rename toward `get_contact_brief`
- [x] Add or rename toward `get_contact_timeline`
- [x] Add or rename toward `get_contact_signals`
- [x] Keep deprecated tools working as wrappers during migration
- [x] Make `context_search` prefer `entity_type="contact"` for people-oriented prompts

Done when:
- chat can answer contact-centric prompts without requiring thread IDs

### 10. Add tests for contact-first retrieval
- [x] Update/add `backend/tests/unit/test_chat_mentions.py`
- [x] Update/add `backend/tests/unit/test_chat_tool_policy.py`
- [x] Update/add `backend/tests/unit/test_chat_native_tool_flow.py`
- [x] Cover contact mention resolution
- [x] Cover contact brief retrieval
- [x] Cover contact-first context ordering
- [x] Cover fallback behavior when only thread data exists

## Phase 3: Drafting and Meeting Briefs
### 11. Route drafting through contact briefs
- [x] Update `backend/src/app/superpowers/email_drafting.py`
- [x] Replace scattered contact/thread/event querying with `ContactBriefService` for known contacts
- [x] Use contact commitments, preferences, and recent decisions as explicit prompt sections
- [x] Keep thread/message-specific context as supporting evidence

Done when:
- draft generation always uses the relationship brief when the recipient/contact is known

### 12. Route meeting briefs through contact intelligence
- [x] Update `backend/src/app/superpowers/meeting_brief.py`
- [x] For each participant with a resolvable contact, attach contact brief sections:
  - relationship summary
  - open commitments
  - recent changes
  - sensitive context
- [x] Keep event-scoped context for meeting-specific facts only

Done when:
- meeting prep becomes attendee-centric, not event-note-centric

### 13. Add tests for drafting and meeting prep
- [x] Add/update:
  - `backend/tests/unit/test_email_drafting_channel_mode.py`
  - new `backend/tests/unit/test_contact_brief_drafting.py`
  - new `backend/tests/unit/test_meeting_brief_contact_context.py`

## Phase 4: Timeline, Signals, and Commitments
### 14. Add `ContactTimelineService`
- [x] Create `backend/src/app/services/contact_timeline.py`
- [x] Normalize timeline items from:
  - messages
  - thread decisions
  - tasks
  - meetings
  - `ContextEntry`
- [x] Sort descending by relevant timestamp
- [x] Return typed timeline events

### 15. Add contact signals logic
- [x] Create `backend/src/app/services/contact_signals.py`
- [x] Start with deterministic signals only:
  - overdue follow-up
  - unresolved commitment
  - upcoming meeting without recent interaction
  - new decision since last meeting
  - VIP/external priority marker
- [x] Do not infer personality or intent

### 16. Add timeline/signals endpoints
- [x] Update contact route module (`vault.py` or new `contacts.py`)
- [x] Add:
  - `GET /contacts/{contact_id}/timeline`
  - `GET /contacts/{contact_id}/signals`

### 17. Add tests for timeline/signals
- [x] Add:
  - `backend/tests/unit/test_contact_timeline_service.py`
  - `backend/tests/unit/test_contact_signals.py`
  - `backend/tests/integration/test_contact_timeline_route.py`

## Phase 5: Canonical Contact Model Cleanup
### 18. Demote `ContactContext`
- [x] Review `backend/src/app/data/models.py`
- [x] Keep `ContactContext` for legacy stats/manual metadata only
- [x] Update comments to reflect derived/legacy status

### 19. Reduce new writes into `ContactContext`
- [x] Review and update:
  - `backend/src/app/services/contact_stats.py`
  - `backend/src/app/handlers/message_handlers.py`
  - `backend/src/app/services/email_filter.py`
  - `backend/src/app/services/vault_ingestion.py`
- [x] Ensure new relationship intelligence writes go to `ContextEntry` and `Contact`, not `ContactContext`
- [x] Keep reply-rate / message-count style metrics in derived storage if still needed

### 20. Improve contact linkage coverage
- [x] Update:
  - `backend/src/app/services/contact_linking.py`
  - `backend/src/app/routes/v1/messages.py`
  - `backend/src/app/routes/v1/webhooks.py`
  - `backend/src/app/jobs/worker.py`
  - `backend/src/app/services/thread_state.py`
- [x] Ensure every ingested message/thread carries `contact_id` whenever possible
- [x] Add alias handling and better fallback resolution by email/name

Done when:
- contact linkage is reliable enough that contact briefs do not depend on manual cleanup

## Phase 6: Product API Consolidation
### 21. Add dedicated contact routes module
- [x] Create `backend/src/app/routes/v1/contacts.py`
- [x] Move or wrap:
  - contact list/detail
  - contact brief
  - contact timeline
  - contact signals
- [x] Keep existing `vault` routes working during transition

### 22. Register routes
- [x] Update `backend/src/main.py`
- [x] Add the new router under `/v1/contacts`

### 23. Update schemas and docs
- [x] Update `backend/src/app/data/schemas.py`
- [x] Ensure OpenAPI models reflect contact-centric API responses

## Cross-Cutting Checks
### 24. Privacy and safety review
- [x] Review:
  - `backend/src/app/routes/v1/gdpr.py`
  - `backend/src/app/security/*`
  - `backend/src/app/routes/v1/auth.py`
- [x] Ensure contact briefs export/delete correctly
- [x] Ensure signals remain factual and do not auto-generate subjective judgments

### 25. Cache invalidation review
- [x] Review:
  - `backend/src/app/services/entity_cache_coordinator.py`
  - `backend/src/app/services/warm_cache.py`
  - `backend/src/app/services/warm_context_snapshot.py`
- [x] Invalidate contact-scoped caches when:
  - contact record changes
  - contact-scoped context entry changes
  - linked message/thread/task/event state changes materially

### 26. Observability
- [x] Add logs/metrics around:
  - contact brief generation latency
  - contact linkage hit rate
  - contact-brief usage by drafting/chat/meeting-prep
  - signal generation counts

## Recommended Execution Order
1. `schemas.py`
2. new `contact_brief.py`
3. route for `/contacts/{id}/brief`
4. unit/integration tests for brief
5. `warm_context_snapshot.py`
6. `mention_context.py`
7. `context_assembler.py`
8. `chat/orchestrator.py`
9. `chat/tools.py`
10. `email_drafting.py`
11. `meeting_brief.py`
12. timeline/signals services + routes
13. linkage cleanup
14. route consolidation into `contacts.py`

## Definition Of Done
- a contact has a first-class backend brief
- chat can answer people-first questions better than thread-first questions
- drafting and meeting briefing consume contact intelligence by default
- timeline and signals exist without requiring LLM inference
- the backend can credibly support the product claim:
  - `Teeks helps executive assistants remember everything that matters about the people their executives work with.`

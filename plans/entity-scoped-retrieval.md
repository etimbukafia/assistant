Entity-Scoped Retrieval Plan

  1. Mention UX + Data Contract

  - Build @ mention picker in playground chat for contact, event, thread.
  - Display labels only (contact name, event title, thread subject), never IDs.
  - On selection, attach canonical payload to message state:
  - mentions: [{ kind, ref, label }]
  - Update chat request schema to include mentions.

  2. Backend Mention Resolver

  - Add MentionResolverService to validate each mention by tenant/user ownership.
  - Resolve each mention to canonical scope keys:
  - contact:{email_or_key}
  - event:{event_key}
  - thread:{thread_key}
  - Reject untrusted free-typed mentions that were not selected from picker.
  - Return normalized mention list + resolution metadata.

  3. Scoped Prefetch Pipeline

  - Before LLM call, if mentions exist:
  - Fetch each scope (warm cache -> DB fallback) in parallel.
  - Deduplicate repeated entities.
  - Merge into a structured context bundle by entity.
  - Push selected entries into hot session context.

  4. Retrieval Budgeting + Ranking

  - Add strict caps:
  - max_items_per_entity (e.g. 5)
  - max_items_total (e.g. 25)
  - Rank by:
  - explicit mention match
  - importance_level
  - recency
  - task intent fit (draft/recap/scheduling)
  - Trim deterministically with audit metadata.

  5. Prompt Assembly Integration

  - Extend ContextAssembler to include a new section:
  - Mentioned Entity Context
  - Keep entity blocks segmented (not flattened).
  - Preserve provenance fields (entity, type, created_at, importance).

  6. Tool Interop

  - Keep Gemini function-calling active.
  - Mention prefetch provides initial scoped context.
  - Model can still call tools for additional context when needed.
  - Add get_event_context examples to system tool guidance.

  7. Observability

  - Log per turn:
  - mentions received
  - mentions resolved/rejected
  - scopes fetched
  - cache hit/miss/fallback
  - items selected/dropped and reasons
  - final context token/item counts
  - Expose this in admin debug endpoint payload.

  8. Edge Cases (must handle)

  - Renamed entities (label changes, canonical ref stable).
  - Repeated mentions of same entity (dedupe).
  - Too many mentions in one message (hard cap + graceful warning).
  - Missing/deleted entity after mention selection (skip + explain softly).
  - Unauthorized or cross-tenant ref (hard reject, no leakage).
  - Free-typed @foo not selected from picker (treat as plain text).
  - Partial retrieval failures (continue with available scopes).
  - Conflicting context across entities (preserve provenance, ask clarification when high impact).
  - Prompt bloat from multi-entity mentions (budget trim + deterministic ordering).

  9. Testing Plan

  - Unit tests: resolver validation, scope mapping, ranking/budget trim.
  - Integration tests: multi-entity message (2 contacts + 1 event + 1 thread) and partial failures.
  - Security tests: cross-tenant mention injection attempts.
  - UX tests: disambiguation flow and no-ID rendering.

  10. Rollout

  - Stage 1: backend support + hidden mentions payload.
  - Stage 2: frontend picker + chip rendering.
  - Stage 3: enforce mention-only retrieval and tighten limits.
  - Stage 4: monitor logs and tune caps/ranking.
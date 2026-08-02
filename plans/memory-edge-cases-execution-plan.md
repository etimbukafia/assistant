# Memory Edge Cases Implementation Checklist

> Principle: Teeks should never show something broken, never act on something it does not trust, and when the user says "forget this," it should forget.

## Status Legend
- `[x]` Done
- `[-]` Partial
- `[ ]` Not started

## Phase 1. Trust Boundaries In Retrieval

### 1. Confidence-gate memory retrieval
- [x] Exclude low-confidence entries from retrieval unless `user_corrected = true`
- [x] Keep low-confidence entries visible in the vault for human review
- [x] Apply the filter to main memory retrieval paths, contact context, warm snapshots, and action-chip context
- [x] Add focused backend coverage for confidence-gated retrieval

### 2. Add `forgotten` as a real lifecycle state
- [x] Add `forgotten` to context-entry status enums and DB constraints
- [x] Add migration for `forgotten`
- [x] Exclude `forgotten` entries from retrieval and prefetch paths
- [x] Exclude `forgotten` entries from hot-context filtering
- [x] Audit every remaining backend retrieval path for `forgotten` handling consistency

## Phase 2. Broken Reference Suppression

### 3. Orphan-safe rendering
- [x] Hide the primary scope chip when the scoped entity no longer resolves in the vault
- [x] Keep the memory card and memory text even when the scope entity is gone
- [x] Strip orphaned secondary links from surfaced capture responses
- [x] Hide dead memory references in the main mention/reference suggestion path
- [x] Audit other memory surfaces beyond vault and the main chat/reference pane for orphan-safe rendering

### 4. Strip dead source links from surfaced memory
- [x] If the source entity no longer resolves, surface the memory without the dead link
- [x] Add an explicit provenance response rule so Teeks says the source thread/message is no longer present when asked
- [x] Add focused tests for provenance wording once the rule exists

## Phase 3. Aging Without Lying

### 5. Stale context honesty
- [x] Add orchestration guidance so older memory is framed as historical and potentially changed
- [x] Tighten the prompt/runtime behavior so age disclaimers only appear when the memory actually used is old
- [x] Add focused tests for old-context phrasing in answer-generation paths

### 6. Replace TTL-style hiding with recency-weighted retrieval
- [x] Audit current `expires_at` / `stale` behavior across context retrieval and diary listing
- [x] Stop treating old decisions as effectively expired when they are still valid history
- [x] Keep older decisions retrievable, but rank recent memories first
- [x] Apply recency weighting consistently across `context_search`, contact timelines, and memory prefetch
- [x] Add verification that old but valid decisions still surface when directly relevant

## Phase 4. Surface Audit And Cleanup

### 7. UI and product consistency
- [x] Replace vault entry deletion UX with `Forget this`
- [x] Optimistically remove forgotten entries from the visible vault feed
- [x] Remove or repurpose any remaining entry-delete code paths that no longer match the product model
- [x] Audit chat previews, memory cards, and other secondary memory surfaces for consistency with the orphan-safe and forgotten rules

## Execution Order
1. Phase 3.6: recency-weighted retrieval and removal of TTL-like stale hiding where it distorts history
2. Phase 2.4: provenance honesty for deleted source threads/messages
3. Phase 4.7: remaining surface audits and cleanup

## Done So Far
- Confidence-gated retrieval is implemented.
- `forgotten` status and vault `Forget this` action are implemented.
- Primary scope-chip hiding and dead secondary-link stripping are implemented.
- The orchestrator now tells Teeks to be honest when relying on older memory.
- Provenance honesty for missing source threads/messages is implemented.
- Age disclaimers now only appear when an actually old retrieved memory item is in play.
- Historical decisions remain retrievable across the main memory readers while recency still ranks newer memory first.

## Remaining Work
- Audit remaining surfaces and cleanup any old delete-oriented paths.

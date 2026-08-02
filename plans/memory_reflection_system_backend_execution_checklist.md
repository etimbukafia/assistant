# Memory Reflection System Backend Execution Checklist

## Goal
Make backend chat behave like a read-only memory retrieval system for natural-language questions about people, threads, meetings, approvals, preferences, and prior captures.

## Prompt and Orchestration
- Replace generic thinking/chat framing in [backend/prompts/chat_system.md](/C:/Users/j/afiavana/assistant/backend/prompts/chat_system.md) with explicit Memory Reflection instructions.
- Decide whether [backend/prompts/chat_reflection.md](/C:/Users/j/afiavana/assistant/backend/prompts/chat_reflection.md) should be retired, repurposed, or kept for a separate surface.
- Update planner/orchestrator guidance in [backend/src/app/chat/orchestrator.py](/C:/Users/j/afiavana/assistant/backend/src/app/chat/orchestrator.py) so entity resolution and memory retrieval are preferred before any generic response path.
- Ensure responses lead with the answer, then concise supporting context.

## Retrieval Gating
- Update [backend/src/app/chat/tool_policy.py](/C:/Users/j/afiavana/assistant/backend/src/app/chat/tool_policy.py) so read-context retrieval is allowed for clear memory questions even without explicit mentions.
- Keep small talk blocked from unnecessary retrieval.
- Keep write and execution tool families disallowed for this surface.
- Add explicit intent handling for:
  - "when last"
  - "did we approve"
  - "what do we know about"
  - "communication preference"
  - "what changed"
  - "remind me about"

## Entity Resolution
- Add a deterministic entity-resolution step before retrieval for plain-language names like people, vendors, and projects.
- Use `entity_search` as the first resolver when no explicit mention token exists.
- Return a structured resolution state:
  - `resolved`
  - `ambiguous`
  - `unresolved`
- For `ambiguous`, return a short clarification payload with distinguishing metadata.
- For `unresolved`, fall back to topic/context search when reasonable.

## Retrieval Composition
- After resolution, route to the appropriate read path:
  - contact brief / timeline / signals for people
  - `context_search` for decisions, commitments, risks, preferences, and approvals
  - thread or event context when the entity is not a contact
- Review whether approval-history questions need a dedicated deterministic query instead of relying only on general context entries.
- Preserve current read-only behavior and avoid accidental action execution.

## Response Safety
- Never guess between multiple plausible entities.
- Never fabricate memory when no match exists.
- Ask one short clarification question when required.
- Be explicit about uncertainty and missing records.

## Tests
- Update [backend/tests/unit/test_chat_tool_policy.py](/C:/Users/j/afiavana/assistant/backend/tests/unit/test_chat_tool_policy.py) for natural-language retrieval without `@mentions`.
- Add tests for:
  - ambiguous person name
  - no matching entity
  - exact match resolution
  - preference question
  - approval-history question
  - "when last did we discuss" query
- Add orchestrator or service tests for clarification behavior and fallback retrieval.

## Verification
- Run targeted backend unit tests for tool policy, orchestration, and retrieval.
- Verify no regression in small-talk handling.
- Verify no regression in approval-gated or write-tool blocking.
- Confirm logs and metrics still make sense after the retrieval-path changes.

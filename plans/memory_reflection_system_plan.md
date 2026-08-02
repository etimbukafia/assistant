# Memory Reflection System Plan

## Product Thesis
Turn chat into a **Memory Reflection Space**: a calm, read-only workspace where an executive assistant can ask natural questions about prior captures, people, threads, meetings, decisions, approvals, preferences, and relationship context.

## Jobs-Like Product Standard
- One job: recall and clarify what matters.
- No mode confusion.
- No syntax burden like mandatory `@mentions`.
- No false certainty.
- If memory exists, surface it cleanly.
- If memory is ambiguous or missing, say so plainly and ask one sharp question.

## Core Product Rules
- Default behavior is memory retrieval, not generic chat.
- Natural-language questions should work:
  - "When last did we discuss X with Sarah?"
  - "Is there any communication preference I need to know about Mike?"
  - "Did we approve vendor X?"
- Read-only by default.
- Never fabricate certainty.

## System Plan

### 1. Reframe the Surface
- Rename the chat workspace to `Memory Reflection Space`.
- Replace generic starter prompts with memory-first questions.
- Rename generic UI labels like `References` to something product-native such as `Memory Sources` or `Context in View`.

### 2. Rewrite the Backend Prompt
- Make the assistant's role explicit: answer memory questions using captured context.
- Lead with the answer, then show the relevant memory used.
- If memory is missing, say what is known and ask one concrete follow-up.
- Remove emotional-support/reflection framing from this surface.

### 3. Change Retrieval Gating
- Stop requiring explicit mentions for read-only retrieval.
- Unlock retrieval when intent is clearly about:
  - history
  - prior discussions
  - approvals
  - preferences
  - relationship context
  - updates or what changed
- Keep writes and execution paths separately gated.

### 4. Add Entity Resolution as a First-Class Step
- Resolve plain-language names before retrieval.
- Prefer deterministic resolution before asking the model to answer.
- Resolution states:
  - `resolved`
  - `ambiguous`
  - `unresolved`

### 5. Define Ambiguity Handling
- If multiple matches exist:
  - ask one concise clarification question
  - show human-readable distinctions such as role, organization, email, or last interaction
- If no match exists:
  - say no direct match was found
  - offer fallback topic, thread, or context search

## Execution Order
1. Product framing and prompt rewrite
2. Retrieval gating changes
3. Entity resolution and ambiguity flow
4. UI refinement around memory-first behavior
5. Tests for natural-language memory queries, ambiguous entities, and missing entities

## Success Criteria
- Users can ask memory questions naturally without special syntax.
- The system does not guess when identity is unclear.
- Answers feel grounded in prior context, not generic.
- The surface clearly feels like a memory product, not a general chat box.

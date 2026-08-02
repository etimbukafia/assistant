# Playground Chat Streaming Plan (Jobs-Style)

## UX Contract (Must-Have)
- User message appears instantly (optimistic render).
- First visible assistant reaction in **<200ms** (`Thinking` state).
- No false failure toast while processing is still active.
- No internal jargon in UI (`tool_call`, `invalid params`, stack traces).
- Stop/cancel is immediate and clean.

## Latency Targets
- `TTFV` (time to first visible assistant state): **<200ms**.
- `TTFT` (first token): best-effort, measured separately; do not block UX on it.
- No blocking UI waits without status transitions.

## Phase 1 — Mirror Main Backend Chat Architecture in Playground
### Files to add/copy from main backend
- `backend/src/app/chat/context.py` -> `playground/backend/src/app/chat/context.py`
- `backend/src/app/chat/orchestrator.py` -> `playground/backend/src/app/chat/orchestrator.py`
- `backend/src/app/chat/planner_models.py` -> `playground/backend/src/app/chat/planner_models.py`
- `backend/src/app/chat/planner_parser.py` -> `playground/backend/src/app/chat/planner_parser.py`
- `backend/src/app/chat/dag_executor.py` -> `playground/backend/src/app/chat/dag_executor.py`
- `backend/src/app/chat/tool_policy.py` -> `playground/backend/src/app/chat/tool_policy.py`
- `backend/src/app/chat/tools.py` -> `playground/backend/src/app/chat/tools.py`
- `backend/src/app/chat/approval_intent.py` -> `playground/backend/src/app/chat/approval_intent.py`
- `backend/src/app/chat/service.py` -> `playground/backend/src/app/chat/service.py`

### Files to adapt (playground-specific)
- `playground/backend/src/app/data/models.py`
  - Ensure all chat session/message/job/action models expected by main chat service exist.
- `playground/backend/src/app/data/schemas.py`
  - Match main chat request/response contracts.
- `playground/backend/src/app/db.py`
  - Ensure indices and columns required by planner/DAG/actions/jobs exist.
- `playground/backend/src/app/services/mention_context.py`
  - Match main mention/slash contract shape used by chat route and frontend.

## Phase 2 — Mirror Main Backend Chat API Surface
### Files
- `backend/src/app/routes/v1/chat.py` -> `playground/backend/src/app/routes/v1/chat.py` (new)
- `playground/backend/main.py`
  - Mount v1 chat router.
  - Keep legacy `playground/backend/src/app/routes/chat.py` only as temporary fallback; then unhook.

### Endpoints to support
- `POST /v1/chat/sessions/{session_id}/messages`
- `GET /v1/chat/jobs/{job_id}`
- `GET /v1/chat/sessions`
- `POST /v1/chat/sessions`
- `GET /v1/chat/sessions/{session_id}`
- `DELETE /v1/chat/sessions/{session_id}`
- `GET /v1/chat/mentions`
- `GET /v1/chat/slash-suggestions`
- `GET /v1/chat/action-chips`
- approvals/rejections endpoints used by current main UI

## Phase 3 — Prompt Parity
### Files
- `backend/prompts/chat_system.md` -> `playground/backend/prompts/chat_system.md`
- `backend/prompts/teeks_chat_agent_prompt.md` -> `playground/backend/prompts/teeks_chat_agent_prompt.md`
- Any planner/executor prompt assets used by main flow -> same location under `playground/backend/prompts/`

### Prompt requirements
- Human status language only.
- Explicit tool behavior constraints.
- Multi-intent decomposition and approval behavior preserved.

## Phase 4 — Stream-First Backend (SSE)
### Files
- `playground/backend/src/app/routes/v1/chat.py`
  - Add stream endpoint (SSE) for send-message path.
- `playground/backend/src/app/chat/service.py`
  - Emit structured stream events from planner/executor/tool pipeline.
- `playground/backend/src/app/chat/orchestrator.py`
  - Surface stage events (`thinking`, `checking_context`, `drafting`, `needs_approval`, `completed`, `failed`).
- `playground/backend/src/app/chat/dag_executor.py`
  - Emit per-node lifecycle events.

### Event envelope (stable)
- `event_id`
- `session_id`
- `message_id`
- `type` (`state`, `token`, `approval`, `error`, `complete`)
- `payload`
- `ts`

### Rules
- Stream starts with `state:thinking` immediately.
- Do one final authoritative `complete` event with final message payload.
- Keep polling endpoint alive as silent fallback.

## Phase 5 — Mirror Main Frontend Chat Architecture in Playground
### Files to add/copy from main frontend
- `frontend/src/services/chat.ts` -> `playground/frontend/src/services/chat.ts`
- `frontend/src/hooks/useChat.ts` -> `playground/frontend/src/hooks/useChat.ts`
- `frontend/src/components/chat/MessageBubble.tsx` -> `playground/frontend/src/components/chat/MessageBubble.tsx`
- `frontend/src/components/chat/ActionBubble.tsx` -> `playground/frontend/src/components/chat/ActionBubble.tsx`
- `frontend/src/components/chat/ApprovalGateComposer.tsx` -> `playground/frontend/src/components/chat/ApprovalGateComposer.tsx`
- `frontend/src/app/dashboard/chat/page.tsx` -> `playground/frontend/src/app/dashboard/chat/page.tsx` (or map route equivalent)

### Files to adapt
- `playground/frontend/src/features/core/api.ts`
  - Wire to `/v1/chat/*` endpoints.
- `playground/frontend/src/app/chat/page.tsx`
  - Use new chat workspace architecture (or route redirect to dashboard chat page).

## Phase 6 — Stream-First Frontend Integration
### Files
- `playground/frontend/src/services/chat.ts`
  - Add `sendMessageStream(...)` SSE client.
  - Keep polling fallback (`sendMessageWithPolling`) only when stream fails.
- `playground/frontend/src/hooks/useChat.ts`
  - Stream lifecycle state machine.
  - Optimistic user message + immediate `Thinking`.
- `playground/frontend/src/components/chat/MessageBubble.tsx`
  - Incremental token rendering.
  - Human-only state badges.

### UX rules
- Never show `failed` before stream truly ends in error.
- If reconnect occurs, dedupe by `event_id`.
- Preserve single assistant message per turn.

## Phase 7 — Persistence, Correctness, and Safety
### Files
- `playground/backend/src/app/chat/service.py`
- `playground/backend/src/app/data/models.py`
- `playground/backend/src/app/db.py`

### Requirements
- Final assistant message committed once.
- Idempotent completion handling.
- Background metrics writes must not block stream completion.

## Phase 8 — Tests + QA
### Backend tests
- `playground/backend/tests/test_chat_stream_smalltalk.py`
- `playground/backend/tests/test_chat_stream_single_tool.py`
- `playground/backend/tests/test_chat_stream_multi_intent_dag.py`
- `playground/backend/tests/test_chat_stream_approval.py`
- `playground/backend/tests/test_chat_stream_reconnect_dedupe.py`

### Frontend/manual QA focus
- `plans/manual_qa_checklist_playground_streaming.md` (new)
  - Verify <200ms first visible assistant state.
  - Verify no false failure flashes.
  - Verify approval + fallback behavior.

## Rollout Sequence (Playground)
1. Backend architecture parity.
2. Frontend architecture parity.
3. Stream endpoint + client on a single route.
4. Golden path QA.
5. Remove legacy chat route wiring.


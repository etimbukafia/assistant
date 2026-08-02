# Playground Chat Parity Mapping (Main -> Playground)

## Goal
- Bring playground chat architecture to production parity before full streaming rollout.
- Keep UX constraints: instant user echo + <200ms assistant visible reaction.

## Backend Mapping

### Chat Core
- `backend/src/app/chat/context.py` -> `playground/backend/src/app/chat/context.py`
- `backend/src/app/chat/orchestrator.py` -> `playground/backend/src/app/chat/orchestrator.py`
- `backend/src/app/chat/planner_models.py` -> `playground/backend/src/app/chat/planner_models.py`
- `backend/src/app/chat/planner_parser.py` -> `playground/backend/src/app/chat/planner_parser.py`
- `backend/src/app/chat/dag_executor.py` -> `playground/backend/src/app/chat/dag_executor.py`
- `backend/src/app/chat/tool_policy.py` -> `playground/backend/src/app/chat/tool_policy.py`
- `backend/src/app/chat/tools.py` -> `playground/backend/src/app/chat/tools.py`
- `backend/src/app/chat/approval_intent.py` -> `playground/backend/src/app/chat/approval_intent.py`
- `backend/src/app/chat/service.py` -> `playground/backend/src/app/chat/service.py`

### Route Surface
- `backend/src/app/routes/v1/chat.py` -> `playground/backend/src/app/routes/v1/chat.py`

### Prompts
- `backend/prompts/chat_system.md` -> `playground/backend/prompts/chat_system.md`
- `backend/prompts/teeks_chat_agent_prompt.md` -> `playground/backend/prompts/teeks_chat_agent_prompt.md`

### Data/Infra Dependencies Needed in Playground
- `chat_sessions`, `chat_messages`, `chat_pending_actions` models/tables
- session/job/action payload contracts used by main frontend
- mention/slash suggestion payload parity

## Frontend Mapping

### Chat UI Stack
- `frontend/src/app/dashboard/chat/page.tsx` -> `playground/frontend/src/app/dashboard/chat/page.tsx`
- `frontend/src/hooks/useChat.ts` -> `playground/frontend/src/hooks/useChat.ts`
- `frontend/src/services/chat.ts` -> `playground/frontend/src/services/chat.ts`
- `frontend/src/components/chat/MessageBubble.tsx` -> `playground/frontend/src/components/chat/MessageBubble.tsx`
- `frontend/src/components/chat/ActionBubble.tsx` -> `playground/frontend/src/components/chat/ActionBubble.tsx`
- `frontend/src/components/chat/ApprovalGateComposer.tsx` -> `playground/frontend/src/components/chat/ApprovalGateComposer.tsx`

### Playground Adapters
- `playground/frontend/src/features/core/api.ts` must expose `/v1/chat/*`
- current feature-based chat page should route to parity chat workspace

## Current Gap Snapshot

### Completed in this step
- Added chat persistence models to playground:
  - `playground/backend/src/app/data/models.py`
    - `ChatSession`
    - `ChatMessage`
    - `ChatPendingAction`
- Added chat schema models:
  - `playground/backend/src/app/data/schemas.py`
    - `ChatSessionResponse`
    - `ChatMessageResponse`
    - `ChatPendingActionResponse`

### Remaining blockers
- Main chat service/orchestrator imports modules not present in playground (`security`, telemetry writer, some infra wiring).
- Playground currently has legacy `/api/chat` route; parity `/v1/chat` route is not mounted yet.
- Frontend playground still uses simplified feature chat and polling assumptions from legacy route.

## Next Implementation Slice
1. Port/mirror `backend/src/app/routes/v1/chat.py` into playground with playground auth/db adapters.
2. Port/mirror `backend/src/app/chat/service.py` and minimal dependencies needed to make `/v1/chat/sessions` + `/messages` run.
3. Wire playground frontend chat service/hook/page to parity route contracts.
4. Then layer SSE streaming on top.


# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered executive assistant inbox management system. FastAPI backend + React Native (Expo) mobile app. Connects to Gmail, auto-summarizes threads, extracts tasks/dates/people/decisions, classifies emails, and drafts replies using AI.

## Development Commands

### Backend (from `backend/` directory)
```bash
uvicorn src.main:app --reload          # Run API server
python -m src.app.jobs.worker          # Run background worker (uses BatchWorker for LLM efficiency)
curl http://localhost:8000/queue/stats # Monitor queue
```

### Mobile (from `mobile/` directory)
```bash
npm start        # Start Expo
npm run android  # Run on Android
npm run ios      # Run on iOS
```

### Testing (from `backend/` directory)
```bash
pytest                              # Run all tests
pytest tests/unit/test_auth.py      # Run specific test file
pytest -m unit                      # Fast, mocked tests
pytest -m integration               # May use real resources
pytest -m sandbox                   # Polar sandbox tests
pytest -m api                       # API endpoint tests
pytest -m "not slow"                # Skip LLM/API tests
pytest -m "not live"                # Skip tests that cost money
```

## Architecture

### Directory Structure
```
backend/src/
├── core/              # Reusable frameworks (copy to other projects unchanged)
│   ├── events/        # Event emission with FastAPI BackgroundTasks
│   ├── queue/         # Postgres-backed task queue with row-level locking
│   └── llm/           # LLM provider abstraction (Gemini, HuggingFace/Outlines)
├── app/               # Application-specific code
│   ├── routes/v1/     # API endpoints
│   ├── handlers/      # Event handlers (decorated with @register_handler)
│   ├── services/      # Business logic (thread_state, digest, calendar, polar)
│   ├── processors/    # AI processing (ai.py, message.py, document.py)
│   ├── agents/        # Autonomous modules (scheduling, follow-up, communication)
│   ├── chat/          # Chat/conversation system with tool execution
│   ├── intelligence/  # Context building & pattern tracking
│   ├── integrations/  # Gmail integration
│   ├── data/          # Models & schemas
│   ├── infra/         # Config, database, logging
│   ├── security/      # Encryption, auth, feature gating
│   └── jobs/          # Worker handlers (worker.py defines TASK_HANDLERS)
backend/prompts/       # AI prompts as markdown files (template vars: {sender}, {subject}, {body})

mobile/
├── app/               # Expo Router screens (file-based routing)
│   └── (tabs)/        # Tab navigation screens
├── src/
│   ├── components/    # Reusable UI components
│   ├── context/       # React contexts (AuthContext, ChatContext)
│   ├── hooks/         # TanStack Query hooks
│   ├── services/      # API service functions
│   └── theme/         # Design tokens and colors
```

### Key Backend Patterns

**Event-Driven Processing**: Endpoints emit events via `emit_event()`, handlers run in BackgroundTasks. Register handlers with `@register_handler("event_name")`. Handlers are defined in `app/handlers/`.

**LLM Orchestration**: `LLMOrchestrator` in `core/llm/` abstracts provider selection. Returns structured JSON (Dict or List[Dict]). Supports `generate()` for single prompts and `generate_batch()` for multiple.

**Thread State Machine**: `ThreadStateService` tracks thread state incrementally (open_tasks, decisions, participants). First message calls `init_thread_state()`, subsequent messages call `update_thread_state()`. Avoids re-analyzing full transcripts.

**Batch Processing**: `BatchWorker` groups tasks by `user_id` for efficient LLM inference. User data never mixed. Standard `Worker` processes tasks individually.

**Context Injection**: `ContextBuilder` injects user preferences from `PrincipalMemory`, `DecisionPattern`, and `ContactContext` into prompts.

**Subscription Gating**: Two levels of access control:
- `require_active_subscription` - FastAPI dependency for endpoints requiring active trial/pro
- `require_feature(Feature.X)` - Fine-grained feature gating with 3-day grace period (features defined in `Feature` enum)

**Business Model** (Freemium with Polar billing):
- **Sandbox**: Demo mode, `trial_ends_at = null`, shows mock data
- **Trial**: 7 days, `trial_ends_at` set, full features
- **Pro**: Paid via Polar, `subscription_tier = "pro"`, `subscription_status = "active"`
- **Grace Period**: 3 days after expiration, features still accessible
- **Expired**: Read-only access, upgrade CTA shown

Revenue-critical paths: Trial activation → Gmail sync → AI value delivery → Upgrade prompt → Polar checkout → Webhook confirms payment. Polar webhooks handled in `app/handlers/webhook_handlers.py`. Always return 200 to prevent retry storms.

**RLS Context**: All handlers must set PostgreSQL RLS context with:
```python
db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
```

### Key Mobile Patterns

**State Management**: TanStack Query for server state (API data), React Context for client state (auth, settings).

**Sandbox Mode**: Before trial activation, `isSandbox=true` shows demo data from `demo_state.json`. After trial activation, fetches real data.

**Subscription States**:
- `isSandbox` - Never started trial (show demo data)
- `isActive` - Trial/pro currently valid (allow sync)
- `!isActive && !isSandbox` - Expired (show CTA, read-only access)

**API Hooks Pattern**: Create hooks in `src/hooks/` that wrap TanStack Query, pass `enabled: false` when in sandbox to avoid unnecessary API calls.

### Data Flow
1. `/sync` fetches Gmail messages → saved to DB → `emit_event("message_received")`
2. Handler enqueues `process_email` task with `user_id` in payload
3. `BatchWorker` groups tasks by user → `process_messages_batch()` → `ThreadStateService` → AI extraction
4. Mobile app polls `/messages/new` for updates

### Chat System
- `ChatOrchestrator` routes messages through LLM with tool execution
- Two session types: `command` (with tools) and `reflection` (no tools)
- Tools defined in `ChatToolRegistry`, some require user approval (pending actions)
- Prompts loaded from `backend/prompts/chat_system.md` and `chat_reflection.md`

## Environment Variables

Required in `.env`:
- `DATABASE_URL` - PostgreSQL connection string (or SQLite for local dev)
- `GOOGLE_API_KEY` - Gemini API key
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - Gmail OAuth credentials
- `ENCRYPTION_KEY` - For at-rest email body encryption (Fernet key)
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET` - Supabase auth
- `POLAR_ACCESS_TOKEN`, `POLAR_WEBHOOK_SECRET` - Polar billing

Optional:
- `LLM_PROVIDER` - "huggingface" or "gemini" (default)
- `LLM_HF_MODEL` - HuggingFace model ID for local inference
- `FRONTEND_URL` - Frontend URL for OAuth redirects

## Database

SQLAlchemy models in `app/data/models.py`. Migrations in `backend/migrations/` as raw SQL files. Key models:
- `Message`, `ThreadState`, `Task`, `GmailAccount`
- `PrincipalMemory`, `DecisionPattern`, `ContactContext` (user preferences)
- `TaskQueue` (persistent job queue with row-level locking)
- `SchedulingSuggestion`, `CalendarEvent`, `Digest`, `ChatSession`, `ChatMessage`, `ChatPendingAction`
- `UserSettings` - has `@property` methods `is_active` and `days_remaining` for computed subscription status

## Task Queue

Tasks are defined in `backend/src/app/jobs/worker.py` in `TASK_HANDLERS` dict. Key task types:
- `process_email` - AI processing of email messages (batched by user)
- `emit_event` - Event chaining after handler completes
- `trigger_agent` - Triggers autonomous agent orchestrator
- `generate_digest` - Scheduled digest generation (self-reschedules)
- `email_backfill` - Initial sync of historical emails
- `data_cleanup` - Nightly cleanup of expired content (runs at 2 AM UTC)
- `chat_cleanup` - Hourly cleanup of expired chat sessions
- `cleanup_stuck_chat_messages` - Every 10 min, expires stuck "processing" chat messages (5-min threshold)
- `process_chat_message` - Async chat processing when sync times out or tools detected

## Test Markers

Tests use pytest markers defined in `backend/pytest.ini`:
- `@pytest.mark.unit` - Fast, isolated, mocked dependencies
- `@pytest.mark.integration` - May use real resources
- `@pytest.mark.sandbox` - Polar sandbox tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.slow` - LLM inference, API calls
- `@pytest.mark.live` - Real API calls (costs money)

## Guidelines

- **Avoid Over-engineering**: Balance simplicity, efficiency, and scalability. Don't add abstractions for one-time operations.
- **SQLite Compatibility**: Tests use SQLite. Avoid PostgreSQL-specific JSON queries like `column["key"].astext`; filter in Python instead.
- **Always Set RLS Context**: Every handler touching user data must call `set_config('app.user_id', ...)`.
- **Self-Rescheduling Jobs**: Cleanup/scheduled tasks must enqueue their next run before completing.

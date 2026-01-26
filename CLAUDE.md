# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered executive assistant inbox management system. FastAPI backend + React frontend + React Native (Expo) mobile app. Connects to Gmail, auto-summarizes threads, extracts tasks/dates/people/decisions, classifies emails, and drafts replies using AI.

## Development Commands

### Backend (from `backend/` directory)
```bash
uvicorn src.main:app --reload          # Run API server
python -m src.app.jobs.worker          # Run background worker
curl http://localhost:8000/queue/stats # Monitor queue
```

### Frontend (from `frontend/` directory)
```bash
npm run dev      # Development server (Vite)
npm run build    # Production build
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
│   ├── handlers/      # Event handlers
│   ├── services/      # Business logic (thread_state, digest, calendar, polar)
│   ├── processors/    # AI processing (ai.py, message.py, document.py)
│   ├── agents/        # Autonomous modules (scheduling, follow-up, communication)
│   ├── chat/          # Chat/conversation system
│   ├── intelligence/  # Context building & pattern tracking
│   ├── integrations/  # Gmail integration
│   ├── data/          # Models & schemas
│   ├── infra/         # Config, database, logging
│   └── security/      # Encryption, auth, feature gating
backend/prompts/       # AI prompts as markdown files (cached loading)

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

**Event-Driven Processing**: Endpoints emit events via `emit_event()`, handlers run in BackgroundTasks. Register handlers with `@register_handler("event_name")`.

**LLM Orchestration**: `LLMOrchestrator` in `core/llm/` abstracts provider selection. Use `hf_outlines` provider for structured JSON output.

**Thread State Machine**: `ThreadStateService` tracks thread state incrementally (open_tasks, decisions, participants). Avoids re-analyzing full transcripts on each message.

**Batch Processing**: Worker batches messages by user for efficient LLM inference. User data never mixed.

**Context Injection**: `ContextBuilder` injects user preferences from `PrincipalMemory`, `DecisionPattern`, and `ContactContext` into prompts.

**Subscription Gating**: Two levels of access control:
- `require_active_subscription` - FastAPI dependency for endpoints requiring active trial/pro
- `require_feature(Feature.X)` - Fine-grained feature gating with 3-day grace period

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
2. Handler enqueues `process_email` task
3. Worker polls queue → `ThreadStateService.process_message()` → AI extraction
4. Frontend polls `/messages/new` for updates

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
- `TaskQueue` (persistent job queue)
- `SchedulingSuggestion`, `CalendarEvent`, `Digest`, `ChatSession`
- `UserSettings` - has `@property` methods `is_active` and `days_remaining` for computed subscription status

## Test Markers

Tests use pytest markers defined in `backend/pytest.ini`:
- `@pytest.mark.unit` - Fast, isolated, mocked dependencies
- `@pytest.mark.integration` - May use real resources
- `@pytest.mark.sandbox` - Polar sandbox tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.slow` - LLM inference, API calls
- `@pytest.mark.live` - Real API calls (costs money)

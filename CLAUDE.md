# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered executive assistant inbox management system. FastAPI backend + React frontend that connects to Gmail, auto-summarizes threads, extracts tasks/dates/people/decisions, classifies emails, and drafts replies.

## Development Commands

### Backend
```bash
# Run API server
uvicorn app.main:app --reload

# Run background worker (processes email analysis queue)
python -m app.worker

# Monitor queue
curl http://localhost:8000/queue/stats
```

### Frontend
```bash
cd frontend
npm run dev      # Development server
npm run build    # Production build
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_example.py

# Run by marker
pytest -m unit           # Fast, mocked tests
pytest -m integration    # May use real resources
pytest -m "not slow"     # Skip LLM/API tests
pytest -m "not live"     # Skip tests that cost money
```

## Architecture

### Directory Structure
- `core/` - **Reusable frameworks** (copy to other projects unchanged)
  - `core/events/` - Event emission with FastAPI BackgroundTasks
  - `core/queue/` - Postgres-backed task queue with row-level locking
  - `core/llm/` - LLM provider abstraction (Gemini, HuggingFace/Outlines)
- `app/` - Application-specific code
  - `app/handlers/` - Event handlers (message_received, task events, etc.)
  - `app/agents/` - Autonomous modules (scheduling, follow-up, communication)
  - `app/main.py` - FastAPI endpoints
  - `app/worker.py` - Queue worker with task handlers
- `prompts/` - AI prompts as markdown files (loaded with caching)
- `frontend/src/` - React components in `components/` and `views/`

### Key Patterns

**Event-Driven Processing**: Endpoints emit events via `emit_event()`, handlers run in BackgroundTasks. Handlers are registered with `@register_handler("event_name")` decorator.

**LLM Orchestration**: `LLMOrchestrator` abstracts provider selection. Providers cached at class level. Use `hf_outlines` provider for structured JSON output.

**Thread State Machine**: `ThreadStateService` tracks thread state incrementally (open_tasks, decisions, participants). Avoids re-analyzing full transcripts on each message.

**Batch Processing**: Worker batches messages by user for efficient LLM inference. User data never mixed.

**Context Injection**: `ContextBuilder` injects user preferences from `PrincipalMemory`, `DecisionPattern`, and `ContactContext` into prompts.

### Data Flow
1. `/sync` fetches Gmail messages → saved to DB → `emit_event("message_received")`
2. Handler enqueues `process_email` task
3. Worker polls queue → `ThreadStateService.process_message()` → AI extraction
4. Frontend polls `/messages/new` for updates

## Environment Variables

Required in `.env`:
- `DATABASE_URL` - PostgreSQL connection string (or SQLite for local dev)
- `GOOGLE_API_KEY` - Gemini API key (if using Gemini provider)
- `ENCRYPTION_KEY` - For at-rest email body encryption

Optional:
- `LLM_PROVIDER` - "huggingface" or "gemini" (default)
- `LLM_HF_MODEL` - HuggingFace model ID for local inference

## Database

SQLAlchemy models in `app/models.py`. Migrations in `migrations/` as raw SQL files. Key models:
- `Message`, `ThreadState`, `Task`, `GmailAccount`
- `PrincipalMemory`, `DecisionPattern`, `ContactContext` (user preferences)
- `TaskQueue` (persistent job queue)
- `SchedulingSuggestion`, `CalendarEvent`, `Digest`

## Test Markers

Tests use pytest markers defined in `pytest.ini`:
- `@pytest.mark.unit` - Fast, isolated, mocked dependencies
- `@pytest.mark.integration` - May use real resources
- `@pytest.mark.slow` - LLM inference, API calls
- `@pytest.mark.live` - Real API calls (costs money)

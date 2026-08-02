# EA Diary: Voice Capture Backend Execution Checklist

## Phase 1: Transcription Ingestion
- [x] add backend config for OpenAI speech-to-text
  - files:
    - `backend/src/app/infra/config.py`
    - `backend/.env.example`
- [x] add OpenAI Python SDK dependency if not already present
  - file:
    - `backend/requirements.txt`
- [x] add a dedicated voice capture endpoint
  - `POST /v1/context/captures/voice`
  - accept:
    - audio file
    - `scope_type`
    - `scope_id`
  - require `Pro` access
  - files:
    - `backend/src/app/routes/v1/vault.py`
    - `backend/src/app/data/schemas.py`
- [x] validate scope ownership using the same canonical capture rules as typed capture
  - file:
    - `backend/src/app/routes/v1/vault.py`
- [x] enforce supported audio formats and request size limits
  - accept only supported transcription formats:
    - `mp3`
    - `mp4`
    - `mpeg`
    - `mpga`
    - `m4a`
    - `wav`
    - `webm`
  - keep uploads below the API file-size limit
  - file:
    - `backend/src/app/routes/v1/vault.py`

## Phase 2: 45-Second Constraint
- [x] enforce the `45s` product limit in the backend contract
  - reject oversized duration metadata when available
  - add a fallback max upload size guard
  - file:
    - `backend/src/app/routes/v1/vault.py`
- [x] document that the frontend must auto-stop at `45s`
  - file:
    - `plans/ea-diary-voice-capture-implementation-plan.md`

## Phase 3: OpenAI Transcription Service
- [x] add a dedicated transcription service
  - file:
    - `backend/src/app/services/voice_transcription.py`
- [x] call `client.audio.transcriptions.create(...)`
  - model:
    - `gpt-4o-mini-transcribe`
  - endpoint family:
    - `v1/audio/transcriptions`
- [x] request JSON response format for determinism
  - normalize the returned `text` field to plain transcript text
- [x] normalize transcript text before persistence
  - trim whitespace
  - collapse repeated whitespace/newlines
- [x] treat OpenAI response text as untrusted input
  - do not log raw transcript text
  - keep any diagnostic data internal

## Phase 4: Overflow Shortening
- [x] compare transcript length against the existing capture text limit
- [x] if over limit, shorten with Gemma before save
  - file:
    - `backend/src/app/services/context_capture_shortener.py`
- [x] keep the shortening prompt in a dedicated prompt file
  - file:
    - `backend/src/app/prompts/shorten_context_capture.md`
- [x] persist only the final saved capture text
  - do not retain raw audio
  - do not create a separate voice-note object

## Phase 5: Persistence and Reuse
- [x] persist voice captures through the same `ContextEntry` path as typed captures
- [ ] add optional `input_source="voice"` metadata if needed
- [x] add optional `input_source="voice"` metadata if needed
  - files:
    - `backend/src/app/data/models.py`
    - `backend/src/app/data/schemas.py`
    - migration if added
- [x] enqueue the existing async `classify_context_capture` flow after save
  - file:
    - `backend/src/app/routes/v1/vault.py`

## Phase 6: Privacy and Failure Handling
- [x] ensure uploaded audio is stored only ephemerally
- [x] delete temp audio immediately after transcription attempt
- [x] fail softly
  - if transcription fails, return a calm capture-specific error
  - do not expose provider internals
- [ ] add abuse controls
- [x] add abuse controls
  - per-user rate limiting
  - request throttling for voice capture

## Phase 7: Observability
- [x] log voice-capture workflow metrics only
  - request count
  - transcription latency
  - shortening count
  - failure count
- [x] do not log raw audio or transcript text
- [x] tag source as `voice_capture`

## Phase 8: Tests
- [x] unit tests for scope validation and file validation
  - likely file:
    - `backend/tests/unit/test_voice_capture_route.py`
- [x] unit tests for the OpenAI transcription service
  - likely file:
    - `backend/tests/unit/test_voice_transcription.py`
- [x] unit tests for overflow shortening behavior
  - likely file:
    - `backend/tests/unit/test_context_capture_shortener.py`
- [x] unit tests for observability logging
  - likely file:
    - `backend/tests/unit/test_voice_capture_observability.py`
- [ ] integration tests for:
  - successful voice capture save
  - transcript over limit gets shortened
  - transcription failure returns a safe error
  - classification pipeline is still queued

## Acceptance Criteria
- [x] backend accepts short audio uploads for scoped context capture
- [x] backend transcribes with `gpt-4o-mini-transcribe`
- [ ] recording contract is capped at `45s`
- [x] over-limit transcript text is shortened with Gemma
- [x] saved result is a normal context capture
- [x] raw audio is not retained by default
- [x] voice capture reuses the existing classification flow

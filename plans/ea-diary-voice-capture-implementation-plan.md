# EA Diary: Voice Capture Implementation Plan

## Objective
Add fast voice capture to the diary while preserving the existing capture-first product model:
- one capture flow
- one saved context record
- one scope model

Voice should only change how text is entered.

## Locked Decisions
- transcription provider: OpenAI speech-to-text API
- transcription model: `gpt-4o-mini-transcribe`
- recording limit: `45 seconds`
- no override for the recording limit
- voice capture is available only to `Pro` users
- audio is not retained after transcription by default
- OpenAI speech-to-text is used only for transcription
- Gemma is used only for overflow shortening and classification

## Product Flow
1. user opens a scoped or unscoped `Capture Context` surface
2. user records up to `45s`
3. frontend uploads audio to the backend
4. backend transcribes with `gpt-4o-mini-transcribe`
5. if transcript is longer than the text capture limit, backend shortens it with Gemma
6. backend saves a normal context capture
7. existing async classification pipeline runs

## Backend Design

### 1. API shape
Add a dedicated voice ingestion endpoint, for example:
- `POST /v1/context/captures/voice`

Request:
- audio file
- `scope_type`
- `scope_id`

Response:
- normal saved capture response
- initial state:
  - `type="insight"`
  - `classification_status="pending"`

Do not expose provider-specific transcription fields in the user contract.
Use the same subscription guard as other premium AI surfaces.

### 2. Audio handling
- accept only supported short audio formats
- validate content type and size before processing
- enforce the `45s` cap client-side and server-side where feasible
- store the upload only ephemerally
- delete temp audio immediately after transcription

### 3. Transcription
- call OpenAI audio transcription with a short, deterministic path
- prioritize responsiveness over transcript perfection
- normalize whitespace and punctuation before further processing

### 4. Overflow shortening
- if transcript exceeds the existing capture text limit, call Gemma to shorten it
- keep the shortening prompt in a dedicated prompt file, not inline in service code
- preserve the same meaning and scope
- optimize for latency:
  - low token budget
  - constrained summarization prompt
  - one-pass compression

### 5. Persistence
Persist as a normal context capture, with optional source metadata such as:
- `input_source="voice"`

Do not create a separate voice-note table or alternate memory model.

### 6. Classification reuse
- hand off to the existing `classify_context_capture` worker
- keep low-confidence fallback to `insight`
- preserve the same user-correction path

## Frontend Design

### 1. Capture surfaces
Add a mic action to:
- diary capture composer
- contact capture card
- email/thread capture card
- task capture card
- event capture card

### 2. Recording UI
Keep it minimal:
- mic button
- `Listening...`
- timer
- stop/cancel

Auto-stop at `45s`.

### 3. Post-recording UI
Show:
- `Transcribing...`
- then the same saved/organizing states as typed capture

Do not show:
- waveform theater unless it serves a real UX need
- transcript confidence
- model/provider labels

## Privacy and Safety
- raw audio should not be retained after transcription
- validate file type, file size, and ownership/scope before processing
- rate-limit voice capture to prevent abuse and cost spikes
- do not log raw transcript text unnecessarily

## Performance Targets
- recording stop to transcript available: fast enough to feel immediate
- save should still feel near-instant after transcription
- heavy work stays asynchronous except:
  - OpenAI transcription
  - overflow shortening when required

## Phases

### Phase 1
- add frontend recording UI with `45s` cap
- add backend voice capture endpoint
- wire `gpt-4o-mini-transcribe`
- save as normal context capture

### Phase 2
- add overflow shortening with Gemma
- add subtle `shortened for clarity` messaging when needed
- add source metadata for observability

### Phase 3
- add rate limiting, metrics, and privacy audits
- test latency and failure handling
- extend contextual capture surfaces consistently

## Tests
- audio over `45s` is rejected or auto-stopped cleanly
- audio is deleted after transcription
- transcript within limit saves directly
- transcript over limit is shortened before save
- voice capture reuses existing classification flow
- scoped voice capture attaches to the correct contact/entity/global scope

## Definition of Done
- assistants can record up to `45s`
- Teeks transcribes with `gpt-4o-mini-transcribe`
- over-limit transcript text is shortened with Gemma
- saved result is a normal context capture
- classification UX matches typed capture
- no long-lived raw audio retention by default

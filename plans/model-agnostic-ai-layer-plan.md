# Model-Agnostic AI Layer Plan

## Goal

Move all provider-specific behavior behind `backend/src/core/llm/` so application code can switch between Gemini, Claude, and local models without endpoint-level changes.

## Current Coupling

Provider-specific code currently leaks into app logic in these places:

- Shared LLM configuration and provider registration:
  - `backend/src/core/llm/config.py`
  - `backend/src/core/llm/orchestrator.py`
- Gemini-native chat tool calling:
  - `backend/src/app/chat/orchestrator.py`
  - `backend/src/app/services/genai_client.py`
- Direct drafting SDK usage:
  - `backend/src/app/superpowers/email_drafting.py`
- Gemini-specific billing and usage rules:
  - `backend/src/core/llm/token_tracking.py`
  - `backend/src/app/services/credits.py`
  - `backend/src/core/llm/model_pricing.json`

## Target Architecture

Rules:

- `app/*` may depend on `core.llm`, never on provider SDKs.
- `core.llm.providers/*` owns SDK clients and provider translation.
- Chat/tool orchestration depends on a normalized tool-calling interface.
- Usage and credit logic depends on model metadata and pricing policy, not string checks like `is_gemini_model()`.

Core interfaces to support:

- `generate_structured(prompt, system_prompt, schema)`
- `generate_text(prompt, system_prompt)`
- `generate_with_tools(messages, tools, system_prompt, max_output_tokens)`
- `generate_with_files(...)` only where capability exists
- `get_token_usage()`

## Phase 1: Stabilize the Core Contract

Files to change:

- `backend/src/core/llm/providers/base.py`
- `backend/src/core/llm/orchestrator.py`
- `backend/src/core/llm/config.py`
- `backend/src/app/infra/config.py`
- `backend/.env.example`

Tasks:

- Expand `LLMConfig.provider` to support `anthropic`.
- Split config by workload:
  - `LLM_CHAT_PROVIDER`, `LLM_CHAT_MODEL`
  - `LLM_DRAFT_PROVIDER`, `LLM_DRAFT_MODEL`
  - `LLM_EMAIL_PROVIDER`, `LLM_EMAIL_MODEL`
- Add generic provider capability methods to the base provider interface.
- Add `ANTHROPIC_API_KEY` and make config validation conditional by active provider.
- Keep existing Gemini defaults working during transition.

Acceptance criteria:

- App boots with current Gemini config unchanged.
- Provider selection is workload-specific and not hard-coded to Google.

## Phase 2: Add Anthropic Provider

Files to add or change:

- `backend/src/core/llm/providers/anthropic.py`
- `backend/src/core/llm/providers/__init__.py`
- `backend/src/core/llm/orchestrator.py`
- `backend/src/core/llm/config.py`
- `backend/requirements.txt`

Tasks:

- Implement `AnthropicProvider` for:
  - text generation
  - structured generation
  - token usage reporting
  - tool use normalization
- Register it in `LLMOrchestrator`.
- Add provider cleanup and initialization parity with Gemini.

Acceptance criteria:

- `LLMOrchestrator(config=LLMConfig.for_chat())` can use Claude without endpoint code changes.

## Phase 3: Remove Provider Logic from Chat

Files to change:

- `backend/src/app/chat/orchestrator.py`
- `backend/src/app/chat/tools.py`
- `backend/src/app/chat/service.py`
- `backend/src/app/services/genai_client.py`

Tasks:

- Extract Gemini-native `_call_llm()` logic into provider-agnostic calls.
- Introduce a normalized tool call shape:
  - assistant text
  - tool calls
  - tool results
  - usage
- Move schema translation from chat code into provider adapters.
- Delete the direct dependency on `get_genai_client()` from chat orchestration.
- Retain one fallback path for providers without native tools.

Acceptance criteria:

- `/chat/sessions/{session_id}/messages` works with Gemini and Claude.
- No provider SDK import remains in `app/chat/*`.

## Phase 4: Refactor Drafting Flows

Files to change:

- `backend/src/app/superpowers/email_drafting.py`
- `backend/src/app/routes/v1/action_tools.py`
- `backend/src/app/routes/v1/messages.py`
- `backend/src/app/agents/modules/communication.py`
- `backend/src/app/agents/modules/scheduling.py`

Tasks:

- Replace direct `google.genai` usage in `EmailDraftingService` with `core.llm`.
- Route action-tool drafting and legacy message reply drafting through the same drafting workload config.
- Keep prompt construction in app code, but move execution to the shared LLM layer.

Acceptance criteria:

- `/action-tools/email-draft` works with Claude.
- `/messages/{message_id}/draft-reply` works with Claude.
- No provider SDK import remains in drafting modules.

## Phase 5: Generalize Pricing, Usage, and Credits

Files to change:

- `backend/src/core/llm/token_tracking.py`
- `backend/src/app/services/credits.py`
- `backend/src/core/llm/model_pricing.json`
- any metrics/reporting code that assumes `provider="genai"`

Tasks:

- Replace `is_gemini_model()` checks with model metadata or pricing policy.
- Store usage by `provider` and `model`.
- Distinguish pricing policy from credit policy:
  - free local models
  - paid hosted models
- Support Anthropic pricing entries in `model_pricing.json`.

Acceptance criteria:

- Usage and credit accounting works for Claude without pretending it is Gemini.

## Phase 6: Test and Rollout

Files to add or change:

- backend unit tests around `core.llm`
- chat integration tests
- drafting endpoint tests

Test matrix:

- Gemini chat with tools
- Claude chat with tools
- Gemini draft reply
- Claude draft reply
- fallback behavior when provider tools are unavailable
- token accounting and billing policy for hosted vs local models

Rollout order:

1. Land core contract and Anthropic provider behind feature flags.
2. Migrate `/messages/{message_id}/draft-reply`.
3. Migrate `/action-tools/email-draft`.
4. Migrate chat.
5. Remove dead Gemini-only helper code.

Suggested feature flags:

- `AI_CHAT_PROVIDER`
- `AI_DRAFT_PROVIDER`
- `AI_ENABLE_PROVIDER_NATIVE_TOOLS`

## Immediate Implementation Checklist

- Add `AnthropicProvider`.
- Extend `LLMConfig` and env settings.
- Refactor chat `_call_llm()` behind `LLMOrchestrator.generate_with_tools(...)`.
- Refactor `EmailDraftingService` to use `core.llm`.
- Replace Gemini-only credit checks with provider/model policy.
- Add regression tests before flipping defaults.

## Definition of Done

- Switching from Gemini to Claude for chat and drafting requires env/config only.
- Endpoint code contains no provider SDK calls.
- Local Gemma/email-processing flows continue to work unchanged.
- Usage tracking, billing, and telemetry remain accurate across providers.

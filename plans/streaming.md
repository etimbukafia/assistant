• Short answer: moderate-to-high complexity, depending on scope.

  In this codebase (current sync + async job polling model):

  1. Low-risk streaming (SSE progress, no token streaming)

  - Cost: 1–2 days
  - Complexity: low-medium
  - What you get: immediate UX feedback (received, thinking, running tools, done) and no “failed then later success” flicker.
  - Backend changes: add SSE endpoint + emit stage events from current flow.
  - Frontend changes: replace poll loop with EventSource listener.

  2. Token streaming for simple turns (no tool calls)

  - Cost: 2–4 days
  - Complexity: medium
  - What you get: words appear live for direct replies.
  - Backend changes: Gemini stream API path + chunk buffering + final commit semantics.
  - Frontend changes: incremental render + abort/cancel handling.

  3. Full streaming (tokens + tool events + async queue jobs)

  - Cost: 5–10 days
  - Complexity: high
  - What you get: consistent live UX across all turn types.
  - Requires: event bus/pub-sub between worker and API stream endpoint, reconnection semantics, ordering/idempotency, timeout handling.

  Main complexity drivers

  - Keeping DB correctness while streaming partial output.
  - Streaming across queued/worker jobs (not just direct request path).
  - Auth + connection lifecycle for long-lived streams.
  - Proxy/load-balancer buffering/timeouts.

  Pragmatic recommendation

  - Start with SSE progress events first (fast win), then add token streaming only for no-tool turns.
  - This gives most UX benefit quickly without destabilizing orchestration.
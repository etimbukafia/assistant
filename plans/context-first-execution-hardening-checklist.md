# Context-First Execution Hardening Checklist

## Scope
Harden Teeks for the positioning:

`AI Assistant that helps executive assistants manage context`

This checklist is execution-focused: reliability, latency, context quality, UX trust, and release readiness.

## Acceptance Targets (Release Gate)

| Metric | Target | How Measured | Owner |
|---|---:|---|---|
| Context retrieval precision (tagged QA set) | >= 90% | Manual QA set + sampled log review | QA |
| Chat p95 (no-tool turns) | <= 2.5s | `chat_sync_stage_timing` logs | Backend |
| Chat p95 (mention/tool turns) | <= 4.5s | `chat_sync_stage_timing` logs | Backend |
| User-facing internal-error leaks | 0 | UI regression + error log scan | Frontend + Backend |
| Cache invalidation consistency bugs | 0 open P0/P1 | Mutation/invalidation test suite | Backend |

## Owners

- `Backend`: API, orchestrator, tool execution, context assembly, cache invalidation, telemetry.
- `Frontend`: chat UX, references pane behavior, formatting safety, user-safe errors.
- `QA`: manual checklist runs, integration scenarios, release signoff.

## Workstream Checklist

| ID | Task | Owner | File Targets | Verification | Status |
|---|---|---|---|---|---|
| REL-01 | Make mention resolution deterministic for `contact/thread/event/task` | Backend | `backend/src/app/services/mention_context.py` | Mention matrix pass (single + multi mention) | [ ] |
| REL-02 | Ensure referenced archived threads remain readable | Backend | `backend/src/app/services/mention_context.py`, `backend/src/app/chat/tools.py` | Chat mention of archived thread returns usable context | [ ] |
| REL-03 | Remove generic fallbacks and enforce human-safe tool failure messages | Backend | `backend/src/app/chat/tools.py`, `backend/src/app/chat/orchestrator.py` | No internal wording in failures | [ ] |
| REL-04 | Add integration tests: mention -> prefetch -> tool -> final response | Backend | `backend/tests/integration/` | CI pass | [ ] |
| CTX-01 | Enforce freshness policy (`active/resolved/stale` + `expires_at`) in retrieval paths | Backend | `backend/src/app/services/context_assembler.py`, `backend/src/app/services/mention_context.py`, `backend/src/app/services/warm_context_snapshot.py` | Expired/resolved behavior matches spec | [ ] |
| CTX-02 | Tag assembled context with status/freshness metadata for model interpretation | Backend | `backend/src/app/services/context_assembler.py` | Context trace includes freshness markers | [ ] |
| CTX-03 | Keep deep retrieval limited to explicit entity/context references | Backend | `backend/src/app/chat/orchestrator.py`, `backend/src/app/chat/tool_policy.py` | Smalltalk path has minimal context | [ ] |
| CTX-04 | Add regression tests for small talk (`hi`, `thanks`, `ok`) | Backend | `backend/tests/integration/` | No unnecessary retrieval/tool usage | [ ] |
| LAT-01 | Keep no-mention path to one LLM call | Backend | `backend/src/app/chat/orchestrator.py` | `llm_calls=1` for no-mention turns | [ ] |
| LAT-02 | Remove non-essential sync work before response completion | Backend | `backend/src/app/chat/service.py`, `backend/src/app/services/telemetry_writer.py` | Stage timing reduction confirmed | [ ] |
| LAT-03 | Tighten DB transaction scope for chat core writes | Backend | `backend/src/app/chat/service.py` | `write_ms` and `commit_ms` reduced | [ ] |
| LAT-04 | Ensure targeted invalidation and prewarm only touched scopes | Backend | `backend/src/app/services/entity_cache_coordinator.py` | No global cache churn on local mutations | [ ] |
| UX-01 | Show concise "used references" context chips per answer | Frontend | `frontend/src/app/dashboard/chat/page.tsx`, `frontend/src/services/chat.ts` | Chips visible only when relevant | [ ] |
| UX-01B | Add lightweight "why this was used" detail (reason + source + freshness) on each used-reference chip | Frontend + Backend | `frontend/src/app/dashboard/chat/page.tsx`, `backend/src/app/services/context_assembler.py` | User can inspect reason without seeing internal jargon | [ ] |
| UX-02 | Keep references pane independently scrollable and paginated | Frontend | `frontend/src/app/dashboard/chat/page.tsx` | Page does not grow with pane list | [ ] |
| UX-03 | Enforce truncation with ellipsis and add detail view for long reference text | Frontend | `frontend/src/app/dashboard/chat/page.tsx` | No clipped unreadable cards | [ ] |
| UX-04 | Standardize draft/brief rendering (no markdown artifacts leaking) | Frontend + Backend | `frontend/src/app/dashboard/chat/page.tsx`, `backend/src/app/chat/orchestrator.py` | No raw `**`/format artifacts in UI output | [ ] |
| UX-05 | Archive/restore consistency in inbox and thread intelligence views | Frontend + Backend | `frontend/src/components/inbox/*.tsx`, `backend/src/app/routes/v1/messages.py` | Archive state always reflected correctly | [ ] |
| LCY-01 | Standardize context lifecycle semantics: `active`, `resolved`, `stale`, `expires_at`; map dismiss/delete to resolved UX language | Backend | `backend/src/app/routes/v1/context.py`, `backend/src/app/services/context_assembler.py` | Single lifecycle behavior across all context endpoints | [ ] |
| LCY-02 | Expose context lifecycle actions beyond Diary (chat side pane + any context cards): edit, dismiss, resolve | Frontend | `frontend/src/app/dashboard/chat/page.tsx`, context UI components | Same lifecycle controls available outside Diary | [ ] |
| LCY-03 | Invalidate/prewarm scoped caches on lifecycle mutation (`status`, `expires_at`, `content`) | Backend | `backend/src/app/services/entity_cache_coordinator.py` | No stale reads after lifecycle updates | [ ] |
| LCY-04 | Add lifecycle integration tests across Diary + Chat reference pane + retrieval | QA + Backend | `backend/tests/integration/`, `plans/manual_qa_checklist_main_integration.md` | End-to-end lifecycle flows pass | [ ] |
| OBS-01 | Add structured logs for mention hit/miss and resolution reasons | Backend | `backend/src/app/services/mention_context.py` | Logs include unresolved reason taxonomy | [ ] |
| OBS-02 | Add structured logs for selected/dropped context and tool routing reason | Backend | `backend/src/app/chat/orchestrator.py`, `backend/src/app/services/context_assembler.py` | Trace output complete per turn | [ ] |
| OBS-03 | Add latency dashboards from existing stage logs | Backend | Log pipeline/docs | p50/p95 by turn type available | [ ] |
| QA-01 | Expand manual QA checklist with context-first acceptance cases | QA | `plans/manual_qa_checklist_main_integration.md` | Checklist updated and run | [ ] |
| QA-02 | Add E2E tests for archive + mention archived thread + multi-reference batch | QA + Backend | `backend/tests/integration/`, frontend test notes | Pass on clean DB seed | [ ] |
| RELS-01 | Run 3 consecutive clean validation runs (manual + integration) | QA | QA report | 3/3 pass before release | [ ] |

## Test Matrix (Minimum)

| Test ID | Scenario | Steps | Expected |
|---|---|---|---|
| MNT-01 | Mention known thread | Mention `@thread` in chat | Thread context used; no "content unavailable" |
| MNT-02 | Mention archived thread | Archive thread then mention it | Context still readable and used |
| MNT-03 | Mention unknown entity | Mention non-existent `@name` | Human-safe clarification; no internal error |
| MNT-04 | Multi-entity mention | Mention contact + thread + event in one turn | Relevant scoped context only; no duplication |
| ASM-01 | Smalltalk gate | Send `Hi` | Minimal assembly, no tools |
| ASM-02 | Context-needed turn | Ask past decision with explicit reference | Retrieval triggered with relevant entries |
| EXP-01 | Explainability trust | Inspect used-reference chip detail | Shows human-readable why/source/freshness |
| FMT-01 | Email draft formatting | Request draft response | Clean final formatting, no markdown artifacts |
| FMT-02 | Meeting brief formatting | Request brief via event mention | Structured readable brief, no template leakage |
| LAT-01 | No-mention latency | 20 no-mention turns | p95 <= 2.5s |
| LAT-02 | Mention latency | 20 mention turns | p95 <= 4.5s |
| ARC-01 | Archive from inbox | Archive message in inbox list | Moves to archived view |
| ARC-02 | Restore from thread intelligence | Open archived thread detail and restore | Returns to inbox; action label flips correctly |
| LCY-01 | Dismiss context from chat pane | Dismiss a referenced context card | Entry becomes resolved; retrieval excludes as active |
| LCY-02 | Expiry transition | Set expiry in near future and pass deadline | Entry treated stale with clear freshness label |

## Definition of Done

- All checklist items marked complete.
- Acceptance targets met.
- No P0/P1 defects open.
- QA signoff recorded in `plans/manual_qa_checklist_main_integration.md`.

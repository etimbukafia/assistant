Execution Checklist

1. [done] Create DB migration for new memory model in main backend: add `context_entries` and `entity_references` with status, expires_at, timestamps, indexes, tenant/user scoping.
2. [skipped by decision] Legacy vault backfill bridge. Rationale: legacy vault is being deleted/no longer used, so we avoid migration complexity and use clean cutover.
3. [done] Port playground context services into main: `backend/src/app/services/context_assembler.py`, `backend/src/app/services/mention_context.py`, `backend/src/app/services/warm_context_snapshot.py`, `backend/src/app/services/hot_context_cache.py`.
4. [done] Implement `EntityCacheCoordinator` and central invalidation (`thread_cache`, `calendar_cache`, warm scopes, hot fragments).
5. [mostly done] Route diary/entity mutations through coordinator (`backend/src/app/routes/v1/vault.py`). Remaining review: any non-diary mutation paths that touch thread/event/message/contact memory.
6. [done] Replace mention model with entity mentions (`contact/thread/event/message`) in backend chat + frontend composer.
7. [done] Move chat orchestration to single Gemini function-calling loop with tool rounds, deferred action handling, and continuation flow.
8. [done] Integrate action tools (`draft_email`, `generate_meeting_brief`) with scoped context and multi-action cap behavior.
9. [done] Update backend prompt for tool-use gating and concise responses (`backend/prompts/chat_system.md`).
10. [done] Replace frontend chat UX with command-surface behavior while keeping existing dashboard shell.
11. [done] Replace vault page with create-first diary UX (Remember + linked references + contacts).
12. [done] Update frontend `@` mention composer to new entity suggestion model.
13. [done] Add structured chat/context logging and human-safe errors (sync + async failure paths).
14. [in progress] Run full manual QA sweep and fix regressions. Preflight complete (`compileall`, `tsc`) and checklist prepared at `plans/manual_qa_checklist_main_integration.md`; runtime E2E still required on local machine.
15. [done] Remove deprecated legacy vault/context/chat paths after verification and safe cutover. Removed legacy `memory` route exposure, `vault` mentionable/candidate/promote/prep endpoints, legacy prep tool path, and deleted `app/intelligence/context_builder.py` plus `app/services/vault_context.py`.

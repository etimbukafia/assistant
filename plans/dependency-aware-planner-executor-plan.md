# Dependency-Aware Planner/Executor Plan (DAG + Tool Families + Gating + Approval)

## 1) Objective
- Deliver agent-like multi-action chat behavior with production-grade control.
- Keep behavior deterministic, fast, auditable, and safe.
- Support multi-intent user messages by planning, dependency ordering, and controlled execution.

## 2) Scope and Constraints
- In scope:
  - Structured planning pass that outputs atomic sub-requests.
  - DAG-based execution with dependency-aware ordering.
  - Tool family model and tool gating policy.
  - Unified approval gate for write actions.
  - Task write remains supported.
- Out of scope:
  - Memory write from chat (memory edits happen in app surfaces).
  - Unbounded autonomous loops.

## 3) Core Architecture
1. `IntentClassifier` (lightweight)
- Classifies each incoming message into intent mix and complexity.
- Flags likely trivial/small-talk turns for fast path.

2. `PlanBuilder` (LLM, structured JSON output)
- Converts message into `ExecutionPlan`:
  - `sub_requests[]` (atomic tasks)
  - `nodes[]` (tool/action nodes)
  - `edges[]` (dependencies)
  - `needs_clarification` plus single blocking question (if required)

3. `ToolPolicyEngine`
- Applies family rules and turn-level gating.
- Decides allowed tools per node.

4. `DAGExecutor`
- Topological execution.
- Runs independent read nodes in parallel.
- Runs writes through approval gate.

5. `ApprovalGate`
- Consolidated approval payload for all write nodes in a turn.
- Supports partial approval/rejection.
- Approval is by user text instruction in chat (not button UI).

6. `ResponseComposer`
- Produces one user-facing response from node outputs.
- Human, concise, non-internal phrasing.

## 4) Tool Families
1. `read_context`
- Examples: contact/thread/event/task retrieval, preferences, mentions lookup.
- Side effects: none.
- Default: allowed when relevant.

2. `generate_artifact`
- Examples: email draft, meeting brief.
- Side effects: none.
- Default: allowed when user asks for artifact.

3. `write_task`
- Examples: create/update/close task.
- Side effects: persistent write.
- Default: requires approval gate.

4. `external_action` (future)
- Examples: send email, calendar mutation.
- Side effects: external systems.
- Default: strict approval plus policy checks.

## 5) Gating Rules
1. Turn-level gate
- If small-talk/trivial: disable all tools, direct model reply.
- If no entities and no actionable intent: no tools.
- If explicit action intent: allow only relevant families.

2. Node-level gate
- Each node gets `allowed_tools` from:
  - intent type
  - referenced entities
  - policy constraints
  - user role/permissions

3. Mention is a hint, not a forced tool call
- Mentions increase relevance score.
- Executor still skips tools if the request is answerable without them.

## 6) Structured Plan Contract
```json
{
  "plan_id": "uuid",
  "sub_requests": [
    {"id": "sr1", "intent": "draft_email", "text": "...", "blocking": false}
  ],
  "nodes": [
    {
      "id": "n1",
      "sub_request_id": "sr1",
      "family": "read_context",
      "tool": "get_contact_context",
      "args": {"contact_ref": "@Eti Afia"},
      "depends_on": []
    },
    {
      "id": "n2",
      "sub_request_id": "sr1",
      "family": "generate_artifact",
      "tool": "draft_email",
      "args": {"intent": "confirm user revocation support"},
      "depends_on": ["n1"]
    }
  ],
  "clarification": {
    "needed": false,
    "question": null
  }
}
```

## 7) Ambiguity Policy
- Ask one clarifying question only when execution is blocked.
- If not blocked:
  - pick safest default
  - state assumption briefly in output.
- Example blocked cases:
  - "draft reply to Sarah" with multiple candidate Sarah entities and no clear target.
  - "schedule meeting Monday" without timezone or participants when required for write action.

## 8) DAG Execution Policy
1. Build execution layers from dependencies.
2. Execute read-only nodes in parallel within each layer.
3. Pause before write-family layer and request consolidated approval.
4. Continue only approved nodes; skip rejected nodes with graceful summary.
5. Per-node timeout and retry budget.
6. Per-node failure isolation (one node failure should not kill whole turn).

## 9) Approval Gate Design (Text-Driven)
- Input: all pending write nodes with human summaries.
- Output: approved/rejected node IDs plus optional edits.
- UX:
  - assistant presents numbered actions in one compact message.
  - user approves via text, for example:
    - `proceed`
    - `approve all`
    - `run 1 and 3`
    - `skip 2`
    - `cancel`
- Backend:
  - no write executes without approval token tied to plan/node IDs.
  - add `ApprovalIntentParser` to map text to deterministic decisions:
    - `approve_all`
    - `approve_subset [ids]`
    - `reject_subset [ids]`
    - `cancel_all`
    - `edit_then_approve`
  - if approval text is ambiguous, ask one short follow-up before any write.

## 10) Safety and Security Controls
- SQL safety:
  - parameterized SQL only.
  - CI guard test blocks `text(f"...")` and `execute(f"...")`.
- Tool arg validation:
  - strict schema validation plus sanitization.
- Policy enforcement:
  - deny non-allowed families early.
- Audit trail:
  - persist plan, node decisions, approvals, and tool results.

## 11) Observability
- Metrics:
  - `planner_ms`, `gating_ms`, `executor_ms`, `approval_wait_ms`, `node_success_rate`.
- Logs:
  - `plan_created`, `node_started`, `node_done`, `node_failed`, `approval_requested`, `approval_decision`.
- Traces:
  - correlation IDs from chat turn to plan to node.

## 12) Rollout Plan
1. Phase 1: Read-only DAG
- Enable planner and DAG for read/generate families only.
- Keep write actions on current path.

2. Phase 2: Write-task approval
- Route `write_task` via approval gate.
- Enable text-based approval flow in chat (no button dependency).

3. Phase 3: Optimization and hardening
- Parallel read layers.
- Better ambiguity defaults.
- Failure/retry tuning.

## 13) Test Plan
- Unit:
  - plan schema validation
  - DAG cycle detection
  - gating allow/deny matrix
  - approval token enforcement
  - approval-intent parsing from natural-language user replies
- Integration:
  - mixed message with 6+ actions plus trivial question
  - partial approval flow
  - text approvals: approve all, subset, cancel, ambiguous input
  - dependency failures with graceful output
- Security:
  - SQL interpolation guard tests
  - tool-arg validation tests

## 14) Immediate Next Steps
1. Add `ExecutionPlan` and `PlanNode` schemas.
2. Implement `ToolPolicyEngine` with family matrix.
3. Add planner output parser/validator.
4. Implement DAG executor (read parallel plus write approval pause).
5. Wire text-based approval flow in chat (no button approval UI).

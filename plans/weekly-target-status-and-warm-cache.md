# Plan: Weekly Target Status + Focus in Warm Cache

## Context

The weekly target ("What's your target this week?") has two problems:
1. **No completion tracking** — it's just text with no way to mark it done/missed. That status is useful data for the assistant and the user.
2. **Invisible to the chat AI** — the assistant can't reference it when answering priority/planning questions like "What should I focus on?"

### Design Decisions

**Warm cache (signal layer)** — inject weekly target + today's open goals as synthetic items in the profile snapshot. Always present in structured context. Costs ~30-40 tokens. Covers 90% of planning-related questions without tool calls or added latency.

**Type: `"commitment"`** — chosen because `_select_structured_items()` selects by type priority: `["preferences", "commitment", "decision", "relationships", "insight"]`. A weekly target is semantically a self-commitment. With `importance_level: "high"` it also lands in `critical_items` (selected first), guaranteeing inclusion.

---

## Changes

### 1. Migration — `backend/migrations/041_add_weekly_target_status.sql` (NEW)

```sql
ALTER TABLE daily_focus
    ADD COLUMN IF NOT EXISTS weekly_target_status TEXT DEFAULT 'active';

ALTER TABLE daily_focus
    ADD CONSTRAINT ck_daily_focus_weekly_target_status
    CHECK (weekly_target_status IN ('active', 'completed', 'missed'));
```

No new RLS needed — table already has row-level security from migration 031.

### 2. Model — `backend/src/app/data/models.py` (~line 361)

Add after `weekly_target`:
```python
weekly_target_status = Column(Text, default="active")
```

### 3. Schemas — `backend/src/app/data/schemas.py` (~lines 964-996)

- `DailyFocusResponse`: add `weekly_target_status: Optional[str] = "active"`
- `DailyFocusUpdateRequest`: add `weekly_target_status: Optional[str] = None`
- `WeeklySummaryResponse`: add `weekly_target_status: Optional[str] = None`

### 4. Routes — `backend/src/app/routes/v1/focus.py`

- `_to_response()`: add `weekly_target_status=row.weekly_target_status`
- `update_daily_focus()`:
  - Validate status value ("active"/"completed"/"missed")
  - Propagate across ISO week (same pattern as `weekly_target` propagation)
  - Auto-set to "active" when a new `weekly_target` text is set
- `get_weekly_summary()`: add `weekly_target_status` from first row to response

### 5. Warm Cache Injection — `backend/src/app/services/warm_context_snapshot.py`

Add `_build_focus_items(db, user_id)` → queries today's `DailyFocus` → returns synthetic snapshot items:

- **Weekly target** → `type: "commitment"`, `importance_level: "high"`, content: `"Weekly target (active): Close Q1 planning"`
- **Today's open goals** → `type: "commitment"`, `importance_level: "normal"`, content: `"Today's open goals: Review deck; Send update"`

Modify `build_profile_snapshot()` to call `_build_focus_items()` and pass results as `extra_items` to `_build_snapshot()`.

Modify `_build_snapshot()` signature to accept optional `extra_items: List[Dict]` and bucket them alongside ORM rows.

### 6. Frontend Types — `frontend/src/services/focus.ts`

Add `weekly_target_status: "active" | "completed" | "missed" | null` to `DailyFocus`, `DailyFocusUpdate`, and `WeeklySummary` interfaces.

### 7. Frontend Component — `frontend/src/components/focus/WeeklyTargetInput.tsx`

- Accept new props: `status` and `onStatusChange`
- Add toggle button (checkmark circle) to the right of the input
- Click: active → completed
- Visual: completed = strikethrough + green check; active = normal styling

### 8. Frontend Page — `frontend/src/app/dashboard/focus/page.tsx`

Wire `handleUpdateWeeklyTargetStatus` callback, pass `status` and `onStatusChange` to `WeeklyTargetInput`.

---

## File List

| File | Action |
|------|--------|
| `backend/migrations/041_add_weekly_target_status.sql` | NEW |
| `backend/src/app/data/models.py` | Edit (1 line) |
| `backend/src/app/data/schemas.py` | Edit (3 fields) |
| `backend/src/app/routes/v1/focus.py` | Edit (status handling + response) |
| `backend/src/app/services/warm_context_snapshot.py` | Edit (focus injection) |
| `frontend/src/services/focus.ts` | Edit (types) |
| `frontend/src/components/focus/WeeklyTargetInput.tsx` | Edit (status UI) |
| `frontend/src/app/dashboard/focus/page.tsx` | Edit (wire callback) |

## Implementation Order

1. Migration → Model → Schemas (foundation)
2. Routes (API works end-to-end)
3. Warm cache injection (AI gains visibility)
4. Frontend types → Component → Page (UI)

## Verification

- Set weekly target → confirm persists on refresh
- Mark as completed → verify status propagates across week via `GET /focus/weekly-summary`
- Chat: ask "What should I focus on?" → confirm assistant references the weekly target
- Check warm cache logs for focus items in structured context trace

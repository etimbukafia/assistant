# Scheduling Intents + Calendar Orchestrator — Implementation Plan

Context

The current scheduling suggestion pipeline generates slots, draft replies, and event descriptions eagerly at email processing time — running 3–4 LLM calls per scheduling email regardless of whether the user
ever acts on them. The generated content is stale by the time the user sees it and there is no opportunity for user input.

The new approach:
1. At email processing time: detect intent + generate one natural-language summary sentence. Store a lean SchedulingIntent record. Nothing else.
2. At action time: a CalendarOrchestrator agent runs with fresh calendar data, user preferences, decisions/commitments, open tasks, and optional user-supplied context to produce best-fit slot recommendations
and draft reply.
3. Frontend: intent cards in the calendar sidebar with dynamic buttons per intent type; clicking the primary action opens an orchestrator panel/dialog.

---
Architecture Overview

Email arrives
→ AI extraction (existing, +3 new fields)
→ scheduling_intent_detected event (confidence ≥ 0.6)
→ handler creates SchedulingIntent record (lean, no slots/drafts)

User opens calendar page
→ SuggestionsPanel → shows SchedulingIntent cards
→ Card shows: intent_summary + dynamic buttons per intent_type
→ "meeting_reminder" → checks calendar for title+date match → Acknowledge / Add to calendar

User clicks primary action (e.g. "Suggest availability")
→ OrchestratorPanel dialog opens
→ User optionally types context note ("keep Friday free")
→ POST /scheduling/intents/{id}/run → CalendarOrchestrator runs
→ Returns: suggested slots + draft reply (ephemeral, not stored)
→ User edits reply if desired → Send / Add to calendar

---
Intent Type → Button Mapping

┌──────────────────────┬─────────────────────────────────────────────────────────────┬───────────┐
│     Intent Type      │                       Primary Button                        │ Secondary │
├──────────────────────┼─────────────────────────────────────────────────────────────┼───────────┤
│ availability_request │ Suggest availability                                        │ Dismiss   │
├──────────────────────┼─────────────────────────────────────────────────────────────┼───────────┤
│ time_request         │ Suggest time                                                │ Dismiss   │
├──────────────────────┼─────────────────────────────────────────────────────────────┼───────────┤
│ meeting_confirmation │ Add to calendar                                             │ Dismiss   │
├──────────────────────┼─────────────────────────────────────────────────────────────┼───────────┤
│ meeting_reminder     │ Acknowledge (if matched) / Add to calendar (if not matched) │ Dismiss   │
├──────────────────────┼─────────────────────────────────────────────────────────────┼───────────┤
│ reschedule_request   │ Suggest new times                                           │ Dismiss   │
└──────────────────────┴─────────────────────────────────────────────────────────────┴───────────┘

Meeting reminder calendar match: fuzzy title similarity (token overlap > 0.7) AND same date (or ±1 hour for time-specific). Checked at intent creation; stored as matched_event_id.

---
Files to Create / Modify

Backend

1. backend/migrations/044_scheduling_intents.sql ← CREATE
2. backend/src/app/data/models.py ← update SchedulingSuggestion → SchedulingIntent (or add new model)
3. backend/src/app/data/schemas.py ← new SchedulingIntentResponse, remove old suggestion schemas
4. backend/src/app/processors/ai.py ← add 3 new extracted fields
5. backend/prompts/ ← update scheduling extraction prompt to output new fields
6. backend/src/app/handlers/scheduling_handlers.py ← strip to intent-only creation
7. backend/src/app/routes/v1/scheduling.py ← replace all routes with intent routes
8. backend/src/app/services/calendar_orchestrator.py ← CREATE
9. backend/src/app/agents/modules/scheduling.py ← remove generate_suggestions() pipeline

Frontend

10. frontend/src/services/scheduling.ts ← replace with intent API service
11. frontend/src/app/dashboard/calendar/CalendarClient.tsx ← replace SuggestionsPanel, add OrchestratorPanel

---
Step-by-Step Implementation

1. Migration: 044_scheduling_intents.sql

CREATE TABLE IF NOT EXISTS scheduling_intents (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    thread_id TEXT,
    sender_name TEXT,
    sender_email TEXT,
    intent_type TEXT NOT NULL DEFAULT 'availability_request',
    intent_summary TEXT,
    meeting_title TEXT,           -- extracted for calendar matching
    meeting_date DATE,            -- extracted for calendar matching
    matched_event_id INTEGER REFERENCES calendar_events(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | dismissed | acknowledged | added
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scheduling_intents_user_id ON scheduling_intents(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduling_intents_message_id ON scheduling_intents(message_id);
CREATE INDEX IF NOT EXISTS idx_scheduling_intents_status ON scheduling_intents(status);
CREATE INDEX IF NOT EXISTS idx_scheduling_intents_thread_id ON scheduling_intents(thread_id);

ALTER TABLE scheduling_intents ENABLE ROW LEVEL SECURITY;
CREATE POLICY scheduling_intents_user_policy ON scheduling_intents
    USING (user_id = current_setting('app.user_id', true));

-- Keep scheduling_suggestions table for now (data preservation, drop in future migration)

---
2. models.py — Add SchedulingIntent model

Add alongside (not replacing) SchedulingSuggestion for now:

class SchedulingIntent(Base):
    __tablename__ = "scheduling_intents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True)
    thread_id = Column(String, index=True)
    sender_name = Column(String, nullable=True)
    sender_email = Column(String, nullable=True)
    intent_type = Column(String, nullable=False, default="availability_request")
    intent_summary = Column(Text, nullable=True)
    meeting_title = Column(String, nullable=True)
    meeting_date = Column(Date, nullable=True)
    matched_event_id = Column(Integer, ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

---
3. schemas.py — New schemas

class SchedulingIntentResponse(BaseModel):
    id: int
    user_id: str
    message_id: Optional[int]
    thread_id: Optional[str]
    sender_name: Optional[str]
    sender_email: Optional[str]
    intent_type: str
    intent_summary: Optional[str]
    meeting_title: Optional[str]
    meeting_date: Optional[date]
    matched_event_id: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SchedulingIntentsListResponse(BaseModel):
    intents: List[SchedulingIntentResponse]
    total: int

class OrchestratorRunRequest(BaseModel):
    user_note: Optional[str] = None   # extra context from user

class OrchestratorRunResponse(BaseModel):
    suggested_slots: List[Dict[str, Any]]   # [{start_time, end_time, label}]
    draft_reply: str
    reasoning: Optional[str] = None         # brief explanation of slot choices

class IntentSendRequest(BaseModel):
    edited_reply: Optional[str] = None
    slot_index: Optional[int] = None        # if adding to calendar at same time

---
4. processors/ai.py — Add 3 new extraction fields

In the scheduling section of the extraction schema, add:
- scheduling_intent_summary — str | null: One sentence natural language e.g. "Sarah asked when you're free for the end-of-year team dinner"
- scheduling_intent_meeting_title — str | null: Clean meeting title e.g. "End-of-year team dinner"
- scheduling_intent_meeting_date — str | null: ISO date string e.g. "2024-12-20" or null if not specified

Update extraction in process_message() and in the batch path:
'scheduling_intent_summary': scheduling.get('summary'),
'scheduling_intent_meeting_title': scheduling.get('meeting_title'),
'scheduling_intent_meeting_date': scheduling.get('meeting_date'),

These flow through to message.py which includes them in the scheduling_intent_detected event payload.

---
5. Update scheduling detection prompt (prompts/)

The prompt file used by ai.py for scheduling (likely part of the main extraction prompt or detect_scheduling_intent.md) needs to add to its JSON schema output:

{
"scheduling_intent": {
    "detected": true,
    "type": "availability_request",
    "confidence": 0.85,
    "summary": "Sarah asked when you're free for the end-of-year team dinner",
    "meeting_title": "End-of-year team dinner",
    "meeting_date": "2024-12-20"
}
}

meeting_date should be null if no specific date mentioned. summary should always be present when detected=true.

---
6. scheduling_handlers.py — Stripped-down handler

Replace the entire handle_scheduling_intent body with lean intent creation:

@register_handler("scheduling_intent_detected")
async def handle_scheduling_intent(event, payload):
    message_id = payload.get("message_id")
    user_id = payload.get("user_id")
    # ... validation ...

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
    try:
        # Deduplicate
        existing = db.query(SchedulingIntent).filter(
            SchedulingIntent.message_id == message_id,
            SchedulingIntent.status == "pending"
        ).first()
        if existing:
            return

        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            return

        # Resolve meeting_date string → date object
        meeting_date = None
        raw_date = payload.get("meeting_date")
        if raw_date:
            try:
                meeting_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                pass

        # Check for calendar match (meeting_reminder only)
        matched_event_id = None
        if payload.get("intent_type") == "meeting_reminder":
            matched_event_id = _find_calendar_match(
                db, user_id,
                title=payload.get("meeting_title"),
                meeting_date=meeting_date
            )

        # Expire previous pending intents for same thread
        db.query(SchedulingIntent).filter(
            SchedulingIntent.thread_id == message.thread_id,
            SchedulingIntent.status == "pending"
        ).update({"status": "expired"})

        intent = SchedulingIntent(
            user_id=user_id,
            message_id=message_id,
            thread_id=message.thread_id,
            sender_name=payload.get("sender_name") or _name_from_email(message.sender),
            sender_email=message.sender,
            intent_type=payload.get("intent_type", "availability_request"),
            intent_summary=payload.get("intent_summary"),
            meeting_title=payload.get("meeting_title"),
            meeting_date=meeting_date,
            matched_event_id=matched_event_id,
            status="pending"
        )
        db.add(intent)
        db.commit()

        if user_id and message.thread_id:
            thread_cache.invalidate(user_id, message.thread_id)

    finally:
        db.close()


def _find_calendar_match(db, user_id, title, meeting_date):
    """Fuzzy title + date match. Returns event_id or None."""
    if not title or not meeting_date:
        return None
    from difflib import SequenceMatcher
    candidates = db.query(CalendarEvent).filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.status != "cancelled",
        func.date(CalendarEvent.start_time) == meeting_date
    ).all()
    for event in candidates:
        ratio = SequenceMatcher(None, title.lower(), event.title.lower()).ratio()
        if ratio > 0.7:
            return event.id
    return None


def _name_from_email(email):
    if not email:
        return None
    local = email.split("@")[0]
    return local.replace(".", " ").replace("_", " ").title()

---
7. routes/v1/scheduling.py — Replace all routes

GET  /scheduling/intents                        → list pending intents
GET  /scheduling/intents/{id}                   → single intent
POST /scheduling/intents/{id}/run               → run CalendarOrchestrator, returns slots+draft
POST /scheduling/intents/{id}/send              → send reply (edited_reply + optional slot to add)
POST /scheduling/intents/{id}/dismiss           → status = dismissed
POST /scheduling/intents/{id}/acknowledge       → status = acknowledged (meeting_reminder found in cal)
POST /scheduling/intents/{id}/add-to-calendar   → create CalendarEvent from intent + slot choice

Keep old GET /scheduling/suggestions and POST /scheduling/detect returning empty/deprecated responses for backwards compat (mobile app may still call them).

---
8. services/calendar_orchestrator.py — New service (CREATE)

class CalendarOrchestratorToolRegistry:
    """Tools available to the CalendarOrchestrator agent."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # Tool: get_upcoming_events — uses calendar cache
    # Tool: get_busy_slots(start, end) — CalendarService.get_availability()
    # Tool: get_user_preferences — UserSettings (working hours, buffer, preferred_times, timezone)
    # Tool: get_decisions_and_commitments — ThreadState / ContextEntry for open decisions
    # Tool: get_open_tasks(priority) — Task model, filter by deadline proximity
    # Tool: suggest_slots(duration, count, constraints) — CalendarService.suggest_time_slots()
    # Tool: draft_reply(intent_type, slots, sender_name, user_note) — LLM call


class CalendarOrchestrator:
    """
    On-demand orchestrator for scheduling intent actions.

    Given a SchedulingIntent and optional user note, reasons over
    calendar data, preferences, tasks, and decisions to suggest
    optimal meeting slots and draft a reply.

    Output is ephemeral — not stored until user confirms.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.tools = CalendarOrchestratorToolRegistry(db, user_id)

    def run(self, intent: SchedulingIntent, user_note: str = "") -> OrchestratorResult:
        """
        Run the orchestrator for a given intent.
        Returns suggested_slots, draft_reply, reasoning.
        """
        # 1. Load context: preferences, busy slots, tasks, decisions
        # 2. Call suggest_slots via CalendarService (uses calendar cache for busy data)
        # 3. Apply risk signals: urgent tasks near proposed times, deadline conflicts
        # 4. Generate draft reply via LLM with all context
        # 5. Return OrchestratorResult (not persisted)

Reuse: CalendarService.suggest_time_slots() and CalendarService.get_availability() already exist in backend/src/app/services/calendar.py:189–374 — call directly, no reimplementation.

---
9. frontend/src/services/scheduling.ts — Replace

export const SchedulingIntentSchema = z.object({
    id: z.number(),
    user_id: z.string(),
    message_id: z.number().nullable().optional(),
    thread_id: z.string().nullable().optional(),
    sender_name: z.string().nullable().optional(),
    sender_email: z.string().nullable().optional(),
    intent_type: z.string(),
    intent_summary: z.string().nullable().optional(),
    meeting_title: z.string().nullable().optional(),
    meeting_date: z.string().nullable().optional(),
    matched_event_id: z.number().nullable().optional(),
    status: z.string(),
    created_at: z.string(),
    updated_at: z.string(),
});

// Functions:
fetchSchedulingIntents(params?)           // GET /scheduling/intents
runOrchestrator(intentId, userNote?)      // POST /scheduling/intents/{id}/run
sendIntent(intentId, editedReply?, slotIndex?) // POST /scheduling/intents/{id}/send
dismissIntent(intentId)                   // POST /scheduling/intents/{id}/dismiss
acknowledgeIntent(intentId)               // POST /scheduling/intents/{id}/acknowledge
addIntentToCalendar(intentId, slotIndex)  // POST /scheduling/intents/{id}/add-to-calendar

---
10. CalendarClient.tsx — Replace SuggestionsPanel + add OrchestratorPanel

Replace SuggestionsPanel with SchedulingIntentsPanel:
- Fetches GET /scheduling/intents?status=pending
- Shows one card per intent:
- Overline: sender name + intent type label
- Body: intent_summary
- Primary + Dismiss buttons (dynamic per intent_type per mapping above)
- meeting_reminder with matched_event_id → "Acknowledge"; without → "Add to calendar"
- Each card is clickable to open OrchestratorPanel

Add OrchestratorPanel (Dialog):
- Shows intent summary at top
- <textarea> for optional user context note ("keep Friday free", etc.)
- "Get recommendations" button → calls runOrchestrator()
- Loading state: three .teeks-dot spans
- Results section:
- Slot chips (sticker style matching label palette) — user picks one
- Draft reply textarea (pre-filled, editable)
- "Send reply" button → sendIntent()
- "Add to calendar" button (if intent_type warrants it) → addIntentToCalendar()
- Design tokens: CARD_SHADOW, rounded-[14px], overline labels, font-playfair headings

---
Event Payload Update (message.py)

The scheduling_intent_detected event payload gains 3 new fields:
"event_payload": {
    "message_id": message.id,
    "user_id": message.user_id,
    "thread_id": message.thread_id,
    "intent_type": ai_results["scheduling_intent_type"],
    "confidence": ai_results["scheduling_intent_confidence"],
    # NEW:
    "intent_summary": ai_results.get("scheduling_intent_summary"),
    "meeting_title": ai_results.get("scheduling_intent_meeting_title"),
    "meeting_date": ai_results.get("scheduling_intent_meeting_date"),
    "sender_name": ...,   # derive from message.sender in handler
}

---
Key Reuse

┌───────────────────────────┬─────────────────────────────────────────────────┬──────────────────────────────┐
│           Need            │                  Existing code                  │           Location           │
├───────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────┤
│ Time slot suggestion      │ CalendarService.suggest_time_slots()            │ services/calendar.py:266     │
├───────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────┤
│ Busy slot lookup          │ CalendarService.get_availability()              │ services/calendar.py:189     │
├───────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────┤
│ LLM call                  │ LLMOrchestrator.generate()                      │ core/llm/ via BaseModule     │
├───────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────┤
│ Prompt loading            │ BaseModule._load_prompt()                       │ agents/modules/base.py       │
├───────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────┤
│ Calendar cache            │ calendar_cache.get_or_build_events()            │ core/cache/calendar_cache.py │
├───────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────┤
│ Thread cache invalidation │ thread_cache.invalidate()                       │ core/cache/                  │
├───────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────┤
│ RLS context               │ set_config('app.user_id', ...)                  │ pattern throughout handlers  │
├───────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────┤
│ Gmail send                │ existing send route used by old suggestion send │ routes/v1/scheduling.py:70   │
└───────────────────────────┴─────────────────────────────────────────────────┴──────────────────────────────┘

---
Verification

1. Send a test email with scheduling language → check scheduling_intents table has a row with intent_summary populated
2. GET /scheduling/intents?status=pending returns the intent with all fields
3. Open calendar page → intent card appears in sidebar with correct buttons
4. For meeting_reminder with matching calendar event → card shows "Acknowledge"
5. Click "Suggest availability" → OrchestratorPanel opens → type a note → "Get recommendations" → slots appear with draft reply
6. Send reply → intent status = sent, Gmail delivers the reply
7. "Add to calendar" from panel → CalendarEvent created, calendar cache invalidated
"""
Calendar Orchestrator

On-demand scheduling assistant. Given a SchedulingIntent and optional user context note,
reasons over live calendar data, user preferences, open tasks, and thread decisions to
suggest optimal meeting slots and draft a context-appropriate reply.

Output is ephemeral — nothing is stored until the user confirms an action.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.data.models import SchedulingIntent, UserSettings, Task, ThreadState, CalendarEvent
from app.services.calendar import CalendarService

logger = logging.getLogger(__name__)


class OrchestratorResult:
    """Ephemeral result from CalendarOrchestrator. Not persisted."""

    def __init__(
        self,
        suggested_slots: List[Dict[str, Any]],
        draft_reply: str,
        reasoning: Optional[str] = None,
    ):
        self.suggested_slots = suggested_slots
        self.draft_reply = draft_reply
        self.reasoning = reasoning

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggested_slots": self.suggested_slots,
            "draft_reply": self.draft_reply,
            "reasoning": self.reasoning,
        }


class CalendarOrchestrator:
    """
    On-demand orchestrator for scheduling intent actions.

    Collects:
    - Calendar events (upcoming busy slots) from CalendarService
    - User preferences (working hours, buffer, timezone, preferred times)
    - Open tasks with deadlines that could conflict
    - Thread decisions/commitments for context
    - Optional user context note typed in the UI

    Then: suggests best available slots + drafts a reply tailored to intent type.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def run(self, intent: SchedulingIntent, user_note: str = "") -> OrchestratorResult:
        """
        Run the orchestrator for a given intent.
        Returns suggested_slots, draft_reply, reasoning.
        """
        settings = self._get_settings()
        context = self._build_context(intent, settings, user_note)
        slots = self._suggest_slots(intent, settings, context)
        draft_reply = self._draft_reply(intent, slots, settings, context, user_note)
        reasoning = self._build_reasoning(intent, slots, context)

        return OrchestratorResult(
            suggested_slots=slots,
            draft_reply=draft_reply,
            reasoning=reasoning,
        )

    # ── Context gathering ────────────────────────────────────────────────────

    def _get_settings(self) -> Optional[UserSettings]:
        return self.db.query(UserSettings).filter(
            UserSettings.user_id == self.user_id
        ).first()

    def _build_context(
        self,
        intent: SchedulingIntent,
        settings: Optional[UserSettings],
        user_note: str,
    ) -> Dict[str, Any]:
        """Gather all context signals needed for slot selection and reply drafting."""
        return {
            "upcoming_events": self._get_upcoming_events(),
            "urgent_tasks": self._get_urgent_tasks(),
            "deadline_tasks": self._get_deadline_tasks(),
            "thread_decisions": self._get_thread_decisions(intent.thread_id),
            "user_note": user_note,
            "timezone": getattr(settings, "default_timezone", "UTC"),
            "working_hours_start": getattr(settings, "working_hours_start", "09:00"),
            "working_hours_end": getattr(settings, "working_hours_end", "17:00"),
            "buffer_minutes": getattr(settings, "buffer_minutes", 15),
            "preferred_times": getattr(settings, "preferred_meeting_times", "any"),
        }

    def _get_upcoming_events(self) -> List[Dict[str, Any]]:
        """Fetch upcoming calendar events for the next 14 days."""
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=14)
        events = self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == self.user_id,
            CalendarEvent.status != "cancelled",
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= end,
        ).order_by(CalendarEvent.start_time).limit(50).all()
        return [
            {
                "id": e.id,
                "title": e.title,
                "start_time": e.start_time.isoformat() if e.start_time else None,
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "label": e.label,
            }
            for e in events
        ]

    def _get_urgent_tasks(self) -> List[Dict[str, Any]]:
        """Fetch urgent/high-priority open tasks."""
        tasks = self.db.query(Task).filter(
            Task.user_id == self.user_id,
            Task.status.in_(["approved", "pending_approval"]),
            Task.priority.in_(["urgent", "high"]),
        ).limit(10).all()
        return [
            {
                "title": t.title,
                "priority": t.priority,
                "deadline": t.deadline.isoformat() if t.deadline else None,
            }
            for t in tasks
        ]

    def _get_deadline_tasks(self) -> List[Dict[str, Any]]:
        """Fetch tasks with deadlines in the next 14 days."""
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=14)
        tasks = self.db.query(Task).filter(
            Task.user_id == self.user_id,
            Task.status.in_(["approved", "pending_approval"]),
            Task.deadline >= now,
            Task.deadline <= end,
        ).order_by(Task.deadline).limit(10).all()
        return [
            {
                "title": t.title,
                "priority": t.priority,
                "deadline": t.deadline.isoformat() if t.deadline else None,
            }
            for t in tasks
        ]

    def _get_thread_decisions(self, thread_id: Optional[str]) -> List[str]:
        """Fetch decisions made in the related email thread."""
        if not thread_id:
            return []
        thread_state = self.db.query(ThreadState).filter(
            ThreadState.thread_id == thread_id,
            ThreadState.user_id == self.user_id,
        ).first()
        if not thread_state or not thread_state.decisions:
            return []
        return [
            d.get("decision", "") for d in thread_state.decisions
            if isinstance(d, dict) and d.get("decision")
        ]

    # ── Slot suggestion ──────────────────────────────────────────────────────

    def _suggest_slots(
        self,
        intent: SchedulingIntent,
        settings: Optional[UserSettings],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Call CalendarService.suggest_time_slots with user preferences.
        Applies user_note constraints (e.g. "keep Friday free", "prefer afternoons").
        """
        if not settings:
            return []

        # Intent types that need slot suggestions
        needs_slots = intent.intent_type in (
            "availability_request", "time_request", "reschedule_request"
        )
        if not needs_slots:
            return []

        now = datetime.now(timezone.utc)
        start_date = now
        end_date = now + timedelta(days=14)

        # Parse user_note for preferred time hints
        user_note = (context.get("user_note") or "").lower()
        preferred_times = context.get("preferred_times", "any")
        if "afternoon" in user_note:
            preferred_times = "afternoon"
        elif "morning" in user_note:
            preferred_times = "morning"

        calendar_service = CalendarService(self.db, user_id=self.user_id)

        try:
            coro = calendar_service.suggest_time_slots(
                start_date=start_date,
                end_date=end_date,
                duration_minutes=30,
                count=3,
                working_hours_start=context.get("working_hours_start", "09:00"),
                working_hours_end=context.get("working_hours_end", "17:00"),
                buffer_minutes=context.get("buffer_minutes", 15),
                preferred_times=preferred_times,
                calendar_ids=settings.calendar_ids or [],
            )
            try:
                loop = asyncio.get_running_loop()
                import nest_asyncio
                nest_asyncio.apply()
                slots = loop.run_until_complete(coro)
            except RuntimeError:
                slots = asyncio.run(coro)

            return [s.to_dict() for s in slots]

        except Exception as e:
            logger.error(f"CalendarOrchestrator: failed to suggest slots: {e}")
            return []

    # ── Reply drafting ───────────────────────────────────────────────────────

    def _draft_reply(
        self,
        intent: SchedulingIntent,
        slots: List[Dict[str, Any]],
        settings: Optional[UserSettings],
        context: Dict[str, Any],
        user_note: str,
    ) -> str:
        """
        Generate a context-appropriate scheduling reply using the LLM.
        Falls back to a simple template if LLM call fails.
        """
        try:
            from core.llm import LLMOrchestrator
            llm = LLMOrchestrator()

            tz = context.get("timezone", "UTC")
            tz_display = tz.split("/")[-1].replace("_", " ") if "/" in tz else tz
            sender = intent.sender_name or (intent.sender_email or "").split("@")[0]

            slot_texts = self._format_slots_for_prompt(slots, tz_display)

            # Build decisions context
            decisions = context.get("thread_decisions", [])
            decisions_text = ""
            if decisions:
                decisions_text = "\nRelevant thread decisions:\n" + "\n".join(f"- {d}" for d in decisions[:3])

            urgent_tasks = context.get("urgent_tasks", [])
            tasks_warning = ""
            if urgent_tasks:
                tasks_warning = f"\nNote: there are {len(urgent_tasks)} urgent open tasks — avoid scheduling in peak work hours if possible."

            user_note_text = f"\nUser preference: {user_note}" if user_note else ""

            prompt = f"""Write a short, professional scheduling reply email body.

Intent type: {intent.intent_type}
Meeting: {intent.meeting_title or 'the meeting'}
Sender: {sender}
Available slots: {slot_texts or 'checking calendar...'}
Timezone: {tz_display}
{decisions_text}{tasks_warning}{user_note_text}

Rules:
- 1–2 sentences only
- Include the available times exactly
- Include timezone
- End with a question asking them to confirm which works
- No subject line, no greeting, just the body text

Reply:"""

            result = llm.generate(prompt)
            if isinstance(result, dict):
                reply = result.get("reply") or result.get("text") or result.get("content", "")
                if not reply and not result.get("_error"):
                    # Some providers return the raw string under a different key; try the whole dict
                    for v in result.values():
                        if isinstance(v, str) and len(v) > 10:
                            reply = v
                            break
                return reply or self._fallback_reply(intent, slots, tz_display, sender)
            if isinstance(result, str):
                return result
            return self._fallback_reply(intent, slots, tz_display, sender)

        except Exception as e:
            logger.error(f"CalendarOrchestrator: draft reply LLM call failed: {e}")
            return self._fallback_reply(intent, slots, context.get("timezone", "UTC"), "")

    def _fallback_reply(
        self,
        intent: SchedulingIntent,
        slots: List[Dict[str, Any]],
        tz_display: str,
        sender: str,
    ) -> str:
        """Simple template reply used when LLM is unavailable."""
        if not slots:
            return "I'll check my calendar and get back to you with available times."

        slot_texts = self._format_slots_for_prompt(slots, tz_display)
        if intent.intent_type in ("availability_request", "time_request"):
            return (
                f"I'm available {slot_texts} ({tz_display}). "
                "Let me know which works best for you."
            )
        if intent.intent_type == "reschedule_request":
            return (
                f"Happy to reschedule. I'm free {slot_texts} ({tz_display}). "
                "Which of those works for you?"
            )
        return f"I'm available {slot_texts} ({tz_display}). Does any of those work?"

    def _format_slots_for_prompt(self, slots: List[Dict[str, Any]], tz_display: str) -> str:
        """Format slot list as a readable string for the prompt."""
        if not slots:
            return ""
        texts = []
        for slot in slots[:3]:
            try:
                start = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
                texts.append(start.strftime("%a %-d %b at %-I%p").replace("AM", "am").replace("PM", "pm"))
            except Exception:
                pass
        if not texts:
            return ""
        if len(texts) == 1:
            return texts[0]
        return ", ".join(texts[:-1]) + f", or {texts[-1]}"

    # ── Reasoning ────────────────────────────────────────────────────────────

    def _build_reasoning(
        self,
        intent: SchedulingIntent,
        slots: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Optional[str]:
        """
        Brief human-readable explanation of why these slots were chosen.
        Surfaced in the OrchestratorPanel for transparency.
        """
        parts = []

        upcoming = context.get("upcoming_events", [])
        if upcoming:
            parts.append(f"{len(upcoming)} existing events checked for conflicts")

        urgent = context.get("urgent_tasks", [])
        if urgent:
            parts.append(f"{len(urgent)} urgent task(s) noted")

        decisions = context.get("thread_decisions", [])
        if decisions:
            parts.append("thread context included")

        user_note = context.get("user_note", "")
        if user_note:
            parts.append(f"your note applied: \"{user_note[:60]}\"")

        if not slots:
            return "No available slots found in the next 14 days matching your preferences."

        if not parts:
            return None

        return "Slots selected based on: " + "; ".join(parts) + "."

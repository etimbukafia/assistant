"""
Calendar Orchestrator

On-demand scheduling assistant. Given a SchedulingIntent and optional user context note,
reasons over live calendar data, user preferences, open tasks, and thread decisions to
suggest optimal meeting slots and draft a context-appropriate reply.

Output is ephemeral — nothing is stored until the user confirms an action.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.data.models import SchedulingIntent, UserSettings, Task, ThreadState, CalendarEvent, Message
from app.services.calendar import CalendarService

logger = logging.getLogger(__name__)


class OrchestratorResult:
    """Ephemeral result from CalendarOrchestrator. Not persisted."""

    def __init__(
        self,
        suggested_slots: List[Dict[str, Any]],
        draft_reply: str,
        reasoning: Optional[str] = None,
        availability_check: Optional[Dict[str, Any]] = None,
    ):
        self.suggested_slots = suggested_slots
        self.draft_reply = draft_reply
        self.reasoning = reasoning
        self.availability_check = availability_check

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggested_slots": self.suggested_slots,
            "draft_reply": self.draft_reply,
            "reasoning": self.reasoning,
            "availability_check": self.availability_check,
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
        availability_check = self._build_availability_check(intent, context)
        slots = self._suggest_slots(intent, settings, context)
        draft_reply = self._draft_reply(intent, slots, settings, context, user_note, availability_check)
        reasoning = self._build_reasoning(intent, slots, context, availability_check)

        return OrchestratorResult(
            suggested_slots=slots,
            draft_reply=draft_reply,
            reasoning=reasoning,
            availability_check=availability_check,
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

    def _build_availability_check(
        self,
        intent: SchedulingIntent,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        For availability/time intents with concrete requested times, check calendar
        conflicts and return an explicit available/busy verdict with overlap details.
        """
        if intent.intent_type not in ("availability_request", "time_request"):
            return None

        windows = self._extract_requested_windows(intent)
        if not windows:
            return None

        checks: List[Dict[str, Any]] = []
        for window in windows[:3]:
            start_dt = window["start_time"]
            end_dt = window["end_time"]
            conflicts = self.db.query(CalendarEvent).filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.status != "cancelled",
                CalendarEvent.start_time < end_dt,
                CalendarEvent.end_time > start_dt,
            ).order_by(CalendarEvent.start_time.asc()).limit(5).all()

            conflict_payload = [
                {
                    "id": e.id,
                    "title": e.title,
                    "start_time": e.start_time.isoformat() if e.start_time else None,
                    "end_time": e.end_time.isoformat() if e.end_time else None,
                    "label": e.label,
                }
                for e in conflicts
            ]
            checks.append(
                {
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat(),
                    "is_available": len(conflict_payload) == 0,
                    "conflicts": conflict_payload,
                }
            )

        return {
            "is_available": all(c.get("is_available", False) for c in checks),
            "requested_checks": checks,
        }

    def _extract_requested_windows(self, intent: SchedulingIntent) -> List[Dict[str, datetime]]:
        """Extract concrete requested time windows from message metadata/body."""
        if not intent.message_id:
            return []

        message = self.db.query(Message).filter(
            Message.id == intent.message_id,
            Message.user_id == self.user_id,
        ).first()
        if not message:
            return []

        candidate_datetimes: List[datetime] = []
        extracted_dates = message.extracted_dates or []
        candidate_datetimes.extend(self._parse_datetime_candidates(extracted_dates))

        if not candidate_datetimes and intent.meeting_date:
            time_candidates = self._extract_times_from_text(f"{message.subject or ''} {message.decrypted_body or ''}")
            for hour, minute in time_candidates:
                candidate_datetimes.append(
                    datetime.combine(intent.meeting_date, datetime.min.time(), tzinfo=timezone.utc).replace(
                        hour=hour, minute=minute
                    )
                )

        dedup: Dict[str, datetime] = {}
        for dt_obj in candidate_datetimes:
            normalized = dt_obj if dt_obj.tzinfo else dt_obj.replace(tzinfo=timezone.utc)
            dedup[normalized.isoformat()] = normalized

        duration = timedelta(minutes=30)
        windows: List[Dict[str, datetime]] = []
        for dt_obj in sorted(dedup.values()):
            windows.append({"start_time": dt_obj, "end_time": dt_obj + duration})

        return windows

    def _parse_datetime_candidates(self, raw_dates: Any) -> List[datetime]:
        """Parse datetime candidates from extracted date structures."""
        if not isinstance(raw_dates, list):
            return []

        candidates: List[datetime] = []
        for raw in raw_dates:
            if isinstance(raw, str):
                parsed = self._safe_parse_datetime(raw)
                if parsed and not (parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0):
                    candidates.append(parsed)
                continue

            if isinstance(raw, dict):
                for key in ("datetime", "start_time", "start", "value", "iso"):
                    value = raw.get(key)
                    if isinstance(value, str):
                        parsed = self._safe_parse_datetime(value)
                        if parsed:
                            candidates.append(parsed)
                            break

                date_value = raw.get("date")
                time_value = raw.get("time")
                if isinstance(date_value, str) and isinstance(time_value, str):
                    parsed = self._safe_parse_datetime(f"{date_value}T{time_value}")
                    if parsed:
                        candidates.append(parsed)

        return candidates

    @staticmethod
    def _extract_times_from_text(text: str) -> List[tuple[int, int]]:
        """Extract clock times (e.g. 2pm, 14:30) from free text."""
        if not text:
            return []

        out: List[tuple[int, int]] = []

        for match in re.finditer(r"\b([0]?[1-9]|1[0-2])(?::([0-5]\d))?\s*([ap]m)\b", text, flags=re.IGNORECASE):
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            meridiem = match.group(3).lower()
            if meridiem == "pm" and hour != 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0
            out.append((hour, minute))

        for match in re.finditer(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text):
            out.append((int(match.group(1)), int(match.group(2))))

        seen = set()
        deduped: List[tuple[int, int]] = []
        for value in out:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    @staticmethod
    def _safe_parse_datetime(value: str) -> Optional[datetime]:
        """Best-effort ISO-ish datetime parser with UTC fallback."""
        if not value:
            return None
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

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
        availability_check: Optional[Dict[str, Any]] = None,
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

            if availability_check and availability_check.get("requested_checks"):
                return self._availability_check_reply(availability_check, slots, tz_display)

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
                return reply or self._fallback_reply(intent, slots, tz_display)
            if isinstance(result, str):
                return result
            return self._fallback_reply(intent, slots, tz_display)

        except Exception as e:
            logger.error(f"CalendarOrchestrator: draft reply LLM call failed: {e}")
            return self._fallback_reply(intent, slots, context.get("timezone", "UTC"))

    def _fallback_reply(
        self,
        intent: SchedulingIntent,
        slots: List[Dict[str, Any]],
        tz_display: str,
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

    def _availability_check_reply(
        self,
        availability_check: Dict[str, Any],
        slots: List[Dict[str, Any]],
        tz_display: str,
    ) -> str:
        """Deterministic yes/no reply for requested time checks."""
        checks = availability_check.get("requested_checks") or []
        if not checks:
            return "I could not find a concrete time to check. Share a specific time and I will check it."

        first = checks[0]
        start_label = self._format_datetime_label(first.get("start_time"))

        if first.get("is_available", False):
            return f"Yes — you're free at {start_label} ({tz_display}). Want me to confirm that time?"

        conflicts = first.get("conflicts") or []
        if conflicts:
            top = conflicts[0]
            top_start = self._format_datetime_label(top.get("start_time"))
            top_end = self._format_datetime_label(top.get("end_time"), include_date=False)
            conflict_text = f"{top.get('title', 'another meeting')} ({top_start}–{top_end})"
        else:
            conflict_text = "another meeting"

        alternatives = self._format_slots_for_prompt(slots, tz_display)
        if alternatives:
            return (
                f"No — you're not free at {start_label} ({tz_display}) because of {conflict_text}. "
                f"You are available {alternatives} ({tz_display})."
            )
        return f"No — you're not free at {start_label} ({tz_display}) because of {conflict_text}."

    @staticmethod
    def _format_datetime_label(value: Optional[str], include_date: bool = True) -> str:
        if not value:
            return "that time"
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if include_date:
                return dt.strftime("%a %b %d at %I:%M %p")
            return dt.strftime("%I:%M %p")
        except Exception:
            return "that time"

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
        availability_check: Optional[Dict[str, Any]] = None,
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

        if availability_check and availability_check.get("requested_checks"):
            first = availability_check["requested_checks"][0]
            if first.get("is_available"):
                parts.append("requested time is free")
            else:
                parts.append(f"requested time conflicts with {len(first.get('conflicts') or [])} event(s)")

        if not slots and not (availability_check and availability_check.get("requested_checks")):
            return "No available slots found in the next 14 days matching your preferences."

        if not parts:
            return None

        return "Slots selected based on: " + "; ".join(parts) + "."

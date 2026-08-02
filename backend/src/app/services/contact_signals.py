from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.data.models import CalendarEvent, Contact
from app.services.contact_brief import ContactBriefService
from app.services.contact_observability import log_contact_signals_metric


class ContactSignalsService:
    """Build deterministic relationship signals for one contact."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get_contact_signals(self, contact_id: int, *, consumer: str = "unknown") -> Optional[List[Dict[str, Any]]]:
        started = time.perf_counter()
        contact = (
            self.db.query(Contact)
            .filter(Contact.id == contact_id, Contact.user_id == self.user_id)
            .first()
        )
        if not contact:
            return None

        brief = ContactBriefService(self.db, user_id=self.user_id).get_contact_brief(contact.id, consumer="contact_signals")
        if not brief:
            return None

        now = datetime.now(timezone.utc)
        signals: List[Dict[str, Any]] = []
        last_interaction = brief.get("stats", {}).get("last_interaction_at")
        recent_interactions = brief.get("recent_interactions") or []
        commitments = brief.get("commitments") or []
        upcoming_events = brief.get("upcoming_events") or []
        decisions = brief.get("decisions") or []

        overdue_threads = [
            item
            for item in recent_interactions
            if item.get("needs_reply") and self._older_than(item.get("occurred_at"), days=3, now=now)
        ]
        if overdue_threads:
            signals.append(
                {
                    "key": "overdue_follow_up",
                    "label": "Overdue follow-up",
                    "severity": "high",
                    "detail": f"{len(overdue_threads)} interaction(s) involving this contact have needed a reply for more than 3 days.",
                }
            )

        unresolved_commitments = [
            item
            for item in commitments
            if str(item.get("status") or "").lower() in {"active", "pending_approval", "approved", "snoozed"}
        ]
        if unresolved_commitments:
            signals.append(
                {
                    "key": "unresolved_commitment",
                    "label": "Unresolved commitment",
                    "severity": "medium",
                    "detail": f"{len(unresolved_commitments)} active commitment(s) are still open with this contact.",
                }
            )

        if upcoming_events and self._older_than(last_interaction, days=14, now=now):
            next_event = self._soonest_event(upcoming_events)
            signals.append(
                {
                    "key": "upcoming_meeting_without_recent_interaction",
                    "label": "Upcoming meeting without recent interaction",
                    "severity": "medium",
                    "detail": f"Next meeting is {self._format_datetime(next_event.get('start_time'))}, but there has been no tracked interaction in the last 14 days.",
                }
            )

        last_meeting_end = self._last_completed_meeting_end(contact=contact, now=now)
        if last_meeting_end and any(self._after(item.get("created_at"), last_meeting_end) for item in decisions):
            signals.append(
                {
                    "key": "new_decision_since_last_meeting",
                    "label": "New decision since last meeting",
                    "severity": "info",
                    "detail": "A new decision was recorded after the last completed meeting with this contact.",
                }
            )

        category = " ".join(str(contact.category or "").strip().lower().split())
        if category in {"vip", "external", "vendor"}:
            signals.append(
                {
                    "key": "priority_marker",
                    "label": "Priority relationship",
                    "severity": "high" if category == "vip" else "info",
                    "detail": f"Contact is marked as {category}.",
                }
            )

        severity_rank = {"high": 3, "medium": 2, "info": 1}
        signals.sort(
            key=lambda item: (
                severity_rank.get(str(item.get("severity") or "info").lower(), 0),
                str(item.get("key") or ""),
            ),
            reverse=True,
        )
        final_signals = signals[:6]
        log_contact_signals_metric(
            user_id=self.user_id,
            contact_id=contact.id,
            consumer=consumer,
            signal_count=len(final_signals),
            high_count=sum(1 for item in final_signals if str(item.get("severity") or "").lower() == "high"),
            medium_count=sum(1 for item in final_signals if str(item.get("severity") or "").lower() == "medium"),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return final_signals

    def _last_completed_meeting_end(self, *, contact: Contact, now: datetime) -> Optional[datetime]:
        email_norm = self._normalize_email(contact.email)
        name_norm = " ".join(str(contact.name or "").strip().lower().split())
        candidate_events = (
            self.db.query(CalendarEvent)
            .filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.end_time < now,
                CalendarEvent.status.in_(["completed", "upcoming", "created"]),
            )
            .order_by(CalendarEvent.end_time.desc())
            .limit(40)
            .all()
        )
        for event in candidate_events:
            if not self._event_matches_contact(event=event, email_norm=email_norm, name_norm=name_norm):
                continue
            if event.end_time:
                return event.end_time
        return None

    def _event_matches_contact(self, *, event: CalendarEvent, email_norm: Optional[str], name_norm: str) -> bool:
        organizer_email = self._normalize_email(event.organizer)
        if email_norm and organizer_email == email_norm:
            return True

        participants = event.participants or []
        if not isinstance(participants, list):
            return False
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            participant_email = self._normalize_email(participant.get("email"))
            if email_norm and participant_email == email_norm:
                return True
            if (not email_norm) and name_norm:
                participant_name = " ".join(str(participant.get("name") or "").strip().lower().split())
                if participant_name and participant_name == name_norm:
                    return True
        return False

    def _normalize_email(self, value: Any) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        _, parsed = parseaddr(raw)
        candidate = (parsed or raw).strip().lower()
        if "@" not in candidate:
            return None
        return candidate

    def _older_than(self, value: Any, *, days: int, now: datetime) -> bool:
        parsed = self._parse_datetime(value)
        if not parsed:
            return True
        return parsed <= now - timedelta(days=days)

    def _after(self, value: Any, threshold: datetime) -> bool:
        parsed = self._parse_datetime(value)
        if not parsed:
            return False
        return parsed > threshold

    def _soonest_event(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        sorted_events = sorted(
            events,
            key=lambda item: self._parse_datetime(item.get("start_time")) or datetime.max.replace(tzinfo=timezone.utc),
        )
        return sorted_events[0] if sorted_events else {}

    def _format_datetime(self, value: Any) -> str:
        parsed = self._parse_datetime(value)
        if not parsed:
            return "soon"
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if parsed.tzinfo else parsed.strftime("%Y-%m-%d %H:%M")

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

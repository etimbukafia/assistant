"""Meeting brief action tool implementation for playground."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import CalendarEvent, ContextEntry, EntityReference


class MeetingBriefService:
    """Builds concise meeting briefs from event data and context entries."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def build_brief(
        self,
        event_id: Optional[str] = None,
        meeting_subject: Optional[str] = None,
        participant_ids: Optional[List[str]] = None,
        include_recent_context: bool = True,
    ) -> Dict[str, Any]:
        event = self._resolve_event(event_id=event_id, meeting_subject=meeting_subject)
        if not event:
            return {
                "event_id": event_id,
                "meeting_subject": meeting_subject,
                "summary": "No matching meeting found.",
                "participants": participant_ids or [],
                "agenda": [],
                "decisions": [],
                "commitments": [],
                "risks": [],
                "open_items": [],
                "context_entries": [],
            }

        event_entries = self._event_entries(event.event_id, include_recent_context)
        decisions = [entry.content for entry in event_entries if entry.type == "decision"][:5]
        commitments = [entry.content for entry in event_entries if entry.type == "commitment"][:5]
        risks = [entry.content for entry in event_entries if entry.type == "insight"][:5]
        open_items = [entry.content for entry in event_entries if entry.type in {"commitment", "insight"}][:6]
        agenda = self._derive_agenda(event, decisions, commitments, risks)
        participants = self._participants(event.attendees, participant_ids or [])

        summary = self._summary(event.subject, decisions, commitments, risks)

        context_payload = [
            {
                "id": entry.id,
                "type": entry.type,
                "content": entry.content,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "importance_level": entry.importance_level,
            }
            for entry in event_entries[:15]
        ]

        return {
            "event_id": event.event_id,
            "meeting_subject": event.subject,
            "summary": summary,
            "participants": participants,
            "agenda": agenda,
            "decisions": decisions,
            "commitments": commitments,
            "risks": risks,
            "open_items": open_items,
            "context_entries": context_payload,
            "start_at": event.start_at.isoformat() if event.start_at else None,
            "end_at": event.end_at.isoformat() if event.end_at else None,
            "location": event.location,
        }

    def _resolve_event(self, event_id: Optional[str], meeting_subject: Optional[str]) -> Optional[CalendarEvent]:
        if event_id:
            event = (
                self.db.query(CalendarEvent)
                .filter(CalendarEvent.user_id == self.user_id, CalendarEvent.event_id == event_id.strip())
                .first()
            )
            if event:
                return event

        subject = (meeting_subject or "").strip()
        if subject:
            event = (
                self.db.query(CalendarEvent)
                .filter(
                    CalendarEvent.user_id == self.user_id,
                    func.lower(CalendarEvent.subject) == subject.lower(),
                )
                .first()
            )
            if event:
                return event

            event = (
                self.db.query(CalendarEvent)
                .filter(
                    CalendarEvent.user_id == self.user_id,
                    CalendarEvent.subject.ilike(f"%{subject}%"),
                )
                .order_by(CalendarEvent.start_at.asc())
                .first()
            )
            if event:
                return event

            ref = (
                self.db.query(EntityReference)
                .filter(
                    EntityReference.user_id == self.user_id,
                    EntityReference.entity_type == "event",
                    or_(
                        func.lower(EntityReference.display_name) == subject.lower(),
                        EntityReference.ref == subject,
                    ),
                )
                .first()
            )
            if ref:
                return (
                    self.db.query(CalendarEvent)
                    .filter(CalendarEvent.user_id == self.user_id, CalendarEvent.event_id == ref.ref)
                    .first()
                )
        return None

    def _event_entries(self, event_id: str, include_recent_context: bool) -> List[ContextEntry]:
        query = (
            self.db.query(ContextEntry)
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.entity_type == "event",
                ContextEntry.entity_id == event_id,
            )
            .order_by(ContextEntry.importance_level.desc(), ContextEntry.created_at.desc())
            .limit(30)
        )
        entries = query.all()
        if entries or not include_recent_context:
            return entries

        return (
            self.db.query(ContextEntry)
            .filter(ContextEntry.user_id == self.user_id, ContextEntry.entity_type == "executive")
            .order_by(ContextEntry.created_at.desc())
            .limit(12)
            .all()
        )

    def _participants(self, attendees_raw: Optional[str], extra: List[str]) -> List[str]:
        attendees = [item.strip() for item in (attendees_raw or "").split(",") if item.strip()]
        for value in extra:
            cleaned = value.strip()
            if cleaned and cleaned not in attendees:
                attendees.append(cleaned)
        return attendees

    def _derive_agenda(
        self,
        event: CalendarEvent,
        decisions: List[str],
        commitments: List[str],
        risks: List[str],
    ) -> List[str]:
        agenda = [f"Review objective for {event.subject}"]
        if decisions:
            agenda.append("Confirm previous decisions")
        if commitments:
            agenda.append("Track commitment status")
        if risks:
            agenda.append("Discuss active risks and mitigations")
        agenda.append("Close with owners and deadlines")
        return agenda

    def _summary(
        self,
        subject: str,
        decisions: List[str],
        commitments: List[str],
        risks: List[str],
    ) -> str:
        return (
            f"{subject}: {len(decisions)} decisions, {len(commitments)} commitments, "
            f"{len(risks)} active risks tracked."
        )

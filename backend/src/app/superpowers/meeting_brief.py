"""Meeting brief generation service from event-scoped context."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import CalendarEvent, ContextEntry, EntityReference


class MeetingBriefService:
    """Build concise meeting briefs from event records and related memory."""

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

        entity_ref = self._resolve_event_ref(event, meeting_subject)
        entries = self._event_entries(entity_ref, include_recent_context)

        decisions = [entry.content for entry in entries if entry.type == "decision"][:5]
        commitments = [entry.content for entry in entries if entry.type == "commitment"][:5]
        risks = [entry.content for entry in entries if entry.type in {"insight", "relationships"}][:5]
        open_items = [entry.content for entry in entries if entry.type in {"commitment", "insight"}][:6]
        agenda = self._derive_agenda(event.title, decisions, commitments, risks)
        participants = self._participants(event.participants, participant_ids or [])

        summary = (
            f"{event.title}: {len(decisions)} decisions, "
            f"{len(commitments)} commitments, {len(risks)} active risks tracked."
        )
        context_payload = [
            {
                "id": entry.id,
                "type": entry.type,
                "content": entry.content,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "importance_level": entry.importance_level,
                "status": entry.status,
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
            }
            for entry in entries[:15]
        ]
        return {
            "event_id": entity_ref,
            "meeting_subject": event.title,
            "summary": summary,
            "participants": participants,
            "agenda": agenda,
            "decisions": decisions,
            "commitments": commitments,
            "risks": risks,
            "open_items": open_items,
            "context_entries": context_payload,
            "start_at": event.start_time.isoformat() if event.start_time else None,
            "end_at": event.end_time.isoformat() if event.end_time else None,
            "location": event.location,
        }

    def _resolve_event(self, event_id: Optional[str], meeting_subject: Optional[str]) -> Optional[CalendarEvent]:
        if event_id:
            if str(event_id).isdigit():
                event = self.db.query(CalendarEvent).filter(
                    CalendarEvent.user_id == self.user_id,
                    CalendarEvent.id == int(event_id),
                ).first()
                if event:
                    return event
            event = self.db.query(CalendarEvent).filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.external_event_id == event_id.strip(),
            ).first()
            if event:
                return event

        subject = (meeting_subject or "").strip()
        if subject:
            event = self.db.query(CalendarEvent).filter(
                CalendarEvent.user_id == self.user_id,
                func.lower(CalendarEvent.title) == subject.lower(),
            ).first()
            if event:
                return event

            event = self.db.query(CalendarEvent).filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.title.ilike(f"%{subject}%"),
            ).order_by(CalendarEvent.start_time.asc()).first()
            if event:
                return event

            ref = self.db.query(EntityReference).filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == "event",
                or_(
                    func.lower(EntityReference.display_name) == subject.lower(),
                    EntityReference.ref == subject,
                ),
            ).first()
            if ref:
                event = self.db.query(CalendarEvent).filter(
                    CalendarEvent.user_id == self.user_id,
                    CalendarEvent.external_event_id == ref.ref,
                ).first()
                if event:
                    return event
        return None

    def _resolve_event_ref(self, event: CalendarEvent, meeting_subject: Optional[str]) -> str:
        if event.external_event_id:
            return event.external_event_id
        fallback = (meeting_subject or "").strip()
        if fallback:
            ref = self.db.query(EntityReference).filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == "event",
                func.lower(EntityReference.display_name) == fallback.lower(),
            ).first()
            if ref:
                return ref.ref
        return f"event:{event.id}"

    def _event_entries(self, event_ref: str, include_recent_context: bool) -> List[ContextEntry]:
        now = datetime.now(timezone.utc)
        query = self.db.query(ContextEntry).filter(
            ContextEntry.user_id == self.user_id,
            ContextEntry.entity_type == "event",
            ContextEntry.entity_id == event_ref,
            ((ContextEntry.expires_at.is_(None)) | (ContextEntry.expires_at >= now)),
        ).order_by(ContextEntry.importance_level.desc(), ContextEntry.created_at.desc()).limit(30)
        entries = query.all()
        if entries or not include_recent_context:
            return entries
        threshold = now - timedelta(days=1)
        return (
            self.db.query(ContextEntry)
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.entity_type.in_(["assistant", "executive"]),
                ContextEntry.created_at >= threshold,
            )
            .order_by(ContextEntry.created_at.desc())
            .limit(12)
            .all()
        )

    def _participants(self, participants_raw: Any, extra: List[str]) -> List[str]:
        participants: List[str] = []
        if isinstance(participants_raw, list):
            for p in participants_raw:
                if isinstance(p, str):
                    val = p.strip()
                    if val and val not in participants:
                        participants.append(val)
                elif isinstance(p, dict):
                    val = (p.get("email") or p.get("name") or "").strip()
                    if val and val not in participants:
                        participants.append(val)
        for value in extra:
            cleaned = value.strip()
            if cleaned and cleaned not in participants:
                participants.append(cleaned)
        return participants

    def _derive_agenda(
        self,
        subject: str,
        decisions: List[str],
        commitments: List[str],
        risks: List[str],
    ) -> List[str]:
        agenda = [f"Review objective for {subject}"]
        if decisions:
            agenda.append("Confirm previous decisions")
        if commitments:
            agenda.append("Track commitment status")
        if risks:
            agenda.append("Discuss active risks and mitigations")
        agenda.append("Close with owners and deadlines")
        return agenda

"""Meeting brief generation service from event-scoped context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import CalendarEvent, Contact, ContextEntry, EntityReference
from app.security.prompt_sanitizer import sanitize_with_detection
from app.services.contact_brief import ContactBriefService
from app.services.context_memory_policy import (
    apply_historical_expiry_retrieval_filter,
    apply_memory_retrieval_filter,
)


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
        risks = [entry.content for entry in entries if entry.type == "risk"][:5]
        open_items = [entry.content for entry in entries if entry.type in {"commitment", "risk"}][:6]
        agenda = self._derive_agenda(event.title, decisions, commitments, risks)
        participants = self._participants(event.participants, participant_ids or [])
        participant_briefs = self._build_participant_briefs(participants)

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
            "participant_briefs": participant_briefs,
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
        query = self.db.query(ContextEntry).filter(
            ContextEntry.user_id == self.user_id,
            ContextEntry.entity_type == "event",
            ContextEntry.entity_id == event_ref,
        )
        query = apply_memory_retrieval_filter(query, allowed_statuses=("active", "resolved", "stale"))
        query = apply_historical_expiry_retrieval_filter(query)
        query = query.order_by(ContextEntry.created_at.desc()).limit(30)
        entries = query.all()
        # Keep meeting briefs strictly event-scoped to avoid leaking unrelated global context.
        # include_recent_context is kept for forward compatibility with richer scoped fallbacks.
        if entries or not include_recent_context:
            return entries
        return []

    def _participants(self, participants_raw: Any, requested: List[str]) -> List[str]:
        normalized_requested = {
            token
            for token in (self._normalize_lookup_token(value) for value in requested)
            if token
        }
        participants: List[str] = []
        if not isinstance(participants_raw, list):
            return participants

        for participant in participants_raw:
            if normalized_requested and not self._participant_matches_requested(participant, normalized_requested):
                continue
            val = self._participant_display_value(participant)
            if val and val not in participants:
                participants.append(val)
        return participants

    def _build_participant_briefs(self, participants: List[str]) -> List[Dict[str, Any]]:
        if not participants:
            return []

        brief_service = ContactBriefService(self.db, user_id=self.user_id)
        results: List[Dict[str, Any]] = []
        for participant in participants[:6]:
            contact = self._resolve_contact(participant)
            if not contact:
                continue
            brief = brief_service.get_contact_brief(contact.id, consumer="meeting_brief")
            if not brief:
                continue
            summary = brief.get("summary") or {}
            results.append(
                {
                    "contact": {
                        "id": contact.id,
                        "name": self._sanitize_contact_text(contact.name),
                        "role": self._sanitize_contact_text(contact.role),
                        "organization": self._sanitize_contact_text(contact.organization),
                    },
                    "relationship_summary": self._sanitize_contact_text(summary.get("headline")),
                    "preferred_tone": self._sanitize_contact_text(summary.get("preferred_tone")),
                }
            )
        return results

    def _resolve_contact(self, participant: str) -> Optional[Contact]:
        lookup = self._normalize_lookup_token(participant)
        if not lookup:
            return None
        if "@" in lookup:
            return (
                self.db.query(Contact)
                .filter(
                    Contact.user_id == self.user_id,
                    func.lower(Contact.email) == lookup.lower(),
                )
                .first()
            )
        rows = (
            self.db.query(Contact)
            .filter(
                Contact.user_id == self.user_id,
                func.lower(Contact.name) == lookup.lower(),
            )
            .limit(2)
            .all()
        )
        if len(rows) != 1:
            return None
        return rows[0]

    def _participant_display_value(self, participant: Any) -> Optional[str]:
        if isinstance(participant, str):
            value = " ".join(participant.split()).strip()
            return value or None
        if isinstance(participant, dict):
            value = " ".join(str(participant.get("email") or participant.get("name") or "").split()).strip()
            return value or None
        return None

    def _normalize_lookup_token(self, value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _participant_matches_requested(self, participant: Any, requested: set[str]) -> bool:
        if isinstance(participant, dict):
            tokens = {
                self._normalize_lookup_token(participant.get("email")),
                self._normalize_lookup_token(participant.get("name")),
            }
            return any(token and token in requested for token in tokens)
        token = self._normalize_lookup_token(participant)
        return bool(token and token in requested)

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

    def _sanitize_contact_text(self, value: Optional[str]) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        result = sanitize_with_detection(text)
        cleaned = " ".join(result.sanitized_text.split()).strip()
        return cleaned or None

    def _sanitize_contact_list(self, values: List[Optional[str]]) -> List[str]:
        cleaned: List[str] = []
        for value in values:
            item = self._sanitize_contact_text(value)
            if item:
                cleaned.append(item)
        return cleaned

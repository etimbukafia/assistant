from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import getaddresses, parseaddr
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import CalendarEvent, Contact, ContactContext, ContextEntry, EntityReference, Message, Task, ThreadState
from app.services.context_memory_policy import (
    apply_confidence_retrieval_filter,
    apply_historical_expiry_retrieval_filter,
)
from app.services.contact_observability import log_contact_brief_metric


ACTIVE_TASK_STATUSES = {"pending_approval", "approved", "snoozed"}
DEFAULT_CONTEXT_LIMIT = 8
DEFAULT_INTERACTION_LIMIT = 6
DEFAULT_EVENT_LIMIT = 5


class ContactBriefService:
    """Build a deterministic relationship brief for one contact."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get_contact_brief(self, contact_id: int, *, consumer: str = "unknown") -> Optional[Dict[str, Any]]:
        started = time.perf_counter()
        contact = (
            self.db.query(Contact)
            .filter(Contact.id == contact_id, Contact.user_id == self.user_id)
            .first()
        )
        if not contact:
            log_contact_brief_metric(
                user_id=self.user_id,
                contact_id=contact_id,
                consumer=consumer,
                found=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            return None

        email_norm = (contact.email or "").strip().lower()
        now = datetime.now(timezone.utc)

        context_entries = self._contact_context_entries(email_norm=email_norm, now=now)
        thread_states, messages = self._load_threads_and_messages(contact_id=contact.id, email_norm=email_norm)
        tasks = self._load_tasks(messages=messages, thread_states=thread_states)
        upcoming_events = self._load_upcoming_events(contact=contact, now=now)
        legacy_context = self._load_legacy_contact_context(contact=contact, email_norm=email_norm)

        preferences = self._build_preferences(context_entries=context_entries, legacy_context=legacy_context)
        commitments = self._build_commitments(
            context_entries=context_entries,
            tasks=tasks,
        )
        decisions = self._build_decisions(
            context_entries=context_entries,
            thread_states=thread_states,
        )
        recent_interactions = self._build_recent_interactions(messages=messages)
        stats = self._build_stats(
            messages=messages,
            thread_states=thread_states,
            tasks=tasks,
            upcoming_events=upcoming_events,
            legacy_context=legacy_context,
        )
        summary = self._build_summary(
            contact=contact,
            context_entries=context_entries,
            legacy_context=legacy_context,
            stats=stats,
        )
        signals = self._build_signals(
            stats=stats,
            commitments=commitments,
            upcoming_events=upcoming_events,
            now=now,
        )

        result = {
            "contact": contact,
            "summary": summary,
            "stats": stats,
            "preferences": preferences,
            "commitments": commitments,
            "decisions": decisions,
            "recent_interactions": recent_interactions,
            "upcoming_events": upcoming_events,
            "signals": signals,
        }
        log_contact_brief_metric(
            user_id=self.user_id,
            contact_id=contact.id,
            consumer=consumer,
            found=True,
            latency_ms=int((time.perf_counter() - started) * 1000),
            context_count=len(context_entries),
            message_count=len(messages),
            task_count=len(tasks),
            event_count=len(upcoming_events),
            commitment_count=len(commitments),
            decision_count=len(decisions),
            signal_count=len(signals),
        )
        return result

    def _contact_context_entries(self, *, email_norm: str, now: datetime) -> List[ContextEntry]:
        if not email_norm:
            return []

        return (
            apply_historical_expiry_retrieval_filter(
                apply_confidence_retrieval_filter(self.db.query(ContextEntry)),
                now=now,
            )
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.entity_type == "contact",
                ContextEntry.entity_id == email_norm,
                ContextEntry.status == "active",
            )
            .order_by(ContextEntry.updated_at.desc(), ContextEntry.created_at.desc())
            .limit(50)
            .all()
        )

    def _load_threads_and_messages(
        self,
        *,
        contact_id: int,
        email_norm: str,
    ) -> tuple[List[ThreadState], List[Message]]:
        message_query = self.db.query(Message).filter(Message.user_id == self.user_id)
        if email_norm:
            message_query = message_query.filter(
                or_(
                    Message.contact_id == contact_id,
                    func.lower(Message.sender).contains(email_norm),
                    func.lower(Message.recipient).contains(email_norm),
                )
            )
        else:
            message_query = message_query.filter(Message.contact_id == contact_id)

        candidate_messages = (
            message_query
            .order_by(Message.received_at.desc(), Message.created_at.desc())
            .limit(120)
            .all()
        )
        messages = [
            message for message in candidate_messages
            if self._message_matches_contact(message=message, contact_id=contact_id, email_norm=email_norm)
        ][:40]
        thread_ids = sorted({m.thread_id for m in messages if m.thread_id})
        thread_states = []
        if thread_ids:
            thread_states = (
                self.db.query(ThreadState)
                .filter(
                    ThreadState.user_id == self.user_id,
                    ThreadState.thread_id.in_(thread_ids),
                )
                .all()
            )
        return thread_states, messages

    def _load_tasks(self, *, messages: List[Message], thread_states: List[ThreadState]) -> List[Task]:
        message_ids = [m.id for m in messages if m.id is not None]
        thread_ids = [t.thread_id for t in thread_states if t.thread_id]
        if not message_ids and not thread_ids:
            return []

        query = self.db.query(Task).filter(Task.user_id == self.user_id)
        filters = []
        if message_ids:
            filters.append(Task.message_id.in_(message_ids))
        if thread_ids:
            filters.append(Task.thread_id.in_(thread_ids))
        query = query.filter(or_(*filters))
        tasks = query.limit(40).all()
        tasks.sort(
            key=lambda task: (
                self._sortable_datetime(task.deadline, default_max=True),
                self._sortable_datetime(task.updated_at, default_max=False),
                self._sortable_datetime(task.created_at, default_max=False),
            )
        )
        return tasks[:20]

    def _load_upcoming_events(self, *, contact: Contact, now: datetime) -> List[Dict[str, Any]]:
        name_norm = (contact.name or "").strip().lower()
        email_norm = (contact.email or "").strip().lower()
        candidate_events = (
            self.db.query(CalendarEvent)
            .filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.start_time >= now - timedelta(hours=12),
                CalendarEvent.status.in_(["upcoming", "created"]),
            )
            .order_by(CalendarEvent.start_time.asc())
            .limit(50)
            .all()
        )

        matched: List[Dict[str, Any]] = []
        for event in candidate_events:
            if not self._event_matches_contact(event=event, email_norm=email_norm, name_norm=name_norm):
                continue
            participants = event.participants or []
            matched.append(
                {
                    "id": event.id,
                    "title": event.title,
                    "start_time": event.start_time,
                    "end_time": event.end_time,
                    "location": event.location,
                    "organizer": event.organizer,
                    "participant_count": len(participants) if isinstance(participants, list) else 0,
                }
            )
            if len(matched) >= DEFAULT_EVENT_LIMIT:
                break
        return matched

    def _event_matches_contact(self, *, event: CalendarEvent, email_norm: str, name_norm: str) -> bool:
        if email_norm:
            organizer_email = self._normalize_single_email(event.organizer)
            if organizer_email == email_norm:
                return True

        participants = event.participants or []
        if isinstance(participants, list):
            for participant in participants:
                if not isinstance(participant, dict):
                    continue
                participant_email = str(participant.get("email") or "").strip().lower()
                if email_norm and participant_email == email_norm:
                    return True
                if (not email_norm) and name_norm:
                    participant_name = self._normalize_person_name(participant.get("name"))
                    if participant_name and participant_name == name_norm:
                        return True
        return False

    def _message_matches_contact(self, *, message: Message, contact_id: int, email_norm: str) -> bool:
        if message.contact_id == contact_id:
            return True
        if not email_norm:
            return False

        emails = set()
        emails.update(self._extract_email_candidates(message.sender))
        emails.update(self._extract_email_candidates(message.recipient))
        return email_norm in emails

    def _extract_email_candidates(self, value: Any) -> List[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        parsed: List[str] = []
        for _, email in getaddresses([raw]):
            normalized = self._normalize_single_email(email)
            if normalized:
                parsed.append(normalized)
        if parsed:
            return parsed
        normalized = self._normalize_single_email(raw)
        return [normalized] if normalized else []

    def _normalize_single_email(self, value: Any) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        _, parsed = parseaddr(raw)
        candidate = (parsed or raw).strip().lower()
        if "@" not in candidate:
            return None
        return candidate

    def _normalize_person_name(self, value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _legacy_context_matches_contact(self, *, contact: Contact, legacy_context: ContactContext) -> bool:
        contact_email = (contact.email or "").strip().lower()
        legacy_email = (legacy_context.contact_email or "").strip().lower()
        if not contact_email or legacy_email != contact_email:
            return False

        legacy_name = self._normalize_person_name(legacy_context.contact_name)
        contact_name = self._normalize_person_name(contact.name)
        if legacy_name and contact_name and legacy_name != contact_name:
            return False
        return True

    def _load_legacy_contact_context(self, *, contact: Contact, email_norm: str) -> Optional[ContactContext]:
        if not email_norm:
            return None
        legacy_context = (
            self.db.query(ContactContext)
            .filter(
                ContactContext.user_id == self.user_id,
                func.lower(ContactContext.contact_email) == email_norm,
            )
            .first()
        )
        if not legacy_context:
            return None
        if not self._legacy_context_matches_contact(contact=contact, legacy_context=legacy_context):
            return None
        return legacy_context

    def _build_preferences(
        self,
        *,
        context_entries: List[ContextEntry],
        legacy_context: Optional[ContactContext],
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for entry in context_entries:
            if entry.type != "preference":
                continue
            items.append(
                {
                    "id": f"context:{entry.id}",
                    "content": entry.content,
                    "source_type": "context_entry",
                    "source_ref": entry.linked_to or entry.entity_id,
                    "created_at": entry.created_at,
                }
            )
            if len(items) >= DEFAULT_CONTEXT_LIMIT:
                break

        if legacy_context and legacy_context.preferred_tone:
            items.insert(
                0,
                {
                    "id": f"legacy-tone:{legacy_context.id}",
                    "content": f"Preferred tone: {legacy_context.preferred_tone}",
                    "source_type": "legacy_contact_context",
                    "source_ref": legacy_context.contact_email,
                    "created_at": legacy_context.updated_at,
                },
            )
        return items[:DEFAULT_CONTEXT_LIMIT]

    def _build_commitments(
        self,
        *,
        context_entries: List[ContextEntry],
        tasks: List[Task],
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for entry in context_entries:
            if entry.type != "commitment":
                continue
            key = f"context:{entry.id}"
            seen.add(key)
            items.append(
                {
                    "id": key,
                    "title": entry.content,
                    "detail": entry.linked_to,
                    "status": entry.status or "active",
                    "source_type": "context_entry",
                    "source_ref": entry.entity_id,
                    "due_at": entry.expires_at,
                    "created_at": entry.created_at,
                }
            )

        for task in tasks:
            if task.status not in ACTIVE_TASK_STATUSES:
                continue
            key = f"task:{task.id}"
            if key in seen:
                continue
            items.append(
                {
                    "id": key,
                    "title": task.title,
                    "detail": task.description or task.source_snippet,
                    "status": task.status,
                    "source_type": "task",
                    "source_ref": task.thread_id or str(task.message_id),
                    "due_at": task.deadline,
                    "created_at": task.created_at,
                }
            )
        items.sort(
            key=lambda item: (
                self._sortable_datetime(item.get("due_at"), default_max=True),
                self._sortable_datetime(item.get("created_at"), default_max=False),
            )
        )
        return items[:DEFAULT_CONTEXT_LIMIT]

    def _build_decisions(
        self,
        *,
        context_entries: List[ContextEntry],
        thread_states: List[ThreadState],
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for entry in context_entries:
            if entry.type != "decision":
                continue
            key = f"context:{entry.id}"
            seen.add(key)
            items.append(
                {
                    "id": key,
                    "decision": entry.content,
                    "source_type": "context_entry",
                    "source_ref": entry.entity_id,
                    "created_at": entry.created_at,
                }
            )

        for thread_state in thread_states:
            for idx, decision in enumerate(thread_state.decisions or []):
                text = str(decision.get("decision") or "").strip()
                if not text:
                    continue
                key = f"thread:{thread_state.thread_id}:{idx}:{text}"
                if key in seen:
                    continue
                seen.add(key)
                created_at = self._parse_datetime(decision.get("made_at"))
                items.append(
                    {
                        "id": key,
                        "decision": text,
                        "source_type": "thread_state",
                        "source_ref": thread_state.thread_id,
                        "created_at": created_at,
                    }
                )

        items.sort(
            key=lambda item: self._sortable_datetime(item.get("created_at"), default_max=False),
            reverse=True,
        )
        return items[:DEFAULT_CONTEXT_LIMIT]

    def _build_recent_interactions(self, *, messages: List[Message]) -> List[Dict[str, Any]]:
        interactions: List[Dict[str, Any]] = []
        for message in messages[:DEFAULT_INTERACTION_LIMIT]:
            interactions.append(
                {
                    "id": f"message:{message.id}",
                    "interaction_type": "email",
                    "subject": message.subject,
                    "summary": message.summary or (message.decrypted_body[:180] if message.decrypted_body else None),
                    "thread_id": message.thread_id,
                    "thread_resolved": self._thread_ref_resolved(message.thread_id),
                    "occurred_at": message.received_at or message.created_at,
                    "needs_reply": bool(message.needs_reply),
                }
            )
        return interactions

    def _thread_ref_resolved(self, thread_ref: Optional[str]) -> Optional[bool]:
        normalized = " ".join(str(thread_ref or "").split()).strip()
        if not normalized:
            return None
        if (
            self.db.query(Message.id)
            .filter(
                Message.user_id == self.user_id,
                Message.thread_id == normalized,
            )
            .first()
            is not None
        ):
            return True
        if (
            self.db.query(ThreadState.thread_id)
            .filter(
                ThreadState.user_id == self.user_id,
                ThreadState.thread_id == normalized,
            )
            .first()
            is not None
        ):
            return True
        if (
            self.db.query(EntityReference.id)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == "thread",
                EntityReference.ref == normalized,
            )
            .first()
            is not None
        ):
            return True
        return False

    def _build_stats(
        self,
        *,
        messages: List[Message],
        thread_states: List[ThreadState],
        tasks: List[Task],
        upcoming_events: List[Dict[str, Any]],
        legacy_context: Optional[ContactContext],
    ) -> Dict[str, Any]:
        metadata = (legacy_context.contact_metadata or {}) if legacy_context else {}
        last_interaction_at = self._parse_datetime(metadata.get("last_interaction_at"))
        if not last_interaction_at and messages:
            last_interaction_at = messages[0].received_at or messages[0].created_at

        return {
            "total_messages": len(messages),
            "total_threads": len(thread_states),
            "open_tasks": sum(1 for task in tasks if task.status in ACTIVE_TASK_STATUSES),
            "upcoming_events": len(upcoming_events),
            "needs_reply_threads": sum(1 for thread in thread_states if bool(thread.needs_reply)),
            "last_interaction_at": last_interaction_at,
            "primary_channel": metadata.get("primary_channel"),
            "reply_rate": metadata.get("reply_rate"),
            "avg_response_latency_hours": metadata.get("avg_response_latency_hours"),
        }

    def _build_summary(
        self,
        *,
        contact: Contact,
        context_entries: List[ContextEntry],
        legacy_context: Optional[ContactContext],
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        relationship_notes = [entry.content for entry in context_entries if entry.type == "insight"][:3]
        headline = relationship_notes[0] if relationship_notes else self._default_headline(contact=contact, stats=stats)
        manual_notes = (contact.notes or "").strip() or (legacy_context.notes.strip() if legacy_context and legacy_context.notes else None)

        preferred_tone = legacy_context.preferred_tone if legacy_context and legacy_context.preferred_tone else None
        return {
            "headline": headline,
            "category": contact.category,
            "role": contact.role,
            "organization": contact.organization,
            "manual_notes": manual_notes,
            "relationship_notes": relationship_notes,
            "preferred_tone": preferred_tone,
        }

    def _default_headline(self, *, contact: Contact, stats: Dict[str, Any]) -> str:
        parts = []
        if contact.role and contact.organization:
            parts.append(f"{contact.role} at {contact.organization}")
        elif contact.role:
            parts.append(contact.role)
        elif contact.organization:
            parts.append(f"Works at {contact.organization}")

        if contact.category:
            parts.append(f"Category: {contact.category}")

        if stats.get("total_messages"):
            parts.append(f"{stats['total_messages']} tracked interactions")

        if parts:
            return f"{contact.name}: " + " - ".join(parts)
        return f"{contact.name}: relationship context is still being built."

    def _build_signals(
        self,
        *,
        stats: Dict[str, Any],
        commitments: List[Dict[str, Any]],
        upcoming_events: List[Dict[str, Any]],
        now: datetime,
    ) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        if stats.get("needs_reply_threads", 0) > 0:
            signals.append(
                {
                    "key": "needs_reply",
                    "label": "Pending reply context",
                    "severity": "high",
                    "detail": f"{stats['needs_reply_threads']} thread(s) involving this contact still need a reply.",
                }
            )
        if commitments:
            signals.append(
                {
                    "key": "open_commitments",
                    "label": "Open commitments",
                    "severity": "medium",
                    "detail": f"{len(commitments)} open commitment(s) are tied to this relationship.",
                }
            )
        if upcoming_events:
            next_event = upcoming_events[0]
            signals.append(
                {
                    "key": "upcoming_meeting",
                    "label": "Upcoming meeting",
                    "severity": "info",
                    "detail": f"Next meeting is {self._format_event_date(next_event.get('start_time'))}.",
                }
            )
        last_interaction = stats.get("last_interaction_at")
        if last_interaction and isinstance(last_interaction, datetime):
            normalized_last_interaction = self._sortable_datetime(last_interaction, default_max=False)
            normalized_stale_cutoff = self._sortable_datetime(now - timedelta(days=30), default_max=False)
            if normalized_last_interaction < normalized_stale_cutoff:
                signals.append(
                    {
                        "key": "stale_relationship",
                        "label": "Stale relationship",
                        "severity": "medium",
                        "detail": "No tracked interaction in the last 30 days.",
                    }
                )
        return signals[:4]

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _format_event_date(self, value: Any) -> str:
        if not isinstance(value, datetime):
            return "soon"
        if value.tzinfo is None:
            return value.strftime("%Y-%m-%d %H:%M")
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _sortable_datetime(
        self,
        value: Any,
        *,
        default_max: bool,
    ) -> datetime:
        parsed = self._parse_datetime(value) if not isinstance(value, datetime) else value
        if parsed is None:
            return datetime.max if default_max else datetime.min
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed


from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import getaddresses, parseaddr
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import CalendarEvent, Contact, ContextEntry, EntityReference, Message, Task, ThreadState
from app.services.context_memory_policy import (
    apply_confidence_retrieval_filter,
    apply_historical_expiry_retrieval_filter,
)


class ContactTimelineService:
    """Build a deterministic relationship timeline for one contact."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get_contact_timeline(self, contact_id: int, limit: int = 25) -> Optional[List[Dict[str, Any]]]:
        contact = (
            self.db.query(Contact)
            .filter(Contact.id == contact_id, Contact.user_id == self.user_id)
            .first()
        )
        if not contact:
            return None

        email_norm = (contact.email or "").strip().lower()
        now = datetime.now(timezone.utc)
        messages = self._load_messages(contact_id=contact.id, email_norm=email_norm)
        thread_states = self._load_thread_states(messages=messages, contact_id=contact.id)
        tasks = self._load_tasks(messages=messages, thread_states=thread_states)
        meetings = self._load_meetings(contact=contact, now=now)
        context_entries = self._load_contact_context_entries(email_norm=email_norm, now=now)

        items: List[Dict[str, Any]] = []
        items.extend(self._message_items(messages))
        items.extend(self._thread_decision_items(thread_states))
        items.extend(self._task_items(tasks))
        items.extend(self._meeting_items(meetings))
        items.extend(self._context_entry_items(context_entries))

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for item in items:
            key = (
                item.get("kind"),
                " ".join(str(item.get("title") or "").strip().lower().split()),
                self._sortable_datetime(item.get("occurred_at")),
                item.get("source_type"),
                item.get("source_ref"),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        deduped.sort(
            key=lambda item: (
                self._sortable_datetime(item.get("occurred_at")),
                str(item.get("id") or ""),
            ),
            reverse=True,
        )
        return deduped[: max(1, min(limit, 100))]

    def _load_messages(self, *, contact_id: int, email_norm: str) -> List[Message]:
        query = self.db.query(Message).filter(Message.user_id == self.user_id)
        if email_norm:
            query = query.filter(
                or_(
                    Message.contact_id == contact_id,
                    func.lower(Message.sender).contains(email_norm),
                    func.lower(Message.recipient).contains(email_norm),
                )
            )
        else:
            query = query.filter(Message.contact_id == contact_id)

        candidate_messages = (
            query.order_by(Message.received_at.desc(), Message.created_at.desc()).limit(120).all()
        )
        return [
            message
            for message in candidate_messages
            if self._message_matches_contact(message=message, contact_id=contact_id, email_norm=email_norm)
        ][:50]

    def _load_thread_states(self, *, messages: List[Message], contact_id: int) -> List[ThreadState]:
        thread_ids = sorted({message.thread_id for message in messages if message.thread_id})
        if not thread_ids and not contact_id:
            return []
        query = self.db.query(ThreadState).filter(ThreadState.user_id == self.user_id)
        filters = []
        if thread_ids:
            filters.append(ThreadState.thread_id.in_(thread_ids))
        if contact_id:
            filters.append(ThreadState.contact_id == contact_id)
        return query.filter(or_(*filters)).all() if filters else []

    def _load_tasks(self, *, messages: List[Message], thread_states: List[ThreadState]) -> List[Task]:
        message_ids = [message.id for message in messages if message.id is not None]
        thread_ids = [thread.thread_id for thread in thread_states if thread.thread_id]
        if not message_ids and not thread_ids:
            return []

        query = self.db.query(Task).filter(Task.user_id == self.user_id)
        filters = []
        if message_ids:
            filters.append(Task.message_id.in_(message_ids))
        if thread_ids:
            filters.append(Task.thread_id.in_(thread_ids))
        tasks = query.filter(or_(*filters)).limit(60).all() if filters else []
        tasks.sort(
            key=lambda item: (
                self._sortable_datetime(item.deadline or item.updated_at or item.created_at),
                str(item.id),
            ),
            reverse=True,
        )
        return tasks[:30]

    def _load_meetings(self, *, contact: Contact, now: datetime) -> List[CalendarEvent]:
        name_norm = self._normalize_person_name(contact.name)
        email_norm = (contact.email or "").strip().lower()
        candidate_events = (
            self.db.query(CalendarEvent)
            .filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.start_time >= now - timedelta(days=180),
                CalendarEvent.start_time <= now + timedelta(days=60),
                CalendarEvent.status.in_(["upcoming", "created", "completed"]),
            )
            .order_by(CalendarEvent.start_time.desc())
            .limit(80)
            .all()
        )
        return [
            event
            for event in candidate_events
            if self._event_matches_contact(event=event, email_norm=email_norm, name_norm=name_norm)
        ][:20]

    def _load_contact_context_entries(self, *, email_norm: str, now: datetime) -> List[ContextEntry]:
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
                ContextEntry.status.in_(["active", "resolved", "stale"]),
            )
            .order_by(ContextEntry.updated_at.desc(), ContextEntry.created_at.desc())
            .limit(40)
            .all()
        )

    def _message_items(self, messages: List[Message]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for message in messages:
            occurred_at = message.received_at or message.created_at
            if not occurred_at:
                continue
            title = " ".join(str(message.subject or message.summary or "Email interaction").split()).strip()
            detail = " ".join(str(message.summary or "").split()).strip() or None
            items.append(
                {
                    "id": f"message:{message.id}",
                    "kind": "interaction",
                    "title": title,
                    "detail": detail,
                    "occurred_at": occurred_at,
                    "source_type": "message",
                    "source_ref": message.thread_id,
                    "source_resolved": self._thread_ref_resolved(message.thread_id),
                    "status": "needs_reply" if message.needs_reply else None,
                }
            )
        return items

    def _thread_decision_items(self, thread_states: List[ThreadState]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for thread_state in thread_states:
            for idx, decision in enumerate(thread_state.decisions or []):
                text = " ".join(str(decision.get("decision") or "").split()).strip()
                if not text:
                    continue
                occurred_at = self._parse_datetime(decision.get("made_at")) or thread_state.updated_at or thread_state.created_at
                if not occurred_at:
                    continue
                items.append(
                    {
                        "id": f"thread-decision:{thread_state.thread_id}:{idx}",
                        "kind": "decision",
                        "title": text,
                        "detail": None,
                        "occurred_at": occurred_at,
                        "source_type": "thread_state",
                        "source_ref": thread_state.thread_id,
                        "source_resolved": self._thread_ref_resolved(thread_state.thread_id),
                        "status": None,
                    }
                )
        return items

    def _task_items(self, tasks: List[Task]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for task in tasks:
            occurred_at = task.deadline or task.updated_at or task.created_at
            if not occurred_at:
                continue
            title = " ".join(str(task.title or "").split()).strip()
            due_label = self._format_due_label(task.deadline)
            items.append(
                {
                    "id": f"task:{task.id}",
                    "kind": "task",
                    "title": title,
                    "detail": due_label,
                    "occurred_at": occurred_at,
                    "source_type": "task",
                    "source_ref": task.thread_id or (str(task.message_id) if task.message_id is not None else None),
                    "source_resolved": self._task_source_resolved(task),
                    "status": task.status,
                }
            )
        return items

    def _meeting_items(self, meetings: List[CalendarEvent]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for event in meetings:
            items.append(
                {
                    "id": f"meeting:{event.id}",
                    "kind": "meeting",
                    "title": (event.title or "Meeting").strip(),
                    "detail": (event.location or "").strip() or None,
                    "occurred_at": event.start_time,
                    "source_type": "calendar_event",
                    "source_ref": event.external_event_id or str(event.id),
                    "source_resolved": self._event_ref_resolved(event),
                    "status": event.status,
                }
            )
        return items

    def _context_entry_items(self, entries: List[ContextEntry]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for entry in entries:
            if entry.type not in {"decision", "commitment", "insight"}:
                continue
            occurred_at = entry.updated_at or entry.created_at
            if not occurred_at:
                continue
            items.append(
                {
                    "id": f"context:{entry.id}",
                    "kind": entry.type,
                    "title": " ".join((entry.content or "").split()).strip(),
                    "detail": None,
                    "occurred_at": occurred_at,
                    "source_type": "context_entry",
                    "source_ref": entry.entity_id,
                    "source_resolved": None,
                    "status": entry.status,
                }
            )
        return items

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

    def _event_ref_resolved(self, event: CalendarEvent) -> bool:
        if event.id is not None:
            existing = (
                self.db.query(CalendarEvent.id)
                .filter(
                    CalendarEvent.user_id == self.user_id,
                    CalendarEvent.id == event.id,
                )
                .first()
            )
            if existing is not None:
                return True
        normalized_external = " ".join(str(event.external_event_id or "").split()).strip()
        if not normalized_external:
            return False
        if (
            self.db.query(CalendarEvent.id)
            .filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.external_event_id == normalized_external,
            )
            .first()
            is not None
        ):
            return True
        return (
            self.db.query(EntityReference.id)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == "event",
                EntityReference.ref == normalized_external,
            )
            .first()
        ) is not None

    def _task_source_resolved(self, task: Task) -> Optional[bool]:
        if task.thread_id:
            return self._thread_ref_resolved(task.thread_id)
        if task.message_id is None:
            return None
        return (
            self.db.query(Message.id)
            .filter(
                Message.user_id == self.user_id,
                Message.id == task.message_id,
            )
            .first()
        ) is not None

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

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _sortable_datetime(self, value: Any) -> datetime:
        parsed = self._parse_datetime(value) if not isinstance(value, datetime) else value
        if parsed is None:
            return datetime.min
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def _format_due_label(self, value: Any) -> Optional[str]:
        parsed = self._parse_datetime(value) if not isinstance(value, datetime) else value
        if parsed is None:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc)
            return parsed.strftime("Due %Y-%m-%d %H:%M UTC")
        return parsed.strftime("Due %Y-%m-%d %H:%M")

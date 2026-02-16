from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.data.models import (
    VaultNote,
    VaultLink,
    VaultMetricsDaily,
    CalendarEvent,
    Message,
    ThreadState,
)


class VaultContextService:
    MAX_TOKENS = 800
    CHARS_PER_TOKEN = 4

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def _record_hit(self, injected: bool, notes_referenced: int = 0):
        today = datetime.now(timezone.utc).date()
        metric = self.db.query(VaultMetricsDaily).filter(
            VaultMetricsDaily.user_id == self.user_id,
            VaultMetricsDaily.date == today
        ).first()
        if not metric:
            metric = VaultMetricsDaily(user_id=self.user_id, date=today)
            self.db.add(metric)
        metric.context_attempt_count = (metric.context_attempt_count or 0) + 1
        if injected:
            metric.context_injected_count = (metric.context_injected_count or 0) + 1
            metric.notes_referenced_count = (metric.notes_referenced_count or 0) + notes_referenced
        self.db.commit()

    def build_context_packet(
        self,
        participant_emails: Optional[List[str]] = None,
        topic_slugs: Optional[List[str]] = None,
        context_type: str = "drafting",
    ) -> str:
        participant_emails = [e.lower() for e in (participant_emails or []) if e]
        topic_slugs = topic_slugs or []

        notes: List[VaultNote] = []
        if participant_emails:
            notes.extend(
                self.db.query(VaultNote).filter(
                    VaultNote.user_id == self.user_id,
                    VaultNote.note_type == "person",
                    VaultNote.canonical_email.in_(participant_emails),
                    VaultNote.status == "active",
                ).all()
            )
        if topic_slugs:
            notes.extend(
                self.db.query(VaultNote).filter(
                    VaultNote.user_id == self.user_id,
                    VaultNote.slug.in_(topic_slugs),
                    VaultNote.status == "active",
                ).all()
            )

        unique_notes = {n.id: n for n in notes}
        if unique_notes:
            base_ids = list(unique_notes.keys())
            links = self.db.query(VaultLink).filter(
                VaultLink.user_id == self.user_id,
                (VaultLink.source_note_id.in_(base_ids)) | (VaultLink.target_note_id.in_(base_ids))
            ).all()
            neighbor_ids = set()
            for l in links:
                neighbor_ids.add(l.source_note_id)
                neighbor_ids.add(l.target_note_id)
            if neighbor_ids:
                neighbors = self.db.query(VaultNote).filter(
                    VaultNote.user_id == self.user_id,
                    VaultNote.id.in_(neighbor_ids),
                    VaultNote.status == "active",
                ).all()
                for n in neighbors:
                    unique_notes[n.id] = n

        sorted_notes = sorted(
            unique_notes.values(),
            key=lambda n: (
                0 if n.note_type == "commitment" else
                1 if n.note_type == "decision" else
                2 if n.note_type == "person" else 3,
                n.updated_at or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )

        max_chars = self.MAX_TOKENS * self.CHARS_PER_TOKEN
        lines: List[str] = []
        used = 0
        for note in sorted_notes:
            snippet = (note.body or "").strip()
            if len(snippet) > 280:
                snippet = snippet[:280] + "..."
            line = f"[{note.note_type}] {note.title}: {snippet}"
            if used + len(line) > max_chars:
                break
            lines.append(line)
            used += len(line)
            note.last_referenced_at = datetime.now(timezone.utc)

        injected = bool(lines)
        self._record_hit(injected=injected, notes_referenced=len(lines))
        if injected:
            self.db.commit()
            return "Vault context:\n" + "\n".join(lines)
        return ""

    def build_meeting_prep(self, event_id: int) -> Dict[str, Any]:
        event = self.db.query(CalendarEvent).filter(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == self.user_id,
        ).first()
        if not event:
            return {
                "summary": "Meeting not found.",
                "participants": [],
                "open_items": [],
                "decisions": [],
                "related_threads": [],
                "warnings": ["Meeting not found"],
            }

        participant_emails = []
        for p in event.participants or []:
            if isinstance(p, dict):
                email = p.get("email")
                if email:
                    participant_emails.append(email.lower())

        notes_context = self.build_context_packet(
            participant_emails=participant_emails,
            context_type="meeting_prep",
        )

        related_threads = self.db.query(ThreadState).filter(
            ThreadState.user_id == self.user_id
        ).order_by(ThreadState.updated_at.desc()).limit(10).all()

        open_items = []
        decisions = []
        for t in related_threads:
            open_items.extend([x.get("title") for x in (t.open_tasks or []) if isinstance(x, dict) and x.get("title")])
            decisions.extend([x.get("decision") for x in (t.decisions or []) if isinstance(x, dict) and x.get("decision")])

        return {
            "summary": notes_context or f"Prep for {event.title}",
            "participants": participant_emails,
            "open_items": open_items[:8],
            "decisions": decisions[:8],
            "related_threads": [
                {
                    "thread_id": t.thread_id,
                    "summary": t.summary,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in related_threads[:5]
            ],
            "warnings": [] if participant_emails else ["No participants found on event"],
        }

    def build_reply_context(self, thread_id: Optional[str], sender_email: Optional[str]) -> str:
        participants = [sender_email.lower()] if sender_email else []
        slugs: List[str] = []

        if thread_id:
            thread = self.db.query(ThreadState).filter(
                ThreadState.user_id == self.user_id,
                ThreadState.thread_id == thread_id
            ).first()
            if thread and thread.subject:
                slugs.append(thread.subject.lower().replace(" ", "-"))

        return self.build_context_packet(
            participant_emails=participants,
            topic_slugs=slugs,
            context_type="reply",
        )


"""Playground placeholder: vault context service (signatures only)."""

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
        _ = (injected, notes_referenced)
        return None

    def build_context_packet(
        self,
        participant_emails: Optional[List[str]] = None,
        topic_slugs: Optional[List[str]] = None,
        context_type: str = "drafting",
    ) -> str:
        _ = (participant_emails, topic_slugs, context_type)
        return ""

    def build_meeting_prep(self, event_id: int) -> Dict[str, Any]:
        _ = event_id
        return {
            "summary": "[playground] meeting prep placeholder",
            "participants": [],
            "open_items": [],
            "decisions": [],
            "related_threads": [],
            "warnings": [],
        }

    def build_reply_context(self, thread_id: Optional[str], sender_email: Optional[str]) -> str:
        _ = (thread_id, sender_email)
        return ""

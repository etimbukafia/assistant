from __future__ import annotations

from email.utils import getaddresses, parseaddr
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data.models import Contact, ThreadState
from app.services.contact_observability import log_contact_linkage_metric


def extract_sender_email(sender_value: Optional[str]) -> Optional[str]:
    raw = (sender_value or "").strip()
    if not raw:
        return None

    _, parsed_email = parseaddr(raw)
    candidate = (parsed_email or raw).strip().lower()
    if "@" not in candidate:
        return None
    return candidate


def extract_email_candidates(value: Optional[str]) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []

    emails: list[str] = []
    for _, email in getaddresses([raw]):
        normalized = extract_sender_email(email)
        if normalized and normalized not in emails:
            emails.append(normalized)
    fallback = extract_sender_email(raw)
    if fallback and fallback not in emails:
        emails.append(fallback)
    return emails
class ContactLinker:
    """
    Resolves canonical contacts from exact email matches in message headers and
    persists deterministic links to ingested messages/threads.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self._email_to_contact_id: dict[str, Optional[int]] = {}

    def resolve_contact_id(self, sender_value: Optional[str]) -> Optional[int]:
        return self.resolve_message_contact_id(sender_value=sender_value, source="generic")

    def resolve_message_contact_id(
        self,
        sender_value: Optional[str],
        recipient_value: Optional[str] = None,
        source: str = "unknown",
    ) -> Optional[int]:
        del recipient_value
        candidates = extract_email_candidates(sender_value)
        if not candidates:
            log_contact_linkage_metric(
                user_id=self.user_id,
                source=source,
                matched=False,
                resolution_method="no_email_candidate",
                candidate_count=0,
            )
            return None
        for email in candidates:
            contact_id = self._resolve_contact_id_by_email(email)
            if contact_id:
                log_contact_linkage_metric(
                    user_id=self.user_id,
                    source=source,
                    matched=True,
                    resolution_method="email_exact",
                    candidate_count=len(candidates),
                    contact_id=contact_id,
                )
                return contact_id
        log_contact_linkage_metric(
            user_id=self.user_id,
            source=source,
            matched=False,
            resolution_method="email_exact_miss",
            candidate_count=len(candidates),
        )
        return None

    def _resolve_contact_id_by_email(self, email: str) -> Optional[int]:
        if email in self._email_to_contact_id:
            return self._email_to_contact_id[email]
        contact = (
            self.db.query(Contact.id)
            .filter(
                Contact.user_id == self.user_id,
                Contact.email.isnot(None),
                func.lower(Contact.email) == email,
            )
            .first()
        )
        contact_id = int(contact[0]) if contact else None
        self._email_to_contact_id[email] = contact_id
        return contact_id

    def link_thread_state(self, thread_id: Optional[str], contact_id: Optional[int]) -> None:
        if not thread_id or not contact_id:
            return

        thread_state = (
            self.db.query(ThreadState)
            .filter(
                ThreadState.thread_id == thread_id,
                ThreadState.user_id == self.user_id,
            )
            .first()
        )
        if thread_state and thread_state.contact_id is None:
            thread_state.contact_id = contact_id

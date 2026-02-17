from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.data.models import ThreadState, ContactContext, VaultMetricsDaily, VaultProposal
from app.services.vault import VaultService


class VaultIngestionService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.vault_service = VaultService(db, user_id)

    def _score_significance(self, text: str, content_type: str) -> float:
        normalized = (text or "").lower().strip()
        score = 0.25

        high_signal_keywords = [
            "decide",
            "decision",
            "agreed",
            "commit",
            "deadline",
            "deliver",
            "owner",
            "next step",
            "follow up",
            "action item",
            "by ",
            "due ",
        ]
        score += min(0.55, sum(0.07 for k in high_signal_keywords if k in normalized))

        if any(token in normalized for token in ["tomorrow", "monday", "friday", "eod"]):
            score += 0.08
        if any(token in normalized for token in ["who", "owner", "assigned"]):
            score += 0.06

        if content_type == "commitment":
            score += 0.06
        if len(normalized.split()) >= 7:
            score += 0.04

        return min(score, 0.95)

    def _is_low_signal(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return True
        if len(normalized) < 16:
            return True
        weak_patterns = {
            "thanks",
            "noted",
            "sounds good",
            "ok",
            "yes",
            "done",
            "will do",
            "let's sync",
            "follow up",
        }
        return normalized in weak_patterns

    def _metric_increment(self, field: str, n: int = 1):
        today = datetime.now(timezone.utc).date()
        metric = self.db.query(VaultMetricsDaily).filter(
            VaultMetricsDaily.user_id == self.user_id,
            VaultMetricsDaily.date == today
        ).first()
        if not metric:
            metric = VaultMetricsDaily(user_id=self.user_id, date=today)
            self.db.add(metric)
        current = getattr(metric, field, 0) or 0
        setattr(metric, field, current + n)
        self.db.commit()

    def process_thread_state(self, thread_state: ThreadState) -> List[VaultProposal]:
        proposals: List[VaultProposal] = []

        for d in (thread_state.decisions or []):
            if not isinstance(d, dict):
                continue
            text = d.get("decision", "").strip()
            if not text:
                continue
            if self._is_low_signal(text):
                continue
            confidence = self._score_significance(text, "decision")
            if confidence < 0.45:
                continue
            proposals.append(
                self.vault_service.propose(
                    proposal_type="create_note",
                    proposed_data={
                        "note_type": "decision",
                        "title": text[:120],
                        "body": text,
                        "frontmatter": {
                            "thread_id": thread_state.thread_id,
                            "source": "email_processing",
                        },
                        "source": "email_extraction",
                    },
                    diff_summary=f"Add decision: {text[:180]}",
                    source_type="email_processing",
                    source_id=str(thread_state.thread_id),
                    confidence=confidence,
                )
            )

        for t in (thread_state.open_tasks or []):
            if not isinstance(t, dict):
                continue
            title = (t.get("title") or "").strip()
            if not title:
                continue
            if self._is_low_signal(title):
                continue
            confidence = self._score_significance(title, "commitment")
            if confidence < 0.45:
                continue
            proposals.append(
                self.vault_service.propose(
                    proposal_type="create_note",
                    proposed_data={
                        "note_type": "commitment",
                        "title": title[:120],
                        "body": title,
                        "frontmatter": {
                            "thread_id": thread_state.thread_id,
                            "source": "email_processing",
                        },
                        "source": "email_extraction",
                    },
                    diff_summary=f"Add commitment: {title[:180]}",
                    source_type="email_processing",
                    source_id=str(thread_state.thread_id),
                    confidence=confidence,
                )
            )

        # Suggest promotion for high-frequency contacts
        for p in (thread_state.participants or []):
            if not isinstance(p, dict):
                continue
            email = (p.get("email") or "").lower()
            if not email:
                continue
            contact = self.db.query(ContactContext).filter(
                ContactContext.user_id == self.user_id,
                ContactContext.contact_email == email,
            ).first()
            metadata = (contact.contact_metadata if contact else {}) or {}
            count = metadata.get("message_count", 0)
            if count >= 10 and (not contact or not contact.promoted):
                proposals.append(
                    self.vault_service.propose(
                        proposal_type="create_note",
                        proposed_data={
                            "note_type": "person",
                            "title": p.get("name") or email.split("@")[0],
                            "canonical_email": email,
                            "frontmatter": {"email": email},
                            "source": "email_extraction",
                        },
                        diff_summary=f"Promote contact to vault person: {email}",
                        source_type="email_processing",
                        source_id=str(thread_state.thread_id),
                        confidence=0.7,
                    )
                )

        if proposals:
            self._metric_increment("proposals_created_count", len(proposals))
        return proposals

"""Playground placeholder: vault ingestion service (signatures only)."""

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
        _ = (text, content_type)
        return 0.0

    def _is_low_signal(self, text: str) -> bool:
        _ = text
        return True

    def _metric_increment(self, field: str, n: int = 1):
        _ = (field, n)
        return None

    def process_thread_state(self, thread_state: ThreadState) -> List[VaultProposal]:
        _ = thread_state
        return []

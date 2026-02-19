"""Playground placeholder: vault handlers (signatures only)."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import text

from core.events import register_handler
from app.infra.database import SessionLocal
from app.data.models import ThreadState, TaskQueue
from app.jobs.queue import enqueue_task
from app.services.vault_ingestion import VaultIngestionService


logger = logging.getLogger(__name__)


@register_handler("message_processed")
async def enqueue_vault_ingestion(event: Dict[str, Any], payload: Dict[str, Any]):
    _ = (event, payload)
    return None


def get_next_vault_cleanup_time() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=1)


async def handle_vault_ingest(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    _ = (task_id, task_type, payload, correlation_id)
    return None


async def handle_vault_proposal_cleanup(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    _ = (task_id, task_type, payload, correlation_id)
    return None

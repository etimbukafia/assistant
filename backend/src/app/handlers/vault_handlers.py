import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import text

from core.events import register_handler
from app.infra.database import SessionLocal
from app.infra.config import get_settings
from app.data.models import ThreadState, TaskQueue
from app.jobs.queue import enqueue_task
from app.services.vault_ingestion import VaultIngestionService


logger = logging.getLogger(__name__)


@register_handler("message_processed")
async def enqueue_vault_ingestion(event: Dict[str, Any], payload: Dict[str, Any]):
    if not get_settings().PROPOSALS_ENABLED:
        return

    message_id = payload.get("message_id")
    user_id = payload.get("user_id")
    thread_id = payload.get("thread_id")

    if not message_id or not user_id:
        return

    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

        should_enqueue = (
            payload.get("task_count", 0) > 0 or
            payload.get("decision_count", 0) > 0 or
            payload.get("people_count", 0) > 0
        )
        if not should_enqueue:
            return

        enqueue_task(
            task_type="vault_ingest",
            payload={"user_id": user_id, "thread_id": thread_id, "message_id": message_id},
            correlation_id=event.get("correlation_id"),
            db=db,
        )
    finally:
        db.close()


def get_next_vault_cleanup_time() -> datetime:
    now = datetime.now(timezone.utc)
    return now + timedelta(days=1)


async def handle_vault_ingest(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    if not get_settings().PROPOSALS_ENABLED:
        return

    user_id = payload.get("user_id")
    thread_id = payload.get("thread_id")
    if not user_id or not thread_id:
        return

    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
        thread_state = db.query(ThreadState).filter(
            ThreadState.user_id == user_id,
            ThreadState.thread_id == thread_id,
        ).first()
        if not thread_state:
            return
        ingestion = VaultIngestionService(db, user_id)
        proposals = ingestion.process_thread_state(thread_state)
        logger.info(f"[{correlation_id}] Vault ingest created {len(proposals)} proposals")
    finally:
        db.close()


async def handle_vault_proposal_cleanup(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    if not get_settings().PROPOSALS_ENABLED:
        return

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        expired = db.query(TaskQueue).filter(
            TaskQueue.task_type == "vault_proposal_cleanup"
        ).count()  # no-op metric placeholder to avoid lints in bare workers
        _ = expired

        from app.data.models import VaultProposal
        count = db.query(VaultProposal).filter(
            VaultProposal.status == "pending",
            VaultProposal.created_at < cutoff,
        ).update({"status": "expired"}, synchronize_session=False)
        db.commit()
        logger.info(f"[{correlation_id}] Expired {count} stale vault proposals")

        enqueue_task(
            task_type="vault_proposal_cleanup",
            payload={},
            scheduled_for=get_next_vault_cleanup_time(),
            db=db,
        )
    finally:
        db.close()


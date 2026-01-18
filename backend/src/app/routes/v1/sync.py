from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.security.auth import get_current_user, get_db_for_user, AuthenticatedUser
from app.security.feature_gating import require_feature, Feature
from app.data.models import GmailAccount
from app.jobs.queue import enqueue_task

router = APIRouter(prefix="/gmail", tags=["Gmail Sync"])

@router.post("/sync/initial")
def trigger_initial_sync(
    user: AuthenticatedUser = Depends(require_feature(Feature.EMAIL_SYNC)),
    db: Session = Depends(get_db_for_user)
):
    """
    Trigger initial 24-hour email backfill.
    
    Called when:
    - First Gmail connection after trial activation
    - Returning subscriber after lapsed subscription
    """
    gmail_account = db.query(GmailAccount).filter(
        GmailAccount.user_id == user.id
    ).first()
    
    if not gmail_account:
        raise HTTPException(404, "No Gmail account connected")
    
    if gmail_account.initial_sync_completed:
        # Already synced, use incremental
        return {"status": "already_completed", "sync_type": "incremental"}
    
    # Queue 24-hour backfill job
    # We use 'email_backfill' task name which should be handled by the worker
    enqueue_task("email_backfill", {
        "user_id": user.id,
        "hours_back": 24,
        "gmail_account_id": gmail_account.id
    })
    
    # We don't set initial_sync_completed here; the worker should do it upon completion
    # But for now, to prevent loops if worker fails, we rely on the worker.
    
    return {"status": "queued", "sync_type": "initial", "hours_back": 24}

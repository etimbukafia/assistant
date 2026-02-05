from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.security.auth import get_user_settings, get_db_for_user, get_current_user, AuthenticatedUser
from app.security.feature_gating import require_feature, Feature
from app.data.models import UserSettings, Digest
from app.data.schemas import DigestPreferences, DigestsListResponse, DigestResponse
from app.jobs.worker import schedule_digest_jobs_if_needed
from app.jobs.queue import enqueue_task

router = APIRouter(prefix="/digests", tags=["Digests"])


@router.get("/settings")
def get_digest_preferences(
    settings: UserSettings = Depends(get_user_settings),
):
    """Get user's current digest preferences."""
    return {"preferences": settings.digest_preferences or {}}


@router.put("/settings")
def update_digest_preferences(
    preferences: DigestPreferences,
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user)
):
    """Update user's digest preferences and reschedule jobs."""
    
    settings.digest_preferences = preferences.dict()
    db.commit()
    
    # Reschedule digests based on new preferences
    schedule_digest_jobs_if_needed(db)
    
    return {"status": "updated", "preferences": preferences}


@router.get("/", response_model=DigestsListResponse)
def get_digests(
    limit: int = 10,
    digest_type: str = None,
    db: Session = Depends(get_db_for_user)
):
    """Get recent digests with optional type filter."""
    
    query = db.query(Digest).order_by(Digest.created_at.desc())
    
    if digest_type:
        query = query.filter(Digest.digest_type == digest_type)
    
    total = query.count()
    digests = query.limit(limit).all()
    
    return DigestsListResponse(digests=digests, total=total)


@router.get("/{digest_id}", response_model=DigestResponse)
def get_digest(digest_id: int, db: Session = Depends(get_db_for_user)):
    """Get a specific digest by ID."""
    
    digest = db.query(Digest).filter(Digest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest


@router.post("/generate/{digest_type}")
def trigger_digest_now(
    digest_type: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
    _gate=Depends(require_feature(Feature.DIGESTS)),
):
    """Manually trigger a digest generation."""
    
    if digest_type not in ["morning_briefing", "end_of_day", "weekly_review"]:
        raise HTTPException(status_code=400, detail="Invalid digest type")
    
    user_email = user.email
    
    enqueue_task(
        task_type="generate_digest",
        payload={"user_email": user_email, "digest_type": digest_type, "user_id": user.user_id},
        db=db
    )
    
    return {"status": "queued", "digest_type": digest_type}

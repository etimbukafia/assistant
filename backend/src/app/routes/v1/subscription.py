from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, get_db_for_user, AuthenticatedUser
from app.data.models import UserSettings

router = APIRouter(prefix="/subscription", tags=["Subscription"])

@router.post("/activate-trial")
def activate_trial(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """
    Activate 7-day free trial.
    
    Called when user explicitly chooses to sync their real data.
    """
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == user.user_id
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="User settings not found")

    # PRO users don't need trial activation
    if settings.subscription_tier == "pro":
        return {
            "status": "already_subscribed",
            "subscription_tier": "pro",
            "message": "You have an active Pro subscription"
        }

    # Check if already active or expired
    if settings.trial_ends_at:
        # If existing trial is in the future, return it
        if settings.trial_ends_at > datetime.now(timezone.utc):
            return {
                "status": "active",
                "trial_ends_at": settings.trial_ends_at.isoformat(),
                "days_remaining": settings.days_remaining
            }
        else:
            # Trial expired - guide user to upgrade instead of returning error
            return {
                "status": "trial_expired",
                "message": "Your trial has ended. Upgrade to Pro to continue.",
                "action": "checkout",
                "checkout_endpoint": "/billing/checkout"
            }

    # Activate trial
    settings.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)
    settings.subscription_status = "trialing"
    db.commit()
    
    return {
        "status": "activated",
        "trial_ends_at": settings.trial_ends_at.isoformat(),
        "days_remaining": 7
    }

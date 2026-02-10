from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, get_user_settings, get_db_for_user, AuthenticatedUser
from app.data.models import UserSettings

router = APIRouter(prefix="/subscription", tags=["Subscription"])

class ActivateTrialRequest(BaseModel):
    assistant_name: Optional[str] = None

@router.post("/activate-trial")
def activate_trial(
    request: ActivateTrialRequest = Body(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user)
):
    """
    Activate 7-day free trial.
    
    Called when user explicitly chooses to sync their real data.
    Uses get_user_settings which auto-creates the row for new users.
    """

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
                "days_remaining": settings.days_remaining,
                "assistant_name": settings.assistant_name or "Donna",
                "onboarding_completed": settings.onboarding_completed
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

    # Set assistant name if provided (optional during trial activation)
    if request and request.assistant_name:
        settings.assistant_name = request.assistant_name.strip()[:50] or "Donna"

    # NOTE: Don't set onboarding_completed here - that happens in the setup screen
    # Setting it prematurely causes race conditions with auth flow redirects

    # Initialize credits for trial
    from app.services.credits import initialize_credits_for_trial
    initialize_credits_for_trial(settings)

    db.commit()

    return {
        "status": "activated",
        "trial_ends_at": settings.trial_ends_at.isoformat(),
        "days_remaining": 7,
        "assistant_name": settings.assistant_name,
        "onboarding_completed": settings.onboarding_completed  # Return actual value
    }

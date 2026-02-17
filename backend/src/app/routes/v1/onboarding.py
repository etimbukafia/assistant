from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, get_db_for_user, AuthenticatedUser
from app.data.models import UserSettings

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

class CompleteOnboardingRequest(BaseModel):
    assistant_name: Optional[str] = "Teeks"

@router.post("/complete")
def complete_onboarding(
    request: CompleteOnboardingRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """
    Complete user onboarding (for Pro checkout flow).
    
    Sets assistant name and marks onboarding as completed.
    Called after user completes the onboarding flow via the bottom sheet.
    """
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == user.user_id
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="User settings not found")
    
    name = (request.assistant_name or "").strip()
    settings.assistant_name = name[:50] if name else "Teeks"
    settings.onboarding_completed = True
    db.commit()
    
    return {
        "status": "completed",
        "assistant_name": settings.assistant_name
    }

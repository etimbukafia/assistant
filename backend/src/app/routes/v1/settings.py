from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_user_settings, get_db_for_user
from app.models import UserSettings
from app.schemas import UserSettingsResponse, UserSettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/", response_model=UserSettingsResponse)
def get_settings(
    settings: UserSettings = Depends(get_user_settings)
):
    """Get current user settings. Auto-creates on first access."""
    return settings


@router.put("/", response_model=UserSettingsResponse)
def update_existing_settings(
    request: UserSettingsUpdateRequest,
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user)
):
    """Update user settings"""

    # Update fields
    if request.auto_approve_tasks is not None:
        settings.auto_approve_tasks = request.auto_approve_tasks
    if request.task_detection_instructions is not None:
        settings.task_detection_instructions = request.task_detection_instructions
    if request.reminder_preferences is not None:
        settings.reminder_preferences = request.reminder_preferences
    if request.enable_quick_reply_from_task is not None:
        settings.enable_quick_reply_from_task = request.enable_quick_reply_from_task

    db.commit()
    db.refresh(settings)
    return settings

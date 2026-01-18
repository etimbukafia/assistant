from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.security.auth import get_user_settings, get_db_for_user
from app.data.models import UserSettings
from app.data.schemas import UserSettingsResponse, UserSettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/", response_model=UserSettingsResponse)
def get_settings(
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user)
):
    """Get current user settings. Auto-creates on first access."""
    # Enriched response with Gmail account status
    from app.data.models import GmailAccount
    gmail_account = db.query(GmailAccount).filter(GmailAccount.user_id == settings.user_id).first()
    
    # We attach it to the settings object (schema will pick it up via from_attributes)
    # Note: simple assignment works because Pydantic getter will look for attributes
    settings.initial_sync_completed = gmail_account.initial_sync_completed if gmail_account else False
    
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

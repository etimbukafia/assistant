from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.security.auth import get_user_settings, get_db_for_user
from app.data.models import UserSettings
from app.data.schemas import UserSettingsResponse, UserSettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["Settings"])

def _enrich_settings_response(settings: UserSettings, db: Session) -> UserSettingsResponse:
    """Build enriched settings response with computed fields."""
    from app.data.models import GmailAccount
    gmail_account = db.query(GmailAccount).filter(GmailAccount.user_id == settings.user_id).first()

    return UserSettingsResponse(
        id=settings.id,
        user_email=settings.user_email,
        auto_approve_tasks=settings.auto_approve_tasks,
        task_detection_instructions=settings.task_detection_instructions,
        reminder_preferences=settings.reminder_preferences,
        notification_preferences=settings.notification_preferences or {},
        enable_quick_reply_from_task=settings.enable_quick_reply_from_task,
        # Subscription fields (from model properties)
        subscription_tier=settings.subscription_tier,
        subscription_status=settings.subscription_status,
        trial_ends_at=settings.trial_ends_at,
        is_active=settings.is_active,
        days_remaining=settings.days_remaining,
        # Personalization & Onboarding
        assistant_name=settings.assistant_name or "Donna",
        onboarding_completed=settings.onboarding_completed or False,
        # Integration status (computed)
        initial_sync_completed=gmail_account.initial_sync_completed if gmail_account else False,
        gmail_connected=gmail_account is not None,
        calendar_connected=bool(settings.calendar_ids),
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.get("/", response_model=UserSettingsResponse)
def get_settings(
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user)
):
    """Get current user settings. Auto-creates on first access."""
    return _enrich_settings_response(settings, db)


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
    if request.notification_preferences is not None:
        settings.notification_preferences = request.notification_preferences
    if request.enable_quick_reply_from_task is not None:
        settings.enable_quick_reply_from_task = request.enable_quick_reply_from_task

    db.commit()
    db.refresh(settings)
    return _enrich_settings_response(settings, db)

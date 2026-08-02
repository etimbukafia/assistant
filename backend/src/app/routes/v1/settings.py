import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.security.auth import get_user_settings, get_db_for_user
from app.data.models import UserSettings
from app.data.schemas import UserSettingsResponse, UserSettingsUpdateRequest
from app.services.warm_cache import get_warm_cache_service
from app.services.warm_context_snapshot import build_profile_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])

def _enrich_settings_response(settings: UserSettings, db: Session) -> UserSettingsResponse:
    """Build enriched settings response with computed fields."""
    from app.data.models import GmailAccount, OutlookAccount

    gmail_account = db.query(GmailAccount).filter(GmailAccount.user_id == settings.user_id).first()
    outlook_account = db.query(OutlookAccount).filter(OutlookAccount.user_id == settings.user_id).first()
    
    initial_sync_completed = gmail_account.initial_sync_completed if gmail_account else False
    initial_sync_failed = False
    
    # If Gmail is connected but sync hasn't completed, check if the backfill task permanently failed
    if gmail_account and not initial_sync_completed:
        try:
            from app.data.models import TaskQueue
            failed_task = db.query(TaskQueue).filter(
                TaskQueue.task_type == "email_backfill",
                TaskQueue.status == "failed",
                TaskQueue.user_id == settings.user_id,
            ).first()
            initial_sync_failed = failed_task is not None
        except Exception as e:
            logger.warning(f"Could not check sync failure status: {e}")

    return UserSettingsResponse(
        id=settings.id,
        user_email=settings.user_email,
        notification_email=settings.notification_email or settings.user_email,
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
        dunning_active=bool(settings.dunning_active),
        dunning_deadline_at=settings.dunning_deadline_at,
        dunning_days_remaining=settings.dunning_days_remaining,
        dunning_attempt_count=settings.dunning_attempt_count or 0,
        dunning_suspended_at=settings.dunning_suspended_at,
        # Personalization & Onboarding
        assistant_name=settings.assistant_name or "Teeks",
        onboarding_completed=settings.onboarding_completed or False,
        # Personal profile
        full_name=settings.full_name,
        preferred_name=settings.preferred_name,
        role=settings.role,
        personal_preferences=settings.personal_preferences,
        # Executive profile
        exec_full_name=settings.exec_full_name,
        exec_preferred_name=settings.exec_preferred_name,
        exec_role=settings.exec_role,
        exec_preferences=settings.exec_preferences,
        # Integration status (computed)
        initial_sync_completed=initial_sync_completed,
        initial_sync_failed=initial_sync_failed,
        gmail_connected=gmail_account is not None,
        outlook_connected=outlook_account is not None,
        calendar_connected=bool(settings.calendar_ids),
        connected_provider=settings.connected_provider,
        default_calendar_id=settings.default_calendar_id,
        auto_briefing_enabled=settings.auto_briefing_enabled,
        briefing_hours_before=settings.briefing_hours_before,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.get("/", response_model=UserSettingsResponse)
def get_settings(
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user)
):
    """Get current user settings. Auto-creates on first access."""
    try:
        get_warm_cache_service().get_or_build(
            tenant_id="default",
            user_id=settings.user_id,
            scope="profile",
            builder=lambda: build_profile_snapshot(db, settings.user_id),
        )
    except Exception:
        logger.debug("settings_profile_prewarm_failed user=%s", settings.user_id, exc_info=True)

    logger.info(
        f"Settings for user={settings.user_id}: "
        f"tier={settings.subscription_tier}, status={settings.subscription_status}, "
        f"trial_ends_at={settings.trial_ends_at}, is_active={settings.is_active}, "
        f"days_remaining={settings.days_remaining}, onboarding={settings.onboarding_completed}"
    )
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
    if request.assistant_name is not None:
        name = request.assistant_name.strip()
        settings.assistant_name = name[:50] if name else "Teeks"
    if request.notification_email is not None:
        email = request.notification_email.strip()
        settings.notification_email = email if email else None
    if request.default_calendar_id is not None:
        settings.default_calendar_id = request.default_calendar_id
    if request.auto_briefing_enabled is not None:
        settings.auto_briefing_enabled = request.auto_briefing_enabled
    if request.briefing_hours_before is not None:
        settings.briefing_hours_before = request.briefing_hours_before
    if request.full_name is not None:
        settings.full_name = request.full_name.strip() or None
    if request.preferred_name is not None:
        settings.preferred_name = request.preferred_name.strip() or None
    if request.role is not None:
        settings.role = request.role.strip() or None
    if request.personal_preferences is not None:
        settings.personal_preferences = request.personal_preferences.strip() or None
    if request.exec_full_name is not None:
        settings.exec_full_name = request.exec_full_name.strip() or None
    if request.exec_preferred_name is not None:
        settings.exec_preferred_name = request.exec_preferred_name.strip() or None
    if request.exec_role is not None:
        settings.exec_role = request.exec_role.strip() or None
    if request.exec_preferences is not None:
        settings.exec_preferences = request.exec_preferences.strip() or None

    db.commit()
    db.refresh(settings)
    get_warm_cache_service().invalidate_scope(
        tenant_id="default",
        user_id=settings.user_id,
        scope="profile",
    )
    return _enrich_settings_response(settings, db)

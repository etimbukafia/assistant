"""
Trial Expiration Warning Notifications

Scheduled job that sends push notifications to users when their trial is about to expire.
Runs daily and sends notifications at key milestones:
- 3 days remaining
- 1 day remaining  
- Trial expired (grace period started)
- Grace period ending (1 day left)

Expected impact: +15-25% trial conversion (industry benchmark).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.data.models import UserSettings
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)

# Grace period matches feature_gating.py
GRACE_PERIOD_DAYS = 3


# Notification content for each milestone
NOTIFICATION_CONFIG = {
    "3_days": {
        "title": "Your trial expires in 3 days",
        "body": "Upgrade now to keep your AI assistant working for you. Tap to continue with Pro.",
    },
    "1_day": {
        "title": "Your trial expires tomorrow",
        "body": "Don't lose access to email summaries, tasks, and smart reminders. Upgrade today!",
    },
    "expired": {
        "title": "Your trial has ended",
        "body": "You have 3 days of grace period remaining. Upgrade to restore full access.",
    },
    "grace_ending": {
        "title": "Last chance: Access ends tomorrow",
        "body": "After tomorrow, you'll be limited to sandbox mode. Tap to upgrade now.",
    },
}


def get_next_trial_check_time() -> datetime:
    """
    Calculate next run time for trial expiration check.
    
    Runs daily at 9 AM UTC to catch users in most timezones during business hours.
    """
    now = datetime.now(timezone.utc)
    
    # Next 9 AM UTC
    next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    
    return next_run


def _get_users_for_milestone(
    db: Session, 
    milestone: str, 
    now: datetime
) -> List[UserSettings]:
    """
    Query users who should receive a notification for a specific milestone.
    
    Returns users who:
    - Are on trial tier
    - Haven't received this milestone's notification yet
    - Fall within the time window for this milestone
    """
    base_filters = [
        UserSettings.subscription_tier == "trial",
        UserSettings.trial_ends_at.isnot(None),
    ]
    
    if milestone == "3_days":
        # Trial ends between 2 and 3 days from now
        return db.query(UserSettings).filter(
            *base_filters,
            UserSettings.trial_ends_at.between(
                now + timedelta(days=2), 
                now + timedelta(days=3)
            ),
            or_(
                UserSettings.last_trial_warning_milestone.is_(None),
                UserSettings.last_trial_warning_milestone != "3_days"
            )
        ).all()
    
    elif milestone == "1_day":
        # Trial ends between 0 and 1 day from now
        return db.query(UserSettings).filter(
            *base_filters,
            UserSettings.trial_ends_at.between(now, now + timedelta(days=1)),
            or_(
                UserSettings.last_trial_warning_milestone.is_(None),
                ~UserSettings.last_trial_warning_milestone.in_(["1_day", "expired", "grace_ending"])
            )
        ).all()
    
    elif milestone == "expired":
        # Trial ended, but still in grace period (0 to 3 days ago)
        return db.query(UserSettings).filter(
            *base_filters,
            UserSettings.trial_ends_at < now,
            UserSettings.trial_ends_at > now - timedelta(days=GRACE_PERIOD_DAYS),
            UserSettings.subscription_status != "expired",
            or_(
                UserSettings.last_trial_warning_milestone.is_(None),
                ~UserSettings.last_trial_warning_milestone.in_(["expired", "grace_ending"])
            )
        ).all()
    
    elif milestone == "grace_ending":
        # Grace period ends in ~1 day (trial ended 2-3 days ago)
        return db.query(UserSettings).filter(
            *base_filters,
            UserSettings.trial_ends_at.between(
                now - timedelta(days=GRACE_PERIOD_DAYS),
                now - timedelta(days=GRACE_PERIOD_DAYS - 1)
            ),
            UserSettings.subscription_status != "expired",
            or_(
                UserSettings.last_trial_warning_milestone.is_(None),
                UserSettings.last_trial_warning_milestone != "grace_ending"
            )
        ).all()
    
    return []


def _send_trial_warning(
    db: Session, 
    user: UserSettings, 
    milestone: str,
    correlation_id: str = None
) -> bool:
    """
    Send a trial warning notification to a user.
    
    Returns True if notification was created successfully.
    """
    config = NOTIFICATION_CONFIG.get(milestone)
    if not config:
        logger.warning(f"Unknown milestone: {milestone}")
        return False
    
    try:
        service = NotificationService(db, user.user_id)
        service.create_notification(
            title=config["title"],
            body=config["body"],
            category="system",
            priority="high",  # Ensures push notification is sent
            target_type="settings",
            target_id="subscription",  # Deep links to subscription screen
            send_push=True,
        )
        
        # Update tracking fields
        user.last_trial_warning_sent = datetime.now(timezone.utc)
        user.last_trial_warning_milestone = milestone
        
        logger.info(
            f"[{correlation_id}] Sent '{milestone}' trial warning to user {user.user_id}",
            extra={"user_id": user.user_id, "milestone": milestone}
        )
        return True
        
    except Exception as e:
        logger.error(
            f"[{correlation_id}] Failed to send trial warning to user {user.user_id}: {e}",
            exc_info=True
        )
        return False


async def handle_check_trial_expirations(
    task_id: int, 
    task_type: str, 
    payload: Dict, 
    correlation_id: str
):
    """
    Handler for 'check_trial_expirations' scheduled tasks.
    
    Runs daily to find users at each trial milestone and send appropriate
    warning notifications. Self-reschedules for the next day.
    """
    from app.infra.database import SessionLocal
    from app.jobs.queue import enqueue_task
    
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    
    try:
        total_sent = 0
        milestone_counts = {}
        
        # Process each milestone in order (most urgent first for logging)
        for milestone in ["grace_ending", "expired", "1_day", "3_days"]:
            users = _get_users_for_milestone(db, milestone, now)
            sent_count = 0
            
            for user in users:
                if _send_trial_warning(db, user, milestone, correlation_id):
                    sent_count += 1
            
            if sent_count > 0:
                db.commit()
                milestone_counts[milestone] = sent_count
                total_sent += sent_count
                logger.info(
                    f"[{correlation_id}] Sent {sent_count} '{milestone}' notifications"
                )
        
        if total_sent > 0:
            logger.info(
                f"[{correlation_id}] Trial warning check complete: {total_sent} notifications sent",
                extra={"milestone_counts": milestone_counts}
            )
        else:
            logger.debug(f"[{correlation_id}] Trial warning check complete: no notifications needed")
        
        # Self-reschedule for next run
        next_run = get_next_trial_check_time()
        enqueue_task(
            task_type="check_trial_expirations",
            payload={},
            scheduled_for=next_run,
            db=db
        )
        db.commit()  # Ensure task is committed
        logger.info(f"[{correlation_id}] Next trial check scheduled for {next_run}")
        
    except Exception as e:
        logger.error(
            f"[{correlation_id}] Trial expiration check failed: {e}",
            exc_info=True
        )
        db.rollback()
        raise
    finally:
        db.close()

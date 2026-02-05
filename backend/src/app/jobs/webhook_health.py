"""
Webhook Health Check

Scheduled job that monitors webhook delivery health.
Runs every 6 hours and logs warnings when:
- No Polar webhooks received in 48 hours
- No Gmail webhooks received in 24 hours (when active accounts exist)
- Polar webhook error rate exceeds 20% in last 24 hours
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data.models import WebhookLog, GmailAccount, Message

logger = logging.getLogger(__name__)


def get_next_webhook_health_check_time() -> datetime:
    """Next run time: every 6 hours, on the hour."""
    now = datetime.now(timezone.utc)
    # Round up to next 6-hour boundary
    hour = now.hour
    next_hour = ((hour // 6) + 1) * 6
    next_run = now.replace(hour=next_hour % 24, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(hours=6)
    return next_run


def _check_source_health(db: Session, source: str, max_gap_hours: int, now: datetime) -> bool:
    """Check if a webhook source has recent activity. Returns True if healthy."""
    last = db.query(WebhookLog).filter(
        WebhookLog.source == source,
    ).order_by(WebhookLog.received_at.desc()).first()

    if not last:
        logger.warning(f"WEBHOOK HEALTH: No {source} webhooks ever recorded")
        return False

    gap = now - last.received_at
    if gap > timedelta(hours=max_gap_hours):
        logger.warning(
            f"WEBHOOK HEALTH: No {source} webhooks received in {gap.total_seconds() / 3600:.1f} hours "
            f"(threshold: {max_gap_hours}h). Last received: {last.received_at.isoformat()}"
        )
        return False

    return True


def _check_error_rate(db: Session, source: str, window_hours: int, threshold: float, now: datetime) -> bool:
    """Check webhook error rate. Returns True if healthy."""
    since = now - timedelta(hours=window_hours)

    total = db.query(func.count(WebhookLog.id)).filter(
        WebhookLog.source == source,
        WebhookLog.received_at >= since,
    ).scalar() or 0

    if total == 0:
        return True  # No data, gap check handles this

    errors = db.query(func.count(WebhookLog.id)).filter(
        WebhookLog.source == source,
        WebhookLog.received_at >= since,
        WebhookLog.processed == False,
    ).scalar() or 0

    rate = errors / total
    if rate > threshold:
        logger.warning(
            f"WEBHOOK HEALTH: {source} error rate {rate:.0%} ({errors}/{total}) "
            f"in last {window_hours}h exceeds {threshold:.0%} threshold"
        )
        return False

    return True


async def handle_check_webhook_health(
    task_id: int,
    task_type: str,
    payload: Dict,
    correlation_id: str
):
    """
    Handler for 'check_webhook_health' scheduled tasks.

    Checks webhook delivery health and logs warnings for ops monitoring.
    Self-reschedules for the next run.
    """
    from app.infra.database import SessionLocal
    from app.jobs.queue import enqueue_task

    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        issues = []

        # Check Polar webhook gap (48h threshold — billing events are infrequent)
        if not _check_source_health(db, "polar", 48, now):
            issues.append("polar_gap")

        # Check Gmail webhook gap (24h — should be frequent if accounts are active)
        active_accounts = db.query(func.count(GmailAccount.id)).filter(
            GmailAccount.user_id.isnot(None),
        ).scalar() or 0

        if active_accounts > 0 and not _check_source_health(db, "gmail", 24, now):
            issues.append("gmail_gap")

        # Check Polar error rate (>20% in last 24h)
        if not _check_error_rate(db, "polar", 24, 0.2, now):
            issues.append("polar_errors")

        # Check AI fallback rate (>10% in last 6h)
        since_6h = now - timedelta(hours=6)
        ai_total = db.query(func.count(Message.id)).filter(
            Message.processed == True,
            Message.received_at >= since_6h,
        ).scalar() or 0

        if ai_total > 0:
            ai_fallbacks = db.query(func.count(Message.id)).filter(
                Message.processed == True,
                Message.ai_fallback == True,
                Message.received_at >= since_6h,
            ).scalar() or 0
            fallback_rate = ai_fallbacks / ai_total
            if fallback_rate > 0.1:
                logger.warning(
                    f"AI HEALTH: Fallback rate {fallback_rate:.0%} ({ai_fallbacks}/{ai_total}) "
                    f"in last 6h exceeds 10% threshold"
                )
                issues.append("ai_fallback_rate")

        if not issues:
            logger.debug(f"[{correlation_id}] Webhook health check passed")
        else:
            logger.warning(f"[{correlation_id}] Webhook health issues: {', '.join(issues)}")

        # Self-reschedule
        next_run = get_next_webhook_health_check_time()
        enqueue_task(
            task_type="check_webhook_health",
            payload={},
            scheduled_for=next_run,
            db=db
        )
        db.commit()
        logger.info(f"[{correlation_id}] Next webhook health check scheduled for {next_run}")

    except Exception as e:
        logger.error(f"[{correlation_id}] Webhook health check failed: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

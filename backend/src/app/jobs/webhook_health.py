"""
Webhook Health Check

Scheduled job that monitors webhook delivery health.
Runs every 6 hours and logs warnings when:
- No billing webhooks (active provider) received in 48 hours
- No Gmail webhooks received in 24 hours (when active accounts exist)
- No Outlook webhooks received in 24 hours (when active accounts exist)
- Billing webhook error rate exceeds 20% in last 24 hours
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data.models import GmailAccount, Message, OutlookAccount, WebhookLog
from app.infra.config import get_settings

logger = logging.getLogger(__name__)


def get_next_webhook_health_check_time() -> datetime:
    """Next run time: every 6 hours, on the hour."""
    now = datetime.now(timezone.utc)
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
        logger.warning("WEBHOOK HEALTH: No %s webhooks ever recorded", source)
        return False

    gap = now - last.received_at
    if gap > timedelta(hours=max_gap_hours):
        logger.warning(
            "WEBHOOK HEALTH: No %s webhooks received in %.1f hours (threshold: %sh). Last received: %s",
            source,
            gap.total_seconds() / 3600,
            max_gap_hours,
            last.received_at.isoformat(),
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
        return True

    errors = db.query(func.count(WebhookLog.id)).filter(
        WebhookLog.source == source,
        WebhookLog.received_at >= since,
        WebhookLog.processed == False,
    ).scalar() or 0

    rate = errors / total
    if rate > threshold:
        logger.warning(
            "WEBHOOK HEALTH: %s error rate %.0f%% (%s/%s) in last %sh exceeds %.0f%% threshold",
            source,
            rate * 100,
            errors,
            total,
            window_hours,
            threshold * 100,
        )
        return False

    return True


async def handle_check_webhook_health(
    task_id: int,
    task_type: str,
    payload: Dict,
    correlation_id: str,
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
        issues: list[str] = []
        billing_source = (get_settings().BILLING_PROVIDER or "dodo").strip().lower()

        if not _check_source_health(db, billing_source, 48, now):
            issues.append(f"{billing_source}_gap")

        active_gmail_accounts = db.query(func.count(GmailAccount.id)).filter(
            GmailAccount.user_id.isnot(None),
        ).scalar() or 0

        if active_gmail_accounts > 0 and not _check_source_health(db, "gmail", 24, now):
            issues.append("gmail_gap")

        active_outlook_accounts = db.query(func.count(OutlookAccount.id)).filter(
            OutlookAccount.user_id.isnot(None),
        ).scalar() or 0

        if active_outlook_accounts > 0 and not _check_source_health(db, "outlook", 24, now):
            issues.append("outlook_gap")

        if not _check_error_rate(db, billing_source, 24, 0.2, now):
            issues.append(f"{billing_source}_errors")

        if active_outlook_accounts > 0 and not _check_error_rate(db, "outlook", 24, 0.2, now):
            issues.append("outlook_errors")

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
                    "AI HEALTH: Fallback rate %.0f%% (%s/%s) in last 6h exceeds 10%% threshold",
                    fallback_rate * 100,
                    ai_fallbacks,
                    ai_total,
                )
                issues.append("ai_fallback_rate")

        if not issues:
            logger.debug("[%s] Webhook health check passed", correlation_id)
        else:
            logger.warning("[%s] Webhook health issues: %s", correlation_id, ", ".join(issues))

        next_run = get_next_webhook_health_check_time()
        enqueue_task(
            task_type="check_webhook_health",
            payload={},
            scheduled_for=next_run,
            db=db,
        )
        db.commit()
        logger.info("[%s] Next webhook health check scheduled for %s", correlation_id, next_run)

    except Exception as exc:
        logger.error("[%s] Webhook health check failed: %s", correlation_id, exc, exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

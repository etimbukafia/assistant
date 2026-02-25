"""
Dunning service.

Implements a calm payment-recovery experience:
- Track dunning lifecycle state
- Send staged reminders
- Pause access after unresolved recovery window
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.data.models import Notification, UserSettings
from app.infra.config import get_settings
from app.services.billing_provider import NormalizedBillingEvent

logger = logging.getLogger(__name__)

STAGE_INITIAL = "initial"
STAGE_MIDPOINT = "midpoint"
STAGE_FINAL = "final"
_VALID_STAGES = {STAGE_INITIAL, STAGE_MIDPOINT, STAGE_FINAL}

FAILED_EVENT_TYPES = {"invoice.payment_failed", "payment.failed"}
RECOVERY_EVENT_TYPES = {"invoice.paid", "payment.succeeded", "subscription.active", "subscription.uncanceled"}


@dataclass
class DunningWindow:
    window_days: int
    midpoint_day: int
    expected_retries: int


def _window() -> DunningWindow:
    settings = get_settings()
    window_days = max(1, int(getattr(settings, "DUNNING_WINDOW_DAYS", 7) or 7))
    midpoint_day = max(1, int(getattr(settings, "DUNNING_MIDPOINT_DAY", 3) or 3))
    midpoint_day = min(midpoint_day, window_days)
    expected_retries = max(1, int(getattr(settings, "DUNNING_EXPECTED_RETRIES", 3) or 3))
    return DunningWindow(
        window_days=window_days,
        midpoint_day=midpoint_day,
        expected_retries=expected_retries,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_dt(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_failure_event(event: NormalizedBillingEvent) -> bool:
    if event.event_type in FAILED_EVENT_TYPES:
        return True
    return (event.subscription_status or "").strip().lower() == "past_due"


def is_recovery_event(event: NormalizedBillingEvent) -> bool:
    if event.event_type in RECOVERY_EVENT_TYPES:
        return True
    status = (event.subscription_status or "").strip().lower()
    return status in {"active", "trialing"}


def clear_dunning_state(user: UserSettings) -> None:
    user.dunning_active = False
    user.dunning_started_at = None
    user.dunning_deadline_at = None
    user.dunning_attempt_count = 0
    user.dunning_last_notified_stage = None
    user.dunning_last_payment_failed_at = None
    user.dunning_suspended_at = None


def apply_failure_state(user: UserSettings, event: NormalizedBillingEvent, *, now: Optional[datetime] = None) -> str | None:
    """
    Apply dunning failure progression.

    Returns reminder stage to send immediately, if any.
    """
    if user.subscription_tier != "pro":
        return None

    current = _normalize_dt(now) or _now()
    cfg = _window()

    if not user.dunning_active:
        user.dunning_active = True
        user.dunning_started_at = current
        user.dunning_deadline_at = current + timedelta(days=cfg.window_days)
        user.dunning_attempt_count = 1
        user.dunning_last_payment_failed_at = current
        user.dunning_suspended_at = None
        if user.subscription_status == "active":
            user.subscription_status = "past_due"
        return STAGE_INITIAL

    user.dunning_active = True
    user.dunning_attempt_count = (user.dunning_attempt_count or 0) + 1
    user.dunning_last_payment_failed_at = current
    if not user.dunning_started_at:
        user.dunning_started_at = current
    if not user.dunning_deadline_at:
        user.dunning_deadline_at = user.dunning_started_at + timedelta(days=cfg.window_days)
    if user.subscription_status == "active":
        user.subscription_status = "past_due"
    return None


def stage_due_for_user(user: UserSettings, *, now: Optional[datetime] = None) -> str | None:
    """
    Determine whether a reminder stage is due for this user.
    """
    if not user.dunning_active:
        return None

    if user.dunning_suspended_at:
        return None

    started_at = _normalize_dt(user.dunning_started_at)
    deadline_at = _normalize_dt(user.dunning_deadline_at)
    if started_at is None:
        return STAGE_INITIAL

    current = _normalize_dt(now) or _now()
    cfg = _window()
    elapsed_days = max(0.0, (current - started_at).total_seconds() / 86400.0)

    if deadline_at and current >= deadline_at:
        if user.dunning_last_notified_stage != STAGE_FINAL:
            return STAGE_FINAL
        return None

    if elapsed_days >= cfg.midpoint_day and user.dunning_last_notified_stage in {None, STAGE_INITIAL}:
        return STAGE_MIDPOINT

    if user.dunning_last_notified_stage is None:
        return STAGE_INITIAL

    return None


def should_suspend_access(user: UserSettings, *, now: Optional[datetime] = None) -> bool:
    if not user.dunning_active:
        return False
    if user.dunning_suspended_at:
        return False
    deadline_at = _normalize_dt(user.dunning_deadline_at)
    if not deadline_at:
        return False
    current = _normalize_dt(now) or _now()
    return current >= deadline_at


def suspend_access(user: UserSettings, *, now: Optional[datetime] = None) -> None:
    current = _normalize_dt(now) or _now()
    user.dunning_suspended_at = current
    user.subscription_status = "past_due"


def _stage_copy(stage: str, *, days_remaining: int, attempt_count: int, expected_retries: int) -> tuple[str, str]:
    if stage == STAGE_INITIAL:
        return (
            "Payment update needed to keep Pro active",
            (
                "We couldn't process your latest payment. "
                f"We'll keep trying automatically ({min(attempt_count, expected_retries)}/{expected_retries}). "
                "Please update your payment method to keep your Pro workspace uninterrupted."
            ),
        )
    if stage == STAGE_MIDPOINT:
        return (
            "Payment still needs attention",
            (
                f"We're still unable to process your payment. "
                f"Automatic retries are in progress ({min(attempt_count, expected_retries)}/{expected_retries}). "
                f"You have about {max(1, days_remaining)} day(s) before Pro is paused."
            ),
        )
    return (
        "Pro is paused until payment is updated",
        "We paused Pro features for now. Update your payment method to restore access immediately.",
    )


def _send_reminder_email(db: Session, user: UserSettings, *, subject: str, body: str) -> bool:
    recipient = (user.notification_email or user.user_email or "").strip()
    if not recipient:
        return False

    html_body = f"<p>{body}</p><p>Please open Teeks and update your billing method.</p>"
    provider = (user.connected_provider or "none").strip().lower()

    try:
        if provider == "google":
            from app.integrations.gmail import GmailClient
            gmail = GmailClient(db=db, user_id=user.user_id)
            if not gmail.load_credentials():
                return False
            gmail.send_message(to=recipient, subject=subject, body=html_body, html=True)
            return True

        if provider == "microsoft":
            from app.integrations.outlook import OutlookClient
            outlook = OutlookClient(db=db, user_id=user.user_id)
            if not outlook.load_credentials():
                return False
            outlook.send_message(subject=subject, body=html_body, to=[recipient])
            return True
    except Exception as exc:
        logger.warning("Failed to send dunning email user=%s provider=%s error=%s", user.user_id, provider, exc)
        return False

    return False


def notify_stage(db: Session, user: UserSettings, stage: str) -> None:
    """
    Send in-app reminder and best-effort email for a dunning stage.
    """
    if stage not in _VALID_STAGES:
        return
    if user.dunning_last_notified_stage == stage:
        return

    days_remaining = max(0, user.dunning_days_remaining)
    cfg = _window()
    attempt_count = max(1, int(user.dunning_attempt_count or 0))
    subject, body = _stage_copy(
        stage,
        days_remaining=days_remaining,
        attempt_count=attempt_count,
        expected_retries=cfg.expected_retries,
    )

    # In-app notification is primary.
    db.add(
        Notification(
            user_id=user.user_id,
            title=subject,
            body=body,
            category="billing",
            priority="normal",
            target_type="settings",
            target_id=None,
        )
    )

    email_sent = _send_reminder_email(db, user, subject=subject, body=body)
    if not email_sent:
        logger.info("Dunning email not sent user=%s stage=%s provider=%s", user.user_id, stage, user.connected_provider)

    user.dunning_last_notified_stage = stage

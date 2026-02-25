"""
Subscription access helpers.

Per-feature flags have been removed. Access policy is now:
- active subscription/trial -> access
- pro grace window -> access
- dunning suspension -> blocked
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

# Defaults (can be overridden via env in app config)
DEFAULT_PRO_GRACE_DAYS = 4

# Clock skew tolerance for time comparisons (handles drift between app server and DB)
CLOCK_SKEW_TOLERANCE = timedelta(seconds=30)


def _is_in_grace_period(settings) -> bool:
    """
    Check grace period eligibility for pro users.

    Trial has no grace by policy.
    """
    now = datetime.now(timezone.utc) - CLOCK_SKEW_TOLERANCE

    if settings.subscription_tier == "trial":
        return False

    if settings.subscription_expires_at:
        try:
            from app.infra.config import get_settings

            pro_grace_days = max(0, int(getattr(get_settings(), "PRO_GRACE_DAYS", DEFAULT_PRO_GRACE_DAYS)))
        except Exception:
            pro_grace_days = DEFAULT_PRO_GRACE_DAYS

        grace_end = settings.subscription_expires_at + timedelta(days=pro_grace_days)
        if now <= grace_end:
            return True

    return False


def has_subscription_access(settings) -> bool:
    """Single source of truth for paid/trial access checks."""
    return bool(settings.is_active or _is_in_grace_period(settings))


def get_access_status(settings) -> dict:
    """
    Detailed access status for UI/debug surfaces.
    """
    now = datetime.now(timezone.utc)
    in_grace = _is_in_grace_period(settings)

    grace_days_remaining = 0
    if in_grace and settings.subscription_expires_at:
        try:
            from app.infra.config import get_settings

            pro_grace_days = max(0, int(getattr(get_settings(), "PRO_GRACE_DAYS", DEFAULT_PRO_GRACE_DAYS)))
        except Exception:
            pro_grace_days = DEFAULT_PRO_GRACE_DAYS
        grace_end = settings.subscription_expires_at + timedelta(days=pro_grace_days)
        grace_days_remaining = max(0, (grace_end - now).days)

    return {
        "tier": settings.subscription_tier,
        "status": settings.subscription_status,
        "is_active": settings.is_active,
        "has_subscription_access": has_subscription_access(settings),
        "days_remaining": settings.days_remaining,
        "dunning_active": bool(settings.dunning_active),
        "dunning_suspended_at": settings.dunning_suspended_at.isoformat() if settings.dunning_suspended_at else None,
        "in_grace_period": in_grace,
        "grace_days_remaining": grace_days_remaining,
    }

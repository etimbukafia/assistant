"""
Credit service for AI usage gating.

Manages user credits for Gemini AI operations:
- Trial users: 100 credits = $1.00 USD
- Pro users: 500 credits = $5.00 USD

Credits are only consumed by Gemini models (not Gemma).
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.data.models import UserSettings

logger = logging.getLogger(__name__)

# Credit limits in USD
TRIAL_CREDIT_LIMIT = 1.0  # $1.00 = 100 credits
PRO_CREDIT_LIMIT = 5.0    # $5.00 = 500 credits


def get_credit_limit_for_tier(tier: str) -> float:
    """Get credit limit in USD for a subscription tier."""
    if tier == "pro":
        return PRO_CREDIT_LIMIT
    return TRIAL_CREDIT_LIMIT


def check_credits_available(settings: UserSettings) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if user has credits remaining for AI operations.

    Args:
        settings: UserSettings instance

    Returns:
        Tuple of (can_proceed, error_details)
        - can_proceed: True if user can start new AI operation
        - error_details: Dict with usage info (used for error response)
    """
    credits_used = settings.credits_used or 0.0
    credits_limit = settings.credits_limit or TRIAL_CREDIT_LIMIT
    credits_remaining = max(0.0, credits_limit - credits_used)

    error_details = {
        "credits_used": credits_used,
        "credits_limit": credits_limit,
        "credits_remaining": credits_remaining,
        "tier": settings.subscription_tier,
    }

    if credits_remaining <= 0:
        return False, error_details

    return True, error_details


def add_credit_usage(
    db: Session,
    user_id: str,
    cost_usd: float
) -> None:
    """
    Add credit usage to user's current period.

    Called after recording token usage for Gemini models.

    Args:
        db: Database session
        user_id: User ID
        cost_usd: Cost in USD to add
    """
    if cost_usd <= 0:
        return

    settings = db.query(UserSettings).filter(
        UserSettings.user_id == user_id
    ).first()

    if not settings:
        logger.warning(f"Cannot add credit usage: no settings for user {user_id}")
        return

    current_used = settings.credits_used or 0.0
    settings.credits_used = current_used + cost_usd

    logger.debug(
        f"Credit usage updated for user {user_id}: "
        f"{current_used:.4f} -> {settings.credits_used:.4f} USD"
    )


def reset_credits(
    settings: UserSettings,
    new_limit: float = None
) -> None:
    """
    Reset credits for a new billing period.

    Args:
        settings: UserSettings instance
        new_limit: Optional new limit (defaults to tier-based limit)
    """
    if new_limit is None:
        new_limit = get_credit_limit_for_tier(settings.subscription_tier)

    settings.credits_used = 0.0
    settings.credits_limit = new_limit
    settings.credits_period_start = datetime.now(timezone.utc)

    logger.info(
        f"Credits reset for user {settings.user_id}: "
        f"limit={new_limit} USD, tier={settings.subscription_tier}"
    )


def initialize_credits_for_trial(settings: UserSettings) -> None:
    """
    Initialize credits for a new trial user.

    Args:
        settings: UserSettings instance
    """
    settings.credits_used = 0.0
    settings.credits_limit = TRIAL_CREDIT_LIMIT
    settings.credits_period_start = datetime.now(timezone.utc)

    logger.info(f"Credits initialized for trial user {settings.user_id}")


def initialize_credits_for_pro(settings: UserSettings) -> None:
    """
    Initialize credits for a new Pro subscriber.

    Args:
        settings: UserSettings instance
    """
    settings.credits_used = 0.0
    settings.credits_limit = PRO_CREDIT_LIMIT
    settings.credits_period_start = datetime.now(timezone.utc)

    logger.info(f"Credits initialized for Pro user {settings.user_id}")


def get_credit_status(settings: UserSettings) -> Dict[str, Any]:
    """
    Get detailed credit status for a user.

    Args:
        settings: UserSettings instance

    Returns:
        Dict with credit usage details
    """
    credits_used = settings.credits_used or 0.0
    credits_limit = settings.credits_limit or TRIAL_CREDIT_LIMIT
    credits_remaining = max(0.0, credits_limit - credits_used)

    percentage_used = (credits_used / credits_limit * 100) if credits_limit > 0 else 100.0

    return {
        "credits_used": round(credits_used, 4),
        "credits_limit": round(credits_limit, 4),
        "credits_remaining": round(credits_remaining, 4),
        "percentage_used": round(percentage_used, 2),
        "is_exhausted": credits_remaining <= 0,
        "period_start": settings.credits_period_start.isoformat() if settings.credits_period_start else None,
        "tier": settings.subscription_tier,
    }


def is_gemini_model(model_name: str) -> bool:
    """
    Check if a model name is a Gemini model (not Gemma).

    Gemini models consume credits, Gemma models are free.

    Args:
        model_name: Model name string

    Returns:
        True if this is a billable Gemini model
    """
    if not model_name:
        return False

    model_lower = model_name.lower()

    # Gemma models are free - don't count
    if model_lower.startswith("gemma"):
        return False

    # Gemini models are paid
    if model_lower.startswith("gemini"):
        return True

    # Unknown model - don't count to be safe
    return False

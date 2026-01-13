"""
Feature Gating Module

Centralized feature access control based on subscription tier and status.

Features:
- All features available during trial (7 days)
- All features available for Pro subscribers
- 3-day grace period after subscription expires
"""
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import wraps
from typing import Callable, Set

from fastapi import Depends, HTTPException, status

logger = logging.getLogger(__name__)

# Grace period after subscription expires (days)
GRACE_PERIOD_DAYS = 3


class Feature(str, Enum):
    """All gated features in the application."""
    # Core features
    EMAIL_SYNC = "email_sync"
    TASK_EXTRACTION = "task_extraction"
    THREAD_SUMMARY = "thread_summary"
    
    # Premium features
    DIGESTS = "digests"
    CALENDAR_SYNC = "calendar_sync"
    MEETING_BRIEFINGS = "meeting_briefings"
    SCHEDULING_ASSISTANT = "scheduling_assistant"
    CHAT_REFLECTION = "chat_reflection"
    UNLIMITED_HISTORY = "unlimited_history"


# All features (trial and pro get everything)
ALL_FEATURES: Set[Feature] = set(Feature)


def _is_in_grace_period(settings) -> bool:
    """Check if user is within the 3-day grace period after expiration."""
    now = datetime.now(timezone.utc)
    
    # Check subscription expiration
    if settings.subscription_expires_at:
        grace_end = settings.subscription_expires_at + timedelta(days=GRACE_PERIOD_DAYS)
        if now <= grace_end:
            return True
    
    # Check trial expiration
    if settings.trial_ends_at:
        grace_end = settings.trial_ends_at + timedelta(days=GRACE_PERIOD_DAYS)
        if now <= grace_end:
            return True
    
    return False


def is_feature_enabled(feature: Feature, settings) -> bool:
    """
    Check if a feature is enabled for the user.
    
    Access is granted if:
    1. User has active Pro subscription
    2. User is within valid trial period
    3. User is within 3-day grace period after expiration
    
    Args:
        feature: The feature to check
        settings: UserSettings instance
        
    Returns:
        True if feature is enabled, False otherwise
    """
    # Active subscription or trial = full access
    if settings.is_active:
        return True
    
    # Grace period = full access
    if _is_in_grace_period(settings):
        logger.info(f"User {settings.user_id} accessing {feature.value} during grace period")
        return True
    
    return False


def get_enabled_features(settings) -> Set[Feature]:
    """
    Get all features enabled for the user.
    
    Args:
        settings: UserSettings instance
        
    Returns:
        Set of enabled Feature enums
    """
    if settings.is_active or _is_in_grace_period(settings):
        return ALL_FEATURES.copy()
    
    return set()


def get_access_status(settings) -> dict:
    """
    Get detailed access status for the user.
    
    Returns:
        Dict with tier, status, days_remaining, grace_period info
    """
    now = datetime.now(timezone.utc)
    in_grace = _is_in_grace_period(settings)
    
    grace_days_remaining = 0
    if in_grace and not settings.is_active:
        if settings.subscription_expires_at:
            grace_end = settings.subscription_expires_at + timedelta(days=GRACE_PERIOD_DAYS)
            grace_days_remaining = max(0, (grace_end - now).days)
        elif settings.trial_ends_at:
            grace_end = settings.trial_ends_at + timedelta(days=GRACE_PERIOD_DAYS)
            grace_days_remaining = max(0, (grace_end - now).days)
    
    return {
        "tier": settings.subscription_tier,
        "status": settings.subscription_status,
        "is_active": settings.is_active,
        "days_remaining": settings.days_remaining,
        "in_grace_period": in_grace and not settings.is_active,
        "grace_days_remaining": grace_days_remaining,
        "features_enabled": [f.value for f in get_enabled_features(settings)],
    }


def require_feature(feature: Feature) -> Callable:
    """
    FastAPI dependency factory that requires a specific feature.
    
    Usage:
        @router.get("/digests")
        def get_digests(
            user = Depends(require_feature(Feature.DIGESTS))
        ):
            ...
    
    Args:
        feature: The feature to require
        
    Returns:
        FastAPI dependency function
    """
    from app.security.auth import get_current_user, get_user_settings
    from app.data.models import UserSettings
    
    def dependency(
        user = Depends(get_current_user),
        settings: UserSettings = Depends(get_user_settings),
    ):
        if not is_feature_enabled(feature, settings):
            in_grace = _is_in_grace_period(settings)
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "feature_not_available",
                    "feature": feature.value,
                    "message": f"The {feature.value} feature requires an active subscription.",
                    "tier": settings.subscription_tier,
                    "status": settings.subscription_status,
                    "in_grace_period": in_grace,
                }
            )
        return user
    
    return dependency


def require_any_feature(*features: Feature) -> Callable:
    """
    FastAPI dependency that requires at least one of the specified features.
    
    Usage:
        @router.get("/premium")
        def premium_endpoint(
            user = Depends(require_any_feature(Feature.DIGESTS, Feature.CALENDAR_SYNC))
        ):
            ...
    """
    from app.security.auth import get_current_user, get_user_settings
    from app.data.models import UserSettings
    
    def dependency(
        user = Depends(get_current_user),
        settings: UserSettings = Depends(get_user_settings),
    ):
        for feature in features:
            if is_feature_enabled(feature, settings):
                return user
        
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "feature_not_available",
                "features": [f.value for f in features],
                "message": "This endpoint requires an active subscription.",
                "tier": settings.subscription_tier,
            }
        )
    
    return dependency

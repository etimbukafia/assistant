"""
Unit Tests for UserSettings Model Properties

Tests the computed properties:
- is_active: Determines if user has valid subscription/trial access
- days_remaining: Calculates days until subscription/trial expires

These properties drive access control throughout the application.
"""
import pytest
from datetime import datetime, timezone, timedelta
from freezegun import freeze_time


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def user_settings_class():
    """Import UserSettings class."""
    from app.data.models import UserSettings
    return UserSettings


@pytest.fixture
def make_user(user_settings_class):
    """Factory to create UserSettings with specific subscription state."""
    def _make_user(
        subscription_tier="trial",
        subscription_status="trialing",
        trial_ends_at=None,
        subscription_expires_at=None,
        **kwargs
    ):
        user = user_settings_class(
            user_id="test-user-123",
            user_email="test@example.com",
            subscription_tier=subscription_tier,
            subscription_status=subscription_status,
            **kwargs
        )
        user.trial_ends_at = trial_ends_at
        user.subscription_expires_at = subscription_expires_at
        return user
    return _make_user


# =============================================================================
# Tests: is_active Property
# =============================================================================

class TestIsActiveProperty:
    """Tests for UserSettings.is_active computed property."""

    def test_is_active_true_for_pro_active_status(self, make_user):
        # Arrange
        user = make_user(
            subscription_tier="pro",
            subscription_status="active"
        )

        # Act & Assert
        assert user.is_active is True

    def test_is_active_true_for_pro_trialing_status(self, make_user):
        # Arrange - Pro tier can also have trialing status (e.g., trial of pro features)
        user = make_user(
            subscription_tier="pro",
            subscription_status="trialing"
        )

        # Act & Assert
        assert user.is_active is True

    def test_is_active_false_for_pro_canceled_status(self, make_user):
        # Arrange
        user = make_user(
            subscription_tier="pro",
            subscription_status="canceled"
        )

        # Act & Assert
        assert user.is_active is False

    def test_is_active_true_for_pro_cancel_scheduled_status(self, make_user):
        # Arrange
        user = make_user(
            subscription_tier="pro",
            subscription_status="cancel_scheduled"
        )

        # Act & Assert
        assert user.is_active is True

    def test_is_active_false_for_pro_expired_status(self, make_user):
        # Arrange
        user = make_user(
            subscription_tier="pro",
            subscription_status="expired"
        )

        # Act & Assert
        assert user.is_active is False

    def test_is_active_false_for_pro_past_due_status(self, make_user):
        # Arrange
        user = make_user(
            subscription_tier="pro",
            subscription_status="past_due"
        )

        # Act & Assert
        assert user.is_active is False

    @freeze_time("2026-01-15 12:00:00")
    def test_is_active_true_for_trial_with_future_expiry(self, make_user):
        # Arrange - Trial ends in the future
        user = make_user(
            subscription_tier="trial",
            subscription_status="trialing",
            trial_ends_at=datetime(2026, 1, 20, tzinfo=timezone.utc)
        )

        # Act & Assert
        assert user.is_active is True

    @freeze_time("2026-01-15 12:00:00")
    def test_is_active_false_for_trial_with_past_expiry(self, make_user):
        # Arrange - Trial already ended
        user = make_user(
            subscription_tier="trial",
            subscription_status="trialing",
            trial_ends_at=datetime(2026, 1, 10, tzinfo=timezone.utc)
        )

        # Act & Assert
        assert user.is_active is False

    @freeze_time("2026-01-15 12:00:00")
    def test_is_active_true_for_pro_within_grace(self, make_user):
        # Arrange - expiry 2 days ago, still within 4-day pro grace
        user = make_user(
            subscription_tier="pro",
            subscription_status="active",
            subscription_expires_at=datetime(2026, 1, 13, 12, 0, 0, tzinfo=timezone.utc),
        )

        # Act & Assert
        assert user.is_active is True

    @freeze_time("2026-01-15 12:00:00")
    def test_is_active_false_for_pro_after_grace(self, make_user):
        # Arrange - expiry 10 days ago, outside grace
        user = make_user(
            subscription_tier="pro",
            subscription_status="active",
            subscription_expires_at=datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
        )

        # Act & Assert
        assert user.is_active is False

    def test_is_active_false_for_trial_without_expiry_set(self, make_user):
        # Arrange - Trial not activated (trial_ends_at is None)
        user = make_user(
            subscription_tier="trial",
            subscription_status="trialing",
            trial_ends_at=None
        )

        # Act & Assert
        assert user.is_active is False

    @freeze_time("2026-01-15 12:00:00")
    def test_is_active_boundary_trial_expires_exactly_now(self, make_user):
        # Arrange - Trial expires at exactly the current time
        user = make_user(
            subscription_tier="trial",
            trial_ends_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        )

        # Act & Assert - Expires exactly now means NOT active (not > now)
        assert user.is_active is False


# =============================================================================
# Tests: days_remaining Property
# =============================================================================

class TestDaysRemainingProperty:
    """Tests for UserSettings.days_remaining computed property."""

    @freeze_time("2026-01-15 12:00:00")
    def test_days_remaining_pro_subscription_calculates_correctly(self, make_user):
        # Arrange - 15 days remaining
        user = make_user(
            subscription_tier="pro",
            subscription_status="active",
            subscription_expires_at=datetime(2026, 1, 30, 12, 0, 0, tzinfo=timezone.utc)
        )

        # Act & Assert
        assert user.days_remaining == 15

    @freeze_time("2026-01-15 12:00:00")
    def test_days_remaining_trial_calculates_correctly(self, make_user):
        # Arrange - 5 days remaining in trial
        user = make_user(
            subscription_tier="trial",
            trial_ends_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        )

        # Act & Assert
        assert user.days_remaining == 5

    @freeze_time("2026-01-15 12:00:00")
    def test_days_remaining_returns_zero_when_expired(self, make_user):
        # Arrange - Expired 5 days ago
        user = make_user(
            subscription_tier="pro",
            subscription_status="expired",
            subscription_expires_at=datetime(2026, 1, 10, tzinfo=timezone.utc)
        )

        # Act & Assert
        assert user.days_remaining == 0

    def test_days_remaining_returns_zero_when_no_expiry_set(self, make_user):
        # Arrange - No expiry dates set
        user = make_user(
            subscription_tier="trial",
            trial_ends_at=None,
            subscription_expires_at=None
        )

        # Act & Assert
        assert user.days_remaining == 0

    @freeze_time("2026-01-15 12:00:00")
    def test_days_remaining_never_negative(self, make_user):
        # Arrange - Expired long ago
        user = make_user(
            subscription_tier="pro",
            subscription_expires_at=datetime(2025, 12, 1, tzinfo=timezone.utc)
        )

        # Act & Assert - Should be 0, not negative
        assert user.days_remaining == 0
        assert user.days_remaining >= 0

    @freeze_time("2026-01-15 12:00:00")
    def test_days_remaining_pro_takes_precedence_over_trial(self, make_user):
        # Arrange - Both trial and subscription expiry set, pro tier
        user = make_user(
            subscription_tier="pro",
            subscription_status="active",
            trial_ends_at=datetime(2026, 1, 20, tzinfo=timezone.utc),  # 5 days
            subscription_expires_at=datetime(2026, 2, 14, 12, 0, 0, tzinfo=timezone.utc)  # 30 days
        )

        # Act & Assert - Should use subscription_expires_at for pro users
        assert user.days_remaining == 30

    @freeze_time("2026-01-15 00:00:00")
    def test_days_remaining_partial_day_rounds_down(self, make_user):
        # Arrange - 2 days and 12 hours remaining
        user = make_user(
            subscription_tier="trial",
            trial_ends_at=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
        )

        # Act & Assert - timedelta.days truncates, so 2.5 days = 2
        assert user.days_remaining == 2


# =============================================================================
# Tests: Edge Cases
# =============================================================================

class TestUserSettingsEdgeCases:
    """Edge case tests for UserSettings subscription properties."""

    def test_default_values_for_new_user(self, make_user):
        # Arrange & Act - Use make_user which sets defaults explicitly
        user = make_user()

        # Assert - Defaults match what make_user sets (simulating DB defaults)
        assert user.subscription_tier == "trial"
        assert user.subscription_status == "trialing"
        assert user.is_active is False  # No trial_ends_at set
        assert user.days_remaining == 0

    @freeze_time("2026-01-15 12:00:00")
    def test_is_active_and_days_remaining_consistency(self, make_user):
        # Arrange - Active trial with days remaining
        user = make_user(
            subscription_tier="trial",
            trial_ends_at=datetime(2026, 1, 25, tzinfo=timezone.utc)
        )

        # Act & Assert - If is_active, days_remaining should be > 0
        assert user.is_active is True
        assert user.days_remaining > 0

    @freeze_time("2026-01-15 12:00:00")
    def test_expired_user_consistency(self, make_user):
        # Arrange - Expired trial
        user = make_user(
            subscription_tier="trial",
            trial_ends_at=datetime(2026, 1, 10, tzinfo=timezone.utc)
        )

        # Act & Assert - Not active and 0 days remaining
        assert user.is_active is False
        assert user.days_remaining == 0

    def test_unknown_subscription_status_not_active(self, make_user):
        # Arrange - Unknown status
        user = make_user(
            subscription_tier="pro",
            subscription_status="unknown_status"
        )

        # Act & Assert - Only "active" and "trialing" are considered active
        assert user.is_active is False

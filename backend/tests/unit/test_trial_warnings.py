"""
Unit tests for trial expiration warning notifications.

Tests the logic for:
- User selection for each milestone category
- Duplicate prevention logic
- Notification creation with correct messages
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.data.models import UserSettings, Notification
from app.jobs.trial_warnings import (
    get_next_trial_check_time,
    _get_users_for_milestone,
    _send_trial_warning,
    NOTIFICATION_CONFIG,
    GRACE_PERIOD_DAYS,
)


class TestGetNextTrialCheckTime:
    """Tests for scheduling logic."""
    
    def test_returns_datetime_at_9am_utc(self):
        """Should return a datetime at 9 AM UTC."""
        result = get_next_trial_check_time()
        
        # Should always be 9 AM UTC
        assert result.hour == 9
        assert result.minute == 0
        assert result.second == 0
        assert result.tzinfo == timezone.utc
    
    def test_returns_future_datetime(self):
        """Should return a datetime in the future."""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        result = get_next_trial_check_time()
        
        # Should be in the future
        assert result > now
    
    def test_returns_within_24_hours(self):
        """Should return a datetime within the next 24 hours."""
        from datetime import datetime, timezone, timedelta
        
        now = datetime.now(timezone.utc)
        result = get_next_trial_check_time()
        
        # Should be within 24 hours
        assert result < now + timedelta(hours=24)


class TestGetUsersForMilestone:
    """Tests for user selection logic."""
    
    def test_3_days_milestone_returns_correct_users(self, db_session):
        """Should return users with trial ending in 2-3 days."""
        now = datetime.now(timezone.utc)
        
        # User with trial ending in 2.5 days (should match)
        matching_user = UserSettings(
            user_id="user_match",
            user_email="match@test.com",
            subscription_tier="trial",
            trial_ends_at=now + timedelta(days=2, hours=12),
        )
        db_session.add(matching_user)
        
        # User with trial ending in 4 days (should not match)
        non_matching_user = UserSettings(
            user_id="user_nomatch",
            user_email="nomatch@test.com",
            subscription_tier="trial",
            trial_ends_at=now + timedelta(days=4),
        )
        db_session.add(non_matching_user)
        
        # User already notified (should not match)
        notified_user = UserSettings(
            user_id="user_notified",
            user_email="notified@test.com",
            subscription_tier="trial",
            trial_ends_at=now + timedelta(days=2, hours=12),
            last_trial_warning_milestone="3_days",
        )
        db_session.add(notified_user)
        
        db_session.commit()
        
        users = _get_users_for_milestone(db_session, "3_days", now)
        
        assert len(users) == 1
        assert users[0].user_id == "user_match"
    
    def test_1_day_milestone_returns_correct_users(self, db_session):
        """Should return users with trial ending in 0-1 days."""
        now = datetime.now(timezone.utc)
        
        # User with trial ending in 12 hours (should match)
        matching_user = UserSettings(
            user_id="user_match",
            user_email="match@test.com",
            subscription_tier="trial",
            trial_ends_at=now + timedelta(hours=12),
        )
        db_session.add(matching_user)
        
        # User with trial ending in 2 days (should not match)
        non_matching_user = UserSettings(
            user_id="user_nomatch",
            user_email="nomatch@test.com",
            subscription_tier="trial",
            trial_ends_at=now + timedelta(days=2),
        )
        db_session.add(non_matching_user)
        
        db_session.commit()
        
        users = _get_users_for_milestone(db_session, "1_day", now)
        
        assert len(users) == 1
        assert users[0].user_id == "user_match"
    
    def test_expired_milestone_returns_users_in_grace(self, db_session):
        """Should return users whose trial expired but are in grace period."""
        now = datetime.now(timezone.utc)
        
        # User with trial expired 1 day ago (in grace, should match)
        matching_user = UserSettings(
            user_id="user_match",
            user_email="match@test.com",
            subscription_tier="trial",
            subscription_status="trialing",
            trial_ends_at=now - timedelta(days=1),
        )
        db_session.add(matching_user)
        
        # User with trial expired 5 days ago (past grace, should not match)
        non_matching_user = UserSettings(
            user_id="user_nomatch",
            user_email="nomatch@test.com",
            subscription_tier="trial",
            subscription_status="expired",
            trial_ends_at=now - timedelta(days=5),
        )
        db_session.add(non_matching_user)
        
        db_session.commit()
        
        users = _get_users_for_milestone(db_session, "expired", now)
        
        assert len(users) == 1
        assert users[0].user_id == "user_match"
    
    def test_grace_ending_milestone_returns_correct_users(self, db_session):
        """Should return users with 1 day left in grace period."""
        now = datetime.now(timezone.utc)
        
        # User with trial expired 2 days ago (1 day left in grace, should match)
        matching_user = UserSettings(
            user_id="user_match",
            user_email="match@test.com",
            subscription_tier="trial",
            subscription_status="trialing",
            trial_ends_at=now - timedelta(days=2, hours=12),
        )
        db_session.add(matching_user)
        
        # User with trial expired 1 day ago (2 days left in grace, should not match)
        non_matching_user = UserSettings(
            user_id="user_nomatch",
            user_email="nomatch@test.com",
            subscription_tier="trial",
            subscription_status="trialing",
            trial_ends_at=now - timedelta(days=1),
        )
        db_session.add(non_matching_user)
        
        db_session.commit()
        
        users = _get_users_for_milestone(db_session, "grace_ending", now)
        
        assert len(users) == 1
        assert users[0].user_id == "user_match"
    
    def test_pro_users_are_excluded(self, db_session):
        """Pro users should never receive trial warnings."""
        now = datetime.now(timezone.utc)
        
        pro_user = UserSettings(
            user_id="pro_user",
            user_email="pro@test.com",
            subscription_tier="pro",
            trial_ends_at=now + timedelta(days=2),  # Trial date still set
        )
        db_session.add(pro_user)
        db_session.commit()
        
        users = _get_users_for_milestone(db_session, "3_days", now)
        
        assert len(users) == 0


class TestSendTrialWarning:
    """Tests for notification sending logic."""
    
    def test_creates_notification_with_correct_content(self, db_session):
        """Should create notification with correct title and body."""
        now = datetime.now(timezone.utc)
        
        user = UserSettings(
            user_id="test_user",
            user_email="test@test.com",
            subscription_tier="trial",
            trial_ends_at=now + timedelta(days=2),
        )
        db_session.add(user)
        db_session.commit()
        
        result = _send_trial_warning(db_session, user, "3_days", "test_correlation")
        db_session.commit()
        
        assert result is True
        
        # Check notification was created
        notification = db_session.query(Notification).filter(
            Notification.user_id == "test_user"
        ).first()
        
        assert notification is not None
        assert notification.title == NOTIFICATION_CONFIG["3_days"]["title"]
        assert notification.body == NOTIFICATION_CONFIG["3_days"]["body"]
        assert notification.priority == "high"
        assert notification.target_type == "settings"
        assert notification.target_id == "subscription"
    
    def test_updates_tracking_fields(self, db_session):
        """Should update last_trial_warning_sent and milestone."""
        now = datetime.now(timezone.utc)
        
        user = UserSettings(
            user_id="test_user",
            user_email="test@test.com",
            subscription_tier="trial",
            trial_ends_at=now + timedelta(days=2),
        )
        db_session.add(user)
        db_session.commit()
        
        _send_trial_warning(db_session, user, "1_day", "test_correlation")
        db_session.commit()
        
        # Refresh user from DB
        db_session.refresh(user)
        
        assert user.last_trial_warning_milestone == "1_day"
        assert user.last_trial_warning_sent is not None
    
    def test_returns_false_for_unknown_milestone(self, db_session):
        """Should return False and not create notification for unknown milestone."""
        user = UserSettings(
            user_id="test_user",
            user_email="test@test.com",
            subscription_tier="trial",
        )
        db_session.add(user)
        db_session.commit()
        
        result = _send_trial_warning(db_session, user, "unknown_milestone", "test")
        
        assert result is False
        
        notification = db_session.query(Notification).filter(
            Notification.user_id == "test_user"
        ).first()
        
        assert notification is None


class TestNotificationConfig:
    """Tests for notification configuration."""
    
    def test_all_milestones_have_config(self):
        """All expected milestones should have notification config."""
        expected_milestones = ["3_days", "1_day", "expired", "grace_ending"]
        
        for milestone in expected_milestones:
            assert milestone in NOTIFICATION_CONFIG
            assert "title" in NOTIFICATION_CONFIG[milestone]
            assert "body" in NOTIFICATION_CONFIG[milestone]
    
    def test_grace_period_days_matches_feature_gating(self):
        """Grace period should match the value in feature_gating.py."""
        # This ensures consistency between modules
        assert GRACE_PERIOD_DAYS == 3

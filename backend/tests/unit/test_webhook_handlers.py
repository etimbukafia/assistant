"""
Unit Tests for Polar Webhook Handlers

Pre-Testing Reflection:
1. WHAT ARE WE TESTING?
   - validate_webhook_signature() - Signature validation
   - Event handlers: subscription.created, active, updated, canceled, revoked
   - get_user_by_polar_customer_id() - User lookup by customer ID
   
2. WHY IS TESTING IMPORTANT HERE?
   - Webhooks trigger billing state changes - errors could grant/revoke access incorrectly
   - Financial and access control implications
   
3. WHAT COULD GO WRONG?
   - Invalid signatures processed, Missing customer_id, User not found
   - Date parsing errors, Status updates applied to wrong user
   
4. WHAT DO WE NOT NEED TO TEST?
   - Polar SDK signature validation internals (third-party)
   - Database transactions (tested in integration tests)

Test Categories:
- validate_webhook_signature() - config errors, validation success/failure
- handle_subscription_created() - activates Pro, sets dates, missing data
- handle_subscription_active() - renews subscription
- handle_subscription_updated() - syncs status/dates
- handle_subscription_canceled() - marks cancel_scheduled, keeps access
- handle_subscription_revoked() - revokes access immediately
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_settings():
    """Mock Settings with webhook secret configured."""
    settings = MagicMock()
    settings.POLAR_WEBHOOK_SECRET = "whsec_test_secret_12345"
    return settings


@pytest.fixture
def mock_settings_no_secret():
    """Mock Settings without webhook secret."""
    settings = MagicMock()
    settings.POLAR_WEBHOOK_SECRET = ""
    return settings


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = MagicMock()
    return session


@pytest.fixture
def mock_user_settings():
    """Create a mock UserSettings object."""
    user = MagicMock()
    user.user_id = "user-uuid-123"
    user.user_email = "customer@example.com"
    user.polar_customer_id = "cust_polar_123"
    user.polar_subscription_id = None
    user.subscription_tier = "trial"
    user.subscription_status = "trialing"
    user.subscription_expires_at = None
    return user


@pytest.fixture
def subscription_created_event():
    """Mock subscription.created webhook event data."""
    return {
        "type": "subscription.created",
        "data": {
            "id": "sub_new_123",
            "customer_id": "cust_polar_123",
            "status": "active",
            "current_period_start": "2026-01-01T00:00:00Z",
            "current_period_end": "2026-02-01T00:00:00Z",
        }
    }


@pytest.fixture
def subscription_active_event():
    """Mock subscription.active webhook event data."""
    return {
        "type": "subscription.active",
        "data": {
            "id": "sub_123",
            "customer_id": "cust_polar_123",
            "status": "active",
            "current_period_end": "2026-03-01T00:00:00Z",
        }
    }


@pytest.fixture
def subscription_updated_event():
    """Mock subscription.updated webhook event data."""
    return {
        "type": "subscription.updated",
        "data": {
            "id": "sub_123",
            "customer_id": "cust_polar_123",
            "status": "past_due",
            "current_period_end": "2026-02-15T00:00:00Z",
        }
    }


@pytest.fixture
def subscription_canceled_event():
    """Mock subscription.canceled webhook event data."""
    return {
        "type": "subscription.canceled",
        "data": {
            "id": "sub_123",
            "customer_id": "cust_polar_123",
            "cancel_at_period_end": True,
        }
    }


@pytest.fixture
def subscription_revoked_event():
    """Mock subscription.revoked webhook event data."""
    return {
        "type": "subscription.revoked",
        "data": {
            "id": "sub_123",
            "customer_id": "cust_polar_123",
        }
    }


# =============================================================================
# Tests: validate_webhook_signature()
# =============================================================================

class TestValidateWebhookSignature:
    """Tests for webhook signature validation."""

    def test_validate_webhook_signature_raises_500_without_secret(
        self, mock_settings_no_secret
    ):
        # Arrange
        from app.handlers.webhook_handlers import validate_webhook_signature
        
        with patch("app.handlers.webhook_handlers.get_settings", return_value=mock_settings_no_secret):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                validate_webhook_signature(b"payload", {"webhook-signature": "sig"})
            
            assert exc_info.value.status_code == 500
            assert "not configured" in exc_info.value.detail

    def test_validate_webhook_signature_returns_event_on_success(
        self, mock_settings
    ):
        # Arrange
        expected_event = {"type": "subscription.created", "data": {}}
        
        with patch("app.handlers.webhook_handlers.get_settings", return_value=mock_settings):
            with patch("polar_sdk.webhooks.validate_event", return_value=expected_event):
                # Act
                from app.handlers.webhook_handlers import validate_webhook_signature
                result = validate_webhook_signature(
                    b"payload",
                    {"webhook-signature": "valid_sig"}
                )
                
                # Assert
                assert result == expected_event

    def test_validate_webhook_signature_raises_400_on_invalid_signature(
        self, mock_settings
    ):
        # Arrange
        from app.handlers.webhook_handlers import validate_webhook_signature
        
        with patch("app.handlers.webhook_handlers.get_settings", return_value=mock_settings):
            with patch("polar_sdk.webhooks.validate_event", side_effect=Exception("Invalid signature")):
                # Act & Assert
                with pytest.raises(HTTPException) as exc_info:
                    validate_webhook_signature(b"payload", {"webhook-signature": "bad_sig"})
                
                assert exc_info.value.status_code == 400
                assert "Invalid webhook signature" in exc_info.value.detail


# =============================================================================
# Tests: get_user_by_polar_customer_id()
# =============================================================================

class TestGetUserByPolarCustomerId:
    """Tests for user lookup by Polar customer ID."""

    def test_get_user_by_polar_customer_id_returns_user(
        self, mock_db_session, mock_user_settings
    ):
        # Arrange
        from app.handlers.webhook_handlers import get_user_by_polar_customer_id
        mock_db_session.query().filter().first.return_value = mock_user_settings
        
        # Act
        result = get_user_by_polar_customer_id(mock_db_session, "cust_polar_123")
        
        # Assert
        assert result == mock_user_settings

    def test_get_user_by_polar_customer_id_returns_none_when_not_found(
        self, mock_db_session
    ):
        # Arrange
        from app.handlers.webhook_handlers import get_user_by_polar_customer_id
        mock_db_session.query().filter().first.return_value = None
        
        # Act
        result = get_user_by_polar_customer_id(mock_db_session, "cust_unknown")
        
        # Assert
        assert result is None


# =============================================================================
# Tests: handle_subscription_created()
# =============================================================================

class TestHandleSubscriptionCreated:
    """Tests for subscription.created event handler."""

    def test_handle_subscription_created_activates_pro_tier(
        self, mock_db_session, mock_user_settings, subscription_created_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_created
        mock_db_session.query().filter().first.return_value = mock_user_settings
        
        # Act
        handle_subscription_created(subscription_created_event, mock_db_session)
        
        # Assert
        assert mock_user_settings.subscription_tier == "pro"
        assert mock_user_settings.subscription_status == "active"
        assert mock_user_settings.polar_subscription_id == "sub_new_123"

    def test_handle_subscription_created_sets_expiry_date(
        self, mock_db_session, mock_user_settings, subscription_created_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_created
        mock_db_session.query().filter().first.return_value = mock_user_settings
        
        # Act
        handle_subscription_created(subscription_created_event, mock_db_session)
        
        # Assert
        expected_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert mock_user_settings.subscription_expires_at == expected_date

    def test_handle_subscription_created_handles_missing_customer_id(
        self, mock_db_session
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_created
        event_data = {"type": "subscription.created", "data": {"id": "sub_123"}}
        
        # Act - Should not raise
        handle_subscription_created(event_data, mock_db_session)
        
        # Assert - DB should not be queried
        mock_db_session.query().filter().first.assert_not_called()

    def test_handle_subscription_created_handles_user_not_found(
        self, mock_db_session, subscription_created_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_created
        mock_db_session.query().filter().first.return_value = None
        
        # Act - Should not raise
        handle_subscription_created(subscription_created_event, mock_db_session)
        
        # Assert - No error, graceful handling


# =============================================================================
# Tests: handle_subscription_active()
# =============================================================================

class TestHandleSubscriptionActive:
    """Tests for subscription.active event handler."""

    def test_handle_subscription_active_updates_status(
        self, mock_db_session, mock_user_settings, subscription_active_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_active
        mock_db_session.query().filter().first.return_value = mock_user_settings
        mock_user_settings.subscription_status = "cancel_scheduled"
        
        # Act
        handle_subscription_active(subscription_active_event, mock_db_session)
        
        # Assert
        assert mock_user_settings.subscription_status == "active"

    def test_handle_subscription_active_updates_expiry_date(
        self, mock_db_session, mock_user_settings, subscription_active_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_active
        mock_db_session.query().filter().first.return_value = mock_user_settings
        
        # Act
        handle_subscription_active(subscription_active_event, mock_db_session)
        
        # Assert
        expected_date = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert mock_user_settings.subscription_expires_at == expected_date


# =============================================================================
# Tests: handle_subscription_updated()
# =============================================================================

class TestHandleSubscriptionUpdated:
    """Tests for subscription.updated event handler."""

    def test_handle_subscription_updated_syncs_status(
        self, mock_db_session, mock_user_settings, subscription_updated_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_updated
        mock_db_session.query().filter().first.return_value = mock_user_settings
        
        # Act
        handle_subscription_updated(subscription_updated_event, mock_db_session)
        
        # Assert
        assert mock_user_settings.subscription_status == "past_due"

    def test_handle_subscription_updated_syncs_expiry_date(
        self, mock_db_session, mock_user_settings, subscription_updated_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_updated
        mock_db_session.query().filter().first.return_value = mock_user_settings
        
        # Act
        handle_subscription_updated(subscription_updated_event, mock_db_session)
        
        # Assert
        expected_date = datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert mock_user_settings.subscription_expires_at == expected_date

    def test_handle_subscription_updated_handles_missing_status(
        self, mock_db_session, mock_user_settings
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_updated
        mock_db_session.query().filter().first.return_value = mock_user_settings
        mock_user_settings.subscription_status = "active"
        
        # Event without status field
        event_data = {
            "type": "subscription.updated",
            "data": {
                "customer_id": "cust_polar_123",
                "current_period_end": "2026-04-01T00:00:00Z",
            }
        }
        
        # Act
        handle_subscription_updated(event_data, mock_db_session)
        
        # Assert - Status unchanged
        assert mock_user_settings.subscription_status == "active"


# =============================================================================
# Tests: handle_subscription_canceled()
# =============================================================================

class TestHandleSubscriptionCanceled:
    """Tests for subscription.canceled event handler."""

    def test_handle_subscription_canceled_marks_status_cancel_scheduled(
        self, mock_db_session, mock_user_settings, subscription_canceled_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_canceled
        mock_db_session.query().filter().first.return_value = mock_user_settings
        mock_user_settings.subscription_tier = "pro"
        
        # Act
        handle_subscription_canceled(subscription_canceled_event, mock_db_session)
        
        # Assert
        assert mock_user_settings.subscription_status == "cancel_scheduled"
        # Tier remains Pro until period ends
        assert mock_user_settings.subscription_tier == "pro"


# =============================================================================
# Tests: handle_subscription_uncanceled()
# =============================================================================

class TestHandleSubscriptionUncanceled:
    """Tests for subscription.uncanceled event handler."""

    def test_handle_subscription_uncanceled_reactivates_status(
        self, mock_db_session, mock_user_settings
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_uncanceled
        mock_db_session.query().filter().first.return_value = mock_user_settings
        mock_user_settings.subscription_status = "cancel_scheduled"
        mock_user_settings.subscription_tier = "pro"
        
        event_data = {
            "type": "subscription.uncanceled",
            "data": {
                "id": "sub_123",
                "customer_id": "cust_polar_123",
            }
        }
        
        # Act
        handle_subscription_uncanceled(event_data, mock_db_session)
        
        # Assert
        assert mock_user_settings.subscription_status == "active"
        assert mock_user_settings.subscription_tier == "pro"


# =============================================================================
# Tests: handle_subscription_revoked()
# =============================================================================

class TestHandleSubscriptionRevoked:
    """Tests for subscription.revoked event handler."""

    def test_handle_subscription_revoked_downgrades_to_trial(
        self, mock_db_session, mock_user_settings, subscription_revoked_event
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_revoked
        mock_db_session.query().filter().first.return_value = mock_user_settings
        mock_user_settings.subscription_tier = "pro"
        mock_user_settings.polar_subscription_id = "sub_old_123"
        mock_user_settings.subscription_expires_at = datetime.now(timezone.utc)
        
        # Act
        handle_subscription_revoked(subscription_revoked_event, mock_db_session)
        
        # Assert - Full access revocation
        assert mock_user_settings.subscription_tier == "trial"
        assert mock_user_settings.subscription_status == "expired"
        assert mock_user_settings.polar_subscription_id is None
        assert mock_user_settings.subscription_expires_at is None


# =============================================================================
# Tests: Edge Cases
# =============================================================================

class TestWebhookEdgeCases:
    """Edge case tests for webhook handlers."""

    def test_handle_subscription_created_handles_invalid_date_format(
        self, mock_db_session, mock_user_settings
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_created
        mock_db_session.query().filter().first.return_value = mock_user_settings
        
        # Invalid date format
        event_data = {
            "type": "subscription.created",
            "data": {
                "id": "sub_123",
                "customer_id": "cust_polar_123",
                "current_period_end": "not-a-date",
            }
        }
        
        # Act - Should not raise
        handle_subscription_created(event_data, mock_db_session)
        
        # Assert - Date parsing failed gracefully
        assert mock_user_settings.subscription_tier == "pro"

    def test_event_handlers_mapping_contains_all_expected_events(self):
        # Arrange
        from app.handlers.webhook_handlers import EVENT_HANDLERS
        
        # Act & Assert
        expected_events = [
            "subscription.created",
            "subscription.active",
            "subscription.updated",
            "subscription.canceled",
            "subscription.revoked",
            "subscription.uncanceled",
        ]
        
        for event in expected_events:
            assert event in EVENT_HANDLERS, f"Missing handler for {event}"

    def test_handle_subscription_with_empty_data(
        self, mock_db_session
    ):
        # Arrange
        from app.handlers.webhook_handlers import handle_subscription_created
        event_data = {"type": "subscription.created", "data": {}}
        
        # Act - Should not raise
        handle_subscription_created(event_data, mock_db_session)
        
        # Assert - Handled gracefully (no customer_id means early return)
        mock_db_session.query().filter().first.assert_not_called()

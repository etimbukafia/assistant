"""
Integration Tests for Polar Webhook Endpoint

Tests the POST /webhooks/polar endpoint:
- Signature validation
- Event routing
- Database commits and rollbacks

Uses FastAPI TestClient with mocked webhook validation.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import json

pytestmark = pytest.mark.integration


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_settings():
    """Mock settings with webhook secret."""
    settings = MagicMock()
    settings.POLAR_WEBHOOK_SECRET = "whsec_test_secret_12345"
    settings.SUPABASE_JWT_SECRET = "test-jwt-secret"
    settings.POLAR_ACCESS_TOKEN = "test_polar_token"
    settings.POLAR_PRODUCT_ID = "prod_test_123"
    return settings


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def user_with_polar_customer():
    """Create a mock user with Polar customer ID."""
    from app.data.models import UserSettings
    user = UserSettings(
        user_id="user-polar-test-123",
        user_email="polar_user@example.com",
        subscription_tier="trial",
        subscription_status="trialing",
        polar_customer_id="cust_polar_webhook_test",
    )
    return user


@pytest.fixture
def valid_webhook_headers():
    """Headers that would be present in a valid Polar webhook."""
    return {
        "webhook-id": "msg_test123",
        "webhook-timestamp": str(int(datetime.now(timezone.utc).timestamp())),
        "webhook-signature": "v1,test_signature_here",
        "content-type": "application/json",
    }


@pytest.fixture
def subscription_created_payload():
    """Payload for subscription.created event."""
    return {
        "type": "subscription.created",
        "data": {
            "id": "sub_webhook_test_123",
            "customer_id": "cust_polar_webhook_test",
            "status": "active",
            "current_period_start": "2026-01-01T00:00:00Z",
            "current_period_end": "2026-02-01T00:00:00Z",
        }
    }


@pytest.fixture
def subscription_canceled_payload():
    """Payload for subscription.canceled event."""
    return {
        "type": "subscription.canceled",
        "data": {
            "id": "sub_webhook_test_123",
            "customer_id": "cust_polar_webhook_test",
            "cancel_at_period_end": True,
        }
    }


@pytest.fixture
def subscription_revoked_payload():
    """Payload for subscription.revoked event."""
    return {
        "type": "subscription.revoked",
        "data": {
            "id": "sub_webhook_test_123",
            "customer_id": "cust_polar_webhook_test",
        }
    }


def create_webhook_test_client(mock_settings, mock_db, mock_user=None):
    """Create a test client for webhook testing."""
    from fastapi.testclient import TestClient
    from main import app
    from app.infra.database import get_db
    from app.infra.config import get_settings

    # Clear any previous overrides
    app.dependency_overrides.clear()

    # Set up mock query to return user
    if mock_user:
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_user
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

    def override_get_db():
        yield mock_db

    def override_get_settings():
        return mock_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    return TestClient(app)


# =============================================================================
# Tests: Webhook Signature Validation
# =============================================================================

class TestWebhookSignatureValidation:
    """Tests for webhook signature validation."""

    def test_webhook_rejects_invalid_signature(
        self, mock_settings, mock_db, valid_webhook_headers, subscription_created_payload
    ):
        # Arrange
        from fastapi import HTTPException
        from fastapi.testclient import TestClient
        from main import app
        from app.infra.database import get_db
        from app.infra.config import get_settings

        app.dependency_overrides.clear()

        def override_get_db():
            yield mock_db

        def override_get_settings():
            return mock_settings

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_settings] = override_get_settings

        # Act - Mock validate_webhook_signature to raise HTTPException
        with patch("app.handlers.webhook_handlers.validate_webhook_signature") as mock_validate:
            mock_validate.side_effect = HTTPException(status_code=400, detail="Invalid webhook signature")

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/webhooks/polar",
                headers=valid_webhook_headers,
                json=subscription_created_payload
            )

        # Assert
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

        # Cleanup
        app.dependency_overrides.clear()

    def test_webhook_rejects_missing_webhook_secret(
        self, mock_db, valid_webhook_headers, subscription_created_payload
    ):
        # Arrange - Settings without webhook secret
        from fastapi.testclient import TestClient
        from main import app
        from app.infra.database import get_db
        from app.infra.config import get_settings

        app.dependency_overrides.clear()

        mock_settings_no_secret = MagicMock()
        mock_settings_no_secret.POLAR_WEBHOOK_SECRET = None

        def override_get_db():
            yield mock_db

        def override_get_settings():
            return mock_settings_no_secret

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_settings] = override_get_settings

        client = TestClient(app, raise_server_exceptions=False)

        # Act
        response = client.post(
            "/webhooks/polar",
            headers=valid_webhook_headers,
            json=subscription_created_payload
        )

        # Assert - Should fail due to validation error
        # Note: Returns 400 because the signature validation fails (not 500)
        assert response.status_code in [400, 500]

        # Cleanup
        app.dependency_overrides.clear()


# =============================================================================
# Tests: Event Processing
# =============================================================================

class TestWebhookEventProcessing:
    """Tests for webhook event processing."""

    def test_webhook_processes_subscription_created(
        self, mock_settings, mock_db, valid_webhook_headers,
        subscription_created_payload, user_with_polar_customer
    ):
        # Arrange
        client = create_webhook_test_client(mock_settings, mock_db, user_with_polar_customer)

        with patch("app.handlers.webhook_handlers.validate_webhook_signature") as mock_validate:
            mock_validate.return_value = subscription_created_payload

            # Act
            response = client.post(
                "/webhooks/polar",
                headers=valid_webhook_headers,
                json=subscription_created_payload
            )

        # Assert
        assert response.status_code == 200
        assert response.json()["handled"] is True

        # Verify user was updated
        assert user_with_polar_customer.subscription_tier == "pro"
        assert user_with_polar_customer.subscription_status == "active"
        assert user_with_polar_customer.polar_subscription_id == "sub_webhook_test_123"

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_webhook_processes_subscription_canceled(
        self, mock_settings, mock_db, valid_webhook_headers,
        subscription_canceled_payload, user_with_polar_customer
    ):
        # Arrange - Set up user as Pro subscriber first
        user_with_polar_customer.subscription_tier = "pro"
        user_with_polar_customer.subscription_status = "active"
        user_with_polar_customer.polar_subscription_id = "sub_webhook_test_123"
        client = create_webhook_test_client(mock_settings, mock_db, user_with_polar_customer)

        with patch("app.handlers.webhook_handlers.validate_webhook_signature") as mock_validate:
            mock_validate.return_value = subscription_canceled_payload

            # Act
            response = client.post(
                "/webhooks/polar",
                headers=valid_webhook_headers,
                json=subscription_canceled_payload
            )

        # Assert
        assert response.status_code == 200
        assert response.json()["handled"] is True

        # Status should be canceled but tier stays pro (access until period end)
        assert user_with_polar_customer.subscription_status == "canceled"
        assert user_with_polar_customer.subscription_tier == "pro"

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_webhook_processes_subscription_revoked(
        self, mock_settings, mock_db, valid_webhook_headers,
        subscription_revoked_payload, user_with_polar_customer
    ):
        # Arrange - Set up user as Pro subscriber first
        user_with_polar_customer.subscription_tier = "pro"
        user_with_polar_customer.subscription_status = "canceled"
        user_with_polar_customer.polar_subscription_id = "sub_webhook_test_123"
        user_with_polar_customer.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=5)
        client = create_webhook_test_client(mock_settings, mock_db, user_with_polar_customer)

        with patch("app.handlers.webhook_handlers.validate_webhook_signature") as mock_validate:
            mock_validate.return_value = subscription_revoked_payload

            # Act
            response = client.post(
                "/webhooks/polar",
                headers=valid_webhook_headers,
                json=subscription_revoked_payload
            )

        # Assert
        assert response.status_code == 200
        assert response.json()["handled"] is True

        # User should be downgraded
        assert user_with_polar_customer.subscription_tier == "trial"
        assert user_with_polar_customer.subscription_status == "expired"
        assert user_with_polar_customer.polar_subscription_id is None
        assert user_with_polar_customer.subscription_expires_at is None

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_webhook_returns_handled_false_for_unknown_event(
        self, mock_settings, mock_db, valid_webhook_headers
    ):
        # Arrange
        unknown_event = {
            "type": "unknown.event.type",
            "data": {"id": "test_123"}
        }
        client = create_webhook_test_client(mock_settings, mock_db)

        with patch("app.handlers.webhook_handlers.validate_webhook_signature") as mock_validate:
            mock_validate.return_value = unknown_event

            # Act
            response = client.post(
                "/webhooks/polar",
                headers=valid_webhook_headers,
                json=unknown_event
            )

        # Assert
        assert response.status_code == 200
        assert response.json()["received"] is True
        assert response.json()["handled"] is False

        # Cleanup
        from main import app
        app.dependency_overrides.clear()


# =============================================================================
# Tests: Database Transactions
# =============================================================================

class TestWebhookDatabaseTransactions:
    """Tests for webhook database commit/rollback behavior."""

    def test_webhook_commits_database_changes(
        self, mock_settings, mock_db, valid_webhook_headers,
        subscription_created_payload, user_with_polar_customer
    ):
        # Arrange
        client = create_webhook_test_client(mock_settings, mock_db, user_with_polar_customer)

        with patch("app.handlers.webhook_handlers.validate_webhook_signature") as mock_validate:
            mock_validate.return_value = subscription_created_payload

            # Act
            response = client.post(
                "/webhooks/polar",
                headers=valid_webhook_headers,
                json=subscription_created_payload
            )

        # Assert
        assert response.status_code == 200
        # Verify commit was called
        mock_db.commit.assert_called_once()

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_webhook_for_unknown_customer_succeeds_gracefully(
        self, mock_settings, mock_db, valid_webhook_headers
    ):
        # Arrange - Event for customer that doesn't exist
        payload = {
            "type": "subscription.created",
            "data": {
                "id": "sub_unknown_123",
                "customer_id": "cust_nonexistent_customer",
                "status": "active",
            }
        }

        # Set up mock to return None (no user found)
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None  # No user found
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        client = create_webhook_test_client(mock_settings, mock_db)

        with patch("app.handlers.webhook_handlers.validate_webhook_signature") as mock_validate:
            mock_validate.return_value = payload

            # Act - Should not crash
            response = client.post(
                "/webhooks/polar",
                headers=valid_webhook_headers,
                json=payload
            )

        # Assert - Should succeed (handler just returns early)
        assert response.status_code == 200
        assert response.json()["handled"] is True

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_webhook_rollback_on_handler_error(
        self, mock_settings, mock_db, valid_webhook_headers,
        subscription_created_payload
    ):
        # Arrange - Make the db.commit raise an error
        mock_db.commit.side_effect = Exception("Database error")

        # Set up user to be found
        user = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = user
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        client = create_webhook_test_client(mock_settings, mock_db)

        with patch("app.handlers.webhook_handlers.validate_webhook_signature") as mock_validate:
            mock_validate.return_value = subscription_created_payload

            # Act
            response = client.post(
                "/webhooks/polar",
                headers=valid_webhook_headers,
                json=subscription_created_payload
            )

        # Assert - Should return 500 and rollback
        assert response.status_code == 500
        mock_db.rollback.assert_called_once()

        # Cleanup
        from main import app
        app.dependency_overrides.clear()


# =============================================================================
# Tests: Event Handler Mapping
# =============================================================================

class TestEventHandlerMapping:
    """Tests for event handler registration."""

    def test_all_expected_event_types_have_handlers(self):
        # Arrange
        from app.handlers.webhook_handlers import EVENT_HANDLERS

        expected_events = [
            "subscription.created",
            "subscription.active",
            "subscription.updated",
            "subscription.canceled",
            "subscription.revoked",
            "subscription.uncanceled",
        ]

        # Act & Assert
        for event_type in expected_events:
            assert event_type in EVENT_HANDLERS, f"Missing handler for {event_type}"
            assert callable(EVENT_HANDLERS[event_type])

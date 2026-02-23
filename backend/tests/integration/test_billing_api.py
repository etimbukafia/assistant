"""
Integration Tests for Billing API Endpoints

Tests the /billing/* routes:
- GET /billing/subscription - Get user's subscription status
- POST /billing/checkout - Create checkout session
- POST /billing/cancel - Cancel subscription
- GET /billing/portal-url - Get customer portal URL

Uses FastAPI TestClient with fully mocked dependencies.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from freezegun import freeze_time

pytestmark = pytest.mark.integration


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_settings():
    """Mock settings with required config."""
    settings = MagicMock()
    settings.SUPABASE_JWT_SECRET = "test-jwt-secret"
    settings.POLAR_ACCESS_TOKEN = "test_polar_token"
    settings.POLAR_PRODUCT_ID = "prod_test_123"
    settings.POLAR_WEBHOOK_SECRET = "whsec_test"
    return settings


@pytest.fixture
def mock_authenticated_user():
    """Mock authenticated user."""
    from app.security.auth import AuthenticatedUser
    return AuthenticatedUser(
        user_id="user-uuid-12345",
        email="test@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={"full_name": "Test User"}
    )


@pytest.fixture
def trial_user_settings():
    """UserSettings for a trial user."""
    from app.data.models import UserSettings
    user = UserSettings(
        user_id="user-uuid-12345",
        user_email="test@example.com",
        subscription_tier="trial",
        subscription_status="trialing",
    )
    user.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)
    return user


@pytest.fixture
def pro_user_settings():
    """UserSettings for a Pro subscriber."""
    from app.data.models import UserSettings
    user = UserSettings(
        user_id="user-uuid-12345",
        user_email="test@example.com",
        subscription_tier="pro",
        subscription_status="active",
        polar_customer_id="cust_polar_123",
        polar_subscription_id="sub_polar_456",
    )
    user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    return user


@pytest.fixture
def mock_polar_service():
    """Mock PolarService."""
    service = MagicMock()
    service.enabled = True
    service.get_or_create_customer.return_value = "cust_new_123"
    service.create_checkout_session.return_value = "https://checkout.polar.sh/test"
    service.cancel_subscription.return_value = True
    service.get_customer_portal_url.return_value = "https://polar.sh/portal/test"
    return service


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


def create_test_client(
    mock_settings, mock_polar_service, mock_authenticated_user, user_settings, mock_db,
    include_auth=True
):
    """Create a test client with specified overrides."""
    from fastapi.testclient import TestClient
    from main import app
    from app.infra.database import get_db
    from app.infra.config import get_settings
    from app.services.polar import get_polar_service
    from app.security.auth import get_current_user, get_user_settings, get_db_for_user

    # Clear any previous overrides first
    app.dependency_overrides.clear()

    def override_get_db():
        yield mock_db

    def override_get_settings():
        return mock_settings

    def override_get_polar_service():
        return mock_polar_service

    def override_get_current_user():
        return mock_authenticated_user

    def override_get_user_settings():
        return user_settings

    def override_get_db_for_user():
        return mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_polar_service] = override_get_polar_service

    if include_auth:
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_user_settings] = override_get_user_settings
        app.dependency_overrides[get_db_for_user] = override_get_db_for_user

    return TestClient(app)


# =============================================================================
# Tests: GET /billing/subscription
# =============================================================================

class TestGetSubscriptionEndpoint:
    """Tests for GET /billing/subscription endpoint."""

    @freeze_time("2026-01-15 12:00:00")
    def test_get_subscription_returns_trial_for_new_user(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db
        )

        # Act
        response = client.get("/billing/subscription")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "trial"
        assert data["status"] == "trialing"
        assert data["is_active"] is True

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_get_subscription_returns_pro_for_subscribed_user(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        pro_user_settings, mock_db
    ):
        # Arrange
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            pro_user_settings, mock_db
        )

        # Act
        response = client.get("/billing/subscription")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "pro"
        assert data["status"] == "active"
        assert data["is_active"] is True
        assert data["days_remaining"] >= 29  # Approximately 30 days

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_get_subscription_requires_authentication(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - No auth overrides
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db, include_auth=False
        )

        # Act
        response = client.get("/billing/subscription")

        # Assert
        assert response.status_code == 401

        # Cleanup
        from main import app
        app.dependency_overrides.clear()


# =============================================================================
# Tests: POST /billing/checkout
# =============================================================================

class TestCreateCheckoutEndpoint:
    """Tests for POST /billing/checkout endpoint."""

    def test_create_checkout_returns_url(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - User already has customer ID
        trial_user_settings.polar_customer_id = "cust_existing_123"
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db
        )

        # Act
        response = client.post(
            "/billing/checkout",
            json={
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel"
            }
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert data["checkout_url"] == "https://checkout.polar.sh/test"

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_create_checkout_creates_polar_customer_if_missing(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - User has no polar_customer_id
        trial_user_settings.polar_customer_id = None
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db
        )

        # Act
        response = client.post(
            "/billing/checkout",
            json={
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel"
            }
        )

        # Assert
        assert response.status_code == 200
        mock_polar_service.get_or_create_customer.assert_called_once()

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_create_checkout_reuses_existing_customer(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - User already has polar_customer_id
        trial_user_settings.polar_customer_id = "cust_existing_456"
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db
        )

        # Act
        response = client.post(
            "/billing/checkout",
            json={
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel"
            }
        )

        # Assert
        assert response.status_code == 200
        mock_polar_service.get_or_create_customer.assert_not_called()
        mock_polar_service.create_checkout_session.assert_called_once_with(
            customer_id="cust_existing_456",
            success_url="https://app.example.com/success",
            cancel_url="https://app.example.com/cancel"
        )

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_create_checkout_requires_authentication(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - No auth overrides
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db, include_auth=False
        )

        # Act
        response = client.post(
            "/billing/checkout",
            json={
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel"
            }
        )

        # Assert
        assert response.status_code == 401

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_create_checkout_handles_polar_service_failure(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange
        trial_user_settings.polar_customer_id = "cust_123"
        mock_polar_service.create_checkout_session.return_value = None
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db
        )

        # Act
        response = client.post(
            "/billing/checkout",
            json={
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel"
            }
        )

        # Assert
        assert response.status_code == 500
        assert "checkout" in response.json()["detail"].lower()

        # Cleanup
        from main import app
        app.dependency_overrides.clear()


# =============================================================================
# Tests: POST /billing/cancel
# =============================================================================

class TestCancelSubscriptionEndpoint:
    """Tests for POST /billing/cancel endpoint."""

    def test_cancel_returns_success_for_active_subscription(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        pro_user_settings, mock_db
    ):
        # Arrange
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            pro_user_settings, mock_db
        )

        # Act
        response = client.post("/billing/cancel")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_polar_service.cancel_subscription.assert_called_once_with("sub_polar_456")

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_cancel_returns_400_when_no_subscription(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - Trial user with no subscription
        trial_user_settings.polar_subscription_id = None
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db
        )

        # Act
        response = client.post("/billing/cancel")

        # Assert
        assert response.status_code == 400
        assert "no active subscription" in response.json()["detail"].lower()

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_cancel_requires_authentication(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - No auth overrides
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db, include_auth=False
        )

        # Act
        response = client.post("/billing/cancel")

        # Assert
        assert response.status_code == 401

        # Cleanup
        from main import app
        app.dependency_overrides.clear()


# =============================================================================
# Tests: GET /billing/portal-url
# =============================================================================

class TestGetPortalUrlEndpoint:
    """Tests for GET /billing/portal-url endpoint."""

    def test_portal_url_returns_url_for_customer(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        pro_user_settings, mock_db
    ):
        # Arrange
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            pro_user_settings, mock_db
        )

        # Act
        response = client.get("/billing/portal-url")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "portal_url" in data
        assert data["portal_url"] == "https://polar.sh/portal/test"
        mock_polar_service.get_customer_portal_url.assert_called_once_with("cust_polar_123")

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_portal_url_returns_400_without_customer(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - User has no polar_customer_id
        trial_user_settings.polar_customer_id = None
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db
        )

        # Act
        response = client.get("/billing/portal-url")

        # Assert
        assert response.status_code == 400
        assert "no billing account" in response.json()["detail"].lower()

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_portal_url_requires_authentication(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        trial_user_settings, mock_db
    ):
        # Arrange - No auth overrides
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            trial_user_settings, mock_db, include_auth=False
        )

        # Act
        response = client.get("/billing/portal-url")

        # Assert
        assert response.status_code == 401

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

    def test_portal_url_handles_polar_service_failure(
        self, mock_settings, mock_polar_service, mock_authenticated_user,
        pro_user_settings, mock_db
    ):
        # Arrange
        mock_polar_service.get_customer_portal_url.return_value = None
        client = create_test_client(
            mock_settings, mock_polar_service, mock_authenticated_user,
            pro_user_settings, mock_db
        )

        # Act
        response = client.get("/billing/portal-url")

        # Assert
        assert response.status_code == 500
        assert "portal" in response.json()["detail"].lower()

        # Cleanup
        from main import app
        app.dependency_overrides.clear()

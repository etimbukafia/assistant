"""Integration tests for billing API (provider-agnostic)."""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.SUPABASE_JWT_SECRET = "test-jwt-secret"
    settings.BILLING_PROVIDER = "dodo"
    settings.FRONTEND_URL = "https://app.example.com"
    settings.CORS_ORIGINS = "https://app.example.com"
    settings.DODO_CREDIT_TOPUP_MIN_USD = 5
    settings.DODO_CREDIT_TOPUP_MAX_USD = 500
    settings.DODO_CREDIT_TOPUP_UNIT_USD = 1
    return settings


@pytest.fixture
def mock_authenticated_user():
    from app.security.auth import AuthenticatedUser
    return AuthenticatedUser(
        user_id="user-uuid-12345",
        email="test@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={"full_name": "Test User"},
    )


@pytest.fixture
def trial_user_settings():
    from datetime import datetime, timezone, timedelta
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
    from datetime import datetime, timezone, timedelta
    from app.data.models import UserSettings

    user = UserSettings(
        user_id="user-uuid-12345",
        user_email="test@example.com",
        subscription_tier="pro",
        subscription_status="active",
        dodo_customer_id="cust_dodo_123",
        dodo_subscription_id="sub_dodo_456",
    )
    user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    return user


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.provider = "dodo"
    provider.enabled = True
    provider.create_checkout_session.return_value = "https://checkout.dodopayments.com/session_123"
    provider.get_customer_portal_url.return_value = "https://app.dodopayments.com/customer-portal/session_123"
    provider.cancel_subscription.return_value = (True, None)
    provider.preview_plan_change.return_value = ({"immediate_amount": 1200, "currency": "USD"}, None)
    provider.change_plan.return_value = ({"status": "active"}, None)
    provider.create_credit_topup_checkout.return_value = ("https://checkout.dodopayments.com/topup_123", None)
    return provider


@pytest.fixture
def mock_db():
    return MagicMock()


def create_test_client(
    mock_settings,
    mock_provider,
    mock_authenticated_user,
    user_settings,
    mock_db,
    include_auth: bool = True,
):
    from fastapi.testclient import TestClient
    from main import app
    from app.infra.database import get_db
    from app.infra.config import get_settings
    from app.security.auth import get_current_user, get_user_settings, get_db_for_user
    from app.services.billing_provider import get_billing_provider

    app.dependency_overrides.clear()

    def override_get_db():
        yield mock_db

    def override_get_settings():
        return mock_settings

    def override_get_current_user():
        return mock_authenticated_user

    def override_get_user_settings():
        return user_settings

    def override_get_db_for_user():
        return mock_db

    def override_get_billing_provider():
        return mock_provider

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_billing_provider] = override_get_billing_provider

    if include_auth:
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_user_settings] = override_get_user_settings
        app.dependency_overrides[get_db_for_user] = override_get_db_for_user

    return TestClient(app)


class TestBillingApi:
    def test_get_subscription(self, mock_settings, mock_provider, mock_authenticated_user, trial_user_settings, mock_db):
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, trial_user_settings, mock_db
        )
        response = client.get("/v1/billing/subscription")
        assert response.status_code == 200
        payload = response.json()
        assert payload["tier"] == "trial"
        assert payload["status"] == "trialing"

    def test_create_checkout(self, mock_settings, mock_provider, mock_authenticated_user, trial_user_settings, mock_db):
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, trial_user_settings, mock_db
        )
        response = client.post(
            "/v1/billing/checkout",
            json={
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )
        assert response.status_code == 200
        assert response.json()["checkout_url"] == "https://checkout.dodopayments.com/session_123"
        mock_provider.create_checkout_session.assert_called_once()

    def test_create_credit_topup_checkout(self, mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db):
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db
        )
        response = client.post(
            "/v1/billing/credits/top-up/checkout",
            json={
                "amount_usd": 5,
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["checkout_url"] == "https://checkout.dodopayments.com/topup_123"
        assert payload["credits_to_add"] == 500
        mock_provider.create_credit_topup_checkout.assert_called_once()

    def test_create_credit_topup_checkout_rejects_below_min(self, mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db):
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db
        )
        response = client.post(
            "/v1/billing/credits/top-up/checkout",
            json={
                "amount_usd": 4,
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )
        assert response.status_code == 400
        assert "minimum top-up is $5" in response.json()["detail"].lower()

    def test_checkout_service_unavailable(self, mock_settings, mock_provider, mock_authenticated_user, trial_user_settings, mock_db):
        mock_provider.enabled = False
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, trial_user_settings, mock_db
        )
        response = client.post(
            "/v1/billing/checkout",
            json={
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )
        assert response.status_code == 503

    def test_cancel_subscription(self, mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db):
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db
        )
        response = client.post("/v1/billing/cancel")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_cancel_no_subscription(self, mock_settings, mock_provider, mock_authenticated_user, trial_user_settings, mock_db):
        mock_provider.cancel_subscription.return_value = (False, "No active subscription to cancel")
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, trial_user_settings, mock_db
        )
        response = client.post("/v1/billing/cancel")
        assert response.status_code == 400

    def test_portal_url(self, mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db):
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db
        )
        response = client.get("/v1/billing/portal-url")
        assert response.status_code == 200
        assert "portal_url" in response.json()

    def test_plan_change_preview(self, mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db):
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db
        )
        response = client.post(
            "/v1/billing/plan-change/preview",
            json={"target_cycle": "annual"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["target_cycle"] == "annual"
        assert "new plan starts immediately" in payload["message"].lower()

    def test_plan_change_execute(self, mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db):
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db
        )
        response = client.post(
            "/v1/billing/plan-change",
            json={"target_cycle": "annual"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert "new plan starts immediately" in payload["message"].lower()

    def test_plan_change_preview_downgrade_deferred(self, mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db):
        pro_user_settings.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=20)
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db
        )
        response = client.post(
            "/v1/billing/plan-change/preview",
            json={"target_cycle": "monthly", "current_cycle": "annual"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["change_direction"] == "downgrade"
        assert payload["effective_timing"] == "next_cycle"
        assert payload["amount_due_today"] == 0.0
        assert "downgrade scheduled" in payload["message"].lower()
        mock_provider.preview_plan_change.assert_not_called()

    def test_plan_change_execute_downgrade_schedules_job(self, mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db):
        from unittest.mock import patch

        pro_user_settings.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=20)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        client = create_test_client(
            mock_settings, mock_provider, mock_authenticated_user, pro_user_settings, mock_db
        )
        with patch("app.routes.v1.billing.enqueue_task") as mocked_enqueue:
            response = client.post(
                "/v1/billing/plan-change",
                json={"target_cycle": "monthly", "current_cycle": "annual"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["change_direction"] == "downgrade"
        assert payload["effective_timing"] == "next_cycle"
        assert "stays active until renewal" in payload["message"].lower()
        mocked_enqueue.assert_called_once()
        mock_provider.change_plan.assert_not_called()

"""Integration tests for generic billing webhook endpoint."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.billing_provider import NormalizedBillingEvent

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def user_settings():
    from app.data.models import UserSettings

    user = UserSettings(
        user_id="user-polar-test-123",
        user_email="polar_user@example.com",
        subscription_tier="trial",
        subscription_status="trialing",
        dodo_customer_id="cust_test_123",
    )
    return user


def create_webhook_test_client(mock_db, user_settings):
    from fastapi.testclient import TestClient
    from main import app
    from app.infra.database import get_db

    app.dependency_overrides.clear()

    def _query_side_effect(model):
        query = MagicMock()
        filtered = MagicMock()
        query.filter.return_value = filtered
        model_name = getattr(model, "__name__", "")
        if model_name == "WebhookDelivery":
            filtered.first.return_value = None
        elif model_name == "UserSettings":
            filtered.first.return_value = user_settings
        else:
            filtered.first.return_value = None
        return query

    mock_db.query.side_effect = _query_side_effect

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


class TestBillingWebhookEndpoint:
    def test_billing_webhook_processes_subscription_created(self, mock_db, user_settings):
        client = create_webhook_test_client(mock_db, user_settings)

        event = NormalizedBillingEvent(
            provider="dodo",
            event_type="subscription.created",
            raw_event_type="subscription.created",
            delivery_id="evt_123",
            customer_id="cust_test_123",
            customer_email="polar_user@example.com",
            subscription_id="sub_test_123",
            subscription_status="active",
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            raw={"type": "subscription.created", "data": {}},
        )

        mock_provider = MagicMock()
        mock_provider.provider = "dodo"
        mock_provider.normalize_webhook_event.return_value = event

        with patch("app.routes.v1.webhooks.build_billing_provider", return_value=mock_provider), \
             patch("app.routes.v1.webhooks.queue_service.enqueue", return_value=MagicMock(id=123)):
            response = client.post(
                "/v1/webhooks/billing",
                headers={
                    "webhook-id": "evt_123",
                    "webhook-timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                    "webhook-signature": "v1,testsig",
                },
                json={"type": "subscription.created", "data": {}},
            )

        assert response.status_code == 200
        assert response.json()["handled"] is True
        assert response.json()["queued"] is True

    def test_billing_webhook_invalid_signature(self, mock_db, user_settings):
        client = create_webhook_test_client(mock_db, user_settings)

        mock_provider = MagicMock()
        mock_provider.provider = "dodo"
        mock_provider.normalize_webhook_event.side_effect = ValueError("invalid_webhook_signature")

        with patch("app.routes.v1.webhooks.build_billing_provider", return_value=mock_provider):
            response = client.post(
                "/v1/webhooks/billing",
                headers={
                    "webhook-id": "evt_123",
                    "webhook-timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                    "webhook-signature": "v1,testsig",
                },
                json={"type": "subscription.created", "data": {}},
            )

        assert response.status_code == 400

    def test_billing_webhook_unknown_event_no_handler(self, mock_db, user_settings):
        client = create_webhook_test_client(mock_db, user_settings)

        event = NormalizedBillingEvent(
            provider="dodo",
            event_type="unknown.event",
            raw_event_type="unknown.event",
            delivery_id="evt_999",
            customer_id="cust_test_123",
            customer_email="polar_user@example.com",
            subscription_id=None,
            subscription_status=None,
            period_start=None,
            period_end=None,
            raw={"type": "unknown.event", "data": {}},
        )

        mock_provider = MagicMock()
        mock_provider.provider = "dodo"
        mock_provider.normalize_webhook_event.return_value = event

        with patch("app.routes.v1.webhooks.build_billing_provider", return_value=mock_provider), \
             patch("app.routes.v1.webhooks.queue_service.enqueue", return_value=MagicMock(id=124)):
            response = client.post(
                "/v1/webhooks/billing",
                headers={
                    "webhook-id": "evt_999",
                    "webhook-timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                    "webhook-signature": "v1,testsig",
                },
                json={"type": "unknown.event", "data": {}},
            )

        assert response.status_code == 200
        assert response.json()["handled"] is True
        assert response.json()["queued"] is True

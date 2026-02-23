import os
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.data.models import UserSettings
from app.handlers import webhook_handlers


class DummyBodyRequest:
    def __init__(self, payload: bytes, headers: dict | None = None):
        self._payload = payload
        self.headers = headers or {}

    async def body(self):
        return self._payload


def _seed_user(db, customer_id: str = "cust-1") -> UserSettings:
    user = UserSettings(
        user_id="user-1",
        user_email="ea@example.com",
        subscription_tier="trial",
        subscription_status="trialing",
        polar_customer_id=customer_id,
        credits_used=1.5,
        credits_limit=1.0,
    )
    db.add(user)
    db.commit()
    return user


@pytest.mark.asyncio
async def test_polar_webhook_duplicate_delivery_is_idempotent(db_session, monkeypatch):
    user = _seed_user(db_session)

    event = {
        "type": "subscription.created",
        "data": {
            "id": "sub-1",
            "customer_id": user.polar_customer_id,
            "current_period_end": "2026-03-31T00:00:00Z",
        },
    }
    monkeypatch.setattr(webhook_handlers, "validate_webhook_signature", lambda payload, headers: event)

    request = DummyBodyRequest(
        payload=b'{"type":"subscription.created"}',
        headers={
            "webhook-id": "polar-delivery-1",
            "webhook-timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "webhook-signature": "sig",
        },
    )

    first = await webhook_handlers.handle_polar_webhook(request=request, db=db_session)
    assert first["handled"] is True

    # Simulate real usage change after first successful processing.
    refreshed = db_session.query(UserSettings).filter(UserSettings.user_id == user.user_id).first()
    refreshed.credits_used = 2.25
    db_session.commit()

    second = await webhook_handlers.handle_polar_webhook(request=request, db=db_session)
    assert second["handled"] is True
    assert second["duplicate"] is True

    after = db_session.query(UserSettings).filter(UserSettings.user_id == user.user_id).first()
    assert after.credits_used == 2.25


@pytest.mark.asyncio
async def test_polar_webhook_customer_id_extraction_top_level_data(db_session, monkeypatch):
    user = _seed_user(db_session, customer_id="cust-top-level")

    event = {
        "type": "subscription.updated",
        "data": {
            "id": "sub-2",
            "customer_id": user.polar_customer_id,
            "status": "past_due",
            "current_period_end": "2026-04-15T00:00:00Z",
        },
    }
    monkeypatch.setattr(webhook_handlers, "validate_webhook_signature", lambda payload, headers: event)

    request = DummyBodyRequest(
        payload=b'{"type":"subscription.updated"}',
        headers={
            "webhook-id": "polar-delivery-2",
            "webhook-timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "webhook-signature": "sig",
        },
    )

    result = await webhook_handlers.handle_polar_webhook(request=request, db=db_session)
    assert result["handled"] is True

    updated = db_session.query(UserSettings).filter(UserSettings.user_id == user.user_id).first()
    assert updated.subscription_status == "past_due"


@pytest.mark.asyncio
async def test_polar_webhook_invalid_signature_bubbles_400(db_session, monkeypatch):
    def _raise_invalid(payload, headers):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    monkeypatch.setattr(webhook_handlers, "validate_webhook_signature", _raise_invalid)

    request = DummyBodyRequest(
        payload=b"{}",
        headers={
            "webhook-id": "polar-delivery-bad",
            "webhook-timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "webhook-signature": "bad",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        await webhook_handlers.handle_polar_webhook(request=request, db=db_session)

    assert exc_info.value.status_code == 400

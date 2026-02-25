import pytest
from datetime import datetime, timezone, timedelta

from app.data.models import BillingEvent, UserSettings, WebhookLog
from app.jobs.worker import handle_process_billing_webhook_event


@pytest.mark.asyncio
async def test_process_billing_webhook_event_updates_subscription_status(db_session, monkeypatch):
    from app.infra import database as db_module

    monkeypatch.setattr(db_module, "SessionLocal", lambda: db_session)

    user = UserSettings(
        user_id="user-billing-worker-1",
        user_email="worker1@example.com",
        subscription_tier="pro",
        subscription_status="active",
        dodo_customer_id="cust_worker_1",
    )
    db_session.add(user)
    db_session.commit()

    payload = {
        "event": {
            "provider": "dodo",
            "event_type": "invoice.payment_failed",
            "raw_event_type": "invoice.payment_failed",
            "delivery_id": "evt_worker_1",
            "customer_id": "cust_worker_1",
            "customer_email": "worker1@example.com",
            "subscription_id": "sub_worker_1",
            "subscription_status": "past_due",
            "period_start": datetime.now(timezone.utc).isoformat(),
            "period_end": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "raw": {
                "type": "invoice.payment_failed",
                "data": {
                    "status": "failed",
                },
            },
        }
    }

    await handle_process_billing_webhook_event(
        task_id=1,
        task_type="process_billing_webhook_event",
        payload=payload,
        correlation_id="evt_worker_1",
    )

    db_session.refresh(user)
    assert user.subscription_status == "past_due"

    event_row = db_session.query(BillingEvent).filter(
        BillingEvent.provider == "dodo",
        BillingEvent.delivery_id == "evt_worker_1",
    ).first()
    assert event_row is not None
    assert event_row.handled is True

    webhook_log = db_session.query(WebhookLog).filter(
        WebhookLog.source == "dodo",
        WebhookLog.event_type == "invoice.payment_failed",
    ).first()
    assert webhook_log is None


@pytest.mark.asyncio
async def test_process_billing_webhook_event_skips_when_already_handled(db_session, monkeypatch):
    from app.infra import database as db_module

    monkeypatch.setattr(db_module, "SessionLocal", lambda: db_session)

    db_session.add(
        BillingEvent(
            provider="dodo",
            delivery_id="evt_worker_dup",
            event_type="subscription.updated",
            handled=True,
            payload={"normalized": {"provider": "dodo", "delivery_id": "evt_worker_dup"}},
        )
    )
    db_session.commit()

    await handle_process_billing_webhook_event(
        task_id=2,
        task_type="process_billing_webhook_event",
        payload={
            "event": {
                "provider": "dodo",
                "event_type": "subscription.updated",
                "raw_event_type": "subscription.updated",
                "delivery_id": "evt_worker_dup",
                "raw": {"type": "subscription.updated", "data": {}},
            }
        },
        correlation_id="evt_worker_dup",
    )

    logs = db_session.query(WebhookLog).filter(
        WebhookLog.source == "dodo",
        WebhookLog.event_type == "subscription.updated",
    ).all()
    assert len(logs) == 0

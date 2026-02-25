from datetime import datetime, timezone

from app.data.models import CreditTopup, UserSettings
from app.services.billing_provider import NormalizedBillingEvent, apply_billing_event


def _event(
    *,
    delivery_id: str,
    product_id: str,
    payment_id: str,
    amount_minor: int,
    customer_id: str = "cust_topup_1",
) -> NormalizedBillingEvent:
    return NormalizedBillingEvent(
        provider="dodo",
        event_type="payment.succeeded",
        raw_event_type="payment.succeeded",
        delivery_id=delivery_id,
        customer_id=customer_id,
        customer_email="topup@example.com",
        subscription_id=None,
        subscription_status=None,
        period_start=None,
        period_end=None,
        raw={
            "type": "payment.succeeded",
            "data": {
                "customer_id": customer_id,
                "payment_id": payment_id,
                "amount": amount_minor,
                "currency": "USD",
                "product_id": product_id,
            },
        },
    )


def test_credit_topup_payment_adds_credits(db_session, monkeypatch):
    user = UserSettings(
        user_id="user_topup_1",
        user_email="topup@example.com",
        dodo_customer_id="cust_topup_1",
        subscription_tier="pro",
        subscription_status="active",
        credits_limit=5.0,
        credits_used=0.0,
        credits_period_start=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()

    class _Settings:
        DODO_CREDIT_TOPUP_PRODUCT_ID = "prod_topup_1"
        DODO_PRODUCT_ID = ""
        DODO_PRODUCT_ID_MONTHLY = ""
        DODO_PRODUCT_ID_ANNUAL = ""

    monkeypatch.setattr("app.services.billing_provider.get_settings", lambda: _Settings())

    handled = apply_billing_event(
        db_session,
        _event(
            delivery_id="evt_topup_1",
            product_id="prod_topup_1",
            payment_id="pay_topup_1",
            amount_minor=700,
        ),
    )
    assert handled is True

    db_session.refresh(user)
    assert user.credits_limit == 12.0

    topup = db_session.query(CreditTopup).filter(
        CreditTopup.provider == "dodo",
        CreditTopup.provider_payment_id == "pay_topup_1",
    ).first()
    assert topup is not None
    assert topup.credits_added == 700


def test_credit_topup_idempotent_by_payment_id(db_session, monkeypatch):
    user = UserSettings(
        user_id="user_topup_2",
        user_email="topup2@example.com",
        dodo_customer_id="cust_topup_2",
        subscription_tier="pro",
        subscription_status="active",
        credits_limit=5.0,
        credits_used=0.0,
    )
    db_session.add(user)
    db_session.commit()

    class _Settings:
        DODO_CREDIT_TOPUP_PRODUCT_ID = "prod_topup_2"
        DODO_PRODUCT_ID = ""
        DODO_PRODUCT_ID_MONTHLY = ""
        DODO_PRODUCT_ID_ANNUAL = ""

    monkeypatch.setattr("app.services.billing_provider.get_settings", lambda: _Settings())

    event = _event(
        delivery_id="evt_topup_2",
        product_id="prod_topup_2",
        payment_id="pay_topup_same",
        amount_minor=500,
        customer_id="cust_topup_2",
    )
    apply_billing_event(db_session, event)
    apply_billing_event(db_session, event)

    db_session.refresh(user)
    assert user.credits_limit == 10.0
    assert db_session.query(CreditTopup).filter(
        CreditTopup.provider_payment_id == "pay_topup_same",
    ).count() == 1


def test_non_subscription_non_topup_payment_does_not_mutate_subscription(db_session, monkeypatch):
    user = UserSettings(
        user_id="user_trial_1",
        user_email="trial@example.com",
        dodo_customer_id="cust_trial_1",
        subscription_tier="trial",
        subscription_status="trialing",
        credits_limit=1.0,
        credits_used=0.0,
    )
    db_session.add(user)
    db_session.commit()

    class _Settings:
        DODO_CREDIT_TOPUP_PRODUCT_ID = "prod_topup_other"
        DODO_PRODUCT_ID = ""
        DODO_PRODUCT_ID_MONTHLY = ""
        DODO_PRODUCT_ID_ANNUAL = ""

    monkeypatch.setattr("app.services.billing_provider.get_settings", lambda: _Settings())

    handled = apply_billing_event(
        db_session,
        _event(
            delivery_id="evt_non_sub_payment",
            product_id="prod_one_time_book",
            payment_id="pay_non_sub",
            amount_minor=999,
            customer_id="cust_trial_1",
        ),
    )
    assert handled is True

    db_session.refresh(user)
    assert user.subscription_tier == "trial"
    assert user.subscription_status == "trialing"
    assert db_session.query(CreditTopup).count() == 0

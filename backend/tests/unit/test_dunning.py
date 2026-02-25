from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.data.models import UserSettings
from app.services.billing_provider import NormalizedBillingEvent
from app.services.dunning import (
    STAGE_FINAL,
    STAGE_INITIAL,
    STAGE_MIDPOINT,
    apply_failure_state,
    clear_dunning_state,
    is_failure_event,
    is_recovery_event,
    should_suspend_access,
    stage_due_for_user,
    suspend_access,
)


def _event(event_type: str, status: str | None = None) -> NormalizedBillingEvent:
    return NormalizedBillingEvent(
        provider="dodo",
        event_type=event_type,
        raw_event_type=event_type,
        delivery_id="evt_test",
        customer_id="cust_test",
        customer_email="test@example.com",
        subscription_id="sub_test",
        subscription_status=status,
        period_start=None,
        period_end=None,
        raw={"type": event_type, "data": {}},
    )


def test_apply_failure_state_starts_dunning_window():
    now = datetime.now(timezone.utc)
    user = UserSettings(
        user_id="user-dunning-1",
        user_email="user1@example.com",
        subscription_tier="pro",
        subscription_status="active",
    )

    stage = apply_failure_state(user, _event("payment.failed"), now=now)

    assert stage == STAGE_INITIAL
    assert user.dunning_active is True
    assert user.subscription_status == "past_due"
    assert user.dunning_attempt_count == 1
    assert user.dunning_started_at is not None
    assert user.dunning_deadline_at is not None


def test_recovery_clears_dunning_state():
    user = UserSettings(
        user_id="user-dunning-2",
        user_email="user2@example.com",
        subscription_tier="pro",
        subscription_status="past_due",
        dunning_active=True,
        dunning_attempt_count=2,
        dunning_last_notified_stage=STAGE_MIDPOINT,
        dunning_suspended_at=datetime.now(timezone.utc),
    )

    assert is_recovery_event(_event("invoice.paid")) is True
    clear_dunning_state(user)

    assert user.dunning_active is False
    assert user.dunning_attempt_count == 0
    assert user.dunning_last_notified_stage is None
    assert user.dunning_suspended_at is None


def test_stage_due_midpoint_and_final():
    now = datetime.now(timezone.utc)
    user = UserSettings(
        user_id="user-dunning-3",
        user_email="user3@example.com",
        subscription_tier="pro",
        subscription_status="past_due",
        dunning_active=True,
        dunning_started_at=now - timedelta(days=4),
        dunning_deadline_at=now + timedelta(days=3),
        dunning_last_notified_stage=STAGE_INITIAL,
    )

    assert stage_due_for_user(user, now=now) == STAGE_MIDPOINT

    user.dunning_last_notified_stage = STAGE_MIDPOINT
    user.dunning_deadline_at = now - timedelta(minutes=1)
    assert stage_due_for_user(user, now=now) == STAGE_FINAL


def test_suspend_access_after_deadline():
    now = datetime.now(timezone.utc)
    user = UserSettings(
        user_id="user-dunning-4",
        user_email="user4@example.com",
        subscription_tier="pro",
        subscription_status="past_due",
        dunning_active=True,
        dunning_deadline_at=now - timedelta(minutes=1),
    )

    assert should_suspend_access(user, now=now) is True
    suspend_access(user, now=now)
    assert user.dunning_suspended_at is not None
    assert user.subscription_status == "past_due"


def test_failure_and_recovery_event_detection():
    assert is_failure_event(_event("invoice.payment_failed")) is True
    assert is_failure_event(_event("subscription.updated", status="past_due")) is True
    assert is_failure_event(_event("subscription.updated", status="active")) is False

    assert is_recovery_event(_event("payment.succeeded")) is True
    assert is_recovery_event(_event("subscription.updated", status="active")) is True

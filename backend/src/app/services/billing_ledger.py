"""
Billing ledger persistence helpers.

Maintains first-class billing domain records:
- billing_plans
- billing_subscriptions
- billing_invoices
- billing_payment_attempts
- billing_events
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.data.models import (
    BillingEvent,
    BillingInvoice,
    BillingPaymentAttempt,
    BillingPlan,
    BillingSubscription,
    UserSettings,
)
from app.infra.config import get_settings
from app.services.billing_provider import NormalizedBillingEvent, serialize_billing_event


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_data(raw: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw.get("payload"), dict) and isinstance(raw["payload"].get("data"), dict):
        return raw["payload"]["data"] or {}
    if isinstance(raw.get("data"), dict):
        return raw["data"] or {}
    return {}


def _normalize_interval(interval: Optional[str], plan_id: Optional[str]) -> str:
    token = ((interval or "") + " " + (plan_id or "")).lower()
    if any(x in token for x in ["year", "annual", "yr"]):
        return "annual"
    if "one_time" in token or "one-time" in token:
        return "one_time"
    return "monthly"


def _normalize_invoice_status(status: Optional[str]) -> str:
    s = (status or "").strip().lower()
    if s in {"paid", "succeeded"}:
        return "paid"
    if s in {"void", "voided"}:
        return "void"
    if s in {"uncollectible"}:
        return "uncollectible"
    if s in {"failed", "payment_failed"}:
        return "failed"
    if s in {"draft"}:
        return "draft"
    return "open"


def _normalize_attempt_status(status: Optional[str], event_type: str) -> str:
    s = (status or "").strip().lower()
    if event_type == "payment.succeeded":
        return "succeeded"
    if event_type == "payment.failed":
        return "failed"
    if s in {"succeeded", "paid"}:
        return "succeeded"
    if s in {"failed", "payment_failed"}:
        return "failed"
    if s in {"requires_action", "requires_payment_method"}:
        return "requires_action"
    if s in {"canceled", "cancelled"}:
        return "canceled"
    return "pending"


def ensure_billing_plan(
    db: Session,
    *,
    provider: str,
    plan_id: str,
    billing_interval: str = "monthly",
    price_minor: int | None = None,
    currency: str = "USD",
    name: str | None = None,
) -> BillingPlan:
    plan = db.query(BillingPlan).filter(
        BillingPlan.provider == provider,
        BillingPlan.plan_id == plan_id,
    ).first()

    if not plan:
        plan = BillingPlan(
            provider=provider,
            plan_id=plan_id,
            billing_interval=billing_interval,
            price_minor=price_minor,
            currency=currency,
            name=name,
        )
        db.add(plan)
        db.flush()
        return plan

    changed = False
    if billing_interval and plan.billing_interval != billing_interval:
        plan.billing_interval = billing_interval
        changed = True
    if price_minor is not None and plan.price_minor != price_minor:
        plan.price_minor = price_minor
        changed = True
    if currency and plan.currency != currency:
        plan.currency = currency
        changed = True
    if name and plan.name != name:
        plan.name = name
        changed = True
    if changed:
        db.flush()
    return plan


def ensure_configured_plans(db: Session, *, provider: str) -> None:
    settings = get_settings()
    if provider != "dodo":
        return

    monthly = settings.DODO_PRODUCT_ID_MONTHLY or settings.DODO_PRODUCT_ID
    annual = settings.DODO_PRODUCT_ID_ANNUAL
    topup = settings.DODO_CREDIT_TOPUP_PRODUCT_ID

    if monthly:
        ensure_billing_plan(
            db,
            provider=provider,
            plan_id=monthly,
            billing_interval="monthly",
        )
    if annual:
        ensure_billing_plan(
            db,
            provider=provider,
            plan_id=annual,
            billing_interval="annual",
        )
    if topup:
        ensure_billing_plan(
            db,
            provider=provider,
            plan_id=topup,
            billing_interval="one_time",
            name="Credits Top-up",
        )


def sync_subscription_snapshot_from_settings(
    db: Session,
    *,
    settings_row: UserSettings,
    provider: str,
) -> None:
    """
    Backfill/sync a billing_subscriptions snapshot from UserSettings.
    Useful for pre-webhook paths (checkout/cancel/read subscription).
    """
    if provider == "dodo":
        provider_sub_id = settings_row.dodo_subscription_id
        provider_customer_id = settings_row.dodo_customer_id
        plan_external_id = settings_row.dodo_subscription_id
    else:
        provider_sub_id = settings_row.polar_subscription_id
        provider_customer_id = settings_row.polar_customer_id
        plan_external_id = settings_row.polar_subscription_id

    subscription = None
    if provider_sub_id:
        subscription = db.query(BillingSubscription).filter(
            BillingSubscription.provider == provider,
            BillingSubscription.provider_subscription_id == provider_sub_id,
        ).first()

    if not subscription:
        subscription = db.query(BillingSubscription).filter(
            BillingSubscription.user_id == settings_row.user_id,
            BillingSubscription.provider == provider,
        ).order_by(BillingSubscription.id.desc()).first()

    if not subscription:
        subscription = BillingSubscription(
            user_id=settings_row.user_id,
            provider=provider,
        )
        db.add(subscription)
        db.flush()

    subscription.provider_subscription_id = provider_sub_id or subscription.provider_subscription_id
    subscription.provider_customer_id = provider_customer_id or subscription.provider_customer_id
    subscription.plan_external_id = plan_external_id or subscription.plan_external_id
    subscription.status = settings_row.subscription_status or subscription.status
    subscription.current_period_end = settings_row.subscription_expires_at or subscription.current_period_end
    subscription.cancel_at_period_end = (subscription.status == "cancel_scheduled")
    db.flush()


def _resolve_plan_from_event(db: Session, provider: str, data: dict[str, Any]) -> BillingPlan | None:
    plan_obj = data.get("plan") if isinstance(data.get("plan"), dict) else {}
    product_obj = data.get("product") if isinstance(data.get("product"), dict) else {}
    plan_id = (
        data.get("product_id")
        or data.get("plan_id")
        or plan_obj.get("id")
        or product_obj.get("id")
    )
    if not plan_id:
        return None

    interval_raw = (
        data.get("payment_frequency_interval")
        or data.get("billing_interval")
        or plan_obj.get("billing_interval")
        or product_obj.get("billing_interval")
    )
    interval = _normalize_interval(interval_raw, plan_id)
    price_minor = (
        _to_int(data.get("recurring_pre_tax_amount"))
        or _to_int(data.get("amount"))
        or _to_int(plan_obj.get("price"))
        or _to_int(product_obj.get("price"))
    )
    currency = str(
        data.get("currency")
        or plan_obj.get("currency")
        or product_obj.get("currency")
        or "USD"
    ).upper()
    name = data.get("product_name") or plan_obj.get("name") or product_obj.get("name")

    return ensure_billing_plan(
        db,
        provider=provider,
        plan_id=str(plan_id),
        billing_interval=interval,
        price_minor=price_minor,
        currency=currency,
        name=name,
    )


def _upsert_subscription(
    db: Session,
    *,
    user: UserSettings,
    event: NormalizedBillingEvent,
    data: dict[str, Any],
) -> BillingSubscription:
    subscription = None
    if event.subscription_id:
        subscription = db.query(BillingSubscription).filter(
            BillingSubscription.provider == event.provider,
            BillingSubscription.provider_subscription_id == event.subscription_id,
        ).first()

    if not subscription:
        subscription = db.query(BillingSubscription).filter(
            BillingSubscription.user_id == user.user_id,
            BillingSubscription.provider == event.provider,
        ).order_by(BillingSubscription.id.desc()).first()

    if not subscription:
        subscription = BillingSubscription(
            user_id=user.user_id,
            provider=event.provider,
        )
        db.add(subscription)
        db.flush()

    plan = _resolve_plan_from_event(db, event.provider, data)
    subscription.provider_subscription_id = event.subscription_id or subscription.provider_subscription_id
    subscription.provider_customer_id = event.customer_id or subscription.provider_customer_id
    subscription.plan_id = plan.id if plan else subscription.plan_id
    subscription.plan_external_id = plan.plan_id if plan else subscription.plan_external_id
    if event.subscription_status:
        subscription.status = event.subscription_status
    if event.period_start:
        subscription.current_period_start = event.period_start
    if event.period_end:
        subscription.current_period_end = event.period_end

    cancel_flag = data.get("cancel_at_next_billing_date")
    if cancel_flag is None:
        cancel_flag = data.get("cancel_at_period_end")
    if cancel_flag is not None:
        subscription.cancel_at_period_end = bool(cancel_flag)

    canceled_at = _parse_dt(data.get("canceled_at")) or _parse_dt(data.get("cancelled_at"))
    if canceled_at:
        subscription.canceled_at = canceled_at

    if event.event_type == "subscription.canceled" and event.period_end:
        subscription.cancel_at_period_end = True
    if event.event_type == "subscription.revoked":
        subscription.cancel_at_period_end = False
        subscription.canceled_at = datetime.now(timezone.utc)
    subscription.provider_metadata = {
        "source_event": event.event_type,
        "raw_status": data.get("status"),
    }
    db.flush()
    return subscription


def _upsert_invoice(
    db: Session,
    *,
    user: UserSettings,
    event: NormalizedBillingEvent,
    subscription: BillingSubscription,
    data: dict[str, Any],
) -> BillingInvoice | None:
    invoice_obj = data.get("invoice") if isinstance(data.get("invoice"), dict) else {}
    provider_invoice_id = (
        data.get("invoice_id")
        or invoice_obj.get("id")
        or invoice_obj.get("invoice_id")
    )
    if not provider_invoice_id:
        return None

    invoice = db.query(BillingInvoice).filter(
        BillingInvoice.provider == event.provider,
        BillingInvoice.provider_invoice_id == str(provider_invoice_id),
    ).first()
    if not invoice:
        invoice = BillingInvoice(
            user_id=user.user_id,
            provider=event.provider,
            provider_invoice_id=str(provider_invoice_id),
        )
        db.add(invoice)
        db.flush()

    invoice.subscription_id = subscription.id if subscription else invoice.subscription_id
    invoice.provider_subscription_id = event.subscription_id or invoice.provider_subscription_id
    invoice.currency = str(
        invoice_obj.get("currency")
        or data.get("currency")
        or invoice.currency
        or "USD"
    ).upper()
    invoice.amount_due_minor = _to_int(invoice_obj.get("amount_due")) or _to_int(data.get("amount_due")) or invoice.amount_due_minor
    invoice.amount_paid_minor = _to_int(invoice_obj.get("amount_paid")) or _to_int(data.get("amount_paid")) or invoice.amount_paid_minor
    invoice.amount_remaining_minor = _to_int(invoice_obj.get("amount_remaining")) or _to_int(data.get("amount_remaining")) or invoice.amount_remaining_minor
    invoice.status = _normalize_invoice_status(
        invoice_obj.get("status") or data.get("invoice_status") or data.get("status")
    )
    invoice.period_start = _parse_dt(invoice_obj.get("period_start")) or invoice.period_start
    invoice.period_end = _parse_dt(invoice_obj.get("period_end")) or invoice.period_end
    invoice.due_at = _parse_dt(invoice_obj.get("due_at")) or invoice.due_at
    invoice.paid_at = _parse_dt(invoice_obj.get("paid_at")) or invoice.paid_at
    invoice.invoice_pdf_url = invoice_obj.get("invoice_pdf") or invoice.invoice_pdf_url
    invoice.hosted_invoice_url = invoice_obj.get("hosted_invoice_url") or invoice.hosted_invoice_url
    invoice.provider_metadata = {
        "source_event": event.event_type,
    }
    db.flush()
    return invoice


def _upsert_payment_attempt(
    db: Session,
    *,
    user: UserSettings,
    event: NormalizedBillingEvent,
    invoice: BillingInvoice | None,
    data: dict[str, Any],
) -> None:
    payment_obj = data.get("payment") if isinstance(data.get("payment"), dict) else {}
    provider_attempt_id = (
        data.get("payment_attempt_id")
        or payment_obj.get("attempt_id")
        or payment_obj.get("id")
    )
    # Only persist payment attempts for explicit payment events or when an attempt id exists.
    if not provider_attempt_id and not event.raw_event_type.lower().startswith("payment."):
        return

    attempt = None
    if provider_attempt_id:
        attempt = db.query(BillingPaymentAttempt).filter(
            BillingPaymentAttempt.provider == event.provider,
            BillingPaymentAttempt.provider_attempt_id == str(provider_attempt_id),
        ).first()

    if not attempt:
        attempt = BillingPaymentAttempt(
            user_id=user.user_id,
            provider=event.provider,
            provider_attempt_id=str(provider_attempt_id) if provider_attempt_id else None,
        )
        db.add(attempt)
        db.flush()

    attempt.invoice_id = invoice.id if invoice else attempt.invoice_id
    attempt.provider_payment_id = (
        payment_obj.get("payment_id")
        or data.get("payment_id")
        or attempt.provider_payment_id
    )
    attempt.provider_subscription_id = event.subscription_id or attempt.provider_subscription_id
    attempt.status = _normalize_attempt_status(
        payment_obj.get("status") or data.get("payment_status"),
        event.raw_event_type.lower(),
    )
    attempt.currency = str(
        payment_obj.get("currency")
        or data.get("currency")
        or attempt.currency
        or "USD"
    ).upper()
    attempt.amount_minor = (
        _to_int(payment_obj.get("amount"))
        or _to_int(data.get("amount"))
        or attempt.amount_minor
    )
    attempt.failure_code = payment_obj.get("failure_code") or data.get("failure_code") or attempt.failure_code
    attempt.failure_message = payment_obj.get("failure_message") or data.get("failure_message") or attempt.failure_message
    attempt.attempted_at = (
        _parse_dt(payment_obj.get("attempted_at"))
        or _parse_dt(data.get("attempted_at"))
        or datetime.now(timezone.utc)
    )
    attempt.provider_metadata = {"source_event": event.event_type}
    db.flush()


def upsert_billing_event_audit(
    db: Session,
    *,
    event: NormalizedBillingEvent,
    user_id: str | None,
    handled: bool,
    error: str | None,
) -> None:
    record = None
    if event.delivery_id:
        record = db.query(BillingEvent).filter(
            BillingEvent.provider == event.provider,
            BillingEvent.delivery_id == event.delivery_id,
        ).first()

    if not record:
        record = BillingEvent(
            provider=event.provider,
            delivery_id=event.delivery_id,
            received_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.flush()

    data = _event_data(event.raw)
    invoice_obj = data.get("invoice") if isinstance(data.get("invoice"), dict) else {}
    invoice_id = data.get("invoice_id") or invoice_obj.get("id")

    record.user_id = user_id or record.user_id
    record.event_type = event.event_type
    record.customer_id = event.customer_id
    record.subscription_id = event.subscription_id
    record.invoice_id = event.invoice_id or (str(invoice_id) if invoice_id else record.invoice_id)
    record.handled = handled
    record.error = error
    record.payload = {
        "normalized": serialize_billing_event(event),
    }
    record.processed_at = datetime.now(timezone.utc)
    db.flush()


def sync_billing_ledger_from_event(
    db: Session,
    *,
    event: NormalizedBillingEvent,
    user: UserSettings | None,
    handled: bool,
    error: str | None = None,
) -> None:
    upsert_billing_event_audit(
        db,
        event=event,
        user_id=user.user_id if user else None,
        handled=handled,
        error=error,
    )

    if not user or not handled:
        return

    data = _event_data(event.raw)
    subscription = _upsert_subscription(
        db,
        user=user,
        event=event,
        data=data,
    )
    invoice = _upsert_invoice(
        db,
        user=user,
        event=event,
        subscription=subscription,
        data=data,
    )
    _upsert_payment_attempt(
        db,
        user=user,
        event=event,
        invoice=invoice,
        data=data,
    )

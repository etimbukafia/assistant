"""
Billing provider abstraction.

Switches billing implementation between Dodo and Polar with a consistent
router-facing API and normalized webhook events.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.data.models import CreditTopup, UserSettings
from app.infra.config import Settings, get_settings
from app.services.dodo import DodoService, get_dodo_service
from app.services.polar import PolarService, get_polar_service

logger = logging.getLogger(__name__)


@dataclass
class NormalizedBillingEvent:
    provider: str
    event_type: str
    raw_event_type: str
    delivery_id: Optional[str]
    customer_id: Optional[str]
    customer_email: Optional[str]
    subscription_id: Optional[str]
    subscription_status: Optional[str]
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    invoice_id: Optional[str]
    payload_kind: Optional[str]
    product_ids: list[str]
    payment_amount_minor: Optional[int]
    payment_currency: Optional[str]
    raw: dict[str, Any]


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _dt_to_iso(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def serialize_billing_event(event: NormalizedBillingEvent) -> dict[str, Any]:
    """Serialize a minimized billing event for queue payloads and replay."""
    return {
        "provider": event.provider,
        "event_type": event.event_type,
        "raw_event_type": event.raw_event_type,
        "delivery_id": event.delivery_id,
        "customer_id": event.customer_id,
        "subscription_id": event.subscription_id,
        "subscription_status": event.subscription_status,
        "period_start": _dt_to_iso(event.period_start),
        "period_end": _dt_to_iso(event.period_end),
        "invoice_id": event.invoice_id,
        "payload_kind": event.payload_kind,
        "product_ids": list(event.product_ids or []),
        "payment_amount_minor": event.payment_amount_minor,
        "payment_currency": event.payment_currency,
    }


def deserialize_billing_event(payload: dict[str, Any]) -> NormalizedBillingEvent:
    """Deserialize queue/replay payload into NormalizedBillingEvent."""
    return NormalizedBillingEvent(
        provider=str(payload.get("provider") or ""),
        event_type=str(payload.get("event_type") or "unknown"),
        raw_event_type=str(payload.get("raw_event_type") or payload.get("event_type") or "unknown"),
        delivery_id=payload.get("delivery_id"),
        customer_id=payload.get("customer_id"),
        customer_email=payload.get("customer_email"),
        subscription_id=payload.get("subscription_id"),
        subscription_status=payload.get("subscription_status"),
        period_start=_parse_dt(payload.get("period_start")),
        period_end=_parse_dt(payload.get("period_end")),
        invoice_id=(str(payload.get("invoice_id")) if payload.get("invoice_id") else None),
        payload_kind=(str(payload.get("payload_kind")) if payload.get("payload_kind") else None),
        product_ids=[str(v) for v in (payload.get("product_ids") or []) if str(v).strip()],
        payment_amount_minor=(int(payload.get("payment_amount_minor")) if payload.get("payment_amount_minor") is not None else None),
        payment_currency=(str(payload.get("payment_currency")).upper() if payload.get("payment_currency") else None),
        raw=payload.get("raw") if isinstance(payload.get("raw"), dict) else {},
    )


def _is_future(value: Optional[datetime]) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value > datetime.now(timezone.utc)


def _normalize_subscription_status(status: Optional[str]) -> Optional[str]:
    if not status:
        return None

    s = status.strip().lower()
    if s in {"active", "trialing", "trial"}:
        return "active"
    if s in {"cancel_scheduled", "cancel_at_period_end"}:
        return "cancel_scheduled"
    if s in {"canceled", "cancelled"}:
        return "canceled"
    if s in {"expired", "revoked", "ended", "terminated"}:
        return "expired"
    if s in {"past_due", "on_hold", "paused", "unpaid", "payment_failed"}:
        return "past_due"
    return s


def _event_data(raw: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw.get("payload"), dict) and isinstance(raw["payload"].get("data"), dict):
        return raw["payload"]["data"] or {}
    if isinstance(raw.get("data"), dict):
        return raw["data"] or {}
    return {}


def _extract_product_ids(data: dict[str, Any]) -> set[str]:
    product_ids: set[str] = set()

    direct = data.get("product_id")
    if isinstance(direct, str) and direct.strip():
        product_ids.add(direct.strip())

    payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
    payment_product_id = payment.get("product_id")
    if isinstance(payment_product_id, str) and payment_product_id.strip():
        product_ids.add(payment_product_id.strip())

    for key in ("product_cart", "line_items", "items"):
        rows = data.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_product_id = row.get("product_id")
            if isinstance(row_product_id, str) and row_product_id.strip():
                product_ids.add(row_product_id.strip())

    return product_ids


def _extract_payment_amount_minor(data: dict[str, Any]) -> int | None:
    payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
    candidates = [
        payment.get("amount"),
        data.get("amount"),
        payment.get("total_amount"),
        data.get("total_amount"),
    ]

    for candidate in candidates:
        try:
            if candidate is None:
                continue
            amount = int(candidate)
            if amount > 0:
                return amount
        except (TypeError, ValueError):
            continue

    return None


def _extract_payment_currency(data: dict[str, Any]) -> str:
    payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
    raw = payment.get("currency") or data.get("currency") or "USD"
    return str(raw).upper()


class BillingProvider(ABC):
    provider: str

    @property
    @abstractmethod
    def enabled(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def create_checkout_session(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        success_url: str,
        cancel_url: str,
        db: Session,
        plan_cycle: str = "monthly",
    ) -> Optional[str]:
        raise NotImplementedError

    @abstractmethod
    def create_credit_topup_checkout(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        amount_usd: int,
        success_url: str,
        cancel_url: str,
        db: Session,
    ) -> tuple[Optional[str], Optional[str]]:
        raise NotImplementedError

    @abstractmethod
    def get_customer_portal_url(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        db: Session,
    ) -> Optional[str]:
        raise NotImplementedError

    @abstractmethod
    def cancel_subscription(
        self,
        *,
        settings_row: UserSettings,
        user_email: str | None = None,
        db: Session | None = None,
    ) -> tuple[bool, str | None]:
        raise NotImplementedError

    @abstractmethod
    def preview_plan_change(
        self,
        *,
        settings_row: UserSettings,
        target_cycle: str,
        db: Session,
    ) -> tuple[dict[str, Any] | None, str | None]:
        raise NotImplementedError

    @abstractmethod
    def change_plan(
        self,
        *,
        settings_row: UserSettings,
        target_cycle: str,
        db: Session,
    ) -> tuple[dict[str, Any] | None, str | None]:
        raise NotImplementedError

    @abstractmethod
    def normalize_webhook_event(self, *, payload: bytes, headers: dict[str, str]) -> NormalizedBillingEvent | None:
        """
        Return None when webhook should be acknowledged but ignored.
        Raise ValueError for invalid signature.
        """
        raise NotImplementedError


class PolarBillingProvider(BillingProvider):
    provider = "polar"

    def __init__(self, settings: Settings, polar: PolarService):
        self.settings = settings
        self.polar = polar

    @property
    def enabled(self) -> bool:
        return self.polar.enabled

    @staticmethod
    def _subscription_payload(event: dict[str, Any]) -> dict[str, Any]:
        data = event.get("data", {}) or {}
        nested = data.get("subscription")
        if isinstance(nested, dict):
            normalized = dict(data)
            normalized.update(nested)
            return normalized
        return data

    def _ensure_customer_id(self, settings_row: UserSettings, user_email: str, db: Session) -> Optional[str]:
        if settings_row.polar_customer_id:
            return settings_row.polar_customer_id

        customer_id = self.polar.get_or_create_customer(user_email)
        if not customer_id:
            return None

        settings_row.polar_customer_id = customer_id
        db.flush()
        return customer_id

    def create_checkout_session(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        success_url: str,
        cancel_url: str,
        db: Session,
        plan_cycle: str = "monthly",
    ) -> Optional[str]:
        _ = plan_cycle
        customer_id = self._ensure_customer_id(settings_row, user_email, db)
        if not customer_id:
            return None

        return self.polar.create_checkout_session(
            customer_id=customer_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    def create_credit_topup_checkout(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        amount_usd: int,
        success_url: str,
        cancel_url: str,
        db: Session,
    ) -> tuple[Optional[str], Optional[str]]:
        _ = settings_row
        _ = user_email
        _ = amount_usd
        _ = success_url
        _ = cancel_url
        _ = db
        return None, "Credit top-up is not supported for this billing provider"

    def get_customer_portal_url(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        db: Session,
    ) -> Optional[str]:
        customer_id = self._ensure_customer_id(settings_row, user_email, db)
        if not customer_id:
            return None
        return self.polar.get_customer_portal_url(customer_id)

    def cancel_subscription(
        self,
        *,
        settings_row: UserSettings,
        user_email: str | None = None,
        db: Session | None = None,
    ) -> tuple[bool, str | None]:
        _ = user_email
        _ = db
        if not settings_row.polar_subscription_id:
            return False, "No active subscription to cancel"

        success = self.polar.cancel_subscription(settings_row.polar_subscription_id)
        if not success:
            return False, "Failed to cancel subscription"

        settings_row.subscription_status = "cancel_scheduled"
        return True, None

    def preview_plan_change(
        self,
        *,
        settings_row: UserSettings,
        target_cycle: str,
        db: Session,
    ) -> tuple[dict[str, Any] | None, str | None]:
        _ = settings_row
        _ = target_cycle
        _ = db
        return None, "Plan change preview is not supported for this billing provider"

    def change_plan(
        self,
        *,
        settings_row: UserSettings,
        target_cycle: str,
        db: Session,
    ) -> tuple[dict[str, Any] | None, str | None]:
        _ = settings_row
        _ = target_cycle
        _ = db
        return None, "Plan change is not supported for this billing provider"

    def normalize_webhook_event(self, *, payload: bytes, headers: dict[str, str]) -> NormalizedBillingEvent | None:
        if not self.settings.POLAR_WEBHOOK_SECRET:
            logger.warning("POLAR_WEBHOOK_SECRET not configured - ignoring Polar webhook")
            return None

        try:
            from polar_sdk.webhooks import validate_event
        except Exception as exc:
            raise RuntimeError("polar-sdk webhook validation is unavailable") from exc

        try:
            event = validate_event(
                payload=payload,
                headers={
                    "webhook-signature": headers.get("webhook-signature", ""),
                    "webhook-id": headers.get("webhook-id", ""),
                    "webhook-timestamp": headers.get("webhook-timestamp", ""),
                },
                secret=self.settings.POLAR_WEBHOOK_SECRET,
            )
        except Exception as exc:
            raise ValueError("invalid_webhook_signature") from exc

        event_type = event.get("type") or "unknown"
        data = self._subscription_payload(event)

        return NormalizedBillingEvent(
            provider=self.provider,
            event_type=event_type,
            raw_event_type=event_type,
            delivery_id=headers.get("webhook-id") or None,
            customer_id=data.get("customer_id"),
            customer_email=((data.get("customer") or {}).get("email") if isinstance(data.get("customer"), dict) else None),
            subscription_id=data.get("id") or data.get("subscription_id"),
            subscription_status=_normalize_subscription_status(data.get("status")),
            period_start=_parse_dt(data.get("current_period_start")),
            period_end=_parse_dt(data.get("current_period_end")),
            invoice_id=(str(data.get("invoice_id")) if data.get("invoice_id") else None),
            payload_kind=str(data.get("payload_type") or "").strip().lower() or None,
            product_ids=sorted(_extract_product_ids(data)),
            payment_amount_minor=_extract_payment_amount_minor(data),
            payment_currency=_extract_payment_currency(data),
            raw=event,
        )


class DodoBillingProvider(BillingProvider):
    provider = "dodo"

    def __init__(self, settings: Settings, dodo: DodoService):
        self.settings = settings
        self.dodo = dodo

    @property
    def enabled(self) -> bool:
        return self.dodo.enabled

    @staticmethod
    def _event_data(event: dict[str, Any]) -> dict[str, Any]:
        if isinstance(event.get("payload"), dict) and isinstance(event["payload"].get("data"), dict):
            data = event["payload"].get("data", {}) or {}
        else:
            data = event.get("data", {}) or {}
        nested = data.get("subscription")
        if isinstance(nested, dict):
            merged = dict(data)
            merged.update(nested)
            return merged
        return data

    @staticmethod
    def _normalize_event_type(raw_type: str) -> str:
        t = (raw_type or "").strip().lower()

        if t in {"subscription.created"}:
            return "subscription.created"
        if t in {"subscription.active", "subscription.renewed"}:
            return "subscription.active"
        if t in {"subscription.updated"}:
            return "subscription.updated"
        if t in {"subscription.cancelled", "subscription.canceled"}:
            return "subscription.canceled"
        if t in {"subscription.expired", "subscription.revoked"}:
            return "subscription.revoked"
        if t in {"subscription.uncanceled", "subscription.uncancelled", "subscription.reactivated"}:
            return "subscription.uncanceled"
        if t in {"subscription.on_hold", "subscription.failed"}:
            return "subscription.updated"
        if t in {"payment.succeeded"}:
            return "payment.succeeded"
        if t in {"payment.failed"}:
            return "payment.failed"
        if t in {"invoice.paid", "invoice.payment_succeeded", "invoice.succeeded"}:
            return "invoice.paid"
        if t in {"invoice.payment_failed", "invoice.failed"}:
            return "invoice.payment_failed"
        if t in {"charge.refunded", "payment.refunded", "refund.created", "refund.succeeded"}:
            return "charge.refunded"

        return t

    def create_checkout_session(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        success_url: str,
        cancel_url: str,
        db: Session,
        plan_cycle: str = "monthly",
    ) -> Optional[str]:
        _ = settings_row
        _ = db

        display_name = user_email.split("@", 1)[0] if "@" in user_email else user_email
        return self.dodo.create_checkout_session(
            customer_email=user_email,
            customer_name=display_name,
            return_url=success_url,
            plan_cycle=plan_cycle,
        )

    def create_credit_topup_checkout(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        amount_usd: int,
        success_url: str,
        cancel_url: str,
        db: Session,
    ) -> tuple[Optional[str], Optional[str]]:
        _ = settings_row
        _ = cancel_url
        _ = db

        if not self.settings.DODO_CREDIT_TOPUP_PRODUCT_ID:
            return None, "Credit top-up product is not configured"

        display_name = user_email.split("@", 1)[0] if "@" in user_email else user_email
        checkout_url = self.dodo.create_credit_topup_checkout(
            customer_email=user_email,
            customer_name=display_name,
            return_url=success_url,
            amount_usd=amount_usd,
        )
        if not checkout_url:
            return None, "Could not create credit top-up checkout"
        return checkout_url, None

    def get_customer_portal_url(
        self,
        *,
        settings_row: UserSettings,
        user_email: str,
        db: Session,
    ) -> Optional[str]:
        customer_id = settings_row.dodo_customer_id
        if not customer_id and user_email:
            customer_id = self.dodo.find_customer_id_by_email(user_email)
            if customer_id:
                settings_row.dodo_customer_id = customer_id
                db.flush()

        if not customer_id:
            return None

        return self.dodo.get_customer_portal_url(
            customer_id=customer_id,
            return_url=self.settings.FRONTEND_URL,
        )

    def cancel_subscription(
        self,
        *,
        settings_row: UserSettings,
        user_email: str | None = None,
        db: Session | None = None,
    ) -> tuple[bool, str | None]:
        if not settings_row.dodo_customer_id and user_email:
            customer_id = self.dodo.find_customer_id_by_email(user_email)
            if customer_id:
                settings_row.dodo_customer_id = customer_id
                if db is not None:
                    db.flush()

        subscription_id = settings_row.dodo_subscription_id
        if not subscription_id and settings_row.dodo_customer_id:
            subscription_id = self.dodo.find_latest_subscription_id_for_customer(settings_row.dodo_customer_id)
            if subscription_id:
                settings_row.dodo_subscription_id = subscription_id

        if not subscription_id:
            return False, "No active subscription to cancel"

        success = self.dodo.cancel_subscription(subscription_id)
        if not success:
            return False, "Failed to cancel subscription"

        settings_row.subscription_status = "cancel_scheduled"
        return True, None

    def _target_product_id(self, target_cycle: str) -> Optional[str]:
        return self.dodo.get_product_id_for_cycle(target_cycle)

    def _resolve_subscription_id(self, settings_row: UserSettings) -> Optional[str]:
        subscription_id = settings_row.dodo_subscription_id
        if subscription_id:
            return subscription_id
        if settings_row.dodo_customer_id:
            latest = self.dodo.find_latest_subscription_id_for_customer(settings_row.dodo_customer_id)
            if latest:
                settings_row.dodo_subscription_id = latest
                return latest
        return None

    def preview_plan_change(
        self,
        *,
        settings_row: UserSettings,
        target_cycle: str,
        db: Session,
    ) -> tuple[dict[str, Any] | None, str | None]:
        _ = db
        subscription_id = self._resolve_subscription_id(settings_row)
        if not subscription_id:
            return None, "No active subscription to change"

        product_id = self._target_product_id(target_cycle)
        if not product_id:
            return None, "Requested plan is not configured"

        preview = self.dodo.preview_subscription_plan_change(
            subscription_id=subscription_id,
            product_id=product_id,
            proration_billing_mode="difference_immediately",
            quantity=1,
        )
        if not preview:
            return None, "Unable to preview plan change right now"
        return preview, None

    def change_plan(
        self,
        *,
        settings_row: UserSettings,
        target_cycle: str,
        db: Session,
    ) -> tuple[dict[str, Any] | None, str | None]:
        _ = db
        subscription_id = self._resolve_subscription_id(settings_row)
        if not subscription_id:
            return None, "No active subscription to change"

        product_id = self._target_product_id(target_cycle)
        if not product_id:
            return None, "Requested plan is not configured"

        result = self.dodo.change_subscription_plan(
            subscription_id=subscription_id,
            product_id=product_id,
            proration_billing_mode="difference_immediately",
            on_payment_failure="prevent_change",
            quantity=1,
        )
        if not result:
            return None, "Plan change failed. Please try again."
        return result, None

    def normalize_webhook_event(self, *, payload: bytes, headers: dict[str, str]) -> NormalizedBillingEvent | None:
        try:
            event = self.dodo.verify_webhook(payload, headers)
        except RuntimeError as exc:
            if "not configured" in str(exc).lower():
                logger.warning("DODO_WEBHOOK_SECRET not configured - ignoring Dodo webhook")
                return None
            raise

        raw_type = str(event.get("type") or event.get("eventType") or event.get("event_type") or "unknown")
        data = self._event_data(event)

        customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}

        customer_id = (
            data.get("customer_id")
            or customer.get("customer_id")
            or customer.get("id")
        )
        customer_email = (
            customer.get("email")
            or data.get("customer_email")
            or data.get("email")
        )

        subscription_obj = data.get("subscription") if isinstance(data.get("subscription"), dict) else {}
        raw_type_token = (raw_type or "").strip().lower()
        subscription_id = (
            data.get("subscription_id")
            or subscription_obj.get("id")
            or (data.get("id") if raw_type_token.startswith("subscription.") else None)
        )

        period_start = (
            _parse_dt(data.get("current_period_start"))
            or _parse_dt(data.get("period_start"))
            or _parse_dt(data.get("billing_cycle_start"))
        )
        period_end = (
            _parse_dt(data.get("current_period_end"))
            or _parse_dt(data.get("period_end"))
            or _parse_dt(data.get("next_billing_date"))
            or _parse_dt(data.get("billing_cycle_end"))
        )

        has_subscription_context = bool(
            subscription_id
            or isinstance(data.get("subscription"), dict)
            or str(data.get("payload_type") or "").lower() == "subscription"
        )

        event_type = self._normalize_event_type(raw_type)

        status_value = str(data.get("status")) if data.get("status") is not None else None
        if str(raw_type).strip().lower() == "payment.failed" and has_subscription_context and not status_value:
            status_value = "past_due"

        return NormalizedBillingEvent(
            provider=self.provider,
            event_type=event_type,
            raw_event_type=raw_type,
            delivery_id=headers.get("webhook-id") or None,
            customer_id=customer_id,
            customer_email=customer_email,
            subscription_id=subscription_id,
            subscription_status=_normalize_subscription_status(status_value),
            period_start=period_start,
            period_end=period_end,
            invoice_id=(str(data.get("invoice_id")) if data.get("invoice_id") else None),
            payload_kind=payload_type or None,
            product_ids=sorted(_extract_product_ids(data)),
            payment_amount_minor=_extract_payment_amount_minor(data),
            payment_currency=_extract_payment_currency(data),
            raw=event,
        )


def _set_provider_customer_id(user: UserSettings, provider: str, customer_id: Optional[str]) -> None:
    if not customer_id:
        return
    if provider == "dodo":
        user.dodo_customer_id = customer_id
    else:
        user.polar_customer_id = customer_id


def _get_provider_subscription_id(user: UserSettings, provider: str) -> Optional[str]:
    return user.dodo_subscription_id if provider == "dodo" else user.polar_subscription_id


def _set_provider_subscription_id(user: UserSettings, provider: str, subscription_id: Optional[str]) -> None:
    if not subscription_id:
        return
    if provider == "dodo":
        user.dodo_subscription_id = subscription_id
    else:
        user.polar_subscription_id = subscription_id


def get_user_for_billing_event(db: Session, event: NormalizedBillingEvent) -> Optional[UserSettings]:
    if event.customer_id:
        field = UserSettings.dodo_customer_id if event.provider == "dodo" else UserSettings.polar_customer_id
        user = db.query(UserSettings).filter(field == event.customer_id).first()
        if user:
            return user

    if event.customer_email:
        user = db.query(UserSettings).filter(UserSettings.user_email == event.customer_email).first()
        if user:
            return user

    return None


def _is_credit_topup_event(event: NormalizedBillingEvent, settings: Settings) -> bool:
    if event.provider != "dodo":
        return False
    if event.event_type != "payment.succeeded":
        return False
    topup_product_id = (settings.DODO_CREDIT_TOPUP_PRODUCT_ID or "").strip()
    if not topup_product_id:
        return False

    data = _event_data(event.raw or {})
    product_ids = set(event.product_ids or _extract_product_ids(data))
    return topup_product_id in product_ids


def _apply_credit_topup(db: Session, *, user: UserSettings, event: NormalizedBillingEvent) -> bool:
    data = _event_data(event.raw or {})
    payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
    provider_payment_id = (
        payment.get("payment_id")
        or data.get("payment_id")
        or payment.get("id")
        or data.get("id")
    )
    if not provider_payment_id:
        logger.warning("Credit top-up event missing payment id user=%s", user.user_id)
        return True

    existing = db.query(CreditTopup).filter(
        CreditTopup.provider == event.provider,
        CreditTopup.provider_payment_id == str(provider_payment_id),
    ).first()
    if existing:
        return True

    amount_minor = event.payment_amount_minor or _extract_payment_amount_minor(data)
    if not amount_minor:
        logger.warning("Credit top-up event missing amount user=%s payment=%s", user.user_id, provider_payment_id)
        return True

    currency = event.payment_currency or _extract_payment_currency(data)
    if currency != "USD":
        logger.warning(
            "Credit top-up currency unsupported user=%s payment=%s currency=%s",
            user.user_id,
            provider_payment_id,
            currency,
        )
        return True

    amount_usd = amount_minor / 100.0
    credits_added = int(round(amount_usd * 100))
    if credits_added <= 0:
        return True

    current_limit = user.credits_limit if user.credits_limit is not None else 0.0
    user.credits_limit = current_limit + amount_usd

    db.add(
        CreditTopup(
            user_id=user.user_id,
            provider=event.provider,
            provider_payment_id=str(provider_payment_id),
            amount_minor=int(amount_minor),
            currency=currency,
            credits_added=credits_added,
            provider_metadata={
                "event_type": event.event_type,
                "delivery_id": event.delivery_id,
            },
        )
    )
    return True


def apply_billing_event(db: Session, event: NormalizedBillingEvent) -> bool:
    """
    Apply normalized billing event to UserSettings.
    Returns True when handled, False when event type is unsupported.
    """
    user = get_user_for_billing_event(db, event)
    if not user:
        logger.warning(
            "Billing webhook for unknown customer provider=%s customer_id=%s",
            event.provider,
            event.customer_id,
        )
        return True

    _set_provider_customer_id(user, event.provider, event.customer_id)

    settings = get_settings()
    raw_data = _event_data(event.raw or {})
    raw_product_ids = set(event.product_ids or _extract_product_ids(raw_data))
    subscription_product_ids = {
        value.strip()
        for value in [
            settings.DODO_PRODUCT_ID_MONTHLY or settings.DODO_PRODUCT_ID,
            settings.DODO_PRODUCT_ID_ANNUAL,
        ]
        if isinstance(value, str) and value.strip()
    }
    payload_type = str(event.payload_kind or raw_data.get("payload_type") or "").strip().lower()
    has_subscription_context = bool(
        event.subscription_id
        or isinstance(raw_data.get("subscription"), dict)
        or payload_type == "subscription"
        or bool(raw_product_ids.intersection(subscription_product_ids))
    )

    if event.event_type == "subscription.created":
        current_sub = _get_provider_subscription_id(user, event.provider)
        already_active_same_sub = (
            user.subscription_tier == "pro"
            and user.subscription_status == "active"
            and current_sub
            and current_sub == event.subscription_id
        )

        user.subscription_tier = "pro"
        user.subscription_status = "active"
        _set_provider_subscription_id(user, event.provider, event.subscription_id)
        if event.period_end:
            user.subscription_expires_at = event.period_end

        if not already_active_same_sub:
            from app.services.credits import initialize_credits_for_pro
            initialize_credits_for_pro(user)
        return True

    if event.event_type in {"subscription.active", "subscription.updated"}:
        transitioned_to_pro = False
        if event.event_type == "subscription.active" or event.subscription_status == "active":
            if user.subscription_tier != "pro":
                transitioned_to_pro = True
            user.subscription_tier = "pro"

        if event.subscription_status:
            user.subscription_status = event.subscription_status
        elif event.event_type == "subscription.active":
            user.subscription_status = "active"

        if event.subscription_id:
            _set_provider_subscription_id(user, event.provider, event.subscription_id)

        if event.period_end:
            user.subscription_expires_at = event.period_end
            if user.subscription_status in {"canceled", "cancel_scheduled"} and _is_future(event.period_end):
                user.subscription_status = "cancel_scheduled"

        if transitioned_to_pro:
            from app.services.credits import initialize_credits_for_pro
            initialize_credits_for_pro(user)

        if event.period_start:
            current_start = user.credits_period_start
            if current_start is None or event.period_start > current_start:
                from app.services.credits import PRO_CREDIT_LIMIT, reset_credits
                reset_credits(user, PRO_CREDIT_LIMIT)

        return True

    if event.event_type == "subscription.canceled":
        if _is_future(event.period_end):
            user.subscription_status = "cancel_scheduled"
        else:
            user.subscription_status = "canceled"
        if event.subscription_id:
            _set_provider_subscription_id(user, event.provider, event.subscription_id)
        if event.period_end:
            user.subscription_expires_at = event.period_end
        return True

    if event.event_type == "subscription.revoked":
        user.subscription_tier = "trial"
        user.subscription_status = "expired"
        if event.provider == "dodo":
            user.dodo_subscription_id = None
        else:
            user.polar_subscription_id = None
        user.subscription_expires_at = None

        from app.services.credits import TRIAL_CREDIT_LIMIT
        user.credits_limit = TRIAL_CREDIT_LIMIT
        return True

    if event.event_type == "subscription.uncanceled":
        user.subscription_status = "active"
        return True

    if event.event_type in {"invoice.paid", "payment.succeeded"}:
        if _is_credit_topup_event(event, settings):
            return _apply_credit_topup(db, user=user, event=event)

        if not has_subscription_context:
            # One-time non-subscription payment (non-topup) should not mutate subscription state.
            return True

        if user.subscription_tier != "pro":
            from app.services.credits import initialize_credits_for_pro
            user.subscription_tier = "pro"
            initialize_credits_for_pro(user)
        user.subscription_status = "active"
        if event.period_end:
            user.subscription_expires_at = event.period_end
        if event.period_start:
            current_start = user.credits_period_start
            if current_start is None or event.period_start > current_start:
                from app.services.credits import PRO_CREDIT_LIMIT, reset_credits
                reset_credits(user, PRO_CREDIT_LIMIT)
        return True

    if event.event_type in {"invoice.payment_failed", "payment.failed"}:
        if not has_subscription_context:
            return True
        # Keep access policy decisions in subscription/dunning gating;
        # billing only marks account as past due.
        if user.subscription_tier == "pro":
            user.subscription_status = "past_due"
        return True

    if event.event_type == "charge.refunded":
        # Refunds are captured in billing ledger and invoices/attempts. Subscription
        # state can differ by provider policy, so we avoid forced lifecycle mutation.
        return True

    return False


def build_billing_provider(settings: Optional[Settings] = None) -> BillingProvider:
    resolved = settings or get_settings()
    provider_name = (resolved.BILLING_PROVIDER or "dodo").strip().lower()

    if provider_name == "polar":
        return PolarBillingProvider(resolved, get_polar_service())
    if provider_name != "dodo":
        logger.warning("Unknown BILLING_PROVIDER '%s'; defaulting to dodo", provider_name)

    return DodoBillingProvider(resolved, get_dodo_service())


def get_billing_provider(settings: Optional[Settings] = None) -> BillingProvider:
    return build_billing_provider(settings or get_settings())

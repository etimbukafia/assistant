"""
Billing Router

Provider-agnostic billing endpoints backed by the configured billing provider.
"""
from __future__ import annotations

from urllib.parse import urlparse
from typing import Literal
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.data.models import BillingEvent, BillingPlan, BillingSubscription, TaskQueue, UserSettings
from app.infra.config import Settings, get_settings
from app.infra.database import get_db
from app.security.auth import (
    AuthenticatedUser,
    get_current_user,
    get_db_for_user,
    get_user_settings,
    require_admin_user,
)
from app.services.billing_provider import (
    BillingProvider,
    apply_billing_event,
    deserialize_billing_event,
    get_billing_provider,
    get_user_for_billing_event,
)
from app.services.billing_ledger import ensure_configured_plans, sync_subscription_snapshot_from_settings
from app.services.dunning import apply_failure_state, clear_dunning_state, is_failure_event, is_recovery_event, notify_stage
from app.jobs.queue import enqueue_task
from core.llm.token_tracking import get_user_usage_summary

router = APIRouter(prefix="/billing", tags=["Billing"])


def _allowed_return_origins(settings: Settings) -> set[str]:
    origins: set[str] = set()
    frontend_url = getattr(settings, "FRONTEND_URL", "") or ""
    if frontend_url:
        parsed = urlparse(frontend_url.strip())
        if parsed.scheme and parsed.netloc:
            origins.add(f"{parsed.scheme}://{parsed.netloc}")

    cors_origins = getattr(settings, "CORS_ORIGINS", "") or ""
    for raw in cors_origins.split(","):
        value = raw.strip()
        if not value:
            continue
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            origins.add(f"{parsed.scheme}://{parsed.netloc}")

    return origins


def _validate_return_url(url: str, settings: Settings) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid return URL")

    allowed_origins = _allowed_return_origins(settings)
    if not allowed_origins:
        raise HTTPException(status_code=500, detail="Billing return URL allowlist not configured")

    url_origin = f"{parsed.scheme}://{parsed.netloc}"
    if allowed_origins and url_origin not in allowed_origins:
        raise HTTPException(status_code=400, detail="Return URL origin not allowed")


def _format_amount_for_copy(amount: float | None, currency: str | None) -> str | None:
    if amount is None:
        return None
    try:
        # Dodo amounts are typically in minor units; normalize to major for display.
        normalized = float(amount) / 100.0
        code = (currency or "USD").upper()
        if code == "USD":
            return f"${normalized:,.2f}"
        return f"{code} {normalized:,.2f}"
    except Exception:
        return None


def _extract_amount_and_currency(payload: dict) -> tuple[float | None, str | None]:
    raw_amount = payload.get("immediate_amount")
    if raw_amount is None:
        raw_amount = payload.get("amount_due_now")
    if raw_amount is None and isinstance(payload.get("invoice_estimate"), dict):
        est = payload.get("invoice_estimate", {})
        raw_amount = est.get("immediate_amount") or est.get("amount_due_now")
    currency = payload.get("currency")
    if currency is None and isinstance(payload.get("invoice_estimate"), dict):
        currency = payload.get("invoice_estimate", {}).get("currency")

    try:
        amount_due = float(raw_amount) if raw_amount is not None else None
    except (TypeError, ValueError):
        amount_due = None

    return amount_due, currency


def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _infer_cycle_from_plan_external_id(plan_external_id: str | None, settings: Settings) -> str | None:
    if not plan_external_id:
        return None
    raw = str(plan_external_id)
    if raw == (settings.DODO_PRODUCT_ID_ANNUAL or ""):
        return "annual"
    if raw == (settings.DODO_PRODUCT_ID_MONTHLY or settings.DODO_PRODUCT_ID or ""):
        return "monthly"
    token = raw.lower()
    if "annual" in token or "year" in token or "_yr" in token:
        return "annual"
    if "month" in token or "monthly" in token or "_mo" in token:
        return "monthly"
    return None


def _classify_plan_change(current_cycle: str | None, target_cycle: str) -> str:
    if not current_cycle:
        return "unknown"
    if current_cycle == target_cycle:
        return "lateral"
    if current_cycle == "monthly" and target_cycle == "annual":
        return "upgrade"
    if current_cycle == "annual" and target_cycle == "monthly":
        return "downgrade"
    return "unknown"


def _resolve_current_cycle_and_period_end(
    db: Session,
    *,
    settings_row: UserSettings,
    provider: str,
    app_settings: Settings,
    requested_current_cycle: str | None = None,
) -> tuple[str | None, datetime | None, BillingSubscription | None]:
    current_cycle = (requested_current_cycle or "").strip().lower() or None
    if current_cycle not in {"monthly", "annual"}:
        current_cycle = None

    provider_subscription_id = (
        settings_row.dodo_subscription_id
        if provider == "dodo"
        else settings_row.polar_subscription_id
    )

    query = db.query(BillingSubscription).filter(
        BillingSubscription.user_id == settings_row.user_id,
        BillingSubscription.provider == provider,
    )
    if provider_subscription_id:
        query = query.order_by(
            (BillingSubscription.provider_subscription_id == provider_subscription_id).desc(),
            BillingSubscription.updated_at.desc(),
        )
    else:
        query = query.order_by(BillingSubscription.updated_at.desc())

    subscription = query.first()
    period_end = subscription.current_period_end if subscription else settings_row.subscription_expires_at

    if current_cycle:
        return current_cycle, period_end, subscription

    if subscription and subscription.plan_id:
        plan = db.query(BillingPlan).filter(BillingPlan.id == subscription.plan_id).first()
        if plan and plan.billing_interval in {"monthly", "annual"}:
            return plan.billing_interval, period_end, subscription

    if subscription:
        inferred = _infer_cycle_from_plan_external_id(subscription.plan_external_id, app_settings)
        if inferred:
            return inferred, period_end, subscription

    return None, period_end, subscription


class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str
    plan_cycle: Literal["monthly", "annual"] = "monthly"


class CheckoutResponse(BaseModel):
    checkout_url: str


class CreditTopupCheckoutRequest(BaseModel):
    amount_usd: int
    success_url: str
    cancel_url: str


class CreditTopupCheckoutResponse(BaseModel):
    checkout_url: str
    amount_usd: int
    credits_to_add: int
    message: str


class PlanChangePreviewRequest(BaseModel):
    target_cycle: Literal["monthly", "annual"]
    current_cycle: Literal["monthly", "annual"] | None = None


class PlanChangePreviewResponse(BaseModel):
    target_cycle: Literal["monthly", "annual"]
    current_cycle: Literal["monthly", "annual"] | None = None
    change_direction: Literal["upgrade", "downgrade", "lateral", "unknown"] = "unknown"
    effective_timing: Literal["immediate", "next_cycle"] = "immediate"
    effective_at: str | None = None
    amount_due_today: float | None = None
    currency: str | None = None
    message: str


class PlanChangeRequest(BaseModel):
    target_cycle: Literal["monthly", "annual"]
    current_cycle: Literal["monthly", "annual"] | None = None


class PlanChangeResponse(BaseModel):
    success: bool
    current_cycle: Literal["monthly", "annual"] | None = None
    change_direction: Literal["upgrade", "downgrade", "lateral", "unknown"] = "unknown"
    effective_timing: Literal["immediate", "next_cycle"] = "immediate"
    effective_at: str | None = None
    message: str
    amount_due_today: float | None = None
    currency: str | None = None


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    is_active: bool
    trial_ends_at: str | None = None
    expires_at: str | None = None
    days_remaining: int


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
    billing: BillingProvider = Depends(get_billing_provider),
):
    try:
        ensure_configured_plans(db, provider=billing.provider)
        sync_subscription_snapshot_from_settings(
            db,
            settings_row=settings,
            provider=billing.provider,
        )
        db.commit()
    except Exception:
        db.rollback()

    return SubscriptionResponse(
        tier=settings.subscription_tier or "trial",
        status=settings.subscription_status or "trialing",
        is_active=settings.is_active,
        trial_ends_at=settings.trial_ends_at.isoformat() if settings.trial_ends_at else None,
        expires_at=settings.subscription_expires_at.isoformat() if settings.subscription_expires_at else None,
        days_remaining=settings.days_remaining,
    )


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    request: CheckoutRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
    app_settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_for_user),
    billing: BillingProvider = Depends(get_billing_provider),
):
    if not billing.enabled:
        raise HTTPException(status_code=503, detail="Billing service not available")

    ensure_configured_plans(db, provider=billing.provider)

    _validate_return_url(request.success_url, app_settings)
    _validate_return_url(request.cancel_url, app_settings)

    checkout_url = billing.create_checkout_session(
        settings_row=settings,
        user_email=user.email,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        db=db,
        plan_cycle=request.plan_cycle,
    )

    if not checkout_url:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    db.commit()
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/credits/top-up/checkout", response_model=CreditTopupCheckoutResponse)
def create_credit_topup_checkout(
    request: CreditTopupCheckoutRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
    app_settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_for_user),
    billing: BillingProvider = Depends(get_billing_provider),
):
    if not billing.enabled:
        raise HTTPException(status_code=503, detail="Billing service not available")

    ensure_configured_plans(db, provider=billing.provider)

    if settings.subscription_tier != "pro":
        raise HTTPException(status_code=400, detail="Credit top-up is available on Pro only")

    min_amount = max(1, int(getattr(app_settings, "DODO_CREDIT_TOPUP_MIN_USD", 5) or 5))
    max_amount = max(min_amount, int(getattr(app_settings, "DODO_CREDIT_TOPUP_MAX_USD", 500) or 500))
    unit = max(1, int(getattr(app_settings, "DODO_CREDIT_TOPUP_UNIT_USD", 1) or 1))
    amount_usd = int(request.amount_usd)

    if amount_usd < min_amount:
        raise HTTPException(status_code=400, detail=f"Minimum top-up is ${min_amount}")
    if amount_usd > max_amount:
        raise HTTPException(status_code=400, detail=f"Maximum top-up is ${max_amount}")
    if amount_usd % unit != 0:
        raise HTTPException(status_code=400, detail=f"Top-up amount must be in ${unit} increments")

    _validate_return_url(request.success_url, app_settings)
    _validate_return_url(request.cancel_url, app_settings)

    checkout_url, error = billing.create_credit_topup_checkout(
        settings_row=settings,
        user_email=user.email,
        amount_usd=amount_usd,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        db=db,
    )
    if error or not checkout_url:
        raise HTTPException(status_code=400, detail=error or "Unable to create top-up checkout")

    db.commit()
    credits_to_add = amount_usd * 100
    return CreditTopupCheckoutResponse(
        checkout_url=checkout_url,
        amount_usd=amount_usd,
        credits_to_add=credits_to_add,
        message=f"You'll add {credits_to_add} credits after payment confirmation.",
    )


@router.post("/cancel")
def cancel_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
    billing: BillingProvider = Depends(get_billing_provider),
):
    if not billing.enabled:
        raise HTTPException(status_code=503, detail="Billing service not available")

    ensure_configured_plans(db, provider=billing.provider)

    ok, error = billing.cancel_subscription(
        settings_row=settings,
        user_email=user.email,
        db=db,
    )
    if not ok:
        status_code = 400 if error and "No active subscription" in error else 500
        raise HTTPException(status_code=status_code, detail=error or "Failed to cancel subscription")

    sync_subscription_snapshot_from_settings(
        db,
        settings_row=settings,
        provider=billing.provider,
    )
    db.commit()
    return {
        "success": True,
        "message": "You're all set. Cancellation is scheduled for the end of your current billing period.",
    }


@router.post("/plan-change/preview", response_model=PlanChangePreviewResponse)
def preview_plan_change(
    request: PlanChangePreviewRequest,
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
    billing: BillingProvider = Depends(get_billing_provider),
):
    if not billing.enabled:
        raise HTTPException(status_code=503, detail="Billing service not available")

    ensure_configured_plans(db, provider=billing.provider)

    current_cycle, period_end, _subscription = _resolve_current_cycle_and_period_end(
        db,
        settings_row=settings,
        provider=billing.provider,
        app_settings=get_settings(),
        requested_current_cycle=request.current_cycle,
    )
    direction = _classify_plan_change(current_cycle, request.target_cycle)

    if direction == "lateral":
        return PlanChangePreviewResponse(
            target_cycle=request.target_cycle,
            current_cycle=current_cycle,
            change_direction=direction,
            effective_timing="immediate",
            amount_due_today=0.0,
            currency="USD",
            message="You're already on this billing cycle. No changes needed.",
        )

    if direction == "downgrade":
        if billing.provider != "dodo":
            raise HTTPException(status_code=400, detail="Downgrade scheduling is not supported for this billing provider")
        if not period_end:
            raise HTTPException(status_code=400, detail="Current billing period end is unavailable")
        effective_at = period_end.isoformat()
        return PlanChangePreviewResponse(
            target_cycle=request.target_cycle,
            current_cycle=current_cycle,
            change_direction=direction,
            effective_timing="next_cycle",
            effective_at=effective_at,
            amount_due_today=0.0,
            currency="USD",
            message=f"Downgrade scheduled. It will take effect on {effective_at}. You keep your current access until then.",
        )

    preview, error = billing.preview_plan_change(settings_row=settings, target_cycle=request.target_cycle, db=db)
    if error or preview is None:
        raise HTTPException(status_code=400, detail=error or "Unable to preview plan change")

    amount_due, currency = _extract_amount_and_currency(preview)
    display_amount = _format_amount_for_copy(amount_due, currency)
    if display_amount:
        message = f"You'll be charged {display_amount} today. Your new plan starts immediately."
    else:
        message = "Your plan changes immediately. Any prorated difference is applied today."

    return PlanChangePreviewResponse(
        target_cycle=request.target_cycle,
        current_cycle=current_cycle,
        change_direction=direction,
        effective_timing="immediate",
        amount_due_today=amount_due,
        currency=currency,
        message=message,
    )


@router.post("/plan-change", response_model=PlanChangeResponse)
def change_plan(
    request: PlanChangeRequest,
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
    billing: BillingProvider = Depends(get_billing_provider),
):
    if not billing.enabled:
        raise HTTPException(status_code=503, detail="Billing service not available")

    ensure_configured_plans(db, provider=billing.provider)

    current_cycle, period_end, subscription = _resolve_current_cycle_and_period_end(
        db,
        settings_row=settings,
        provider=billing.provider,
        app_settings=get_settings(),
        requested_current_cycle=request.current_cycle,
    )
    direction = _classify_plan_change(current_cycle, request.target_cycle)

    if direction == "lateral":
        return PlanChangeResponse(
            success=True,
            current_cycle=current_cycle,
            change_direction=direction,
            effective_timing="immediate",
            amount_due_today=0.0,
            currency="USD",
            message="You're already on this billing cycle. No changes needed.",
        )

    if direction == "downgrade":
        if billing.provider != "dodo":
            raise HTTPException(status_code=400, detail="Downgrade scheduling is not supported for this billing provider")
        if not period_end:
            raise HTTPException(status_code=400, detail="Current billing period end is unavailable")

        effective_at = period_end.isoformat()
        scheduled_for = _to_utc_naive(period_end)

        scheduled_payload = {
            "user_id": settings.user_id,
            "provider": billing.provider,
            "target_cycle": request.target_cycle,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "effective_at": effective_at,
        }
        existing_scheduled = db.query(TaskQueue).filter(
            TaskQueue.task_type == "apply_scheduled_plan_change",
            TaskQueue.user_id == settings.user_id,
            TaskQueue.status == "pending",
        ).order_by(TaskQueue.scheduled_for.desc()).first()

        if existing_scheduled:
            existing_scheduled.payload = scheduled_payload
            existing_scheduled.scheduled_for = scheduled_for
            existing_scheduled.correlation_id = f"{settings.user_id}:scheduled_plan_change"
        else:
            enqueue_task(
                "apply_scheduled_plan_change",
                payload=scheduled_payload,
                correlation_id=f"{settings.user_id}:scheduled_plan_change",
                scheduled_for=scheduled_for,
                db=db,
            )

        if subscription:
            meta = dict(subscription.provider_metadata or {})
            meta["scheduled_plan_change"] = {
                "target_cycle": request.target_cycle,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "effective_at": effective_at,
            }
            subscription.provider_metadata = meta

        db.commit()
        return PlanChangeResponse(
            success=True,
            current_cycle=current_cycle,
            change_direction=direction,
            effective_timing="next_cycle",
            effective_at=effective_at,
            amount_due_today=0.0,
            currency="USD",
            message=f"Downgrade scheduled for {effective_at}. Your current plan stays active until renewal.",
        )

    preview, preview_error = billing.preview_plan_change(settings_row=settings, target_cycle=request.target_cycle, db=db)
    if preview_error or preview is None:
        raise HTTPException(status_code=400, detail=preview_error or "Unable to preview plan change")

    result, error = billing.change_plan(settings_row=settings, target_cycle=request.target_cycle, db=db)
    if error or result is None:
        raise HTTPException(status_code=400, detail=error or "Unable to change plan")

    sync_subscription_snapshot_from_settings(db, settings_row=settings, provider=billing.provider)
    db.commit()

    amount_due, currency = _extract_amount_and_currency(preview)
    display_amount = _format_amount_for_copy(amount_due, currency)
    if display_amount:
        message = f"You'll be charged {display_amount} today. Your new plan starts immediately."
    else:
        message = "Your plan changes immediately. Any prorated difference is applied today."

    return PlanChangeResponse(
        success=True,
        current_cycle=current_cycle,
        change_direction=direction,
        effective_timing="immediate",
        message=message,
        amount_due_today=amount_due,
        currency=currency,
    )


@router.get("/portal-url", response_model=PortalResponse)
def get_portal_url(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
    billing: BillingProvider = Depends(get_billing_provider),
):
    if not billing.enabled:
        raise HTTPException(status_code=503, detail="Billing service not available")

    portal_url = billing.get_customer_portal_url(
        settings_row=settings,
        user_email=user.email,
        db=db,
    )

    if not portal_url:
        raise HTTPException(status_code=400, detail="No billing account found")

    db.commit()
    return PortalResponse(portal_url=portal_url)


class TokenUsageResponse(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float


@router.get("/token-usage", response_model=TokenUsageResponse)
def get_token_usage(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    usage = get_user_usage_summary(db, user.id)
    return TokenUsageResponse(**usage)


class CreditStatusResponse(BaseModel):
    credits_used: float
    credits_limit: float
    credits_remaining: float
    percentage_used: float
    is_exhausted: bool
    period_start: str | None
    tier: str


@router.get("/credits", response_model=CreditStatusResponse)
def get_credit_status(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.credits import get_credit_status

    settings = db.query(UserSettings).filter(
        UserSettings.user_id == user.id
    ).first()

    if not settings:
        raise HTTPException(status_code=404, detail="User settings not found")

    status = get_credit_status(settings)

    return CreditStatusResponse(
        credits_used=status["credits_used"],
        credits_limit=status["credits_limit"],
        credits_remaining=status["credits_remaining"],
        percentage_used=status["percentage_used"],
        is_exhausted=status["is_exhausted"],
        period_start=status["period_start"],
        tier=status["tier"],
    )


class ReplayBillingEventResponse(BaseModel):
    replayed: bool
    event_id: int
    event_type: str
    handled: bool


@router.post("/admin/events/{event_id}/replay", response_model=ReplayBillingEventResponse)
def replay_billing_event(
    event_id: int,
    _admin: AuthenticatedUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    event_row = db.query(BillingEvent).filter(BillingEvent.id == event_id).first()
    if not event_row:
        raise HTTPException(status_code=404, detail="Billing event not found")

    payload = event_row.payload if isinstance(event_row.payload, dict) else {}
    normalized = payload.get("normalized") if isinstance(payload.get("normalized"), dict) else None
    if not normalized:
        # Backward compatibility for legacy rows that stored only raw payload.
        normalized = {
            "provider": event_row.provider,
            "event_type": event_row.event_type,
            "raw_event_type": event_row.event_type,
            "delivery_id": event_row.delivery_id,
            "customer_id": event_row.customer_id,
            "customer_email": event_row.customer_email,
            "subscription_id": event_row.subscription_id,
            "raw": payload.get("raw") if isinstance(payload.get("raw"), dict) else payload,
        }

    normalized_event = deserialize_billing_event(normalized)
    user_row = get_user_for_billing_event(db, normalized_event)
    handled = apply_billing_event(db, normalized_event)
    if user_row:
        if is_recovery_event(normalized_event):
            clear_dunning_state(user_row)
        elif is_failure_event(normalized_event):
            stage = apply_failure_state(user_row, normalized_event)
            if stage:
                notify_stage(db, user_row, stage)

    from app.services.billing_ledger import sync_billing_ledger_from_event

    sync_billing_ledger_from_event(
        db,
        event=normalized_event,
        user=user_row,
        handled=handled,
        error=None if handled else "no_handler",
    )

    event_row.handled = handled
    event_row.error = None if handled else "no_handler"
    event_row.processed_at = datetime.now(timezone.utc)
    db.commit()

    return ReplayBillingEventResponse(
        replayed=True,
        event_id=event_row.id,
        event_type=event_row.event_type,
        handled=handled,
    )


class ReconcileBillingResponse(BaseModel):
    provider: str
    scanned: int
    updated: int


@router.post("/admin/reconcile", response_model=ReconcileBillingResponse)
def reconcile_billing_state(
    provider: Literal["dodo", "polar"] | None = None,
    _admin: AuthenticatedUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    active_provider = provider or (get_settings().BILLING_PROVIDER or "dodo").strip().lower()
    latest_rows = db.query(BillingSubscription).filter(
        BillingSubscription.provider == active_provider,
    ).all()

    scanned = 0
    updated = 0
    by_user: dict[str, BillingSubscription] = {}
    for row in latest_rows:
        current = by_user.get(row.user_id)
        if not current or (row.updated_at or datetime.min.replace(tzinfo=timezone.utc)) > (
            current.updated_at or datetime.min.replace(tzinfo=timezone.utc)
        ):
            by_user[row.user_id] = row

    for user_id, sub in by_user.items():
        scanned += 1
        settings_row = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings_row:
            continue

        desired_tier = "pro" if sub.status in {"active", "trialing", "cancel_scheduled", "past_due"} else "trial"
        desired_status = sub.status
        desired_expiry = sub.current_period_end

        changed = False
        if settings_row.subscription_tier != desired_tier:
            settings_row.subscription_tier = desired_tier
            changed = True
        if settings_row.subscription_status != desired_status:
            settings_row.subscription_status = desired_status
            changed = True
        if settings_row.subscription_expires_at != desired_expiry:
            settings_row.subscription_expires_at = desired_expiry
            changed = True

        if active_provider == "dodo":
            if sub.provider_customer_id and settings_row.dodo_customer_id != sub.provider_customer_id:
                settings_row.dodo_customer_id = sub.provider_customer_id
                changed = True
            if sub.provider_subscription_id and settings_row.dodo_subscription_id != sub.provider_subscription_id:
                settings_row.dodo_subscription_id = sub.provider_subscription_id
                changed = True
        else:
            if sub.provider_customer_id and settings_row.polar_customer_id != sub.provider_customer_id:
                settings_row.polar_customer_id = sub.provider_customer_id
                changed = True
            if sub.provider_subscription_id and settings_row.polar_subscription_id != sub.provider_subscription_id:
                settings_row.polar_subscription_id = sub.provider_subscription_id
                changed = True

        if changed:
            updated += 1

    db.commit()
    return ReconcileBillingResponse(provider=active_provider, scanned=scanned, updated=updated)

"""
Billing Router - Polar.sh checkout and portal endpoints

Exposes the PolarService methods for:
- Creating checkout sessions for Pro subscription
- Getting customer portal URLs for subscription management
- Token usage statistics
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, AuthenticatedUser, get_user_settings, get_db_for_user
from app.data.models import UserSettings
from app.services.polar import get_polar_service, PolarService
from app.infra.database import get_db
from core.llm.token_tracking import get_user_usage_summary

router = APIRouter(prefix="/billing", tags=["Billing"])


class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    request: CheckoutRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
    polar: PolarService = Depends(get_polar_service)
):
    """
    Create a Polar checkout session for Pro subscription upgrade.

    Returns a checkout URL to redirect the user to.
    """
    if not polar.enabled:
        raise HTTPException(status_code=503, detail="Billing service not available")

    # Get or create Polar customer, persist to UserSettings for webhook lookup
    if not settings.polar_customer_id:
        customer_id = polar.get_or_create_customer(user.email)
        if not customer_id:
            raise HTTPException(status_code=500, detail="Failed to create billing customer")
        settings.polar_customer_id = customer_id
        db.commit()
    else:
        customer_id = settings.polar_customer_id

    # Create checkout session
    checkout_url = polar.create_checkout_session(
        customer_id=customer_id,
        success_url=request.success_url,
        cancel_url=request.cancel_url
    )

    if not checkout_url:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    return CheckoutResponse(checkout_url=checkout_url)


@router.get("/portal-url", response_model=PortalResponse)
def get_portal_url(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
    polar: PolarService = Depends(get_polar_service)
):
    """
    Get Polar customer portal URL for subscription management.

    Users can manage their subscription, update payment methods,
    and view invoices through the portal.
    """
    if not polar.enabled:
        raise HTTPException(status_code=503, detail="Billing service not available")

    # Get or create Polar customer, persist for webhook lookup
    if not settings.polar_customer_id:
        customer_id = polar.get_or_create_customer(user.email)
        if not customer_id:
            raise HTTPException(status_code=500, detail="Failed to find billing customer")
        settings.polar_customer_id = customer_id
        db.commit()
    else:
        customer_id = settings.polar_customer_id

    # Get portal URL
    portal_url = polar.get_customer_portal_url(customer_id)

    if not portal_url:
        raise HTTPException(status_code=500, detail="Failed to get billing portal URL")

    return PortalResponse(portal_url=portal_url)


class TokenUsageResponse(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float


@router.get("/token-usage", response_model=TokenUsageResponse)
def get_token_usage(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get total token usage statistics for the current user."""
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
    db: Session = Depends(get_db)
):
    """
    Get current credit usage and remaining balance.

    Credits control access to AI features:
    - Trial: 100 credits = $1.00 USD
    - Pro: 500 credits = $5.00 USD

    Only Gemini models consume credits (Gemma models are free).
    """
    from app.data.models import UserSettings
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
        tier=status["tier"]
    )

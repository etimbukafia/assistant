"""
Polar Webhook Handlers

Handle webhook events from Polar.sh for subscription lifecycle management.
Updates user_settings subscription fields based on Polar events.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.infra.config import get_settings, Settings
from app.infra.database import SessionLocal, get_db
from app.data.models import UserSettings
from app.services import get_polar_service, PolarService
from app.security.auth import get_user_settings, get_db_for_user

logger = logging.getLogger(__name__)

router = APIRouter()


def validate_webhook_signature(payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Validate webhook signature and parse event.
    
    Args:
        payload: Raw request body
        headers: Request headers
        
    Returns:
        Parsed webhook event
        
    Raises:
        HTTPException if validation fails
    """
    settings = get_settings()
    
    if not settings.POLAR_WEBHOOK_SECRET:
        logger.error("POLAR_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )
    
    try:
        from polar_sdk.webhooks import validate_event
        
        event = validate_event(
            payload=payload,
            headers=headers,
            secret=settings.POLAR_WEBHOOK_SECRET
        )
        
        return event
        
    except ImportError:
        logger.error("polar-sdk not installed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook validation library not available"
        )
    except Exception as e:
        logger.warning(f"Webhook signature validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature"
        )


def get_user_by_polar_customer_id(db, customer_id: str) -> UserSettings:
    """Find user settings by Polar customer ID"""
    return db.query(UserSettings).filter(
        UserSettings.polar_customer_id == customer_id
    ).first()


def handle_subscription_created(event_data: Dict[str, Any], db) -> None:
    """
    Handle subscription.created event.
    
    Activates Pro tier and sets subscription dates.
    """
    subscription = event_data.get("data", {})
    customer_id = subscription.get("customer_id")
    subscription_id = subscription.get("id")
    
    if not customer_id:
        logger.error("subscription.created missing customer_id")
        return
    
    user = get_user_by_polar_customer_id(db, customer_id)
    if not user:
        logger.warning(f"No user found for Polar customer {customer_id}")
        return
    
    # Update subscription fields
    user.subscription_tier = "pro"
    user.subscription_status = "active"
    user.polar_subscription_id = subscription_id
    
    # Parse dates
    if subscription.get("current_period_end"):
        try:
            user.subscription_expires_at = datetime.fromisoformat(
                subscription["current_period_end"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass
    
    logger.info(f"Subscription created for user {user.user_email}, tier=pro")


def handle_subscription_active(event_data: Dict[str, Any], db) -> None:
    """
    Handle subscription.active event.
    
    Confirms subscription is active (e.g., after renewal).
    """
    subscription = event_data.get("data", {})
    customer_id = subscription.get("customer_id")
    
    if not customer_id:
        return
    
    user = get_user_by_polar_customer_id(db, customer_id)
    if not user:
        return
    
    user.subscription_status = "active"
    
    # Update expiry date
    if subscription.get("current_period_end"):
        try:
            user.subscription_expires_at = datetime.fromisoformat(
                subscription["current_period_end"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass
    
    logger.info(f"Subscription active for user {user.user_email}")


def handle_subscription_updated(event_data: Dict[str, Any], db) -> None:
    """
    Handle subscription.updated event.
    
    Syncs period dates and status.
    """
    subscription = event_data.get("data", {})
    customer_id = subscription.get("customer_id")
    
    if not customer_id:
        return
    
    user = get_user_by_polar_customer_id(db, customer_id)
    if not user:
        return
    
    # Update status if present
    if subscription.get("status"):
        user.subscription_status = subscription["status"]
    
    # Update expiry date
    if subscription.get("current_period_end"):
        try:
            user.subscription_expires_at = datetime.fromisoformat(
                subscription["current_period_end"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass
    
    logger.info(f"Subscription updated for user {user.user_email}")


def handle_subscription_canceled(event_data: Dict[str, Any], db) -> None:
    """
    Handle subscription.canceled event.
    
    Marks subscription as canceled but keeps access until period end.
    """
    subscription = event_data.get("data", {})
    customer_id = subscription.get("customer_id")
    
    if not customer_id:
        return
    
    user = get_user_by_polar_customer_id(db, customer_id)
    if not user:
        return
    
    user.subscription_status = "canceled"
    # Note: Keep tier as "pro" until revoked - user still has access until period end
    
    logger.info(f"Subscription canceled for user {user.user_email}")


def handle_subscription_revoked(event_data: Dict[str, Any], db) -> None:
    """
    Handle subscription.revoked event.
    
    Revokes access immediately - subscription has ended or payment failed.
    """
    subscription = event_data.get("data", {})
    customer_id = subscription.get("customer_id")
    
    if not customer_id:
        return
    
    user = get_user_by_polar_customer_id(db, customer_id)
    if not user:
        return
    
    user.subscription_tier = "trial"
    user.subscription_status = "expired"
    user.polar_subscription_id = None
    user.subscription_expires_at = None
    
    logger.info(f"Subscription revoked for user {user.user_email}")


def handle_subscription_uncanceled(event_data: Dict[str, Any], db) -> None:
    """
    Handle subscription.uncanceled event.
    
    User reactivated their subscription before the billing period ended.
    """
    subscription = event_data.get("data", {})
    customer_id = subscription.get("customer_id")
    
    if not customer_id:
        return
    
    user = get_user_by_polar_customer_id(db, customer_id)
    if not user:
        return
    
    user.subscription_status = "active"
    
    logger.info(f"Subscription uncanceled for user {user.user_email}")


# Event handler mapping
EVENT_HANDLERS = {
    "subscription.created": handle_subscription_created,
    "subscription.active": handle_subscription_active,
    "subscription.updated": handle_subscription_updated,
    "subscription.canceled": handle_subscription_canceled,
    "subscription.revoked": handle_subscription_revoked,
    "subscription.uncanceled": handle_subscription_uncanceled,
}


@router.post("/webhooks/polar")
async def handle_polar_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Main webhook endpoint for Polar events.
    
    Validates signature and routes to appropriate handler.
    """
    # Get raw body and headers for signature validation
    payload = await request.body()
    headers = {
        "webhook-signature": request.headers.get("webhook-signature", ""),
        "webhook-id": request.headers.get("webhook-id", ""),
        "webhook-timestamp": request.headers.get("webhook-timestamp", ""),
    }
    
    # Validate signature (get_settings() called inside)
    event = validate_webhook_signature(payload, headers)
    
    event_type = event.get("type")
    logger.info(f"Received Polar webhook: {event_type}")
    
    # Route to handler
    handler = EVENT_HANDLERS.get(event_type)
    if not handler:
        logger.debug(f"No handler for event type: {event_type}")
        return {"received": True, "handled": False}
    
    # Process event
    # Process event
    try:
        handler(event, db)
        db.commit()
        return {"received": True, "handled": True}
    except Exception as e:
        db.rollback()
        logger.error(f"Error handling webhook {event_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )


# ===========================================
# Billing REST API Endpoints
# ===========================================

from pydantic import BaseModel
from typing import Optional


class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    is_active: bool
    trial_ends_at: Optional[str] = None
    expires_at: Optional[str] = None
    days_remaining: int


@router.get("/billing/subscription")
async def get_subscription(
    request: Request,
    user: UserSettings = Depends(get_user_settings)
):
    """
    Get current user's subscription status.
    
    Returns tier, status, is_active, and remaining time.
    """
    
    return {
        "tier": user.subscription_tier or "trial",
        "status": user.subscription_status or "trialing",
        "is_active": user.is_active,
        "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        "expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        "days_remaining": user.days_remaining,
    }


@router.post("/billing/checkout")
async def create_checkout(
    request: Request,
    checkout_request: CheckoutRequest,
    db: Session = Depends(get_db_for_user),
    user: UserSettings = Depends(get_user_settings),
    polar_service: PolarService = Depends(get_polar_service)
):
    """
    Create a checkout session for Pro subscription.
    
    Returns checkout URL to redirect user to Polar payment page.
    """
    
    # Get or create Polar customer
    if not user.polar_customer_id:
        customer_id = polar_service.get_or_create_customer(user.user_email)
        if not customer_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to create billing customer"
            )
        user.polar_customer_id = customer_id
        db.commit()
    
    # Create checkout session
    checkout_url = polar_service.create_checkout_session(
        customer_id=user.polar_customer_id,
        success_url=checkout_request.success_url,
        cancel_url=checkout_request.cancel_url,
    )
    
    if not checkout_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to create checkout session"
        )
    
    return {"checkout_url": checkout_url}


@router.post("/billing/cancel")
async def cancel_subscription(
    request: Request,
    db: Session = Depends(get_db_for_user),
    user: UserSettings = Depends(get_user_settings),
    polar_service: PolarService = Depends(get_polar_service)
):
    """
    Cancel the user's subscription at end of billing period.
    """
    
    if not user.polar_subscription_id:
        raise HTTPException(
            status_code=400,
            detail="No active subscription to cancel"
        )
    
    success = polar_service.cancel_subscription(user.polar_subscription_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel subscription"
        )
    
    # Update local status
    user.subscription_status = "canceled"
    db.commit()
    
    return {
        "success": True,
        "message": "Subscription will be canceled at end of billing period"
    }


@router.get("/billing/portal-url")
async def get_portal_url(
    request: Request,
    db: Session = Depends(get_db_for_user),
    user: UserSettings = Depends(get_user_settings),
    polar_service: PolarService = Depends(get_polar_service)
):
    """
    Get URL for customer billing portal.
    
    User can manage payment methods, view invoices, etc.
    """
    
    if not user.polar_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No billing account found"
        )
    
    portal_url = polar_service.get_customer_portal_url(user.polar_customer_id)
    
    if not portal_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to get portal URL"
        )
    
    return {"portal_url": portal_url}

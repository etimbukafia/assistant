"""
Polar Service - Integration with Polar.sh billing

Handles all interactions with the Polar API for:
- Customer management
- Checkout session creation
- Subscription management
- Customer portal access
"""
import logging
from functools import lru_cache
from typing import Optional, Dict, Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class PolarService:
    """
    Service for interacting with Polar.sh API
    
    Uses the polar-sdk Python package for API calls.
    All methods are designed to be called from the billing router.
    """
    
    def __init__(self, settings=None):
        """Initialize Polar client"""
        self.settings = settings or get_settings()
        
        if not self.settings.POLAR_ACCESS_TOKEN:
            logger.warning("POLAR_ACCESS_TOKEN not configured - billing features disabled")
            self.client = None
            self.enabled = False
            return
        
        try:
            from polar_sdk import Polar
            self.client = Polar(access_token=self.settings.POLAR_ACCESS_TOKEN)
            self.enabled = True
            logger.info("PolarService initialized successfully")
        except ImportError:
            logger.error("polar-sdk not installed. Run: pip install polar-sdk")
            self.client = None
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Polar client: {e}")
            self.client = None
            self.enabled = False
    
    def get_or_create_customer(self, email: str) -> Optional[str]:
        """
        Get existing customer or create new one in Polar.
        
        Args:
            email: Customer's email address
            
        Returns:
            Polar customer ID or None if failed
        """
        if not self.enabled:
            logger.warning("Polar not enabled, cannot create customer")
            return None
        
        try:
            # Search for existing customer by email
            customers = self.client.customers.list(email=email)
            
            if customers.result and len(customers.result.items) > 0:
                customer_id = customers.result.items[0].id
                logger.info(f"Found existing Polar customer: {customer_id}")
                return customer_id
            
            # Create new customer
            customer = self.client.customers.create(
                email=email
            )
            
            logger.info(f"Created new Polar customer: {customer.id}")
            return customer.id
            
        except Exception as e:
            logger.error(f"Error in get_or_create_customer: {e}", exc_info=True)
            return None
    
    def create_checkout_session(
        self,
        customer_id: str,
        success_url: str,
        cancel_url: str
    ) -> Optional[str]:
        """
        Create a checkout session for the Pro subscription.
        
        Args:
            customer_id: Polar customer ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if checkout is cancelled
            
        Returns:
            Checkout URL or None if failed
        """
        if not self.enabled:
            logger.warning("Polar not enabled, cannot create checkout")
            return None
        
        if not self.settings.POLAR_PRODUCT_ID:
            logger.error("POLAR_PRODUCT_ID not configured")
            return None
        
        try:
            checkout = self.client.checkouts.create(
                product_id=self.settings.POLAR_PRODUCT_ID,
                customer_id=customer_id,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            
            logger.info(f"Created checkout session: {checkout.id}")
            return checkout.url
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}", exc_info=True)
            return None
    
    def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """
        Get subscription details from Polar.
        
        Args:
            subscription_id: Polar subscription ID
            
        Returns:
            Subscription details dict or None
        """
        if not self.enabled:
            return None
        
        try:
            subscription = self.client.subscriptions.get(subscription_id)
            
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "canceled_at": getattr(subscription, "canceled_at", None),
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription {subscription_id}: {e}", exc_info=True)
            return None
    
    def cancel_subscription(self, subscription_id: str) -> bool:
        """
        Cancel a subscription at the end of the billing period.
        
        Args:
            subscription_id: Polar subscription ID
            
        Returns:
            True if cancellation was successful
        """
        if not self.enabled:
            return False
        
        try:
            self.client.subscriptions.cancel(subscription_id)
            logger.info(f"Cancelled subscription: {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling subscription {subscription_id}: {e}", exc_info=True)
            return False
    
    def get_customer_portal_url(self, customer_id: str) -> Optional[str]:
        """
        Get URL for customer billing portal.
        
        Args:
            customer_id: Polar customer ID
            
        Returns:
            Portal URL or None
        """
        if not self.enabled:
            return None
        
        try:
            session = self.client.customer_sessions.create(
                customer_id=customer_id
            )
            
            return session.customer_portal_url
            

        except Exception as e:
            logger.error(f"Error getting portal URL for customer {customer_id}: {e}", exc_info=True)
            return None


@lru_cache
def get_polar_service() -> PolarService:
    """Factory for DI - returns cached PolarService instance."""
    return PolarService()


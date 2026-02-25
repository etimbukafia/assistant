"""
Dodo Payments service.

Provides checkout, portal, cancellation, and webhook verification.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Optional

import httpx

from app.infra.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _resolve_base_url(settings: Settings) -> str:
    if settings.DODO_BASE_URL:
        return settings.DODO_BASE_URL.rstrip("/")
    if settings.DODO_MODE == "live_mode":
        return "https://live.dodopayments.com"
    return "https://test.dodopayments.com"


class DodoService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = _resolve_base_url(self.settings)
        self.api_key = self.settings.DODO_PAYMENTS_API_KEY
        self.webhook_secret = self.settings.DODO_WEBHOOK_SECRET
        self.product_id = self.settings.DODO_PRODUCT_ID
        self.product_id_monthly = self.settings.DODO_PRODUCT_ID_MONTHLY or self.product_id
        self.product_id_annual = self.settings.DODO_PRODUCT_ID_ANNUAL
        self.credit_topup_product_id = self.settings.DODO_CREDIT_TOPUP_PRODUCT_ID
        self.credit_topup_unit_usd = max(1, int(self.settings.DODO_CREDIT_TOPUP_UNIT_USD or 1))
        self.enabled = bool(self.api_key and (self.product_id_monthly or self.product_id))

        if not self.api_key:
            logger.warning("DODO_PAYMENTS_API_KEY not configured - Dodo billing disabled")
        if not self.product_id_monthly:
            logger.warning("DODO_PRODUCT_ID not configured - Dodo billing disabled")

    def get_product_id_for_cycle(self, cycle: str) -> Optional[str]:
        normalized = (cycle or "").strip().lower()
        if normalized == "annual":
            return self.product_id_annual or self.product_id_monthly
        return self.product_id_monthly

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        if not self.api_key:
            return None

        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    params=params,
                )

            if response.status_code >= 400:
                logger.error(
                    "Dodo API error method=%s path=%s status=%s body=%s",
                    method,
                    path,
                    response.status_code,
                    response.text[:400],
                )
                return None

            if not response.content:
                return {}

            return response.json()
        except Exception as exc:
            logger.error("Dodo API request failed path=%s error=%s", path, exc, exc_info=True)
            return None

    def create_checkout_session(
        self,
        *,
        customer_email: str,
        customer_name: Optional[str],
        return_url: str,
        plan_cycle: str = "monthly",
    ) -> Optional[str]:
        if not self.enabled:
            return None

        product_id = self.get_product_id_for_cycle(plan_cycle)
        if not product_id:
            return None

        customer: dict[str, Any] = {"email": customer_email}
        if customer_name:
            customer["name"] = customer_name

        payload = {
            "product_cart": [{"product_id": product_id, "quantity": 1}],
            "customer": customer,
            "return_url": return_url,
        }
        data = self._request("POST", "/checkouts", json_body=payload)
        if not data:
            return None

        return (
            data.get("checkout_url")
            or data.get("url")
            or ((data.get("checkout") or {}).get("url") if isinstance(data.get("checkout"), dict) else None)
        )

    def create_credit_topup_checkout(
        self,
        *,
        customer_email: str,
        customer_name: Optional[str],
        return_url: str,
        amount_usd: int,
    ) -> Optional[str]:
        """
        Create a one-time checkout for extra AI credits.

        Expects DODO_CREDIT_TOPUP_PRODUCT_ID to reference a $1 one-time product.
        Quantity is derived from the requested USD amount.
        """
        if not self.api_key or not self.credit_topup_product_id:
            return None

        quantity = amount_usd // self.credit_topup_unit_usd
        if quantity <= 0:
            return None

        customer: dict[str, Any] = {"email": customer_email}
        if customer_name:
            customer["name"] = customer_name

        payload = {
            "product_cart": [{"product_id": self.credit_topup_product_id, "quantity": quantity}],
            "customer": customer,
            "return_url": return_url,
        }
        data = self._request("POST", "/checkouts", json_body=payload)
        if not data:
            return None

        return (
            data.get("checkout_url")
            or data.get("url")
            or ((data.get("checkout") or {}).get("url") if isinstance(data.get("checkout"), dict) else None)
        )

    def get_customer_portal_url(
        self,
        *,
        customer_id: str,
        return_url: Optional[str] = None,
    ) -> Optional[str]:
        if not self.api_key:
            return None

        payload: dict[str, Any] = {}
        if return_url:
            payload["return_url"] = return_url

        data = self._request(
            "POST",
            f"/customers/{customer_id}/customer-portal/session",
            json_body=payload,
        )
        if not data:
            return None

        return (
            data.get("portal_url")
            or data.get("url")
            or data.get("link")
            or data.get("session_url")
        )

    def cancel_subscription(self, subscription_id: str) -> bool:
        if not self.api_key:
            return False

        payload = {"cancel_at_next_billing_date": True}
        data = self._request("PATCH", f"/subscriptions/{subscription_id}", json_body=payload)
        return data is not None

    def preview_subscription_plan_change(
        self,
        *,
        subscription_id: str,
        product_id: str,
        proration_billing_mode: str = "difference_immediately",
        quantity: int = 1,
    ) -> Optional[dict[str, Any]]:
        if not self.api_key:
            return None

        payload = {
            "product_id": product_id,
            "quantity": quantity,
            "proration_billing_mode": proration_billing_mode,
        }
        return self._request(
            "POST",
            f"/subscriptions/{subscription_id}/change-plan/preview",
            json_body=payload,
        )

    def change_subscription_plan(
        self,
        *,
        subscription_id: str,
        product_id: str,
        proration_billing_mode: str = "difference_immediately",
        on_payment_failure: str = "prevent_change",
        quantity: int = 1,
    ) -> Optional[dict[str, Any]]:
        if not self.api_key:
            return None

        payload = {
            "product_id": product_id,
            "quantity": quantity,
            "proration_billing_mode": proration_billing_mode,
            "on_payment_failure": on_payment_failure,
        }
        return self._request(
            "POST",
            f"/subscriptions/{subscription_id}/change-plan",
            json_body=payload,
        )

    def find_customer_id_by_email(self, email: str) -> Optional[str]:
        if not self.api_key or not email:
            return None

        data = self._request(
            "GET",
            "/customers",
            params={"email": email, "page_size": 1, "page_number": 0},
        )
        if not data:
            return None

        items = data.get("items")
        if not isinstance(items, list) or not items:
            return None

        customer = items[0] if isinstance(items[0], dict) else {}
        return customer.get("customer_id") or customer.get("id")

    def find_latest_subscription_id_for_customer(self, customer_id: str) -> Optional[str]:
        if not self.api_key or not customer_id:
            return None

        data = self._request(
            "GET",
            "/subscriptions",
            params={"customer_id": customer_id, "page_size": 20, "page_number": 0},
        )
        if not data:
            return None

        items = data.get("items")
        if not isinstance(items, list) or not items:
            return None

        preferred_statuses = ["active", "trialing", "on_hold", "past_due"]
        normalized: list[dict[str, Any]] = [item for item in items if isinstance(item, dict)]

        def pick_by_status(targets: list[str]) -> Optional[dict[str, Any]]:
            for item in normalized:
                status = str(item.get("status") or "").lower()
                if status in targets:
                    return item
            return None

        selected = pick_by_status(preferred_statuses) or normalized[0]
        return selected.get("subscription_id") or selected.get("id")

    def verify_webhook(self, payload: bytes, headers: dict[str, str]) -> dict[str, Any]:
        """
        Verify webhook signature using Standard Webhooks.

        Raises ValueError when verification fails.
        Raises RuntimeError when not configured.
        """
        if not self.webhook_secret:
            raise RuntimeError("DODO_WEBHOOK_SECRET not configured")

        try:
            from standardwebhooks.webhooks import Webhook
        except Exception:
            try:
                from standardwebhooks import Webhook  # type: ignore
            except Exception as exc:
                raise RuntimeError("standardwebhooks package is not installed") from exc

        verifier = Webhook(self.webhook_secret)
        raw_text = payload.decode("utf-8")
        normalized_headers = {
            "webhook-id": headers.get("webhook-id", ""),
            "webhook-signature": headers.get("webhook-signature", ""),
            "webhook-timestamp": headers.get("webhook-timestamp", ""),
        }

        try:
            verified = verifier.verify(raw_text, normalized_headers)
        except Exception as exc:
            raise ValueError("invalid_webhook_signature") from exc

        if isinstance(verified, dict):
            return verified
        if isinstance(verified, bytes):
            return json.loads(verified.decode("utf-8"))
        if isinstance(verified, str):
            return json.loads(verified)

        # Some SDK versions return typed objects. Fall back to raw payload.
        return json.loads(raw_text)


@lru_cache
def get_dodo_service() -> DodoService:
    return DodoService()

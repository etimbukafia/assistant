import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

import httpx
from sqlalchemy.orm import Session

from app.infra.config import get_settings
from app.integrations.outlook import OutlookClient
from app.data.models import OutlookWatchSubscription, OutlookAccount

logger = logging.getLogger(__name__)


def _subscription_url() -> str:
    return "https://graph.microsoft.com/v1.0/subscriptions"


def _build_expiration(hours: int = 48) -> str:
    # Graph limits vary; use 48h as a safe default
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def setup_subscriptions_for_user(db: Session, user_id: str) -> dict:
    """
    Create Outlook mail + calendar subscriptions for a user.
    """
    settings = get_settings()
    if not settings.API_URL:
        logger.warning("API_URL not set; cannot set up Outlook subscriptions")
        return {"setup": 0, "failed": 0}

    client = OutlookClient(db=db, user_id=user_id)
    if not client.load_credentials():
        logger.warning("Cannot setup Outlook subscriptions: credentials invalid")
        return {"setup": 0, "failed": 1}

    webhook_url = f"{settings.API_URL}/v1/webhooks/outlook"
    client_state = uuid.uuid4().hex
    setup = 0
    failed = 0

    resources = [
        "me/mailFolders('Inbox')/messages",
        "me/events",
    ]

    for resource in resources:
        payload = {
            "changeType": "created,updated",
            "notificationUrl": webhook_url,
            "resource": resource,
            "expirationDateTime": _build_expiration(),
            "clientState": client_state,
        }
        try:
            resp = httpx.post(
                _subscription_url(),
                headers=client._graph_headers(),
                json=payload,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            sub = OutlookWatchSubscription(
                user_id=user_id,
                subscription_id=data.get("id"),
                resource=resource,
                client_state=client_state,
                expiration=datetime.fromisoformat(data.get("expirationDateTime")).replace(tzinfo=None),
            )
            db.add(sub)
            setup += 1
        except Exception as e:
            logger.error("Failed to create Outlook subscription for %s: %s", resource, e)
            failed += 1

    if setup > 0:
        db.commit()
    return {"setup": setup, "failed": failed}


def renew_all_subscriptions() -> dict:
    """
    Renew Outlook subscriptions for all users.
    """
    from app.infra.database import SessionLocal
    db = SessionLocal()
    try:
        subs = db.query(OutlookWatchSubscription).all()
        if not subs:
            return {"renewed": 0, "failed": 0}
        renewed = 0
        failed = 0
        # Group by user to load credentials once
        by_user: Dict[str, list[OutlookWatchSubscription]] = {}
        for sub in subs:
            by_user.setdefault(sub.user_id, []).append(sub)

        for user_id, user_subs in by_user.items():
            client = OutlookClient(db=db, user_id=user_id)
            if not client.load_credentials():
                failed += len(user_subs)
                continue
            for sub in user_subs:
                try:
                    payload = {"expirationDateTime": _build_expiration()}
                    resp = httpx.patch(
                        f"{_subscription_url()}/{sub.subscription_id}",
                        headers=client._graph_headers(),
                        json=payload,
                        timeout=10.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    sub.expiration = datetime.fromisoformat(data.get("expirationDateTime")).replace(tzinfo=None)
                    renewed += 1
                except Exception as e:
                    logger.error("Failed to renew Outlook subscription %s: %s", sub.subscription_id, e)
                    failed += 1
        db.commit()
        return {"renewed": renewed, "failed": failed}
    finally:
        db.close()


def stop_subscriptions_for_user(db: Session, user_id: str) -> dict:
    """
    Best-effort cleanup of Outlook subscriptions for a user.
    Removes local rows and attempts to delete remote subscriptions.
    """
    subs = db.query(OutlookWatchSubscription).filter(
        OutlookWatchSubscription.user_id == user_id
    ).all()
    if not subs:
        return {"deleted": 0, "remote_failed": 0}

    remote_failed = 0
    client = OutlookClient(db=db, user_id=user_id)
    can_remote = client.load_credentials()

    for sub in subs:
        if can_remote and sub.subscription_id:
            try:
                httpx.delete(
                    f"{_subscription_url()}/{sub.subscription_id}",
                    headers=client._graph_headers(),
                    timeout=10.0,
                )
            except Exception:
                remote_failed += 1

    deleted = db.query(OutlookWatchSubscription).filter(
        OutlookWatchSubscription.user_id == user_id
    ).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted, "remote_failed": remote_failed}

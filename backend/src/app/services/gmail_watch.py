"""
Gmail Push Notifications (Pub/Sub Watch) Management

Handles setting up and renewing Gmail watch subscriptions so that
new emails trigger Pub/Sub notifications to our webhook endpoint.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.infra.config import get_settings
from app.infra.database import SessionLocal
from app.integrations.gmail import GmailClient
from app.data.models import GmailAccount

logger = logging.getLogger(__name__)


def setup_watch(gmail_client: GmailClient) -> Optional[dict]:
    """
    Set up a Gmail watch for push notifications via Pub/Sub.

    Call this after a user connects their Gmail account.
    The watch expires after 7 days and must be renewed.

    Args:
        gmail_client: Authenticated GmailClient instance

    Returns:
        dict with historyId and expiration, or None on failure
    """
    settings = get_settings()

    if not settings.GOOGLE_CLOUD_PROJECT_ID:
        logger.warning("GOOGLE_CLOUD_PROJECT_ID not set, skipping Gmail watch setup")
        return None

    raw_topic = (settings.GMAIL_PUBSUB_TOPIC or "").strip()
    if raw_topic.startswith("projects/"):
        topic = raw_topic
    else:
        topic = f"projects/{settings.GOOGLE_CLOUD_PROJECT_ID}/topics/{raw_topic}"

    if not gmail_client.service:
        if not gmail_client.load_credentials():
            logger.error("Cannot setup watch: Gmail client not authenticated")
            return None

    try:
        logger.info("Setting up Gmail watch: topic=%s labels=%s", topic, ["INBOX"])
        response = gmail_client.service.users().watch(
            userId='me',
            body={
                'topicName': topic,
                'labelIds': ['INBOX'],
            }
        ).execute()

        logger.info(
            f"Gmail watch set up successfully. "
            f"historyId={response.get('historyId')}, "
            f"expiration={response.get('expiration')}"
        )
        return response

    except Exception as e:
        logger.error("Failed to setup Gmail watch: %s", e, exc_info=True)
        return None


def renew_all_watches():
    """
    Renew Gmail watches for all connected accounts.

    Should be called daily via a scheduled task. Gmail watches
    expire after 7 days; calling watch() again extends them.
    """
    db = SessionLocal()
    try:
        accounts = db.query(GmailAccount).filter(
            GmailAccount.user_id.isnot(None)
        ).all()

        renewed = 0
        failed = 0

        for account in accounts:
            try:
                client = GmailClient(db=db, user_id=account.user_id)
                if not client.load_credentials(email=account.email):
                    logger.warning(f"Cannot renew watch for {account.email}: credentials invalid")
                    failed += 1
                    continue

                result = setup_watch(client)
                if result:
                    # Update stored history ID if we got a newer one
                    history_id = result.get('historyId')
                    if history_id and not account.last_history_id:
                        account.last_history_id = str(history_id)
                    renewed += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Failed to renew watch for {account.email}: {e}")
                failed += 1

        db.commit()
        logger.info(f"Gmail watch renewal complete: {renewed} renewed, {failed} failed")
        return {"renewed": renewed, "failed": failed}

    finally:
        db.close()


def stop_watch(db: Session, user_id: str) -> bool:
    """
    Stop Gmail push notifications for a user.
    Gmail supports users().stop() to turn off push notifications.
    """
    try:
        account = db.query(GmailAccount).filter(GmailAccount.user_id == user_id).first()
        if not account:
            return True

        client = GmailClient(db=db, user_id=user_id)
        if not client.load_credentials(email=account.email):
            logger.warning("Cannot stop Gmail watch: credentials invalid for %s", account.email)
            return False

        client.service.users().stop(userId="me").execute()
        logger.info("Stopped Gmail watch for user=%s", user_id)
        return True
    except Exception as e:
        logger.warning("Failed to stop Gmail watch for user=%s: %s", user_id, e)
        return False

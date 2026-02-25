"""
Google Calendar Push Notification Watch Management

Unlike Gmail (Pub/Sub, idempotent renewal via watch()), each Calendar watch
is a unique channel with its own channel_id and resource_id. Renewal requires:
  1. Stop the old channel via channels().stop()
  2. Create a new watch via events().watch() with a fresh UUID

Watches expire after ~7 days. The daily renewal job handles this automatically.
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.infra.config import get_settings
from app.infra.database import SessionLocal
from app.data.models import CalendarWatchChannel

logger = logging.getLogger(__name__)


def _stop_channel(service, channel_id: str, resource_id: str) -> bool:
    """Stop a single Google Calendar watch channel."""
    try:
        service.channels().stop(body={
            "id": channel_id,
            "resourceId": resource_id,
        }).execute()
        logger.info(f"Stopped Calendar watch channel={channel_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to stop Calendar channel={channel_id}: {e}")
        return False


def setup_watches_for_user(db: Session, user_id: str) -> dict:
    """
    Set up Calendar push notification watches for all of a user's calendars.

    Stops any existing channels for this user first (clean slate), then creates
    fresh watches for every calendar in the account.

    Called after Gmail/Google is connected (same credentials cover Calendar).

    Returns:
        {"setup": N, "failed": M}
    """
    settings = get_settings()

    if not settings.API_URL:
        logger.warning("API_URL not set; cannot set up Calendar watches")
        return {"setup": 0, "failed": 0}

    # Build the Google Calendar service
    try:
        from app.services.calendar import CalendarService
        cal_service = CalendarService(db=db, user_id=user_id)
        service = cal_service._get_service()
    except Exception as e:
        logger.error(f"Cannot build Calendar service for user {user_id}: {e}")
        return {"setup": 0, "failed": 1}

    webhook_url = f"{settings.API_URL}/v1/webhooks/calendar"

    # Stop and remove any existing channels for this user
    existing = db.query(CalendarWatchChannel).filter(
        CalendarWatchChannel.user_id == user_id
    ).all()
    for ch in existing:
        _stop_channel(service, ch.channel_id, ch.resource_id)
        db.delete(ch)
    if existing:
        db.commit()

    # Determine which calendars to watch:
    # - If the user has explicitly chosen calendars, watch only those
    # - Otherwise, watch all calendars on the account
    from app.data.models import UserSettings as _UserSettings
    user_settings = db.query(_UserSettings).filter(_UserSettings.user_id == user_id).first()
    user_calendar_ids = (user_settings.calendar_ids or []) if user_settings else []

    default_cal = (user_settings.default_calendar_id or "primary") if user_settings else "primary"
    calendar_ids = user_calendar_ids if user_calendar_ids else [default_cal]

    setup_count = 0
    failed_count = 0

    for calendar_id in calendar_ids:
        channel_id = str(uuid.uuid4())
        try:
            response = service.events().watch(
                calendarId=calendar_id,
                body={
                    "id": channel_id,
                    "type": "web_hook",
                    "address": webhook_url,
                }
            ).execute()

            # Google returns expiration as milliseconds since epoch
            expiration_ms = int(response.get("expiration", 0))
            expiration_dt = datetime.fromtimestamp(expiration_ms / 1000, tz=timezone.utc)
            # Store as naive UTC (consistent with other DateTime columns in this codebase)
            expiration_dt = expiration_dt.replace(tzinfo=None)

            channel = CalendarWatchChannel(
                user_id=user_id,
                channel_id=response.get("id", channel_id),
                resource_id=response["resourceId"],
                calendar_id=calendar_id,
                expiration=expiration_dt,
            )
            db.add(channel)
            setup_count += 1
            logger.info(
                f"Calendar watch set up: user={user_id} calendar={calendar_id} "
                f"channel={channel_id} expires={expiration_dt}"
            )
        except Exception as e:
            logger.error(
                f"Failed to set up Calendar watch: user={user_id} calendar={calendar_id}: {e}"
            )
            failed_count += 1

    if setup_count > 0:
        db.commit()

    return {"setup": setup_count, "failed": failed_count}


def stop_watches_for_user(db: Session, user_id: str) -> dict:
    """
    Stop and remove Calendar watch channels for a user.
    Used when disconnecting a provider.
    """
    try:
        from app.services.calendar import CalendarService
        cal_service = CalendarService(db=db, user_id=user_id)
        service = cal_service._get_service()
    except Exception as e:
        logger.warning("Cannot build Calendar service for user %s: %s", user_id, e)
        return {"stopped": 0, "failed": 1}

    existing = db.query(CalendarWatchChannel).filter(
        CalendarWatchChannel.user_id == user_id
    ).all()
    stopped = 0
    failed = 0
    for ch in existing:
        if _stop_channel(service, ch.channel_id, ch.resource_id):
            stopped += 1
        else:
            failed += 1
        db.delete(ch)
    if existing:
        db.commit()
    return {"stopped": stopped, "failed": failed}


def renew_all_watches() -> dict:
    """
    Renew all active Calendar watch channels across all users.

    For each user: stops existing channels and creates fresh ones.
    Should be called daily (watches expire in ~7 days).

    Returns:
        {"renewed": N, "failed": M}
    """
    db = SessionLocal()
    try:
        # Get distinct user_ids that have active watch channels
        user_ids = [
            row[0]
            for row in db.query(CalendarWatchChannel.user_id).distinct().all()
        ]

        if not user_ids:
            logger.info("No Calendar watch channels to renew")
            return {"renewed": 0, "failed": 0}

        total_renewed = 0
        total_failed = 0

        for user_id in user_ids:
            try:
                result = setup_watches_for_user(db, user_id)
                total_renewed += result.get("setup", 0)
                total_failed += result.get("failed", 0)
            except Exception as e:
                logger.error(f"Failed to renew Calendar watches for user {user_id}: {e}")
                total_failed += 1

        logger.info(
            f"Calendar watch renewal complete: {total_renewed} renewed, {total_failed} failed"
        )
        return {"renewed": total_renewed, "failed": total_failed}

    finally:
        db.close()

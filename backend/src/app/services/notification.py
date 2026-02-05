"""
Notification Service

Creates in-app notifications and sends Expo push notifications.
Respects quiet hours, priority rules, and user preferences.

Push priority rules:
- "high" priority -> push notification + feed entry
- "normal" priority -> feed entry only
- "low" priority -> feed entry only
"""
import logging
from datetime import datetime, timezone, time
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.data.models import Notification, DeviceToken, UserSettings

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class NotificationService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def create_notification(
        self,
        title: str,
        body: str = None,
        category: str = "system",
        priority: str = "normal",
        target_type: str = None,
        target_id: str = None,
        send_push: bool = True,
    ) -> Notification:
        """
        Create an in-app notification and optionally send push.

        Always creates a feed entry. Only sends push if:
        - priority == "high"
        - send_push == True
        - User has active device tokens
        - Not in quiet hours
        - User preferences allow it
        """
        notification = Notification(
            user_id=self.user_id,
            title=title,
            body=body,
            category=category,
            priority=priority,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
        )
        self.db.add(notification)
        self.db.flush()

        if send_push and priority == "high":
            self._send_push(notification)

        self.db.commit()
        return notification

    def get_notifications(
        self, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Notification], int, int]:
        """Get paginated notifications and counts."""
        total = self.db.query(Notification).filter(
            Notification.user_id == self.user_id
        ).count()

        unread_count = self.db.query(Notification).filter(
            Notification.user_id == self.user_id,
            Notification.is_read == False
        ).count()

        notifications = (
            self.db.query(Notification)
            .filter(Notification.user_id == self.user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return notifications, total, unread_count

    def get_unread_count(self) -> int:
        return self.db.query(Notification).filter(
            Notification.user_id == self.user_id,
            Notification.is_read == False
        ).count()

    def mark_read(self, notification_ids: List[int]):
        """Mark specific notifications as read."""
        self.db.query(Notification).filter(
            Notification.id.in_(notification_ids),
            Notification.user_id == self.user_id
        ).update({
            Notification.is_read: True,
            Notification.read_at: datetime.now(timezone.utc)
        }, synchronize_session="fetch")
        self.db.commit()

    def mark_all_read(self):
        """Mark all notifications as read for the user."""
        self.db.query(Notification).filter(
            Notification.user_id == self.user_id,
            Notification.is_read == False
        ).update({
            Notification.is_read: True,
            Notification.read_at: datetime.now(timezone.utc)
        }, synchronize_session="fetch")
        self.db.commit()

    @staticmethod
    def _is_quiet_hours(preferences: Dict) -> bool:
        """Check if current time is in quiet hours."""
        quiet_start = preferences.get("quiet_hours_start", "22:00")
        quiet_end = preferences.get("quiet_hours_end", "08:00")

        now = datetime.now(timezone.utc).time()
        start = time.fromisoformat(quiet_start)
        end = time.fromisoformat(quiet_end)

        if start < end:
            return start <= now <= end
        else:
            # Overnight range (e.g., 22:00 - 08:00)
            return now >= start or now <= end

    def _send_push(self, notification: Notification):
        """Enqueue push notification for async delivery with retry support."""
        from app.jobs.queue import enqueue_task

        # Check preferences before enqueueing
        settings = self.db.query(UserSettings).filter(
            UserSettings.user_id == self.user_id
        ).first()

        if settings:
            prefs = settings.notification_preferences or {}

            if not prefs.get("push_enabled", True):
                logger.debug(f"Push disabled for user {self.user_id}")
                return

            # Check category-specific preferences
            category_pref_map = {
                "task_urgent": "push_urgent_tasks",
                "task_deadline": "push_deadlines",
                "digest_ready": "push_digests",
                "briefing_ready": "push_briefings",
                "reminder_due": "push_urgent_tasks",
            }
            pref_key = category_pref_map.get(notification.category)
            if pref_key and not prefs.get(pref_key, True):
                logger.debug(f"Push disabled for category {notification.category}")
                return

            # Check quiet hours
            reminder_prefs = settings.reminder_preferences or {}
            if self._is_quiet_hours(reminder_prefs):
                logger.info(f"Quiet hours active, skipping push for notification {notification.id}")
                return

        # Check if user has active device tokens before enqueueing
        token_count = self.db.query(DeviceToken).filter(
            DeviceToken.user_id == self.user_id,
            DeviceToken.is_active == True
        ).count()

        if not token_count:
            logger.debug(f"No active device tokens for user {self.user_id}")
            return

        # Enqueue for async delivery with retry support
        enqueue_task(
            task_type="send_push_notification",
            payload={
                "notification_id": notification.id,
                "user_id": self.user_id,
            },
            db=self.db
        )
        logger.debug(f"Push notification {notification.id} enqueued for delivery")


def send_push_for_notification(notification_id: int, user_id: str, db) -> bool:
    """
    Send push notification to all active devices.

    Called by task handler. Raises on failure for retry support.
    Returns True if at least one push was sent successfully.
    """
    import httpx

    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id
    ).first()

    if not notification:
        logger.warning(f"Notification {notification_id} not found for push delivery")
        return False

    if notification.push_sent:
        logger.debug(f"Notification {notification_id} already sent")
        return True

    # Get active device tokens
    tokens = db.query(DeviceToken).filter(
        DeviceToken.user_id == user_id,
        DeviceToken.is_active == True
    ).all()

    if not tokens:
        logger.debug(f"No active device tokens for user {user_id}")
        return False

    # Build Expo push messages
    messages = []
    for token in tokens:
        messages.append({
            "to": token.expo_push_token,
            "title": notification.title,
            "body": notification.body or "",
            "data": {
                "notification_id": notification.id,
                "category": notification.category,
                "target_type": notification.target_type,
                "target_id": notification.target_id,
            },
            "sound": "default",
            "priority": "high",
            "channelId": "default",
        })

    # Send to Expo - raises on failure for retry
    response = httpx.post(
        EXPO_PUSH_URL,
        json=messages,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    result = response.json()

    # Process response
    any_success = False
    tickets = result.get("data", [])
    for i, ticket in enumerate(tickets):
        if ticket.get("status") == "ok":
            any_success = True
            notification.push_sent = True
            notification.push_sent_at = datetime.now(timezone.utc)
            notification.push_ticket_id = ticket.get("id")
        elif ticket.get("status") == "error":
            error_type = ticket.get("details", {}).get("error", "")
            if error_type == "DeviceNotRegistered" and i < len(tokens):
                tokens[i].is_active = False
                logger.info(f"Deactivated invalid push token for user {user_id}")

    db.commit()
    logger.info(f"Push sent for notification {notification_id} to {len(tokens)} device(s)")
    return any_success

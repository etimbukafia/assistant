"""
Notification Module

Handles notifying users about agent actions and important events.
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timezone

from .base import BaseModule

logger = logging.getLogger(__name__)


class NotificationModule(BaseModule):
    """
    Module for user notifications

    Capabilities:
    - Notify user about agent actions
    - Send priority notifications
    - Queue notifications for batching
    - Track notification delivery

    NOTE: This currently logs notifications. Full notification delivery
    (WhatsApp, Email, Slack, Push) will be added in future updates.
    """

    def get_capabilities(self) -> Dict[str, str]:
        """Return capabilities of this module"""
        return {
            "notify_user": "Notify user about an agent action or event",
            "send_urgent": "Send an urgent notification immediately",
            "queue_digest": "Queue notification for digest delivery",
        }

    def notify_user(
        self,
        message: str,
        type: str = "info",
        priority: str = "normal",
        related_message_id: int = None,
        related_task_id: int = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Notify user about an agent action or event

        Args:
            message: Notification message
            type: Type of notification (info, success, warning, error)
            priority: Priority level (low, normal, high, urgent)
            related_message_id: Related message ID
            related_task_id: Related task ID
            metadata: Additional metadata

        Returns:
            Notification delivery status
        """
        # TODO: Implement actual notification delivery
        # For now, log the notification

        log_level = {
            "info": logging.INFO,
            "success": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }.get(type, logging.INFO)

        logger.log(
            log_level,
            f"[USER NOTIFICATION] ({type.upper()}, {priority}) {message}",
            extra={
                "related_message_id": related_message_id,
                "related_task_id": related_task_id,
                "metadata": metadata,
            }
        )

        return {
            "delivered": True,
            "message": message,
            "type": type,
            "priority": priority,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "delivery_method": "log",
            "note": "Full notification delivery not yet implemented (currently logging only)",
        }

    def send_urgent(
        self,
        message: str,
        related_message_id: int = None,
        related_task_id: int = None
    ) -> Dict[str, Any]:
        """
        Send an urgent notification immediately

        Urgent notifications bypass quiet hours and batching.

        Args:
            message: Notification message
            related_message_id: Related message ID
            related_task_id: Related task ID

        Returns:
            Notification delivery status
        """
        # For urgent notifications, use the notify_user method with urgent priority
        return self.notify_user(
            message=message,
            type="urgent",
            priority="urgent",
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        )

    def queue_digest(
        self,
        message: str,
        category: str = "general",
        related_message_id: int = None,
        related_task_id: int = None
    ) -> Dict[str, Any]:
        """
        Queue notification for digest delivery

        Digest notifications are batched and sent at scheduled times.

        Args:
            message: Notification message
            category: Category for grouping (tasks, emails, calendar, etc.)
            related_message_id: Related message ID
            related_task_id: Related task ID

        Returns:
            Queue status
        """
        # TODO: Implement digest queue system
        # For now, just log it

        logger.info(
            f"[DIGEST QUEUE] ({category}) {message}",
            extra={
                "related_message_id": related_message_id,
                "related_task_id": related_task_id,
            }
        )

        return {
            "queued": True,
            "message": message,
            "category": category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Digest system not yet implemented (currently logging only)",
        }

"""
Follow-Up Module

Handles follow-up evaluation and generation for tasks.
"""
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

from .base import BaseModule
from app.database import SessionLocal
from app.models import Task, Message


class FollowUpModule(BaseModule):
    """
    Module for managing follow-ups on pending tasks

    Capabilities:
    - Evaluate if a follow-up is needed
    - Check if a reply has been received
    - Generate polite follow-up messages
    """

    def get_capabilities(self) -> Dict[str, str]:
        """Return capabilities of this module"""
        return {
            "evaluate_need": "Evaluate if a follow-up is still needed for a task",
            "check_for_reply": "Check if a reply has been received for a waiting_for task",
            "generate_follow_up": "Generate a polite follow-up message for a task",
        }

    def evaluate_need(self, task_id: int) -> Dict[str, Any]:
        """
        Evaluate if a follow-up is still needed

        Args:
            task_id: ID of the task to evaluate

        Returns:
            Dictionary with evaluation result
        """
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()

            if not task:
                return {
                    "needed": False,
                    "reason": "Task not found",
                    "confidence": 0.0,
                }

            # Check if task is still active
            if task.status in ["completed", "dismissed"]:
                return {
                    "needed": False,
                    "reason": f"Task is already {task.status}",
                    "confidence": 1.0,
                }

            # Check task type - only follow up on waiting_for and implied_followup
            if task.task_type not in ["waiting_for", "implied_followup"]:
                return {
                    "needed": False,
                    "reason": f"Task type '{task.task_type}' doesn't require follow-up",
                    "confidence": 0.9,
                }

            # Check if task was created recently (< 3 days ago)
            days_since_created = (datetime.now(timezone.utc) - task.created_at).days
            if days_since_created < 3:
                return {
                    "needed": False,
                    "reason": f"Task created only {days_since_created} days ago, too soon for follow-up",
                    "confidence": 0.8,
                }

            # Check if we already sent a follow-up recently
            if task.last_reminded_at:
                days_since_reminder = (datetime.now(timezone.utc) - task.last_reminded_at).days
                if days_since_reminder < 5:
                    return {
                        "needed": False,
                        "reason": f"Follow-up sent {days_since_reminder} days ago, too soon for another",
                        "confidence": 0.85,
                    }

            # Follow-up is needed
            return {
                "needed": True,
                "reason": f"No activity for {days_since_created} days, follow-up appropriate",
                "confidence": 0.88,
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "task_type": task.task_type,
                    "days_since_created": days_since_created,
                }
            }

        finally:
            db.close()

    def check_for_reply(self, task_id: int) -> Dict[str, Any]:
        """
        Check if a reply has been received for a waiting_for task

        This checks if there are newer messages in the same thread.

        Args:
            task_id: ID of the task

        Returns:
            Dictionary with reply status
        """
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()

            if not task:
                return {
                    "reply_received": False,
                    "reason": "Task not found",
                }

            # Get source message
            source_message = db.query(Message).filter(
                Message.id == task.message_id
            ).first()

            if not source_message:
                return {
                    "reply_received": False,
                    "reason": "Source message not found",
                }

            # Check for newer messages in the same thread
            newer_messages = db.query(Message).filter(
                Message.thread_id == source_message.thread_id,
                Message.received_at > source_message.received_at
            ).count()

            if newer_messages > 0:
                return {
                    "reply_received": True,
                    "reason": f"Found {newer_messages} newer message(s) in thread",
                    "newer_messages_count": newer_messages,
                }

            return {
                "reply_received": False,
                "reason": "No newer messages in thread",
            }

        finally:
            db.close()

    def generate_follow_up(self, task_id: int, context: str = None) -> str:
        """
        Generate a polite follow-up message

        Args:
            task_id: ID of the task to follow up on
            context: Optional additional context

        Returns:
            Follow-up message text
        """
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()

            if not task:
                return "Unable to generate follow-up: task not found"

            # Get source message
            source_message = db.query(Message).filter(
                Message.id == task.message_id
            ).first()

            if not source_message:
                return "Unable to generate follow-up: source message not found"

            # Simple template-based follow-up for now
            # TODO: Use AI to generate more contextual follow-ups

            days_since = (datetime.now(timezone.utc) - task.created_at).days

            if task.task_type == "waiting_for":
                follow_up = (
                    f"Hi,\n\n"
                    f"I wanted to follow up on my previous email about: {task.title}\n\n"
                    f"Just checking if you've had a chance to look at this. "
                    f"Let me know if you need any additional information.\n\n"
                    f"Thanks!"
                )
            else:  # implied_followup
                follow_up = (
                    f"Hi,\n\n"
                    f"Following up on: {task.title}\n\n"
                    f"Wanted to check in on this. Please let me know if there's anything "
                    f"I can do to help move this forward.\n\n"
                    f"Thanks!"
                )

            return follow_up

        finally:
            db.close()

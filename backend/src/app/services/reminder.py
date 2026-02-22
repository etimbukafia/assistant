"""
ReminderService

Central service for scheduling, recording, and auditing task reminders.
Used by the worker (evaluate_reminder job) and any future reminder-aware code.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.data.models import Task, TaskReminder

logger = logging.getLogger(__name__)


class ReminderService:
    """
    Single place for all reminder logic.

    Responsibilities:
    - Record a reminder attempt (success or failure) in task_reminders
    - Update task.last_reminded_at and task.reminder_count
    - Provide helper queries (reminder history, count since date, etc.)
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_reminder(
        self,
        task: Task,
        *,
        reminder_type: str = "scheduled",
        channel: str = "push",
        delivered: bool = True,
        delivery_error: Optional[str] = None,
    ) -> TaskReminder:
        """
        Persist a reminder record and update the task's reminder fields.

        Args:
            task:           The Task being reminded.
            reminder_type:  'scheduled' | 'urgent_nudge' | 'digest' | 'manual'
            channel:        'push' | 'email' | 'in_app'
            delivered:      True if the notification was successfully sent.
            delivery_error: Error message if delivery failed.

        Returns:
            The created TaskReminder row.
        """
        now = datetime.now(timezone.utc)

        reminder = TaskReminder(
            task_id=task.id,
            user_id=self.user_id,
            reminder_type=reminder_type,
            channel=channel,
            reminded_at=now,
            delivered=delivered,
            delivery_error=delivery_error,
        )
        self.db.add(reminder)

        # Keep task fields in sync
        task.last_reminded_at = now
        task.reminder_count = (task.reminder_count or 0) + 1

        self.db.flush()  # get reminder.id without full commit

        logger.info(
            f"Reminder recorded: task_id={task.id} type={reminder_type} "
            f"channel={channel} delivered={delivered}"
        )
        return reminder

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_reminders_for_task(self, task_id: int) -> list[TaskReminder]:
        """Return all reminder records for a task, newest first."""
        return (
            self.db.query(TaskReminder)
            .filter(TaskReminder.task_id == task_id)
            .order_by(TaskReminder.reminded_at.desc())
            .all()
        )

    def reminder_count_for_task(self, task_id: int) -> int:
        """How many times has this task been reminded in total?"""
        return (
            self.db.query(TaskReminder)
            .filter(TaskReminder.task_id == task_id)
            .count()
        )

    def hours_since_last_reminder(self, task: Task) -> Optional[float]:
        """Return hours since the last reminder, or None if never reminded."""
        if not task.last_reminded_at:
            return None
        delta = datetime.now(timezone.utc) - task.last_reminded_at
        return delta.total_seconds() / 3600

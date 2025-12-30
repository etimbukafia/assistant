"""
Email Assistant Worker - App-specific task handlers

This worker is specific to the email assistant.
It uses the generic core/queue worker with email-specific handlers.

Run with:
    python -m app.worker
"""
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime, timedelta, time, timezone
from fastapi import BackgroundTasks

from core.events import emit_event
from core.queue import Worker
from app.queue import queue_service

logger = logging.getLogger(__name__)


async def handle_emit_event(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'emit_event' tasks

    Emits an event after a handler completes.
    This enables event chaining and completion signals.
    """
    event_name = payload.get("event_name")
    event_payload = payload.get("event_payload", {})

    if not event_name:
        raise ValueError("emit_event task missing 'event_name' in payload")

    # Create BackgroundTasks for event emission
    background_tasks = BackgroundTasks()

    # Emit the event
    emit_event(
        event_name=event_name,
        payload=event_payload,
        background_tasks=background_tasks,
        correlation_id=correlation_id
    )

    # Execute background tasks
    await background_tasks()

    logger.info(
        f"Emitted event: {event_name}",
        extra={"task_id": task_id, "event_name": event_name, "correlation_id": correlation_id}
    )


async def handle_send_notification(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'send_notification' tasks

    Future: Send notifications via WhatsApp, Email, Slack
    """
    logger.info(f"Notification task (id={task_id}) - handler not yet implemented")
    # TODO: Implement notification sending
    # notification_type = payload.get("type")  # whatsapp, email, slack
    # message_id = payload.get("message_id")
    # Send notification...


async def handle_trigger_agent(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'trigger_agent' tasks

    Triggers the orchestrator to evaluate and take autonomous actions.
    """
    from app.agents.orchestrator import AssistantOrchestrator

    try:
        event_type = payload.get("event_type")
        event_payload = payload.get("event_payload", {})

        if not event_type:
            logger.error(f"trigger_agent task (id={task_id}) missing 'event_type' in payload")
            return

        logger.info(
            f"Triggering orchestrator for event: {event_type}",
            extra={"task_id": task_id, "correlation_id": correlation_id}
        )

        # Initialize orchestrator
        orchestrator = AssistantOrchestrator()

        # Process the event
        result = orchestrator.process_event(
            event_type=event_type,
            event_payload=event_payload,
            correlation_id=correlation_id
        )

        logger.info(
            f"Orchestrator completed: should_act={result['decision'].get('should_act')}, "
            f"action_type={result['decision'].get('action_type')}",
            extra={"task_id": task_id, "correlation_id": correlation_id}
        )

    except Exception as e:
        logger.error(
            f"Error in handle_trigger_agent: {str(e)}",
            extra={"task_id": task_id, "correlation_id": correlation_id},
            exc_info=True
        )


def is_quiet_hours(preferences: Dict) -> bool:
    """Check if current time is in quiet hours"""
    quiet_start = preferences.get("quiet_hours_start", "22:00")
    quiet_end = preferences.get("quiet_hours_end", "08:00")

    current_time = datetime.now(timezone.utc).time()
    start = time.fromisoformat(quiet_start)
    end = time.fromisoformat(quiet_end)

    if start < end:
        return start <= current_time <= end
    else:  # Crosses midnight
        return current_time >= start or current_time <= end


def get_next_available_time(preferences: Dict) -> datetime:
    """Get next time outside quiet hours"""
    quiet_end = preferences.get("quiet_hours_end", "08:00")
    end_time = time.fromisoformat(quiet_end)

    now = datetime.now(timezone.utc)
    next_time = datetime.combine(now.date(), end_time, tzinfo=timezone.utc)

    if next_time < now:
        next_time += timedelta(days=1)

    return next_time


async def handle_evaluate_reminder(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'evaluate_reminder' tasks

    Evaluates if a task reminder should be sent now using AI.
    Respects quiet hours, frequency limits, and context.
    """
    from app.models import Task, Message, UserSettings, TaskReminder
    from app.database import SessionLocal
    from app.ai_processor import AIProcessor
    from app.queue import enqueue_task

    db = SessionLocal()
    try:
        task_record_id = payload.get("task_id")
        task = db.query(Task).filter(Task.id == task_record_id).first()

        if not task:
            logger.warning(f"Task {task_record_id} not found for reminder evaluation")
            return

        # Check if task is still active
        if task.status in ["completed", "dismissed"]:
            logger.info(f"Task {task_record_id} already {task.status}, skipping reminder")
            return

        # Check if snoozed
        if task.snoozed_until and task.snoozed_until > datetime.now(timezone.utc):
            logger.info(f"Task {task_record_id} snoozed until {task.snoozed_until}")
            # Reschedule for after snooze period
            enqueue_task(
                task_type="evaluate_reminder",
                payload={"task_id": task_record_id},
                scheduled_for=task.snoozed_until,
                db=db
            )
            return

        # Get user settings for reminder limits
        settings = db.query(UserSettings).first()
        if not settings:
            settings = UserSettings(user_email="default@user.com")

        # Check frequency limits
        if task.last_reminded_at:
            hours_since_last = (datetime.now(timezone.utc) - task.last_reminded_at).total_seconds() / 3600
            if hours_since_last < 24:  # Don't remind more than once per day
                logger.info(f"Task {task_record_id} reminded {hours_since_last:.1f}h ago, too soon")
                # Reschedule for tomorrow
                enqueue_task(
                    task_type="evaluate_reminder",
                    payload={"task_id": task_record_id},
                    scheduled_for=datetime.now(timezone.utc) + timedelta(days=1),
                    db=db
                )
                return

        # Check quiet hours
        if is_quiet_hours(settings.reminder_preferences or {}):
            logger.info(f"In quiet hours, rescheduling reminder for task {task_record_id}")
            next_available = get_next_available_time(settings.reminder_preferences or {})
            enqueue_task(
                task_type="evaluate_reminder",
                payload={"task_id": task_record_id},
                scheduled_for=next_available,
                db=db
            )
            return

        # Get source message
        message = db.query(Message).filter(Message.id == task.message_id).first()

        # Use AI to evaluate context
        ai_processor = AIProcessor()
        evaluation = ai_processor.evaluate_reminder_context({
            "task_title": task.title,
            "task_created_at": task.created_at.isoformat(),
            "reminder_context": task.reminder_context,
            "last_reminded_at": task.last_reminded_at.isoformat() if task.last_reminded_at else "Never",
            "reminder_count": task.reminder_count,
            "message_subject": message.subject if message else "",
            "message_sender": message.sender if message else "",
            "current_time": datetime.now(timezone.utc).isoformat()
        })

        if evaluation.get("should_remind"):
            # Send reminder
            logger.info(f"Sending reminder for task {task_record_id}: {evaluation.get('reason')}")

            # Create reminder record
            reminder = TaskReminder(
                task_id=task_record_id,
                reminder_type="scheduled",
                delivered=True
            )
            db.add(reminder)

            # Update task
            task.last_reminded_at = datetime.now(timezone.utc)
            task.reminder_count += 1

            db.commit()

            # Emit reminder_due event (for notification handlers)
            enqueue_task(
                task_type="emit_event",
                payload={
                    "event_name": "reminder_due",
                    "event_payload": {
                        "task_id": task_record_id,
                        "message": evaluation.get("suggested_message"),
                        "task_title": task.title
                    }
                },
                correlation_id=correlation_id,
                db=db
            )

            logger.info(f"Reminder sent for task {task_record_id}")
        else:
            # Don't send, reschedule if needed
            logger.info(f"Not sending reminder for task {task_record_id}: {evaluation.get('reason')}")

            if evaluation.get("reschedule_for"):
                try:
                    reschedule_time = datetime.fromisoformat(evaluation.get("reschedule_for").replace('Z', '+00:00'))
                    enqueue_task(
                        task_type="evaluate_reminder",
                        payload={"task_id": task_record_id},
                        scheduled_for=reschedule_time,
                        correlation_id=correlation_id,
                        db=db
                    )
                    logger.info(f"Rescheduled reminder for task {task_record_id} to {reschedule_time}")
                except Exception as e:
                    logger.error(f"Failed to reschedule task {task_record_id}: {e}")

    except Exception as e:
        logger.error(f"Failed to evaluate reminder for task {task_record_id}: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


def get_next_cleanup_time() -> datetime:
    """Calculate next 2 AM UTC for nightly cleanup job"""
    now = datetime.now(timezone.utc)
    tomorrow = now.date() + timedelta(days=1)
    return datetime.combine(tomorrow, time(2, 0), tzinfo=timezone.utc)


async def handle_data_cleanup(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'data_cleanup' tasks

    Runs nightly to:
    1. Delete raw email bodies older than 30 days (content expiration)
    2. Hard delete messages where source_deleted AND no open tasks AND past retention

    This is the main data lifecycle cleanup job.
    """
    from app.models import Message, Task
    from app.database import SessionLocal
    from app.queue import enqueue_task

    RETENTION_DAYS = 30

    db = SessionLocal()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

        # Step 1: Expire content for messages older than retention period
        expired_count = 0
        messages_to_expire = db.query(Message).filter(
            Message.content_expired == False,
            Message.received_at < cutoff_date
        ).all()

        for msg in messages_to_expire:
            msg.body = None  # Clear the body
            msg.content_expired = True
            expired_count += 1

        if expired_count > 0:
            db.commit()
            logger.info(f"Expired content for {expired_count} messages older than {RETENTION_DAYS} days")

        # Step 2: Hard delete messages meeting all criteria:
        # - source_deleted = True (deleted from Gmail)
        # - past retention period
        # - no open tasks
        deleted_count = 0
        messages_to_delete = db.query(Message).filter(
            Message.source_deleted == True,
            Message.received_at < cutoff_date
        ).all()

        for msg in messages_to_delete:
            # Check for open tasks (pending_approval, approved, snoozed)
            open_tasks = db.query(Task).filter(
                Task.message_id == msg.id,
                Task.status.in_(["pending_approval", "approved", "snoozed"])
            ).count()

            if open_tasks == 0:
                # Safe to hard delete
                # Note: Related records (tasks, scheduling suggestions) will be cascade deleted
                db.delete(msg)
                deleted_count += 1

        if deleted_count > 0:
            db.commit()
            logger.info(f"Hard deleted {deleted_count} source-deleted messages with no open tasks")

        # Step 3: Reschedule for next night
        next_run = get_next_cleanup_time()
        enqueue_task(
            task_type="data_cleanup",
            payload={},
            scheduled_for=next_run,
            db=db
        )
        logger.info(f"Data cleanup complete. Next run scheduled for {next_run}")

    except Exception as e:
        db.rollback()
        logger.error(f"Data cleanup failed: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


# Map task types to handlers
TASK_HANDLERS = {
    "emit_event": handle_emit_event,
    "send_notification": handle_send_notification,
    "trigger_agent": handle_trigger_agent,
    "evaluate_reminder": handle_evaluate_reminder,
    "data_cleanup": handle_data_cleanup,
}


def run_worker(poll_interval: int = 2):
    """
    Run the email assistant worker

    Args:
        poll_interval: Seconds between polls (default: 2)
    """
    worker = Worker(
        queue_service=queue_service,
        handlers=TASK_HANDLERS,
        poll_interval=poll_interval
    )

    worker.run()


if __name__ == "__main__":
    # Import handlers to register them with event system
    import app.handlers

    run_worker()

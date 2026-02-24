"""
Email Assistant Worker - App-specific task handlers

This worker is specific to the email assistant.
It uses the generic core/queue worker with email-specific handlers.

Run with:
    python -m app.worker
"""
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta, time, timezone
from fastapi import BackgroundTasks

from core.events import emit_event
from core.queue import Worker, BatchWorker
from app.jobs.queue import queue_service
from app.jobs.trial_warnings import handle_check_trial_expirations, get_next_trial_check_time
from app.jobs.webhook_health import handle_check_webhook_health, get_next_webhook_health_check_time
from app.handlers.vault_handlers import handle_vault_ingest, handle_vault_proposal_cleanup
from app.infra.config import get_settings
from sqlalchemy import text

logger = logging.getLogger(__name__)
USER_TIMEOUT_MESSAGE = "I couldn't finish that in time. Please send it again."
USER_RETRY_MESSAGE = "I hit a temporary issue handling that. Please try again."


# =============================================================================
# Batch Handlers (for user-isolated LLM processing)
# =============================================================================

async def handle_process_email_batch(user_id: str, tasks: List[Dict[str, Any]]):
    """
    Batch handler for processing multiple emails for a single user.

    This handler:
    1. Receives all pending email tasks for ONE user
    2. Processes them using the message_processor module
    3. Leverages shared LLM provider (no reinitialization)

    Security: Each message is verified to belong to the claimed user_id.
    This prevents cross-user data leakage if queue service has bugs.

    The actual processing logic is in app.message_processor, making it
    reusable across channels (email, Slack, WhatsApp).
    """
    from app.processors.message import process_messages_batch
    from app.infra.database import SessionLocal
    from app.data.models import UserSettings, Message
    from app.services.credits import check_credits_available

    # Require user_id for RLS context
    if not user_id:
        raise ValueError("handle_process_email_batch: user_id is required for RLS context")

    if not tasks:
        return

    # Check if user has credits available before processing
    db_check = SessionLocal()
    try:
        db_check.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
        settings = db_check.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if settings:
            can_proceed, _ = check_credits_available(settings)
            if not can_proceed:
                logger.info(f"Skipping email batch for user {user_id}: credits exhausted")
                return
    finally:
        db_check.close()

    logger.info(f"Processing batch of {len(tasks)} emails for user {user_id}")

    # Create session and set RLS context
    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        # Extract and VERIFY message IDs belong to this user (security)
        candidate_ids = []
        for task in tasks:
            message_id = task["payload"].get("message_id")
            if message_id:
                candidate_ids.append(message_id)
            else:
                logger.warning(f"Task {task['task_id']} missing message_id in payload")

        if not candidate_ids:
            logger.warning(f"No valid message IDs to process for user {user_id}")
            return

        # Verify ownership and skip already-processed messages (idempotency)
        # This prevents cross-user data leakage and duplicate processing on retries
        verified_messages = db.query(Message.id).filter(
            Message.id.in_(candidate_ids),
            Message.user_id == user_id,  # Security: explicit ownership check
            Message.processed == False  # Idempotency: skip already processed
        ).all()
        message_ids = [m.id for m in verified_messages]

        # Log if any messages were skipped (could be already processed or wrong user)
        skipped_count = len(candidate_ids) - len(message_ids)
        if skipped_count > 0:
            logger.info(
                f"Skipped {skipped_count} messages for user {user_id} "
                f"(already processed or ownership mismatch)"
            )

        if not message_ids:
            logger.warning(f"No verified message IDs to process for user {user_id}")
            return

        # Get correlation_id from first task
        correlation_id = tasks[0].get("correlation_id") if tasks else None

        # Process using the reusable message processor
        results = process_messages_batch(message_ids, db=db, user_id=user_id, correlation_id=correlation_id)
        logger.info(f"Batch complete: processed {len(results)} emails for user {user_id}")
    except Exception as e:
        logger.error(f"Batch processing failed for user {user_id}: {e}", exc_info=True)
        raise
    finally:
        db.close()


# Batch handlers map
BATCH_HANDLERS = {
    "process_email": handle_process_email_batch,
}


async def handle_process_email(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'process_email' tasks.

    Processes a single email through the message processor.
    """
    message_id = payload.get("message_id")
    if not message_id:
        logger.warning(f"process_email task (id={task_id}) missing message_id in payload")
        return

    # Require user_id for RLS context
    user_id = payload.get("user_id")
    if not user_id:
        raise ValueError(f"Task {task_id}: user_id is required for RLS context")

    # Wrap as batch task format and delegate to batch handler
    batch_task = {
        "task_id": task_id,
        "payload": payload,
        "correlation_id": correlation_id
    }

    await handle_process_email_batch(user_id, [batch_task])
    logger.info(f"Processed email: message_id={message_id}")


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
    Handler for 'send_notification' tasks.

    Creates an in-app notification and optionally sends push.
    Payload should include: user_id, title, body, category, priority, target_type, target_id
    """
    from app.services.notification import NotificationService

    user_id = payload.get("user_id")
    if not user_id:
        logger.warning(f"[{correlation_id}] send_notification task missing user_id")
        return

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        service = NotificationService(db, user_id)
        service.create_notification(
            title=payload.get("title", "Notification"),
            body=payload.get("body"),
            category=payload.get("category", "system"),
            priority=payload.get("priority", "normal"),
            target_type=payload.get("target_type"),
            target_id=payload.get("target_id"),
        )
        logger.info(f"[{correlation_id}] Notification created for user {user_id}")
    except Exception as e:
        logger.error(f"[{correlation_id}] Failed to create notification: {e}", exc_info=True)
        raise
    finally:
        db.close()


async def handle_send_push_notification(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'send_push_notification' tasks.

    Sends push notification to user devices via Expo Push API.
    Raises on failure to trigger retry via task queue.
    """
    from app.services.notification import send_push_for_notification
    from app.infra.database import SessionLocal

    notification_id = payload.get("notification_id")
    user_id = payload.get("user_id")

    if not notification_id or not user_id:
        logger.warning(f"[{correlation_id}] send_push_notification missing notification_id or user_id")
        return

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        send_push_for_notification(notification_id, user_id, db)
        logger.info(f"[{correlation_id}] Push notification {notification_id} delivered")
    except Exception as e:
        logger.error(f"[{correlation_id}] Push notification {notification_id} failed: {e}", exc_info=True)
        # Record error on notification so it's visible beyond logs
        try:
            from app.data.models import Notification
            notification = db.query(Notification).filter(
                Notification.id == notification_id
            ).first()
            if notification:
                notification.push_error = str(e)
                db.commit()
        except Exception:
            db.rollback()
        raise  # Re-raise for retry
    finally:
        db.close()


async def handle_trigger_agent(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'trigger_agent' tasks

    Triggers the orchestrator to evaluate and take autonomous actions.
    """
    from app.agents.orchestrator import AssistantOrchestrator
    from app.infra.database import SessionLocal

    # Extract user_id from payload for RLS context
    user_id = payload.get("user_id") or payload.get("event_payload", {}).get("user_id")

    # Require user_id for RLS context
    if not user_id:
        raise ValueError(f"Task {task_id}: user_id is required for RLS context")

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

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

        # Process the event (pass db and user_id for RLS)
        result = orchestrator.process_event(
            event_type=event_type,
            event_payload=event_payload,
            correlation_id=correlation_id,
            db=db,
            user_id=user_id
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
    finally:
        db.close()


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
    from app.data.models import Task, Message, UserSettings
    from app.infra.database import SessionLocal
    from app.processors.ai import AIProcessor
    from app.jobs.queue import enqueue_task

    # Extract user_id from payload for RLS context
    user_id = payload.get("user_id")

    db = SessionLocal()

    try:
        task_record_id = payload.get("task_id")

        # If user_id is missing from payload, look it up from the task directly
        if not user_id:
            # Use a superuser-level query to bootstrap (no RLS context yet)
            tmp_task = db.query(Task).filter(Task.id == task_record_id).first()
            if tmp_task and tmp_task.user_id:
                user_id = tmp_task.user_id
                logger.info(f"Resolved user_id={user_id} from task {task_record_id} (missing from payload)")
            else:
                raise ValueError(f"Task {task_id}: user_id missing from payload and task {task_record_id}")

        db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

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
                payload={"task_id": task_record_id, "user_id": user_id},
                scheduled_for=task.snoozed_until,
                db=db
            )
            return

        # Get user settings for reminder limits (filtered by user_id)
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first() if user_id else None
        if not settings:
            logger.warning(f"No UserSettings for user_id={user_id}, using defaults")
            reminder_preferences = {}
        else:
            reminder_preferences = settings.reminder_preferences or {}

        # Check frequency limits
        if task.last_reminded_at:
            hours_since_last = (datetime.now(timezone.utc) - task.last_reminded_at).total_seconds() / 3600
            if hours_since_last < 24:  # Don't remind more than once per day
                logger.info(f"Task {task_record_id} reminded {hours_since_last:.1f}h ago, too soon")
                # Reschedule for tomorrow
                enqueue_task(
                    task_type="evaluate_reminder",
                    payload={"task_id": task_record_id, "user_id": user_id},
                    scheduled_for=datetime.now(timezone.utc) + timedelta(days=1),
                    db=db
                )
                return

        # Check quiet hours
        if is_quiet_hours(reminder_preferences):
            logger.info(f"In quiet hours, rescheduling reminder for task {task_record_id}")
            next_available = get_next_available_time(reminder_preferences)
            enqueue_task(
                task_type="evaluate_reminder",
                payload={"task_id": task_record_id, "user_id": user_id},
                scheduled_for=next_available,
                db=db
            )
            return

        # Get source message
        message = db.query(Message).filter(Message.id == task.message_id).first()

        # Use AI to evaluate context
        from app.agents.modules.follow_up import FollowUpModule
        from app.services.reminder import ReminderService
        follow_up_module = FollowUpModule()
        reminder_service = ReminderService(db=db, user_id=user_id)
        
        evaluation = follow_up_module.evaluate_reminder_context({
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
            logger.info(f"Sending reminder for task {task_record_id}: {evaluation.get('reason')}")

            # Record audit row + update task fields atomically via service
            reminder_service.record_reminder(task, reminder_type="scheduled", channel="push")

            db.commit()

            # Emit reminder_due event (for notification handlers)
            enqueue_task(
                task_type="emit_event",
                payload={
                    "user_id": user_id,
                    "event_name": "reminder_due",
                    "event_payload": {
                        "task_id": task_record_id,
                        "user_id": user_id,
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
                        payload={"task_id": task_record_id, "user_id": user_id},
                        scheduled_for=reschedule_time,
                        correlation_id=correlation_id,
                        db=db
                    )
                    logger.info(f"Rescheduled reminder for task {task_record_id} to {reschedule_time}")
                except Exception as e:
                    logger.error(f"Failed to reschedule task {task_record_id}: {e}")

    except Exception as e:
        logger.error(f"Failed to evaluate reminder for task {payload.get('task_id')}: {str(e)}", exc_info=True)
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
    from app.data.models import Message, Task
    from app.infra.database import SessionLocal
    from app.jobs.queue import enqueue_task

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


def get_next_chat_cleanup_time() -> datetime:
    """Calculate next hourly chat cleanup time (15 minutes past each hour)."""
    now = datetime.now(timezone.utc)
    # Next hour, 15 minutes in
    next_hour = now.replace(minute=15, second=0, microsecond=0)
    if next_hour <= now:
        next_hour = next_hour + timedelta(hours=1)
    return next_hour


async def handle_chat_cleanup(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'chat_cleanup' tasks

    Runs hourly to:
    1. Delete reflection sessions older than 24 hours
    2. Delete command sessions older than 30 days
    3. Expire pending actions on deleted sessions
    """
    from app.chat import ChatService
    from app.infra.database import SessionLocal
    from app.jobs.queue import enqueue_task

    db = SessionLocal()
    try:
        # ChatService cleanup doesn't need user_id for bulk cleanup
        service = ChatService(db, user_id=None)
        result = service.cleanup_expired_sessions()
        
        reflection_deleted = result.get("reflection_deleted", 0)
        command_deleted = result.get("command_deleted", 0)
        
        if reflection_deleted > 0 or command_deleted > 0:
            logger.info(
                f"Chat cleanup: deleted {reflection_deleted} reflection sessions, "
                f"{command_deleted} command sessions"
            )

        # Reschedule for next hour
        next_run = get_next_chat_cleanup_time()
        enqueue_task(
            task_type="chat_cleanup",
            payload={},
            scheduled_for=next_run,
            db=db
        )
        logger.info(f"Chat cleanup complete. Next run scheduled for {next_run}")

    except Exception as e:
        db.rollback()
        logger.error(f"Chat cleanup failed: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


async def handle_generate_briefing(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'generate_briefing' tasks

    Generates a meeting briefing for an upcoming calendar event.
    Scheduled to run 1-2 hours before the meeting.
    """
    from app.data.models import CalendarEvent
    from app.infra.database import SessionLocal
    from app.services.briefing import BriefingService

    # Extract user_id from payload for RLS context
    user_id = payload.get("user_id")

    # Require user_id for RLS context
    if not user_id:
        raise ValueError(f"Task {task_id}: user_id is required for RLS context")

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        event_id = payload.get("event_id")
        event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()

        if not event:
            logger.warning(f"Event {event_id} not found for briefing generation")
            return

        # Skip if already generated
        if event.briefing_generated_at:
            logger.info(f"Briefing already generated for event {event_id}")
            return

        # Skip if event already passed
        if event.start_time < datetime.now(timezone.utc):
            logger.info(f"Event {event_id} already passed, skipping briefing")
            return

        # Generate briefing
        service = BriefingService(db)
        briefing = service.generate_briefing(event)

        logger.info(
            f"Generated briefing for event {event_id}: {event.title}",
            extra={"task_id": task_id, "correlation_id": correlation_id}
        )

        # Emit event for UI notification
        from app.jobs.queue import enqueue_task
        enqueue_task(
            task_type="emit_event",
            payload={
                "user_id": user_id,
                "event_name": "briefing_ready",
                "event_payload": {
                    "event_id": event_id,
                    "title": event.title,
                    "start_time": event.start_time.isoformat(),
                    "message_count": briefing.get("message_count", 0),
                    "task_count": briefing.get("task_count", 0),
                    "user_id": user_id,
                }
            },
            correlation_id=correlation_id,
            db=db
        )

    except Exception as e:
        logger.error(f"Failed to generate briefing for event {payload.get('event_id')}: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


async def handle_email_backfill(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'email_backfill' tasks.

    Supports two modes:
    - "today": Fetches emails from midnight (user's timezone) to now
    - Legacy: Fetches emails from last N hours (hours_back parameter)

    Saves to DB, applies email filters, and queues for AI processing.
    Marks initial_sync_completed = True on success.
    """
    from app.data.models import GmailAccount, Message
    from app.infra.database import SessionLocal
    from app.integrations.gmail import GmailClient
    from app.security.encryption import encrypt_body
    from app.services.email_filter import EmailFilterService, FilterAction
    from app.jobs.queue import enqueue_task
    from zoneinfo import ZoneInfo

    user_id = payload.get("user_id")
    sync_mode = payload.get("sync_mode", "hours")  # "today" or "hours" (legacy)
    user_timezone = payload.get("user_timezone", "UTC")
    hours_back = payload.get("hours_back", 24)

    if not user_id:
        raise ValueError(f"Task {task_id}: user_id is required")

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        # Build Gmail query based on sync mode
        if sync_mode == "today":
            # Calculate midnight in user's timezone
            try:
                user_tz = ZoneInfo(user_timezone)
            except Exception:
                user_tz = timezone.utc
                logger.warning(f"Invalid timezone '{user_timezone}', falling back to UTC")

            now_user = datetime.now(user_tz)
            midnight_user = now_user.replace(hour=0, minute=0, second=0, microsecond=0)

            # Gmail 'after:' query uses epoch seconds
            midnight_epoch = int(midnight_user.timestamp())
            query = f"after:{midnight_epoch}"

            logger.info(
                f"Starting email backfill for user {user_id} "
                f"(today's emails from {midnight_user.isoformat()} in {user_timezone})"
            )
        else:
            # Legacy mode: hours_back
            query = f"newer_than:{hours_back}h"
            logger.info(f"Starting email backfill for user {user_id} (last {hours_back}h)")

        client = GmailClient(db=db, user_id=user_id)
        if not client.load_credentials():
            raise RuntimeError(f"Failed to load Gmail credentials for user {user_id}")

        # Fetch messages
        messages = client.get_messages(max_results=500, query=query)

        logger.info(f"Fetched {len(messages)} messages for backfill")

        # Initialize filter service
        filter_service = EmailFilterService(db=db, user_id=user_id)

        synced_count = 0
        filtered_count = 0
        message_ids = []  # Messages to process with AI

        for msg_data in messages:
            # Check if message already exists
            existing = db.query(Message).filter(
                Message.message_id == msg_data['message_id']
            ).first()

            if existing:
                continue

            # Apply email filters
            gmail_labels = msg_data.get('gmail_labels', [])
            headers = msg_data.get('headers', {})
            body_preview = msg_data.get('body', '')[:200] if msg_data.get('body') else None
            filter_result = filter_service.apply_filters(
                gmail_labels=gmail_labels,
                sender_email=msg_data['sender'],
                subject=msg_data['subject'],
                headers=headers,
                body_preview=body_preview,
                thread_id=msg_data.get('thread_id'),
            )

            # Skip entirely if filter says so
            if filter_result.action == FilterAction.SKIP:
                continue

            # Save message to database
            attachments = msg_data.get('attachments') or []
            message = Message(
                message_id=msg_data['message_id'],
                thread_id=msg_data['thread_id'],
                user_id=user_id,
                subject=msg_data['subject'],
                sender=msg_data['sender'],
                recipient=msg_data['recipient'],
                body=encrypt_body(msg_data['body']),
                body_encrypted=True,
                received_at=msg_data['received_at'],
                processed=filter_result.action == FilterAction.METADATA_ONLY,
                has_attachments=bool(attachments),
                attachments=attachments,
            )

            db.add(message)
            db.flush()
            synced_count += 1

            # Only queue for AI processing if filter allows
            if filter_result.action == FilterAction.PROCESS:
                message_ids.append(message.id)
            else:
                filtered_count += 1

        db.commit()

        # Queue processing tasks for messages that passed the filter
        for msg_id in message_ids:
            enqueue_task(
                task_type="process_email",
                payload={"message_id": msg_id, "user_id": user_id},
                correlation_id=correlation_id,
                db=db
            )

        # Mark sync as completed
        gmail_account = db.query(GmailAccount).filter(GmailAccount.user_id == user_id).first()
        if gmail_account:
            was_completed = gmail_account.initial_sync_completed
            if not was_completed:
                gmail_account.initial_sync_completed = True
                logger.info(f"Marked initial_sync_completed=True for user {user_id}")
            gmail_account.last_sync = datetime.now(timezone.utc)
            db.commit()

            if not was_completed:
                try:
                    from app.services.notification import NotificationService
                    notif_service = NotificationService(db, user_id)
                    notif_service.create_notification(
                        title="Initial sync complete",
                        body="Today's processed emails are ready in your Inbox.",
                        category="system",
                        priority="normal",
                        send_push=False,
                    )
                    from app.data.models import UserSettings
                    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
                    if user_settings and not user_settings.onboarding_completed:
                        user_settings.onboarding_completed = True
                        db.commit()
                except Exception as e:
                    logger.warning(f"Failed to create initial sync notification for user {user_id}: {e}")

        logger.info(
            f"Email backfill complete for user {user_id}: "
            f"{synced_count} synced, {len(message_ids)} to process, {filtered_count} filtered"
        )

    except Exception as e:
        logger.error(f"Email backfill failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


# =============================================================================
# Digest Handlers
# =============================================================================

def get_next_digest_time(digest_type: str, preferences: Dict, user_timezone: str = "UTC") -> datetime:
    """
    Calculate next scheduled time for a digest type in user's timezone.
    
    Args:
        digest_type: morning_briefing | end_of_day | weekly_review
        preferences: User's digest preferences
        user_timezone: IANA timezone string (e.g., "Africa/Johannesburg")
        
    Returns:
        Next scheduled datetime (UTC)
    """
    from zoneinfo import ZoneInfo
    
    config = preferences.get(digest_type, {})
    
    if not config.get("enabled", False):
        return None
    
    # Parse user's timezone
    try:
        user_tz = ZoneInfo(user_timezone)
    except Exception:
        user_tz = timezone.utc
    
    # Get current time in user's timezone
    now_utc = datetime.now(timezone.utc)
    now_user = now_utc.astimezone(user_tz)
    
    time_str = config.get("time", "08:00")
    hour, minute = map(int, time_str.split(":"))
    target_time = time(hour, minute)
    
    if digest_type == "weekly_review":
        # Find next occurrence of specified day (in user's timezone)
        day_name = config.get("day", "monday").lower()
        days = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        target_day = days.get(day_name, 0)
        days_ahead = target_day - now_user.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_date = now_user.date() + timedelta(days=days_ahead)
    else:
        # Daily digest - next occurrence of time (in user's timezone)
        next_date = now_user.date()
        if now_user.time() >= target_time:
            next_date += timedelta(days=1)
    
    # Create datetime in user's timezone, then convert to UTC
    local_dt = datetime.combine(next_date, target_time, tzinfo=user_tz)
    return local_dt.astimezone(timezone.utc)


async def handle_generate_digest(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'generate_digest' tasks.

    Generates a scheduled digest and queues it for delivery.
    Self-reschedules for next occurrence.
    """
    from app.data.models import UserSettings, Digest
    from app.infra.database import SessionLocal
    from app.services.digest import DigestService
    from app.jobs.queue import enqueue_task

    # Extract user_id from payload for RLS context
    user_id = payload.get("user_id")

    # Require user_id for RLS context
    if not user_id:
        raise ValueError(f"Task {task_id}: user_id is required for RLS context")

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        user_email = payload.get("user_email")
        digest_type = payload.get("digest_type")
        
        # Get user settings
        settings = db.query(UserSettings).filter(
            UserSettings.user_email == user_email
        ).first()
        
        if not settings:
            logger.warning(f"No settings found for user {user_email}")
            return
        
        prefs = settings.digest_preferences or {}
        
        # Check if this digest type is enabled
        if not prefs.get("enabled") or not prefs.get(digest_type, {}).get("enabled"):
            logger.info(f"Digest {digest_type} disabled for user {user_email}")
            # Still reschedule to check next time
            next_time = get_next_digest_time(digest_type, prefs, settings.default_timezone)
            if next_time:
                enqueue_task(
                    task_type="generate_digest",
                    payload={"user_email": user_email, "digest_type": digest_type, "user_id": user_id},
                    scheduled_for=next_time,
                    db=db
                )
            return
        
        # Check quiet hours
        if is_quiet_hours(settings.reminder_preferences or {}):
            next_available = get_next_available_time(settings.reminder_preferences or {})
            enqueue_task(
                task_type="generate_digest",
                payload={"user_email": user_email, "digest_type": digest_type, "user_id": user_id},
                scheduled_for=next_available,
                db=db
            )
            logger.info(f"Digest delayed until {next_available} (quiet hours)")
            return
        
        # Generate digest content
        service = DigestService(db, user_email)
        
        if digest_type == "morning_briefing":
            content = service.generate_morning_briefing()
        elif digest_type == "end_of_day":
            content = service.generate_end_of_day()
        elif digest_type == "weekly_review":
            content = service.generate_weekly_review()
        else:
            logger.error(f"Unknown digest type: {digest_type}")
            return
        
        # Calculate counts from content
        stats = content.get("stats", {})
        task_count = stats.get("urgent_count", 0) + stats.get("due_today_count", 0)
        thread_count = stats.get("threads_needing_reply_count", 0)
        event_count = stats.get("events_count", 0)
        
        # Create digest record
        digest = Digest(
            user_email=user_email,
            digest_type=digest_type,
            period_start=datetime.fromisoformat(content["period"]["start"]) if "period" in content else None,
            period_end=datetime.fromisoformat(content["period"]["end"]) if "period" in content else None,
            content=content,
            delivery_channel=prefs.get("delivery_channel", "email"),
            task_count=task_count,
            thread_count=thread_count,
            event_count=event_count
        )
        db.add(digest)
        db.commit()
        
        # Queue delivery
        enqueue_task(
            task_type="deliver_digest",
            payload={"digest_id": digest.id, "user_id": user_id},
            correlation_id=correlation_id,
            db=db
        )
        
        # Schedule next occurrence
        next_time = get_next_digest_time(digest_type, prefs, settings.default_timezone)
        if next_time:
            enqueue_task(
                task_type="generate_digest",
                payload={"user_email": user_email, "digest_type": digest_type, "user_id": user_id},
                scheduled_for=next_time,
                db=db
            )
            logger.info(f"Next {digest_type} scheduled for {next_time}")
        
        logger.info(f"Generated {digest_type} digest for {user_email}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to generate digest: {e}", exc_info=True)
        raise
    finally:
        db.close()


async def handle_deliver_digest(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'deliver_digest' tasks.

    Delivers a generated digest via the configured channel.
    """
    from app.data.models import Digest
    from app.infra.database import SessionLocal
    from app.jobs.queue import enqueue_task

    # Extract user_id from payload for RLS context
    user_id = payload.get("user_id")

    # Require user_id for RLS context
    if not user_id:
        raise ValueError(f"Task {task_id}: user_id is required for RLS context")

    digest = None
    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        digest_id = payload.get("digest_id")
        digest = db.query(Digest).filter(Digest.id == digest_id).first()
        
        if not digest:
            logger.warning(f"Digest {digest_id} not found")
            return
        
        channel = digest.delivery_channel
        
        # Render content for channel
        if channel == "email":
            from app.services.digest_templates import render_digest_email
            from app.integrations.gmail import GmailClient
            
            # Render HTML body
            html_body = render_digest_email(
                digest_type=digest.digest_type,
                content=digest.content,
                user_email=digest.user_email
            )
            
            # Initialize Gmail client
            gmail_client = GmailClient(db=db, user_id=user_id)
            if not gmail_client.load_credentials():
                raise Exception(f"Failed to load Gmail credentials for user {user_id}")
            
            # Send email
            subject = f"Your {digest.digest_type.replace('_', ' ').title()} | Teeks"
            gmail_client.send_message(
                to=digest.user_email,
                subject=subject,
                body=html_body,
                html=True
            )
            
            logger.info(f"Sent email digest to {digest.user_email}")

        elif channel == "telegram":
            # TODO: Send via Telegram bot
            logger.info(f"Would send Telegram digest to {digest.user_email}")
        elif channel == "push":
            from app.services.notification import NotificationService

            title_map = {
                "morning_briefing": "Your Morning Briefing is ready",
                "end_of_day": "Your End of Day Summary is ready",
                "weekly_review": "Your Weekly Review is ready",
            }
            category_map = {
                "morning_briefing": "briefing_ready",
                "end_of_day": "digest_ready",
                "weekly_review": "digest_ready",
            }

            notif_service = NotificationService(db, user_id)
            notif_service.create_notification(
                title=title_map.get(digest.digest_type, "Your digest is ready"),
                body=f"Tap to view your {digest.digest_type.replace('_', ' ')}.",
                category=category_map.get(digest.digest_type, "digest_ready"),
                priority="high",
                target_type="digest",
                target_id=str(digest.id),
            )

            logger.info(f"Push notification sent for {digest.digest_type} to user {user_id}")
        
        # Update delivery status
        digest.delivery_status = "sent"
        digest.delivered_at = datetime.now(timezone.utc)
        db.commit()
        
        # Emit event for UI
        enqueue_task(
            task_type="emit_event",
            payload={
                "user_id": user_id,
                "event_name": "digest_delivered",
                "event_payload": {
                    "digest_id": digest.id,
                    "digest_type": digest.digest_type,
                    "user_email": digest.user_email,
                    "user_id": user_id,
                }
            },
            correlation_id=correlation_id,
            db=db
        )
        
        logger.info(f"Delivered {digest.digest_type} digest to {digest.user_email}")
        
    except Exception as e:
        if digest:
            digest.delivery_status = "failed"
            digest.delivery_error = str(e)
            db.commit()
        logger.error(f"Failed to deliver digest: {e}", exc_info=True)
        raise
    finally:
        db.close()


def schedule_digest_jobs_if_needed(db):
    """
    Schedule digest jobs for all users with enabled digests.

    Called on startup and when preferences change.
    Ensures exactly one pending job per (user, digest_type) combination.
    """
    from app.data.models import UserSettings, TaskQueue
    from app.jobs.queue import enqueue_task

    # Query all pending digest jobs once (O(1) queries, not O(users * types))
    pending_jobs = db.query(TaskQueue).filter(
        TaskQueue.task_type == "generate_digest",
        TaskQueue.status == "pending"
    ).all()

    # Build set of already-scheduled (user_email, digest_type) pairs
    scheduled = {
        (job.payload.get("user_email"), job.payload.get("digest_type"))
        for job in pending_jobs
    }

    settings_list = db.query(UserSettings).all()

    for settings in settings_list:
        prefs = settings.digest_preferences or {}
        if not prefs.get("enabled"):
            continue

        for digest_type in ["morning_briefing", "end_of_day", "weekly_review"]:
            if not prefs.get(digest_type, {}).get("enabled"):
                continue

            # Skip if already scheduled for this user + digest_type
            if (settings.user_email, digest_type) in scheduled:
                logger.debug(f"Digest {digest_type} already scheduled for {settings.user_email}")
                continue

            next_time = get_next_digest_time(digest_type, prefs, settings.default_timezone)
            if next_time:
                enqueue_task(
                    task_type="generate_digest",
                    payload={"user_email": settings.user_email, "digest_type": digest_type},
                    scheduled_for=next_time,
                    db=db
                )
                logger.info(f"Scheduled {digest_type} for {settings.user_email} at {next_time}")


async def handle_process_chat_message(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'process_chat_message' tasks.

    Processes a chat message asynchronously when:
    - Tool intent was detected (likely needs tools)
    - Sync processing timed out

    Updates the placeholder message with the actual response.
    """
    from app.data.models import ChatSession, ChatMessage, ChatPendingAction, UserSettings
    from app.chat.orchestrator import ChatOrchestrator
    from app.infra.database import SessionLocal
    import uuid

    job_id = payload.get("job_id")
    session_id = payload.get("session_id")
    user_id = payload.get("user_id")
    content = payload.get("content")
    mention_context = payload.get("mention_context") or {}
    assistant_message_id = payload.get("assistant_message_id")

    if not all([job_id, session_id, user_id, content, assistant_message_id]):
        logger.error(f"process_chat_message task (id={task_id}) missing required fields")
        return

    logger.info(f"Processing async chat message: job_id={job_id}, session_id={session_id}")

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        # Get session
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        ).first()

        if not session:
            logger.error(f"Session {session_id} not found")
            _update_message_failed(db, assistant_message_id, "Session not found")
            return

        # Idempotency check: skip if already processed (retry safety)
        existing_msg = db.query(ChatMessage).filter(
            ChatMessage.id == assistant_message_id
        ).first()
        if existing_msg and existing_msg.message_metadata:
            existing_status = existing_msg.message_metadata.get("status")
            if existing_status == "complete":
                logger.info(f"Chat message {assistant_message_id} already processed, skipping (idempotent)")
                return

        # Get user's assistant name and first name for personalization
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()
        assistant_name = user_settings.assistant_name if user_settings else "Teeks"
        session_state = session.state or {}
        user_name = session_state.get("user_first_name")

        # Process through orchestrator
        orchestrator = ChatOrchestrator(
            db, user_id,
            assistant_name=assistant_name,
            user_name=user_name,
        )
        result = await orchestrator.process_message(session, content, mention_context=mention_context)

        # Get the placeholder message - verify it belongs to this session
        assistant_msg = db.query(ChatMessage).filter(
            ChatMessage.id == assistant_message_id,
            ChatMessage.session_id == session_id
        ).first()

        if not assistant_msg:
            logger.error(f"Assistant message {assistant_message_id} not found for session {session_id}")
            return

        # Update with actual response
        assistant_msg.content = result.get("response", "")
        assistant_msg.message_metadata = {
            "job_id": job_id,
            "status": "complete",
            "state": result.get("state", {})
        }

        # Create pending actions
        for pa_data in result.get("pending_actions", []):
            pa = ChatPendingAction(
                id=str(uuid.uuid4()),
                session_id=session_id,
                message_id=assistant_msg.id,
                action_type=pa_data["action_type"],
                action_data=pa_data["action_data"],
                status="pending",
                created_at=datetime.now(timezone.utc)
            )
            db.add(pa)

        db.commit()
        logger.info(f"Async chat message complete: job_id={job_id}")

    except Exception as e:
        logger.error(f"Error processing async chat message: {e}", exc_info=True)
        _update_message_failed(db, assistant_message_id, str(e))
    finally:
        db.close()


def _update_message_failed(db, message_id: int, error: str):
    """Update a message to failed status."""
    from app.data.models import ChatMessage

    try:
        msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if msg:
            logger.error(
                "chat_async_message_failed message_id=%s session_id=%s internal_error=%s",
                message_id,
                msg.session_id,
                error,
            )
            user_error = USER_RETRY_MESSAGE
            msg.content = user_error
            msg.message_metadata = {
                **(msg.message_metadata or {}),
                "status": "failed",
                "error": user_error,
                "internal_error": error,
            }
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update message {message_id} as failed: {e}")


def get_next_stuck_chat_cleanup_time() -> datetime:
    """Calculate next cleanup time (every 10 minutes)."""
    now = datetime.now(timezone.utc)
    return now + timedelta(minutes=10)


async def handle_cleanup_stuck_chat_messages(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'cleanup_stuck_chat_messages' tasks.

    Periodically cleans up chat messages stuck in 'processing' state.
    This is a background safety net for messages orphaned by worker crashes.

    Run frequency: every 10 minutes (self-rescheduling)
    Timeout threshold: 5 minutes (longer than TTL-on-read to avoid race conditions)
    """
    from app.data.models import ChatMessage
    from app.infra.database import SessionLocal
    from app.jobs.queue import enqueue_task

    # 5 minutes timeout for background cleanup (longer than 2-min TTL-on-read)
    BACKGROUND_TIMEOUT_MINUTES = 5

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=BACKGROUND_TIMEOUT_MINUTES)

        # Find recent assistant messages that could be stuck
        # Only look at messages created in the last 24 hours to avoid scanning entire table
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        assistant_messages = db.query(ChatMessage).filter(
            ChatMessage.role == "assistant",
            ChatMessage.created_at > recent_cutoff,
            ChatMessage.created_at < cutoff
        ).limit(500).all()

        # Filter status in Python for SQLite compatibility (used in tests)
        expired_count = 0
        for msg in assistant_messages:
            metadata = msg.message_metadata or {}
            if metadata.get("status") == "processing":
                msg.content = USER_TIMEOUT_MESSAGE
                msg.message_metadata = {
                    **metadata,
                    "status": "timeout",
                    "error": USER_TIMEOUT_MESSAGE,
                    "internal_error": "Processing exceeded time limit (background cleanup)",
                    "timed_out_at": datetime.now(timezone.utc).isoformat()
                }
                expired_count += 1

        if expired_count > 0:
            db.commit()
            logger.info(f"[{correlation_id}] Cleaned up {expired_count} stuck chat messages")
        else:
            logger.debug(f"[{correlation_id}] No stuck chat messages found")

        # Self-reschedule for next run
        next_run = get_next_stuck_chat_cleanup_time()
        enqueue_task(
            task_type="cleanup_stuck_chat_messages",
            payload={},
            scheduled_for=next_run,
            db=db
        )
        logger.debug(f"[{correlation_id}] Next stuck chat cleanup scheduled for {next_run}")

    except Exception as e:
        logger.error(f"[{correlation_id}] Error cleaning stuck chat messages: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


async def handle_renew_gmail_watches(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Renew Gmail Pub/Sub watches for all connected accounts.

    Should run daily. Gmail watches expire after 7 days;
    calling watch() again extends them.
    """
    from app.services.gmail_watch import renew_all_watches

    logger.info(f"[{correlation_id}] Renewing Gmail watches")
    result = renew_all_watches()
    logger.info(f"[{correlation_id}] Gmail watch renewal: {result}")

    # Re-schedule for tomorrow
    from datetime import timedelta
    next_run = datetime.utcnow() + timedelta(days=1)
    queue_service.enqueue(
        task_type="renew_gmail_watches",
        payload={},
        scheduled_for=next_run,
    )
    logger.info(f"[{correlation_id}] Next Gmail watch renewal scheduled for {next_run}")


async def handle_renew_calendar_watches(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Renew Google Calendar push notification channels for all users.

    Calendar watches expire after ~7 days. Unlike Gmail, renewal requires
    stopping the old channel (channels().stop()) then creating a new one
    (events().watch()) with a fresh UUID.
    """
    from app.services.calendar_watch import renew_all_watches as renew_calendar_watches

    logger.info(f"[{correlation_id}] Renewing Calendar watches")
    result = renew_calendar_watches()
    logger.info(f"[{correlation_id}] Calendar watch renewal: {result}")

    # Re-schedule for tomorrow
    next_run = datetime.utcnow() + timedelta(days=1)
    queue_service.enqueue(
        task_type="renew_calendar_watches",
        payload={},
        scheduled_for=next_run,
    )
    logger.info(f"[{correlation_id}] Next Calendar watch renewal scheduled for {next_run}")


async def handle_sync_calendar_for_user(task_id: int, task_type: str, payload: Dict[str, Any], correlation_id: str):
    """
    Handler for 'sync_calendar_for_user' tasks.

    Triggered by Google Calendar push notifications (via POST /webhooks/calendar).
    Syncs upcoming events for the affected user and invalidates the calendar cache
    so the next frontend load gets fresh data.
    """
    from app.services.calendar import CalendarService
    from app.infra.database import SessionLocal
    from core.cache import calendar_cache

    user_id = payload.get("user_id")
    if not user_id:
        raise ValueError(f"Task {task_id}: user_id is required")

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        # Invalidate the calendar cache so the next load fetches fresh data
        calendar_cache.invalidate_all(user_id)

        from app.data.models import UserSettings as _UserSettings
        user_settings = db.query(_UserSettings).filter(_UserSettings.user_id == user_id).first()
        chosen = (user_settings.calendar_ids or []) if user_settings else []
        default_cal = (user_settings.default_calendar_id or "primary") if user_settings else "primary"
        calendar_ids = chosen if chosen else [default_cal]

        cal_service = CalendarService(db=db, user_id=user_id)
        await cal_service.sync_upcoming_events(
            days_ahead=14,
            calendar_ids=calendar_ids,
        )
        logger.info(
            f"[{correlation_id}] Calendar synced for user={user_id} (push notification)"
        )
    except Exception as e:
        logger.error(f"[{correlation_id}] Calendar sync failed for user={user_id}: {e}", exc_info=True)
        raise
    finally:
        db.close()


# Map task types to handlers
TASK_HANDLERS = {
    "process_email": handle_process_email,
    "emit_event": handle_emit_event,
    "send_notification": handle_send_notification,
    "send_push_notification": handle_send_push_notification,
    "trigger_agent": handle_trigger_agent,
    "evaluate_reminder": handle_evaluate_reminder,
    "data_cleanup": handle_data_cleanup,
    "cleanup_stuck_chat_messages": handle_cleanup_stuck_chat_messages,
    "chat_cleanup": handle_chat_cleanup,
    "generate_briefing": handle_generate_briefing,
    # DORMANT: "generate_digest": handle_generate_digest,
    # DORMANT: "deliver_digest": handle_deliver_digest,
    "email_backfill": handle_email_backfill,
    "process_chat_message": handle_process_chat_message,
    "renew_gmail_watches": handle_renew_gmail_watches,
    "renew_calendar_watches": handle_renew_calendar_watches,
    "sync_calendar_for_user": handle_sync_calendar_for_user,
    "check_trial_expirations": handle_check_trial_expirations,
    "check_webhook_health": handle_check_webhook_health,
}

if get_settings().PROPOSALS_ENABLED:
    TASK_HANDLERS["vault_ingest"] = handle_vault_ingest
    TASK_HANDLERS["vault_proposal_cleanup"] = handle_vault_proposal_cleanup


def _notify_permanent_failure(task_id: int, task_type: str, payload: dict, error: str, user_id: str):
    """
    Callback for permanent task failures - creates a system notification.

    Only called when all retries are exhausted.
    """
    if not user_id:
        return

    from app.infra.database import SessionLocal
    from app.data.models import Notification

    # Create user-friendly message based on task type
    task_descriptions = {
        "process_email": "Email processing",
        "generate_digest": "Digest generation",
        "deliver_digest": "Digest delivery",
        "email_backfill": "Email sync",
        "process_chat_message": "Chat processing",
    }
    task_desc = task_descriptions.get(task_type, f"Background task ({task_type})")

    db = SessionLocal()
    try:
        notification = Notification(
            user_id=user_id,
            title=f"{task_desc} failed",
            body="We couldn't complete this operation after multiple attempts. Please try again or contact support if the issue persists.",
            category="system",
            priority="normal",
        )
        db.add(notification)
        db.commit()
        logger.info(f"Created failure notification for user {user_id}, task {task_type}")
    except Exception as e:
        logger.error(f"Failed to create failure notification: {e}")
        db.rollback()
    finally:
        db.close()


def schedule_cleanup_jobs_if_needed(db):
    """
    Schedule cleanup jobs if not already pending.

    Called on worker startup to ensure cleanup jobs are running.
    """
    from app.data.models import TaskQueue
    from app.jobs.queue import enqueue_task

    cleanup_jobs = ["cleanup_stuck_chat_messages", "chat_cleanup", "data_cleanup", "check_trial_expirations", "check_webhook_health"]
    if get_settings().PROPOSALS_ENABLED:
        cleanup_jobs.append("vault_proposal_cleanup")

    for task_type in cleanup_jobs:
        existing = db.query(TaskQueue).filter(
            TaskQueue.task_type == task_type,
            TaskQueue.status == "pending"
        ).first()

        if not existing:
            if task_type == "cleanup_stuck_chat_messages":
                next_run = get_next_stuck_chat_cleanup_time()
            elif task_type == "chat_cleanup":
                next_run = get_next_chat_cleanup_time()
            elif task_type == "data_cleanup":
                next_run = get_next_cleanup_time()
            elif task_type == "check_trial_expirations":
                next_run = get_next_trial_check_time()
            elif task_type == "check_webhook_health":
                next_run = get_next_webhook_health_check_time()
            elif task_type == "vault_proposal_cleanup":
                from app.handlers.vault_handlers import get_next_vault_cleanup_time
                next_run = get_next_vault_cleanup_time()
            else:
                continue

            enqueue_task(
                task_type=task_type,
                payload={},
                scheduled_for=next_run,
                db=db
            )
            logger.info(f"Scheduled {task_type} for {next_run}")


def _notify_permanent_failure(task_id: int, task_type: str, payload: Dict[str, Any], error: str, user_id: str):
    """
    Callback fired when a task permanently fails (exhausted all retries).
    Creates an in-app notification + push so the user knows.
    """
    from app.infra.database import SessionLocal
    from app.services.notification import NotificationService

    if not user_id:
        logger.warning(f"Cannot notify permanent failure for task {task_id}: no user_id")
        return

    # Map task types to user-friendly messages
    FAILURE_MESSAGES = {
        "email_backfill": {
            "title": "Initial sync didn't complete",
            "body": "Some earlier emails may be missing, but new emails will continue to appear as they arrive.",
        },
    }

    msg = FAILURE_MESSAGES.get(task_type, {
        "title": "Something went wrong",
        "body": f"A background task ({task_type}) failed after multiple attempts.",
    })

    db = SessionLocal()
    try:
        db.execute(
            text("SELECT set_config('app.current_user_id', :uid, true)"),
            {"uid": user_id},
        )
        svc = NotificationService(db=db, user_id=user_id)
        svc.create_notification(
            title=msg["title"],
            body=msg["body"],
            category="system",
            priority="high",
            send_push=True,
        )
        logger.info(f"Notified user {user_id} of permanent failure for task {task_type} (id={task_id})")
    except Exception as e:
        logger.error(f"Failed to create permanent failure notification: {e}", exc_info=True)
    finally:
        db.close()


def run_worker(poll_interval: int = 2):
    """
    Run the email assistant worker (single-task processing)

    Args:
        poll_interval: Seconds between polls (default: 2)
    """
    from app.infra.database import SessionLocal

    # Ensure cleanup jobs are scheduled on startup
    db = SessionLocal()
    try:
        schedule_cleanup_jobs_if_needed(db)
        db.commit()
    finally:
        db.close()

    worker = Worker(
        queue_service=queue_service,
        handlers=TASK_HANDLERS,
        poll_interval=poll_interval,
        on_permanent_failure=_notify_permanent_failure
    )

    worker.run()


def run_email_batch_worker(poll_interval: int = 2, limit_per_user: int = 30, max_users: int = 5):
    """
    Run the batch worker for user-isolated email processing.

    Groups emails by user and processes them in batches for LLM efficiency.
    No data leakage between users.

    Args:
        poll_interval: Seconds between polls (default: 2)
        limit_per_user: Max emails per user per batch (default: 30)
        max_users: Max users to process per cycle (default: 5)
    """
    from app.infra.database import SessionLocal

    # Ensure cleanup jobs are scheduled on startup
    db = SessionLocal()
    try:
        schedule_cleanup_jobs_if_needed(db)
        db.commit()
    finally:
        db.close()

    worker = BatchWorker(
        queue_service=queue_service,
        handlers=BATCH_HANDLERS,
        single_task_handlers=TASK_HANDLERS,
        poll_interval=poll_interval,
        limit_per_user=limit_per_user,
        max_users=max_users,
        on_permanent_failure=_notify_permanent_failure
    )

    worker.run()


if __name__ == "__main__":
    import app.handlers
    # Use batch worker for efficient LLM batching by user
    run_email_batch_worker()

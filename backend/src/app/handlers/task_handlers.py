"""
Event handlers for task extraction and management
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from core.events import register_handler
from app.database import SessionLocal
from app.models import Message, Task, UserSettings
from app.ai_processor import AIProcessor
from app.queue import enqueue_task

logger = logging.getLogger(__name__)

# Initialize AI processor
ai_processor = AIProcessor()


def calculate_reminder_time(
    reminder_context: Dict[str, Any],
    user_preferences: Dict[str, Any]
) -> datetime:
    """
    Calculate when reminder should be scheduled based on context.

    Args:
        reminder_context: AI-extracted context with type, reference_date, offset_hours
        user_preferences: User's reminder preferences

    Returns:
        datetime when reminder should fire
    """
    if not reminder_context:
        # Default: 24 hours from now
        default_offset = user_preferences.get("default_reminder_offset_hours", 24)
        return datetime.now(timezone.utc) + timedelta(hours=default_offset)

    context_type = reminder_context.get("type")

    if context_type == "deadline":
        # Remind X hours before deadline
        try:
            ref_date_str = reminder_context.get("reference_date")
            ref_date = datetime.fromisoformat(ref_date_str.replace('Z', '+00:00'))
            offset_hours = reminder_context.get("offset_hours", -24)
            return ref_date + timedelta(hours=offset_hours)
        except:
            # Fallback if date parsing fails
            return datetime.now(timezone.utc) + timedelta(hours=24)

    elif context_type == "before_meeting":
        # Remind X hours before meeting
        try:
            meeting_time_str = reminder_context.get("reference_date")
            meeting_time = datetime.fromisoformat(meeting_time_str.replace('Z', '+00:00'))
            offset_hours = reminder_context.get("offset_hours", -2)
            return meeting_time + timedelta(hours=offset_hours)
        except:
            return datetime.now(timezone.utc) + timedelta(hours=2)

    elif context_type == "follow_up_after":
        # Remind after X days
        try:
            ref_date_str = reminder_context.get("reference_date")
            ref_date = datetime.fromisoformat(ref_date_str.replace('Z', '+00:00'))
            return ref_date
        except:
            days = reminder_context.get("days", 3)
            return datetime.now(timezone.utc) + timedelta(days=days)

    elif context_type == "waiting_for_response":
        # Check after X days if no response
        try:
            ref_date_str = reminder_context.get("reference_date")
            ref_date = datetime.fromisoformat(ref_date_str.replace('Z', '+00:00'))
            return ref_date
        except:
            days = reminder_context.get("days", 2)
            return datetime.now(timezone.utc) + timedelta(days=days)

    else:
        # Fallback
        return datetime.now(timezone.utc) + timedelta(hours=24)


# DISABLED: Task extraction now handled by ThreadStateService
# This handler was creating duplicate tasks alongside the thread state approach.
# ThreadStateService.process_message() is now the canonical task creator.
# @register_handler("message_received")
async def extract_and_create_tasks_DEPRECATED(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    DEPRECATED: Task extraction now handled by ThreadStateService.

    This handler used extract_tasks_enhanced() which runs separately from
    thread state processing, causing duplicate tasks with different titles/formats.

    Keeping the code for reference but handler is unregistered.
    """
    message_id = payload.get("message_id")

    if not message_id:
        logger.error("No message_id in payload", extra={"correlation_id": event["correlation_id"]})
        return

    db = SessionLocal()
    try:
        # Get message from database
        message = db.query(Message).filter(Message.id == message_id).first()

        if not message:
            logger.error(f"Message {message_id} not found", extra={"correlation_id": event["correlation_id"]})
            return

        # Get or create user settings
        settings = db.query(UserSettings).first()
        if not settings:
            settings = UserSettings(user_email="default@user.com")
            db.add(settings)
            db.flush()

        # Prepare data for AI
        message_data = {
            "sender": message.sender,
            "subject": message.subject,
            "body": message.decrypted_body,
            "custom_instructions": settings.task_detection_instructions or ""
        }

        # Call AI to extract tasks with enhanced context
        logger.info(f"Extracting enhanced tasks from message {message_id}")
        extracted = ai_processor.extract_tasks_enhanced(message_data)

        # Create Task records
        created_tasks = []
        for task_data in extracted.get("tasks", []):
            # Calculate reminder schedule
            reminder_at = calculate_reminder_time(
                task_data.get("reminder_context"),
                settings.reminder_preferences or {}
            )

            # Determine initial status based on settings
            initial_status = "approved" if settings.auto_approve_tasks else "pending_approval"

            task = Task(
                message_id=message_id,
                title=task_data.get("title"),
                description=task_data.get("description"),
                task_type=task_data.get("task_type"),
                priority=task_data.get("priority", "normal"),
                status=initial_status,
                reminder_context=task_data.get("reminder_context"),
                scheduled_reminder_at=reminder_at,
                related_people=task_data.get("related_people", []),
                related_dates=task_data.get("related_dates", []),
                confidence_score=task_data.get("confidence_score"),
                approved_at=datetime.now(timezone.utc) if settings.auto_approve_tasks else None
            )

            db.add(task)
            db.flush()
            created_tasks.append(task.id)

            # Schedule reminder evaluation if task is approved and has a reminder
            if reminder_at and initial_status == "approved":
                enqueue_task(
                    task_type="evaluate_reminder",
                    payload={"task_id": task.id},
                    scheduled_for=reminder_at,
                    correlation_id=event["correlation_id"],
                    db=db
                )

        db.commit()

        logger.info(
            f"Created {len(created_tasks)} tasks from message {message_id}",
            extra={
                "correlation_id": event["correlation_id"],
                "task_count": len(created_tasks),
                "auto_approved": settings.auto_approve_tasks
            }
        )

        # Emit task_created event for each task
        for task_id in created_tasks:
            enqueue_task(
                task_type="emit_event",
                payload={
                    "event_name": "task_created",
                    "event_payload": {
                        "task_id": task_id,
                        "message_id": message_id,
                        "auto_approved": settings.auto_approve_tasks
                    }
                },
                correlation_id=event["correlation_id"],
                db=db
            )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to extract tasks from message {message_id}: {str(e)}",
            extra={"correlation_id": event["correlation_id"]},
            exc_info=True
        )
        raise
    finally:
        db.close()


@register_handler("task_created")
async def schedule_task_reminders(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Handle task_created event - schedule reminders if deadline exists.
    
    Policy:
    - If deadline > 24h away: remind 24h before deadline
    - If deadline ≤ 24h away: remind 1 hour from now
    - If deadline in the past: no reminder
    - Skip if scheduled_reminder_at already set or no deadline
    
    Works for all task sources: ThreadStateService, manual, Smart Todo, etc.
    """
    task_id = payload.get("task_id")
    
    if not task_id:
        logger.warning("task_created event missing task_id")
        return
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning(f"Task {task_id} not found for reminder scheduling")
            return
        
        # Skip if already has reminder scheduled
        if task.scheduled_reminder_at:
            logger.debug(f"Task {task_id} already has reminder at {task.scheduled_reminder_at}")
            return
        
        # Skip if no deadline
        if not task.deadline:
            logger.debug(f"Task {task_id} has no deadline, skipping reminder")
            return
        
        now = datetime.now(timezone.utc)
        
        # Ensure deadline is timezone-aware
        deadline = task.deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        
        # Skip if deadline already passed
        if deadline <= now:
            logger.info(f"Task {task_id} deadline already passed, no reminder")
            return
        
        # Calculate reminder time based on policy
        time_until_deadline = deadline - now
        
        if time_until_deadline > timedelta(hours=24):
            # More than 24h away: remind 24h before
            reminder_at = deadline - timedelta(hours=24)
        else:
            # Less than 24h away: remind 1 hour from now
            reminder_at = now + timedelta(hours=1)
            # But don't remind after deadline
            if reminder_at >= deadline:
                reminder_at = now + timedelta(minutes=15)  # Minimum 15 min buffer
        
        # Update task with reminder time
        task.scheduled_reminder_at = reminder_at
        db.commit()
        
        logger.info(
            f"Scheduled reminder for task {task_id} at {reminder_at} (deadline: {deadline})",
            extra={"correlation_id": event.get("correlation_id")}
        )
        
        # Queue reminder evaluation if task is approved
        if task.status == "approved":
            enqueue_task(
                task_type="evaluate_reminder",
                payload={"task_id": task.id, "user_id": task.user_id},
                scheduled_for=reminder_at,
                correlation_id=event.get("correlation_id"),
                db=db
            )
            logger.info(f"Queued evaluate_reminder for task {task_id} at {reminder_at}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to schedule reminder for task {task_id}: {e}", exc_info=True)
    finally:
        db.close()

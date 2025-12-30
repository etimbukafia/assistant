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


@register_handler("message_received")
async def extract_and_create_tasks(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Extract structured tasks from messages and create Task records.
    Runs in parallel with process_message_content handler.

    This is the core of the Task & Follow-Up Intelligence system.
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
async def notify_task_created(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Handle task_created event.
    Currently logs the event. Future: send notifications.

    Use cases:
    - Send notification if task needs approval
    - Trigger analytics update
    - Sync to external task manager (Todoist, Asana)
    """
    task_id = payload.get("task_id")
    auto_approved = payload.get("auto_approved", False)

    logger.info(
        f"Task {task_id} created (auto_approved={auto_approved})",
        extra={"correlation_id": event["correlation_id"], "task_id": task_id}
    )

    # Future implementations:
    # if not auto_approved:
    #     enqueue_task("send_notification", {
    #         "type": "task_approval_needed",
    #         "task_id": task_id
    #     })

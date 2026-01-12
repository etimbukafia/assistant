"""
Notification Handlers

Event handlers for sending notifications about urgent items.
Only triggers email for high-value interruptions.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from core.events import register_handler
from app.database import SessionLocal
from app.models import Task, UserSettings
from app.agents.modules.communication import CommunicationModule
from sqlalchemy import text

logger = logging.getLogger(__name__)


def meets_email_criteria(task: Task) -> bool:
    """
    Check if a task warrants an email notification.
    
    Only email if truly urgent and imminent:
    - Priority is "urgent"
    - Has a deadline
    - Deadline is within 4 hours
    - Task is actionable (approved or pending_approval)
    
    Returns:
        True if email should be sent
    """
    if task.priority != "urgent":
        return False
    
    if not task.deadline:
        return False
    
    if task.status not in ["approved", "pending_approval"]:
        return False
    
    # Calculate hours until deadline
    now = datetime.now(timezone.utc)
    deadline = task.deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    
    hours_until = (deadline - now).total_seconds() / 3600
    
    # Only email if due within 4 hours
    return 0 < hours_until <= 4


def render_urgent_task_email(task: Task) -> str:
    """
    Render HTML email body for an urgent task notification.
    
    Args:
        task: The urgent task
        
    Returns:
        HTML email body
    """
    deadline_str = task.deadline.strftime("%I:%M %p") if task.deadline else "Soon"
    
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #FEE2E2; border-left: 4px solid #EF4444; padding: 16px; border-radius: 4px;">
            <h2 style="margin: 0 0 8px 0; color: #991B1B; font-size: 18px;">⚠️ Urgent Task Due Soon</h2>
            <p style="margin: 0; color: #7F1D1D; font-size: 16px; font-weight: 500;">{task.title}</p>
            <p style="margin: 8px 0 0 0; color: #991B1B; font-size: 14px;">Due: {deadline_str}</p>
        </div>
        
        {f'<p style="margin: 16px 0; color: #666;">{task.description}</p>' if task.description else ''}
        
        <p style="margin: 16px 0; color: #888; font-size: 13px;">
            Open your inbox to take action on this task.
        </p>
    </div>
    """


@register_handler("reminder_due")
async def maybe_send_email_notification(event: Dict[str, Any], payload: Dict[str, Any]):
    """
    Handle reminder_due event and send email only for high-value urgent items.
    
    This runs when evaluate_reminder fires. It checks if the task
    is urgent enough to warrant an email interruption.
    """
    task_id = payload.get("task_id")
    user_id = payload.get("user_id")
    
    if not task_id:
        logger.warning("reminder_due event missing task_id")
        return
        
    if not user_id:
        logger.warning("reminder_due event missing user_id")
        return
    
    db = SessionLocal()
    # Set RLS context
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning(f"Task {task_id} not found for email notification check")
            return
        
        # Check if urgent enough for email
        if not meets_email_criteria(task):
            logger.debug(f"Task {task_id} does not meet email criteria")
            return
        
        # Check if user recently active (future: track last_active_at)
        # For now, always send if criteria met
        
        # Get user settings for email
        settings = db.query(UserSettings).first()
        if not settings or not settings.user_email:
            logger.warning("No user email configured for notifications")
            return
        
        # Send email via CommunicationModule
        comm = CommunicationModule()
        result = comm.notify_user_email(
            subject=f"⚠️ Urgent: {task.title}",
            body=render_urgent_task_email(task),
            priority="urgent",
            user_email=settings.user_email
        )
        
        if result.get("sent"):
            logger.info(f"Sent urgent email notification for task {task_id}")
        else:
            logger.error(f"Failed to send email for task {task_id}: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error in email notification handler: {e}", exc_info=True)
    finally:
        db.close()
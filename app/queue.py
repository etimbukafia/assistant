"""
App-specific queue setup

This file bridges core/queue (reusable) with app/ (assistant-specific).
Import queue operations from here in your app code.
"""
from core.queue.service import QueueService
from app.models import TaskQueue
from app.database import SessionLocal

# Initialize queue service for this app
queue_service = QueueService(TaskQueue, SessionLocal)

# Convenience functions that use the app's queue_service
def enqueue_task(task_type, payload, correlation_id=None, scheduled_for=None, max_attempts=3, db=None):
    """Enqueue a task to the app's queue"""
    return queue_service.enqueue(
        task_type=task_type,
        payload=payload,
        correlation_id=correlation_id,
        scheduled_for=scheduled_for,
        max_attempts=max_attempts,
        db=db
    )

def get_pending_tasks(limit=10, task_type=None, db=None):
    """Get pending tasks from the app's queue"""
    return queue_service.get_pending(limit=limit, task_type=task_type, db=db)

def mark_task_in_progress(task_id, db=None):
    """Mark task as in progress"""
    return queue_service.mark_in_progress(task_id, db=db)

def mark_task_completed(task_id, db=None):
    """Mark task as completed"""
    return queue_service.mark_completed(task_id, db=db)

def mark_task_failed(task_id, error, retry=True, db=None):
    """Mark task as failed"""
    return queue_service.mark_failed(task_id, error, retry=retry, db=db)

def cleanup_old_tasks(days=7, db=None):
    """Cleanup old completed/failed tasks"""
    return queue_service.cleanup_old(days=days, db=db)

"""
Task Queue Service - Reusable across projects

Generic queue operations that work with any SQLAlchemy setup.
Pass your TaskQueue model and SessionLocal to use.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class QueueService:
    """
    Generic task queue service

    Usage:
        from core.queue import QueueService
        from app.models import TaskQueue
        from app.database import SessionLocal

        queue = QueueService(TaskQueue, SessionLocal)
        queue.enqueue("send_email", {"to": "user@example.com"})
    """

    def __init__(self, task_queue_model, session_factory: Callable):
        """
        Initialize queue service

        Args:
            task_queue_model: TaskQueue model class
            session_factory: Callable that returns new database session
        """
        self.TaskQueue = task_queue_model
        self.SessionLocal = session_factory

    def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        scheduled_for: Optional[datetime] = None,
        max_attempts: int = 3,
        user_id: Optional[str] = None,
        db: Optional[Session] = None
    ):
        """
        Add a task to the queue

        Args:
            task_type: Type of task (e.g., "emit_event", "send_notification")
            payload: Task data
            correlation_id: Optional correlation ID for tracking related tasks
            scheduled_for: When to run the task (default: now)
            max_attempts: Maximum retry attempts
            user_id: Optional user ID for RLS context
            db: Optional database session (creates new one if not provided)

        Returns:
            Created TaskQueue object
        """
        should_close_db = False
        if db is None:
            db = self.SessionLocal()
            should_close_db = True

        try:
            task = self.TaskQueue(
                task_type=task_type,
                payload=payload,
                correlation_id=correlation_id,
                user_id=user_id,
                scheduled_for=scheduled_for or datetime.utcnow(),
                max_attempts=max_attempts,
                status="pending"
            )

            db.add(task)
            db.commit()
            db.refresh(task)

            logger.info(
                f"Task enqueued: {task_type} (id={task.id})",
                extra={
                    "task_id": task.id,
                    "task_type": task_type,
                    "correlation_id": correlation_id
                }
            )

            return task

        finally:
            if should_close_db:
                db.close()

    def get_pending(
        self,
        limit: int = 10,
        task_type: Optional[str] = None,
        use_row_locking: bool = True,
        db: Optional[Session] = None
    ) -> List:
        """
        Get pending tasks ready to process

        Args:
            limit: Maximum number of tasks to return
            task_type: Optional filter by task type
            use_row_locking: Use FOR UPDATE SKIP LOCKED (requires Postgres)
            db: Optional database session

        Returns:
            List of pending tasks
        """
        should_close_db = False
        if db is None:
            db = self.SessionLocal()
            should_close_db = True

        try:
            query = db.query(self.TaskQueue).filter(
                self.TaskQueue.status == "pending",
                self.TaskQueue.scheduled_for <= datetime.utcnow(),
                self.TaskQueue.attempts < self.TaskQueue.max_attempts
            )

            if task_type:
                query = query.filter(self.TaskQueue.task_type == task_type)

            query = query.order_by(self.TaskQueue.scheduled_for.asc()).limit(limit)

            # Use row locking for Postgres (safe for concurrent workers)
            if use_row_locking:
                query = query.with_for_update(skip_locked=True)

            tasks = query.all()

            return tasks

        finally:
            if should_close_db:
                db.close()

    def mark_in_progress(self, task_id: int, db: Optional[Session] = None) -> bool:
        """Mark a task as in progress"""
        should_close_db = False
        if db is None:
            db = self.SessionLocal()
            should_close_db = True

        try:
            task = db.query(self.TaskQueue).filter(self.TaskQueue.id == task_id).first()

            if not task:
                return False

            task.status = "in_progress"
            task.started_at = datetime.utcnow()
            task.attempts += 1

            db.commit()

            logger.info(
                f"Task started: {task.task_type} (id={task.id}, attempt={task.attempts})",
                extra={
                    "task_id": task.id,
                    "task_type": task.task_type,
                    "attempt": task.attempts
                }
            )

            return True

        finally:
            if should_close_db:
                db.close()

    def mark_completed(self, task_id: int, db: Optional[Session] = None) -> bool:
        """Mark a task as completed"""
        should_close_db = False
        if db is None:
            db = self.SessionLocal()
            should_close_db = True

        try:
            task = db.query(self.TaskQueue).filter(self.TaskQueue.id == task_id).first()

            if not task:
                return False

            task.status = "completed"
            task.completed_at = datetime.utcnow()

            db.commit()

            logger.info(
                f"Task completed: {task.task_type} (id={task.id})",
                extra={
                    "task_id": task.id,
                    "task_type": task.task_type,
                    "correlation_id": task.correlation_id
                }
            )

            return True

        finally:
            if should_close_db:
                db.close()

    def mark_failed(
        self,
        task_id: int,
        error: str,
        retry: bool = True,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Mark a task as failed

        Args:
            task_id: Task ID
            error: Error message
            retry: If True and attempts < max_attempts, reschedule for retry
            db: Optional database session

        Returns:
            Dict with: updated (bool), permanent (bool), user_id (str|None)
        """
        should_close_db = False
        if db is None:
            db = self.SessionLocal()
            should_close_db = True

        try:
            task = db.query(self.TaskQueue).filter(self.TaskQueue.id == task_id).first()

            if not task:
                return {"updated": False, "permanent": False, "user_id": None}

            task.last_error = error
            permanent = False

            # Retry logic with exponential backoff
            if retry and task.attempts < task.max_attempts:
                task.status = "pending"
                # Exponential backoff: 1min, 5min, 25min
                delay_minutes = 1 * (5 ** (task.attempts - 1))
                task.scheduled_for = datetime.utcnow() + timedelta(minutes=delay_minutes)

                logger.warning(
                    f"Task failed, will retry: {task.task_type} (id={task.id}, attempt={task.attempts}/{task.max_attempts})",
                    extra={
                        "task_id": task.id,
                        "task_type": task.task_type,
                        "error": error,
                        "retry_in_minutes": delay_minutes
                    }
                )
            else:
                task.status = "failed"
                permanent = True

                logger.error(
                    f"Task failed permanently: {task.task_type} (id={task.id})",
                    extra={
                        "task_id": task.id,
                        "task_type": task.task_type,
                        "error": error,
                        "attempts": task.attempts
                    }
                )

            db.commit()
            return {"updated": True, "permanent": permanent, "user_id": getattr(task, 'user_id', None)}

        finally:
            if should_close_db:
                db.close()

    def cleanup_old(self, days: int = 7, db: Optional[Session] = None) -> int:
        """
        Delete completed/failed tasks older than specified days

        Args:
            days: Delete tasks older than this many days
            db: Optional database session

        Returns:
            Number of tasks deleted
        """
        should_close_db = False
        if db is None:
            db = self.SessionLocal()
            should_close_db = True

        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            count = db.query(self.TaskQueue).filter(
                self.TaskQueue.status.in_(["completed", "failed"]),
                self.TaskQueue.updated_at < cutoff
            ).delete()

            db.commit()

            if count > 0:
                logger.info(f"Cleaned up {count} old tasks")

            return count

        finally:
            if should_close_db:
                db.close()

    async def process_batch_now(
        self,
        user_id: str,
        task_type: str,
        handler: Callable,
        db: Optional[Session] = None,
        limit: int = 100,
    ) -> Dict[str, int]:
        """
        Process pending tasks for a user/task type immediately in-process.

        This is used by webhook/sync paths to reduce queue latency for
        fresh inbound emails.
        """
        should_close_db = False
        if db is None:
            db = self.SessionLocal()
            should_close_db = True

        try:
            tasks = db.query(self.TaskQueue).filter(
                self.TaskQueue.status == "pending",
                self.TaskQueue.task_type == task_type,
                self.TaskQueue.user_id == user_id,
                self.TaskQueue.scheduled_for <= datetime.utcnow(),
                self.TaskQueue.attempts < self.TaskQueue.max_attempts,
            ).order_by(self.TaskQueue.scheduled_for.asc()).limit(limit).all()

            if not tasks:
                return {"processed": 0, "failed": 0}

            # Lock ownership of this batch for current process.
            for task in tasks:
                task.status = "in_progress"
                task.started_at = datetime.utcnow()
                task.attempts += 1
            db.commit()

            payload_tasks = [
                {
                    "task_id": task.id,
                    "payload": task.payload or {},
                    "correlation_id": task.correlation_id,
                    "attempts": task.attempts,
                }
                for task in tasks
            ]

            try:
                result = handler(user_id, payload_tasks)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                now = datetime.utcnow()
                for task in tasks:
                    task.last_error = str(exc)[:2000]
                    if task.attempts < task.max_attempts:
                        delay_minutes = 1 * (5 ** max(0, task.attempts - 1))
                        task.status = "pending"
                        task.scheduled_for = now + timedelta(minutes=delay_minutes)
                    else:
                        task.status = "failed"
                db.commit()
                raise

            for task in tasks:
                task.status = "completed"
                task.completed_at = datetime.utcnow()
            db.commit()
            return {"processed": len(tasks), "failed": 0}
        finally:
            if should_close_db:
                db.close()


# Convenience functions for backward compatibility
def enqueue_task(
    task_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
    scheduled_for: Optional[datetime] = None,
    max_attempts: int = 3,
    db: Optional[Session] = None,
):
    """
    Convenience function - delegates to global QueueService instance.

    Extracts user_id from payload if present for RLS tracking.
    """
    service = get_queue_service()

    # Extract user_id from payload for task-level tracking
    user_id = payload.get("user_id")

    return service.enqueue(
        task_type=task_type,
        payload=payload,
        correlation_id=correlation_id,
        scheduled_for=scheduled_for,
        max_attempts=max_attempts,
        user_id=user_id,
        db=db
    )


# Global queue_service instance for this application
# Lazy initialization to avoid circular imports
_queue_service_instance = None

def get_queue_service():
    global _queue_service_instance
    if _queue_service_instance is None:
        from app.data.models import TaskQueue
        from app.infra.database import SessionLocal
        _queue_service_instance = QueueService(TaskQueue, SessionLocal)
    return _queue_service_instance

# For backward compatibility with imports
queue_service = property(lambda self: get_queue_service())

# Actually instantiate for direct import
class _QueueServiceProxy:
    def __getattr__(self, name):
        return getattr(get_queue_service(), name)

queue_service = _QueueServiceProxy()

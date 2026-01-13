"""
Generic Task Queue Worker - Reusable across projects

Simple worker that processes tasks from queue.
You provide the task handlers, worker handles the rest.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Type for task handlers
TaskHandler = Callable[[int, str, Dict[str, Any], str], Awaitable[None]]


class Worker:
    """
    Generic queue worker

    Usage:
        from core.queue import Worker, QueueService
        from app.data.models import TaskQueue
        from app.infra.database import SessionLocal

        queue_service = QueueService(TaskQueue, SessionLocal)

        async def handle_emit_event(task_id, task_type, payload, correlation_id):
            # Your handler logic
            pass

        worker = Worker(queue_service, {
            "emit_event": handle_emit_event,
            "send_notification": handle_send_notification
        })

        worker.run()
    """

    def __init__(self, queue_service, handlers: Dict[str, TaskHandler], poll_interval: int = 2):
        """
        Initialize worker

        Args:
            queue_service: QueueService instance
            handlers: Dict mapping task_type to handler function
            poll_interval: Seconds between polls (default: 2)
        """
        self.queue_service = queue_service
        self.handlers = handlers
        self.poll_interval = poll_interval
        self.cleanup_counter = 0

    async def process_task(self, task, db):
        """
        Process a single task by calling its handler

        Args:
            task: TaskQueue object (already locked)
            db: Database session (same session that locked the task)
        """
        task_id = task.id
        task_type = task.task_type
        payload = task.payload
        correlation_id = task.correlation_id

        try:
            # Mark as in progress
            self.queue_service.mark_in_progress(task_id, db=db)

            # Get handler for this task type
            handler = self.handlers.get(task_type)

            if handler is None:
                # Unknown task type - check if there's a default handler
                handler = self.handlers.get("_default")

                if handler is None:
                    logger.warning(f"No handler for task type: {task_type} (task_id={task_id})")
                    # Mark as completed so it doesn't retry forever
                    self.queue_service.mark_completed(task_id, db=db)
                    return

            # Call the handler
            await handler(task_id, task_type, payload, correlation_id)

            # Mark completed
            self.queue_service.mark_completed(task_id, db=db)

        except Exception as e:
            logger.error(f"Task processing failed: {task_type} (id={task_id}): {str(e)}", exc_info=True)
            self.queue_service.mark_failed(task_id, str(e), retry=True, db=db)

    async def process_batch(self):
        """
        Process a batch of tasks from the queue

        Returns:
            Number of tasks processed
        """
        db = self.queue_service.SessionLocal()
        try:
            # Get pending tasks (locks them)
            tasks = self.queue_service.get_pending(limit=10, db=db)

            if tasks:
                logger.info(f"Processing {len(tasks)} pending tasks")

                # Process all tasks in this batch
                for task in tasks:
                    await self.process_task(task, db)

                # Commit all changes at once
                db.commit()

            return len(tasks)

        except Exception as e:
            db.rollback()
            logger.error(f"Batch processing error: {str(e)}", exc_info=True)
            return 0
        finally:
            db.close()

    def run(self):
        """
        Run the worker - continuously polls queue

        Blocks until interrupted (Ctrl+C)
        """
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        logger.info("Worker started, polling queue...")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Registered handlers: {list(self.handlers.keys())}")

        try:
            while True:
                # Process tasks
                processed = asyncio.run(self.process_batch())

                # Cleanup old tasks every ~100 cycles (when idle)
                if processed == 0:
                    self.cleanup_counter += 1
                    if self.cleanup_counter >= 100:
                        count = self.queue_service.cleanup_old(days=7)
                        if count > 0:
                            logger.info(f"Cleaned up {count} old tasks")
                        self.cleanup_counter = 0

                # Wait before next poll
                # If we processed tasks, poll again quickly
                # If queue was empty, wait full interval
                sleep_time = 0.1 if processed > 0 else self.poll_interval
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
        except Exception as e:
            logger.error(f"Worker crashed: {str(e)}", exc_info=True)
            raise


def run_worker(queue_service, handlers: Dict[str, TaskHandler], poll_interval: int = 2):
    """
    Convenience function to run worker

    Args:
        queue_service: QueueService instance
        handlers: Dict mapping task_type to handler function
        poll_interval: Seconds between polls
    """
    worker = Worker(queue_service, handlers, poll_interval)
    worker.run()

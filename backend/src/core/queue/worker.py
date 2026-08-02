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

    def __init__(
        self,
        queue_service,
        handlers: Dict[str, TaskHandler],
        poll_interval: int = 2,
        on_permanent_failure: Callable[[int, str, Dict[str, Any], str, str], None] = None
    ):
        """
        Initialize worker

        Args:
            queue_service: QueueService instance
            handlers: Dict mapping task_type to handler function
            poll_interval: Seconds between polls (default: 2)
            on_permanent_failure: Optional callback(task_id, task_type, payload, error, user_id)
                                  called when a task fails permanently (all retries exhausted)
        """
        self.queue_service = queue_service
        self.handlers = handlers
        self.poll_interval = poll_interval
        self.cleanup_counter = 0
        self.on_permanent_failure = on_permanent_failure

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
                    logger.error(f"No handler for task type: {task_type} (task_id={task_id}) - possible typo or missing handler registration")
                    # Mark as failed (not completed) to surface the issue
                    self.queue_service.mark_failed(task_id, f"Unknown task type: {task_type}", retry=False, db=db)
                    return

            # Call the handler
            await handler(task_id, task_type, payload, correlation_id)

            # Mark completed
            self.queue_service.mark_completed(task_id, db=db)

        except Exception as e:
            logger.error(f"Task processing failed: {task_type} (id={task_id}): {str(e)}", exc_info=True)
            result = self.queue_service.mark_failed(task_id, str(e), retry=True, db=db)

            # Call callback if task failed permanently (all retries exhausted)
            if result.get("permanent") and self.on_permanent_failure:
                try:
                    self.on_permanent_failure(task_id, task_type, payload, str(e), result.get("user_id"))
                except Exception as callback_error:
                    logger.error(f"on_permanent_failure callback failed: {callback_error}")

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


# Type for batch handlers (receives user_id and list of tasks)
BatchHandler = Callable[[str, list], Awaitable[None]]


class BatchWorker:
    """
    Worker that groups tasks by user for efficient batch processing.

    Unlike the regular Worker which processes tasks one-by-one,
    BatchWorker groups pending tasks by (user_id, task_type) and processes
    them as batches. This is optimal for LLM workloads where
    initialization overhead is significant.

    For task types without a batch handler, falls back to single-task
    handlers if provided, processing each task individually.

    Usage:
        async def handle_process_emails(user_id: str, tasks: List[Dict]):
            # All tasks belong to the same user
            for task in tasks:
                message_id = task["payload"]["message_id"]
                # Process message...

        worker = BatchWorker(
            queue_service,
            handlers={"process_email": handle_process_emails},
            single_task_handlers={"email_backfill": handle_email_backfill},
        )
        worker.run()
    """

    def __init__(
        self,
        queue_service,
        handlers: Dict[str, BatchHandler],
        poll_interval: int = 2,
        limit_per_user: int = 30,
        max_users: int = 5,
        max_concurrency: int = 3,
        on_permanent_failure: Callable[[int, str, Dict[str, Any], str, str], None] = None,
        single_task_handlers: Dict[str, TaskHandler] = None,
    ):
        """
        Initialize batch worker.

        Args:
            queue_service: QueueService instance
            handlers: Dict mapping task_type to batch handler function
            poll_interval: Seconds between polls (default: 2)
            limit_per_user: Max tasks per user per batch (default: 30)
            max_users: Max users to process per cycle (default: 5)
            max_concurrency: Max user batches processed concurrently (default: 3)
            on_permanent_failure: Optional callback(task_id, task_type, payload, error, user_id)
                                  called when a task fails permanently (all retries exhausted)
            single_task_handlers: Optional dict of individual task handlers as fallback
                                  for task types not in batch handlers
        """
        self.queue_service = queue_service
        self.handlers = handlers
        self.single_task_handlers = single_task_handlers or {}
        self.poll_interval = poll_interval
        self.limit_per_user = limit_per_user
        self.max_users = max_users
        self.max_concurrency = max_concurrency
        self.cleanup_counter = 0
        self.on_permanent_failure = on_permanent_failure

    async def _run_single_task(self, task, db):
        """
        Run a single-task handler for a task that has no batch handler.
        """
        task_type = task.task_type
        handler = self.single_task_handlers.get(task_type)

        if handler is None:
            logger.warning(f"No handler (batch or single) for task type: {task_type}")
            self.queue_service.mark_completed(task.id, db=db)
            return

        self.queue_service.mark_in_progress(task.id, db=db)

        try:
            await handler(
                task.id,
                task.task_type,
                task.payload,
                task.correlation_id or "",
            )
            self.queue_service.mark_completed(task.id, db=db)
        except Exception as e:
            logger.error(f"Single-task handler failed: {task_type} (id={task.id}): {e}", exc_info=True)
            result = self.queue_service.mark_failed(task.id, str(e), retry=True, db=db)

            if result.get("permanent") and self.on_permanent_failure:
                try:
                    user_id = task.payload.get("user_id", "")
                    self.on_permanent_failure(task.id, task_type, task.payload, str(e), user_id)
                except Exception as callback_error:
                    logger.error(f"on_permanent_failure callback failed: {callback_error}")

    async def process_user_batch(self, user_id: str, task_type: str, tasks: list, db):
        """
        Process a batch of same-type tasks for a single user.

        Args:
            user_id: User ID for this batch
            task_type: The task type for all tasks in this batch
            tasks: List of TaskQueue objects for this user (all same type)
            db: Database session
        """
        if not tasks:
            return

        handler = self.handlers.get(task_type)

        if handler is None:
            # Fall back to single-task handler, process each individually
            for task in tasks:
                await self._run_single_task(task, db)
            return

        # Mark all as in progress
        for task in tasks:
            self.queue_service.mark_in_progress(task.id, db=db)

        try:
            # Convert to handler format
            task_data = [
                {
                    "task_id": t.id,
                    "payload": t.payload,
                    "correlation_id": t.correlation_id
                }
                for t in tasks
            ]

            # Call batch handler with user_id and all their tasks
            await handler(user_id, task_data)

            # Mark all as completed
            for task in tasks:
                self.queue_service.mark_completed(task.id, db=db)

        except Exception as e:
            logger.error(f"Batch processing failed for user {user_id}: {str(e)}", exc_info=True)
            # Mark all as failed
            for task in tasks:
                result = self.queue_service.mark_failed(task.id, str(e), retry=True, db=db)

                # Call callback if task failed permanently
                if result.get("permanent") and self.on_permanent_failure:
                    try:
                        self.on_permanent_failure(task.id, task.task_type, task.payload, str(e), user_id)
                    except Exception as callback_error:
                        logger.error(f"on_permanent_failure callback failed: {callback_error}")

    async def process_batch_cycle(self):
        """
        Process one cycle of batch processing.

        Groups tasks by (user_id, task_type) and processes each group.
        Uses a semaphore to control concurrency.

        Returns:
            Total number of tasks processed
        """
        db = self.queue_service.SessionLocal()
        try:
            # Get pending tasks (more than usual since we're batching)
            all_tasks = self.queue_service.get_pending(
                limit=self.limit_per_user * self.max_users,
                db=db
            )

            if not all_tasks:
                return 0

            # Group by (user_id, task_type) to avoid mixing different task types
            from collections import defaultdict
            groups = defaultdict(list)

            for task in all_tasks:
                user_id = task.payload.get("user_id")
                if user_id:
                    groups[(user_id, task.task_type)].append(task)
                else:
                    # No user_id - process individually via single-task fallback
                    logger.warning(f"Task {task.id} ({task.task_type}) has no user_id, processing individually")
                    await self._run_single_task(task, db)

            # Cap per-group and limit total groups processed
            batches_to_run = []
            users_seen = set()

            for (user_id, task_type), group_tasks in groups.items():
                users_seen.add(user_id)
                if len(users_seen) > self.max_users:
                    break
                batch = group_tasks[:self.limit_per_user]
                batches_to_run.append((user_id, task_type, batch))

            # Process with controlled concurrency via semaphore
            semaphore = asyncio.Semaphore(self.max_concurrency)
            total_tasks = 0

            async def run_batch(user_id, task_type, batch):
                async with semaphore:
                    logger.info(
                        f"Processing {len(batch)} {task_type} tasks for user {user_id}"
                    )
                    await self.process_user_batch(user_id, task_type, batch, db)

            await asyncio.gather(
                *(run_batch(uid, tt, b) for uid, tt, b in batches_to_run)
            )

            total_tasks = sum(len(b) for _, _, b in batches_to_run)
            db.commit()
            return total_tasks

        except Exception as e:
            db.rollback()
            logger.error(f"Batch cycle error: {str(e)}", exc_info=True)
            return 0
        finally:
            db.close()

    def run(self):
        """
        Run the batch worker - continuously polls queue.

        Blocks until interrupted (Ctrl+C).
        """
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        logger.info("BatchWorker started, polling queue...")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Limit per user: {self.limit_per_user}, Max users: {self.max_users}, Max concurrency: {self.max_concurrency}")
        logger.info(f"Registered batch handlers: {list(self.handlers.keys())}")
        logger.info(f"Registered single-task handlers: {list(self.single_task_handlers.keys())}")

        try:
            while True:
                # Process batch cycle
                processed = asyncio.run(self.process_batch_cycle())

                # Cleanup old tasks every ~100 cycles (when idle)
                if processed == 0:
                    self.cleanup_counter += 1
                    if self.cleanup_counter >= 100:
                        count = self.queue_service.cleanup_old(days=7)
                        if count > 0:
                            logger.info(f"Cleaned up {count} old tasks")
                        self.cleanup_counter = 0

                # Wait before next poll
                sleep_time = 0.1 if processed > 0 else self.poll_interval
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("BatchWorker stopped by user")
        except Exception as e:
            logger.error(f"BatchWorker crashed: {str(e)}", exc_info=True)
            raise

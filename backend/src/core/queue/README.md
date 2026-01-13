# Core Queue Framework

**Reusable Postgres-backed task queue** for any Python/FastAPI project.

## Features

- ✅ **Postgres row-level locking** - Safe for concurrent workers
- ✅ **Automatic retries** - Exponential backoff for failed tasks
- ✅ **Survives restarts** - Tasks persisted in database
- ✅ **Simple API** - Easy to integrate
- ✅ **Generic** - Not tied to any specific app
- ✅ **Type-safe** - Full type hints

## Installation in Your Project

1. **Copy `core/queue/` to your project**

2. **Create TaskQueue model in your app:**

```python
# app/models.py
from app.database import Base
from core.queue.models import create_task_queue_model

TaskQueue = create_task_queue_model(Base)
```

3. **Create app-specific queue service:**

```python
# app/queue.py
from core.queue import QueueService
from app.models import TaskQueue
from app.database import SessionLocal

queue_service = QueueService(TaskQueue, SessionLocal)

# Convenience functions
def enqueue_task(task_type, payload, **kwargs):
    return queue_service.enqueue(task_type, payload, **kwargs)
```

4. **Create worker with your task handlers:**

```python
# app/worker.py
from core.queue import Worker
from app.queue import queue_service

async def handle_send_email(task_id, task_type, payload, correlation_id):
    email = payload["email"]
    # Send email logic...

async def handle_process_image(task_id, task_type, payload, correlation_id):
    image_url = payload["url"]
    # Process image logic...

HANDLERS = {
    "send_email": handle_send_email,
    "process_image": handle_process_image,
}

if __name__ == "__main__":
    worker = Worker(queue_service, HANDLERS)
    worker.run()
```

5. **Enqueue tasks in your app:**

```python
# app/main.py
from app.queue import enqueue_task

@app.post("/signup")
def signup(email: str):
    # Save user...

    # Enqueue welcome email
    enqueue_task("send_email", {
        "email": email,
        "template": "welcome"
    })

    return {"status": "ok"}
```

6. **Run the worker:**

```bash
python -m app.worker
```

## API Reference

### QueueService

```python
from core.queue import QueueService

queue = QueueService(TaskQueueModel, SessionLocal)

# Enqueue task
task = queue.enqueue(
    task_type="send_email",
    payload={"email": "user@example.com"},
    correlation_id="signup-123",  # Optional: link related tasks
    scheduled_for=datetime(...),   # Optional: schedule for later
    max_attempts=3                 # Optional: max retries
)

# Get pending tasks (with row locking)
tasks = queue.get_pending(limit=10, task_type="send_email")

# Mark task status
queue.mark_in_progress(task_id)
queue.mark_completed(task_id)
queue.mark_failed(task_id, error="Connection timeout", retry=True)

# Cleanup old tasks
count = queue.cleanup_old(days=7)
```

### Worker

```python
from core.queue import Worker

async def my_handler(task_id, task_type, payload, correlation_id):
    # Process task...
    pass

worker = Worker(
    queue_service=queue_service,
    handlers={"my_task": my_handler},
    poll_interval=2  # Seconds between polls
)

worker.run()  # Blocks until Ctrl+C
```

### Task Handler Signature

```python
async def handler(
    task_id: int,           # Task ID in database
    task_type: str,         # Type of task
    payload: Dict[str, Any],# Task data
    correlation_id: str     # For tracking related tasks
) -> None:
    # Your logic here
    pass
```

## Row-Level Locking

Uses Postgres `FOR UPDATE SKIP LOCKED` for safe concurrent processing:

```sql
SELECT * FROM task_queue
WHERE status = 'pending'
FOR UPDATE SKIP LOCKED
LIMIT 10;
```

**Benefits:**
- Multiple workers can run concurrently
- Each task processed exactly once
- No race conditions
- Workers skip tasks locked by others

## Retry Logic

Failed tasks retry automatically with exponential backoff:

```
Attempt 1: Fails → Retry in 1 minute
Attempt 2: Fails → Retry in 5 minutes
Attempt 3: Fails → Retry in 25 minutes
Attempt 4: Fails → Marked as "failed" permanently
```

Formula: `1 * (5 ^ (attempt - 1))` minutes

## Database Schema

```sql
CREATE TABLE task_queue (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR NOT NULL,
    correlation_id VARCHAR,
    payload JSONB NOT NULL,
    status VARCHAR DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_error TEXT,
    scheduled_for TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON task_queue(status, scheduled_for);
CREATE INDEX ON task_queue(correlation_id);
```

## Error Handling

### Task handler errors

Exceptions in handlers are caught and logged. Task is marked as failed and retried:

```python
async def my_handler(task_id, task_type, payload, correlation_id):
    raise Exception("API timeout")  # Task will retry automatically
```

### Worker crashes

Tasks in "in_progress" status will eventually retry after timeout.

### Unknown task types

If no handler registered for task_type, task is marked completed (won't retry forever).

## Monitoring

### Check queue stats

```python
# In your FastAPI app
@app.get("/queue/stats")
def queue_stats(db: Session = Depends(get_db)):
    pending = db.query(TaskQueue).filter(TaskQueue.status == "pending").count()
    # ...
    return {"pending": pending, ...}
```

### View in database

```sql
-- Pending tasks
SELECT * FROM task_queue WHERE status = 'pending';

-- Failed tasks
SELECT task_type, last_error FROM task_queue WHERE status = 'failed';

-- Task counts by type
SELECT task_type, status, COUNT(*)
FROM task_queue
GROUP BY task_type, status;
```

## Scaling

### Run multiple workers

```bash
python -m app.worker &
python -m app.worker &
python -m app.worker &
```

Each worker safely claims tasks using row locking. No conflicts!

### Adjust poll interval

```python
worker = Worker(queue_service, handlers, poll_interval=1)  # Poll every second
```

### Batch size

```python
tasks = queue.get_pending(limit=20)  # Process 20 tasks per batch
```

## Migration to Other Systems

The worker interface makes it easy to migrate to Redis, RabbitMQ, or Kafka later:

```python
# Same handler signature works with any queue system
async def my_handler(task_id, task_type, payload, correlation_id):
    pass  # Works with Postgres, Redis, RabbitMQ, etc.
```

## Example: Multi-step Workflow

```python
# app/worker.py
async def handle_user_signup(task_id, task_type, payload, correlation_id):
    user_id = payload["user_id"]

    # Send welcome email
    enqueue_task("send_email", {"user_id": user_id, "template": "welcome"})

    # Create sample data
    enqueue_task("create_samples", {"user_id": user_id})

    # Schedule reminder for 3 days
    enqueue_task(
        "send_reminder",
        {"user_id": user_id},
        scheduled_for=datetime.now() + timedelta(days=3)
    )

HANDLERS = {
    "user_signup": handle_user_signup,
    "send_email": handle_send_email,
    "create_samples": handle_create_samples,
    "send_reminder": handle_send_reminder,
}
```

## Differences from Other Queue Systems

| Feature | core/queue | Celery | Redis Queue | AWS SQS |
|---------|-----------|--------|-------------|---------|
| Setup | Simple | Complex | Medium | Medium |
| Dependencies | Postgres | Redis/RabbitMQ | Redis | AWS |
| Concurrent workers | ✅ | ✅ | ✅ | ✅ |
| Retry logic | ✅ | ✅ | ✅ | ✅ |
| Scheduled tasks | ✅ | ✅ | ❌ | ✅ |
| Survives restarts | ✅ | ✅ | ❌ | ✅ |
| Cost | Free | Free | Free | Paid |

**Use core/queue when:**
- Already using Postgres
- Want simple setup
- Don't need extreme throughput (1000+ tasks/sec)
- Want to avoid extra dependencies

**Migrate to Celery/RabbitMQ when:**
- Need 10,000+ tasks/sec
- Need priority queues
- Need complex routing

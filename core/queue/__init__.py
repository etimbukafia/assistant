"""
Reusable Task Queue Framework

A simple, Postgres-backed task queue for background processing.
Uses row-level locking for safe concurrent processing.

## Usage in your app

1. Create TaskQueue model:
```python
from app.database import Base
from core.queue.models import create_task_queue_model

TaskQueue = create_task_queue_model(Base)
```

2. Initialize queue service:
```python
from core.queue import QueueService
from app.models import TaskQueue
from app.database import SessionLocal

queue_service = QueueService(TaskQueue, SessionLocal)
```

3. Enqueue tasks:
```python
queue_service.enqueue("send_email", {"to": "user@example.com"})
```

4. Create worker with handlers:
```python
from core.queue import Worker

async def handle_send_email(task_id, task_type, payload, correlation_id):
    # Your logic here
    pass

worker = Worker(queue_service, {
    "send_email": handle_send_email
})

worker.run()
```

See core/queue/README.md for full documentation.
"""
from .models import create_task_queue_model
from .service import QueueService
from .worker import Worker, run_worker

__all__ = [
    "create_task_queue_model",
    "QueueService",
    "Worker",
    "run_worker"
]

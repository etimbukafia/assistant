# Core Events Framework

A lightweight, reusable event-driven architecture for AI assistant applications.

## Features

- **Simple API**: Emit events and register handlers with minimal boilerplate
- **FastAPI Integration**: Built-in support for BackgroundTasks
- **Observability**: Automatic logging with correlation IDs
- **Type Safety**: Typed event structure
- **Flexible**: Use decorators or class-based handlers
- **Framework Agnostic**: Core logic independent of business domain

## Installation

Copy the `core/` directory to any Python project. No external dependencies beyond FastAPI.

## Quick Start

### 1. Register Handlers

```python
from core.events import register_handler

@register_handler("user_registered")
async def send_welcome_email(event, payload):
    user_id = payload["user_id"]
    # Send email logic
    print(f"Sending welcome email to user {user_id}")

@register_handler("user_registered")
async def create_user_profile(event, payload):
    user_id = payload["user_id"]
    # Create profile logic
    print(f"Creating profile for user {user_id}")
```

### 2. Emit Events

```python
from fastapi import FastAPI, BackgroundTasks
from core.events import emit_event

app = FastAPI()

@app.post("/users")
async def create_user(background_tasks: BackgroundTasks):
    # Create user in database
    user_id = 123

    # Emit event - all registered handlers will run in background
    emit_event(
        event_name="user_registered",
        payload={"user_id": user_id},
        background_tasks=background_tasks
    )

    return {"user_id": user_id}
```

### 3. View Registered Handlers (Optional)

```python
from core.events import get_registered_handlers

@app.get("/debug/handlers")
def list_handlers():
    return get_registered_handlers()
```

## Advanced Usage

### Class-Based Handlers

For handlers with dependencies or state:

```python
from core.events import EventHandler, register_handler_instance

class EmailNotificationHandler(EventHandler):
    def __init__(self, email_service):
        self.email_service = email_service

    @property
    def event_name(self):
        return "user_registered"

    async def handle(self, event, payload):
        await self.email_service.send(payload["user_id"])

# Register instance
email_service = EmailService()
handler = EmailNotificationHandler(email_service)
register_handler_instance(handler)
```

### Using EventEmitter

For more control:

```python
from core.events import EventEmitter

emitter = EventEmitter(background_tasks)

# Emit multiple events
emitter.emit("event_one", {"key": "value"})
emitter.emit("event_two", {"key": "value"})
```

### Correlation IDs

Track related events across handlers:

```python
correlation_id = emit_event(
    event_name="order_created",
    payload={"order_id": 456},
    background_tasks=background_tasks
)

# Use same correlation_id for related events
emit_event(
    event_name="inventory_updated",
    payload={"order_id": 456},
    background_tasks=background_tasks,
    correlation_id=correlation_id  # Same ID for tracing
)
```

## Event Structure

Every event has this structure:

```python
{
    "name": "event_name",
    "payload": {"key": "value"},
    "timestamp": "2024-01-01T12:00:00Z",
    "correlation_id": "uuid-string"
}
```

## Logging

All event emissions and handler executions are automatically logged with structured data:

```python
# Event emission log
{
    "message": "Event emitted: user_registered",
    "event_name": "user_registered",
    "correlation_id": "abc-123",
    "payload_keys": ["user_id"]
}

# Handler execution log
{
    "message": "Handler completed: send_welcome_email",
    "handler": "send_welcome_email",
    "event_name": "user_registered",
    "correlation_id": "abc-123",
    "execution_time_seconds": 0.5,
    "status": "success"
}
```

## Error Handling

Handlers run independently. If one fails, others continue:

```python
@register_handler("risky_event")
async def may_fail(event, payload):
    raise Exception("Oops!")  # Logged, but doesn't affect other handlers

@register_handler("risky_event")
async def always_succeeds(event, payload):
    print("This runs even if may_fail() crashes")
```

## Testing

```python
from core.events import clear_handlers, register_handler

def test_handler():
    # Clear existing handlers
    clear_handlers()

    # Register test handler
    results = []

    @register_handler("test_event")
    async def capture(event, payload):
        results.append(payload)

    # Test...
```

## Migration to Other AI Projects

1. Copy `core/` directory to new project
2. Import and use in app-specific code
3. No modifications needed to core framework

Example project structure:

```
my_new_project/
├── core/              # Copy this entire directory
│   └── events/
├── app/
│   ├── handlers/      # App-specific handlers
│   └── main.py        # Use core.events
```

## Philosophy

- **Phase 1 (Current)**: BackgroundTasks for simple, non-critical events
- **Phase 2 (Future)**: Add DB persistence for critical events
- **Phase 3 (Scale)**: Migrate to message queue (Redis, RabbitMQ)

The handler interface stays the same across all phases.

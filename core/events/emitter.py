import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import BackgroundTasks

from .types import create_event
from .handler import get_handlers

logger = logging.getLogger(__name__)


class EventEmitter:
    """
    Event emitter for background processing.

    Can be used as a singleton or instantiated per request/context.
    """

    def __init__(self, background_tasks: Optional[BackgroundTasks] = None):
        self.background_tasks = background_tasks

    def emit(
        self,
        event_name: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> str:
        """
        Emit an event and schedule handlers to run in the background

        Args:
            event_name: Name of the event (e.g., "message_received")
            payload: Event data
            correlation_id: Optional correlation ID for tracking
            background_tasks: BackgroundTasks instance (overrides instance-level)

        Returns:
            correlation_id for tracking this event
        """
        correlation_id = correlation_id or str(uuid.uuid4())

        event = create_event(
            name=event_name,
            payload=payload,
            correlation_id=correlation_id
        )

        logger.info(
            f"Event emitted: {event_name}",
            extra={
                "event_name": event_name,
                "correlation_id": correlation_id,
                "payload_keys": list(payload.keys())
            }
        )

        handlers = get_handlers(event_name)

        if not handlers:
            logger.warning(f"No handlers registered for event: {event_name}")
            return correlation_id

        # Use provided background_tasks or fall back to instance-level
        tasks = background_tasks or self.background_tasks

        if not tasks:
            raise ValueError(
                "No BackgroundTasks instance available. "
                "Pass it to emit() or set it in __init__()"
            )

        # Schedule all handlers to run in background
        for handler in handlers:
            tasks.add_task(
                _execute_handler,
                handler=handler,
                event=event,
                payload=payload
            )

        logger.info(
            f"Scheduled {len(handlers)} handlers for event {event_name}",
            extra={"correlation_id": correlation_id, "handler_count": len(handlers)}
        )

        return correlation_id


async def _execute_handler(
    handler,
    event: Dict[str, Any],
    payload: Dict[str, Any]
):
    """
    Execute a single event handler with error handling and logging
    """
    handler_name = handler.__name__ if hasattr(handler, '__name__') else str(handler)
    event_name = event["name"]
    correlation_id = event["correlation_id"]

    start_time = datetime.utcnow()

    try:
        logger.info(
            f"Handler started: {handler_name}",
            extra={
                "handler": handler_name,
                "event_name": event_name,
                "correlation_id": correlation_id
            }
        )

        await handler(event, payload)

        execution_time = (datetime.utcnow() - start_time).total_seconds()

        logger.info(
            f"Handler completed: {handler_name}",
            extra={
                "handler": handler_name,
                "event_name": event_name,
                "correlation_id": correlation_id,
                "execution_time_seconds": execution_time,
                "status": "success"
            }
        )

    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()

        logger.error(
            f"Handler failed: {handler_name} - {str(e)}",
            extra={
                "handler": handler_name,
                "event_name": event_name,
                "correlation_id": correlation_id,
                "execution_time_seconds": execution_time,
                "status": "failed",
                "error": str(e)
            },
            exc_info=True
        )


# Convenience function for direct emission
def emit_event(
    event_name: str,
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    correlation_id: Optional[str] = None
) -> str:
    """
    Convenience function to emit an event directly

    Usage:
        emit_event("message_received", {"message_id": 123}, background_tasks)
    """
    emitter = EventEmitter(background_tasks)
    return emitter.emit(event_name, payload, correlation_id)

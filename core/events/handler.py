import logging
from typing import Dict, Any, List, Callable, Awaitable
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Type alias for event handler functions
EventHandlerFunc = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[None]]

# Global registry of event handlers
_EVENT_HANDLERS: Dict[str, List[EventHandlerFunc]] = {}


class EventHandler(ABC):
    """
    Base class for event handlers.

    Subclass this to create handlers with state/dependencies.
    For simple handlers, use the @register_handler decorator instead.
    """

    @abstractmethod
    async def handle(self, event: Dict[str, Any], payload: Dict[str, Any]):
        """
        Handle the event

        Args:
            event: Full event object with metadata
            payload: Event payload data
        """
        pass

    @property
    @abstractmethod
    def event_name(self) -> str:
        """The event this handler listens to"""
        pass


def register_handler(event_name: str):
    """
    Decorator to register a function as an event handler

    Usage:
        @register_handler("message_received")
        async def process_message(event, payload):
            message_id = payload["message_id"]
            # ... handle event
    """
    def decorator(func: EventHandlerFunc):
        if event_name not in _EVENT_HANDLERS:
            _EVENT_HANDLERS[event_name] = []

        _EVENT_HANDLERS[event_name].append(func)
        logger.info(f"Registered handler '{func.__name__}' for event '{event_name}'")

        return func

    return decorator


def register_handler_instance(handler: EventHandler):
    """Register an EventHandler instance"""
    event_name = handler.event_name

    if event_name not in _EVENT_HANDLERS:
        _EVENT_HANDLERS[event_name] = []

    # Wrap the handler's handle method
    async def wrapper(event: Dict[str, Any], payload: Dict[str, Any]):
        await handler.handle(event, payload)

    _EVENT_HANDLERS[event_name].append(wrapper)
    logger.info(f"Registered handler instance '{handler.__class__.__name__}' for event '{event_name}'")


def get_handlers(event_name: str) -> List[EventHandlerFunc]:
    """Get all handlers for a specific event"""
    return _EVENT_HANDLERS.get(event_name, [])


def get_registered_handlers() -> Dict[str, List[str]]:
    """Get a dictionary of all registered handlers (for debugging/monitoring)"""
    result = {}
    for event_name, handlers in _EVENT_HANDLERS.items():
        result[event_name] = [
            handler.__name__ if hasattr(handler, '__name__') else str(handler)
            for handler in handlers
        ]
    return result


def clear_handlers(event_name: str = None):
    """
    Clear handlers. Useful for testing.

    Args:
        event_name: If provided, clear only handlers for this event.
                   If None, clear all handlers.
    """
    if event_name:
        _EVENT_HANDLERS[event_name] = []
    else:
        _EVENT_HANDLERS.clear()

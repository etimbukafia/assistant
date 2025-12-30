from typing import Dict, Any, TypedDict
from datetime import datetime


class Event(TypedDict):
    """Standard event structure"""
    name: str
    payload: Dict[str, Any]
    timestamp: str
    correlation_id: str


def create_event(
    name: str,
    payload: Dict[str, Any],
    correlation_id: str
) -> Event:
    """Create a standard event object"""
    return Event(
        name=name,
        payload=payload,
        timestamp=datetime.utcnow().isoformat(),
        correlation_id=correlation_id
    )

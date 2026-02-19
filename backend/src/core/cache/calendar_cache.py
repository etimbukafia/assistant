"""
Calendar Cache Service.

Owns all caching logic for calendar event views.
Routes and services call this — never hot_cache directly.
"""

from typing import Callable, TypeVar

from core.cache import hot_cache

T = TypeVar("T")

NAMESPACE = "calendar"


def get_or_build_events(user_id: str, cache_key: str, builder: Callable[[], T]) -> T:
    """Return cached event list or build it."""
    return hot_cache.get_or_set(user_id, NAMESPACE, cache_key, builder)


def get_or_build_event(user_id: str, event_id: int, builder: Callable[[], T]) -> T:
    """Return cached single event or build it."""
    return hot_cache.get_or_set(user_id, NAMESPACE, f"event:{event_id}", builder)


def invalidate_event(user_id: str, event_id: int):
    """Invalidate a single event's cache."""
    if user_id:
        hot_cache.invalidate(user_id, NAMESPACE, f"event:{event_id}")


def invalidate_all(user_id: str):
    """Invalidate all calendar cache for a user. Use after creates/deletes/syncs."""
    if user_id:
        hot_cache.invalidate_scope(user_id, NAMESPACE)

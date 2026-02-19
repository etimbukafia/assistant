"""
Thread Intelligence Cache Service.

Owns all caching logic for thread detail views.
Routes and services call this — never hot_cache directly.
"""

from typing import Callable, TypeVar

from core.cache import hot_cache

T = TypeVar("T")

NAMESPACE = "thread"


def get_or_build(user_id: str, thread_id: str, builder: Callable[[], T]) -> T:
    """Return cached thread detail or build it."""
    return hot_cache.get_or_set(user_id, NAMESPACE, thread_id, builder)


def invalidate(user_id: str, thread_id: str):
    """Invalidate a single thread's cached detail."""
    if user_id and thread_id:
        hot_cache.invalidate(user_id, NAMESPACE, thread_id)


def invalidate_all(user_id: str):
    """Invalidate all cached threads for a user."""
    if user_id:
        hot_cache.invalidate_scope(user_id, NAMESPACE)

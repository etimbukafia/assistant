"""Redis client helper with optional dependency and pooled connections."""

from __future__ import annotations

import os
from typing import Optional

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


_redis_client = None


def get_redis_client() -> Optional["redis.Redis"]:
    """Return a singleton Redis client. None if Redis is not configured/available."""
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    if redis is None:
        return None

    redis_url = os.getenv("PLAYGROUND_REDIS_URL") or os.getenv("REDIS_URL")
    if not redis_url:
        return None

    try:
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            health_check_interval=30,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            retry_on_timeout=True,
        )
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception:
        return None

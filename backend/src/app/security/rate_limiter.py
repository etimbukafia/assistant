"""
Rate Limiting Middleware

In-memory rate limiting with per-user limits based on subscription tier.
Uses token bucket algorithm for smooth rate limiting.
"""
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import defaultdict
import time
import threading
import logging

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.security.security_logger import log_rate_limit_hit, log_rate_limit_blocked

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration per tier."""
    requests_per_minute: int
    burst_limit: int  # Max tokens in bucket


# Rate limits by subscription tier
TIER_LIMITS: Dict[str, RateLimitConfig] = {
    "free": RateLimitConfig(requests_per_minute=20, burst_limit=5),
    "trial": RateLimitConfig(requests_per_minute=20, burst_limit=5),
    "pro": RateLimitConfig(requests_per_minute=60, burst_limit=15),
    "enterprise": RateLimitConfig(requests_per_minute=120, burst_limit=30),
    "unauthenticated": RateLimitConfig(requests_per_minute=10, burst_limit=3),
}

# Paths to rate limit (only expensive endpoints)
RATE_LIMITED_PATHS = {
    "/chat/sessions": True,
    "/messages/sync": True,
    "/messages/process": True,
}

# Paths that match prefix
RATE_LIMITED_PREFIXES = [
    "/chat/sessions/",  # All chat session operations
]


class TokenBucket:
    """
    Token bucket for rate limiting.
    Tokens refill at a constant rate, burst allows short spikes.
    """

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens per second to refill
            capacity: Maximum tokens (burst limit)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Try to consume tokens.

        Returns:
            Tuple of (success, retry_after_seconds)
        """
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                # Calculate wait time
                wait_time = (tokens - self.tokens) / self.rate
                return False, wait_time

    def get_remaining(self) -> int:
        """Get remaining tokens without consuming."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            current = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            return int(current)


class InMemoryRateLimiter:
    """
    In-memory rate limiter with automatic cleanup.
    Thread-safe for concurrent requests.
    """

    def __init__(self, cleanup_interval: int = 300):
        """
        Args:
            cleanup_interval: Seconds between cleanup of expired buckets
        """
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = cleanup_interval

    def get_bucket(self, key: str, config: RateLimitConfig) -> TokenBucket:
        """Get or create a token bucket for a key."""
        with self._lock:
            # Periodic cleanup
            now = time.monotonic()
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_expired()
                self._last_cleanup = now

            if key not in self._buckets:
                # Convert requests/minute to tokens/second
                rate = config.requests_per_minute / 60.0
                self._buckets[key] = TokenBucket(rate, config.burst_limit)

            return self._buckets[key]

    def _cleanup_expired(self):
        """Remove buckets that are full (inactive users)."""
        to_remove = []
        for key, bucket in self._buckets.items():
            if bucket.get_remaining() >= bucket.capacity:
                to_remove.append(key)

        for key in to_remove:
            del self._buckets[key]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} rate limit buckets")


# Global rate limiter instance
_rate_limiter = InMemoryRateLimiter()


def _should_rate_limit(path: str) -> bool:
    """Check if a path should be rate limited."""
    if path in RATE_LIMITED_PATHS:
        return True

    for prefix in RATE_LIMITED_PREFIXES:
        if path.startswith(prefix):
            return True

    return False


def _extract_user_info(request: Request) -> Tuple[Optional[str], str]:
    """
    Extract user ID and tier from request.

    Returns:
        Tuple of (user_id, tier)
    """
    # Try to get user info from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    tier = getattr(request.state, "subscription_tier", None)

    if user_id and tier:
        return user_id, tier

    # Try to extract from Authorization header (JWT)
    # Note: This is a simplified extraction - in production you'd decode the JWT
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 50:
        # Has a token - assume authenticated, default to trial
        # The actual tier would come from JWT claims or DB lookup
        return "authenticated_user", "trial"

    # Unauthenticated - use IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}", "unauthenticated"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Applies rate limits based on user tier and endpoint.
    """

    async def dispatch(self, request: Request, call_next):
        # Only rate limit specific paths
        if not _should_rate_limit(request.url.path):
            return await call_next(request)

        # Extract user info
        user_id, tier = _extract_user_info(request)
        config = TIER_LIMITS.get(tier, TIER_LIMITS["unauthenticated"])

        # Create rate limit key
        rate_key = f"{user_id}:{request.url.path}"

        # Get bucket and try to consume
        bucket = _rate_limiter.get_bucket(rate_key, config)
        allowed, retry_after = bucket.consume()

        if not allowed:
            # Log the block
            log_rate_limit_blocked(
                user_id=user_id if not user_id.startswith("ip:") else None,
                endpoint=request.url.path,
                retry_after_seconds=int(retry_after) + 1
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": int(retry_after) + 1
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": str(config.requests_per_minute),
                    "X-RateLimit-Remaining": "0"
                }
            )

        # Log if approaching limit (> 80% used)
        remaining = bucket.get_remaining()
        if remaining < config.burst_limit * 0.2:
            log_rate_limit_hit(
                user_id=user_id if not user_id.startswith("ip:") else None,
                endpoint=request.url.path,
                current_count=config.burst_limit - remaining,
                limit=config.burst_limit
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(config.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


# FastAPI dependency for more granular control
async def check_rate_limit(
    request: Request,
    endpoint_name: str = "default",
    cost: int = 1
) -> None:
    """
    Dependency for checking rate limits on specific endpoints.

    Usage:
        @router.post("/expensive-operation")
        async def expensive_op(
            _: None = Depends(lambda r: check_rate_limit(r, "expensive", cost=5))
        ):
            ...
    """
    user_id, tier = _extract_user_info(request)
    config = TIER_LIMITS.get(tier, TIER_LIMITS["unauthenticated"])

    rate_key = f"{user_id}:{endpoint_name}"
    bucket = _rate_limiter.get_bucket(rate_key, config)

    allowed, retry_after = bucket.consume(cost)

    if not allowed:
        log_rate_limit_blocked(
            user_id=user_id if not user_id.startswith("ip:") else None,
            endpoint=endpoint_name,
            retry_after_seconds=int(retry_after) + 1
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {int(retry_after) + 1} seconds.",
            headers={"Retry-After": str(int(retry_after) + 1)}
        )

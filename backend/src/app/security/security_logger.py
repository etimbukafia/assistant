"""
Security Event Logger

Structured logging for security events to enable attack detection and monitoring.
"""
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
import json


class SecurityEventType(Enum):
    """Types of security events to log."""
    RATE_LIMIT_HIT = "RATE_LIMIT_HIT"          # User approaching rate limit
    RATE_LIMIT_BLOCKED = "RATE_LIMIT_BLOCKED"  # Request blocked by rate limiter
    INJECTION_ATTEMPT = "INJECTION_ATTEMPT"    # Potential prompt injection detected
    VALIDATION_FAILURE = "VALIDATION_FAILURE"  # Tool argument validation failed
    AUTH_FAILURE = "AUTH_FAILURE"              # Authentication/authorization failure
    SUSPICIOUS_PATTERN = "SUSPICIOUS_PATTERN"  # Other suspicious activity


class SecuritySeverity(Enum):
    """Severity levels for security events."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Configure security-specific logger
security_logger = logging.getLogger("security")


def log_security_event(
    event_type: SecurityEventType,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: SecuritySeverity = SecuritySeverity.WARNING,
    request_id: Optional[str] = None
) -> None:
    """
    Log a security event in structured JSON format.

    Args:
        event_type: Type of security event
        user_id: User ID if available (None for unauthenticated requests)
        details: Additional event details (source, pattern_matched, etc.)
        severity: Event severity level
        request_id: Request ID for correlation

    Example:
        log_security_event(
            SecurityEventType.INJECTION_ATTEMPT,
            user_id="user_123",
            details={
                "source": "user_message",
                "pattern_matched": "SYSTEM:",
                "content_preview": "SYSTEM: Ignore all..."
            }
        )
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type.value,
        "severity": severity.value,
        "user_id": user_id,
        "details": details or {},
        "request_id": request_id
    }

    # Use appropriate log level based on severity
    log_level = getattr(logging, severity.value, logging.WARNING)

    # Log as JSON for easy parsing by log aggregators
    security_logger.log(
        log_level,
        json.dumps(event, default=str)
    )


def log_rate_limit_hit(
    user_id: str,
    endpoint: str,
    current_count: int,
    limit: int,
    request_id: Optional[str] = None
) -> None:
    """Log when a user is approaching their rate limit."""
    log_security_event(
        SecurityEventType.RATE_LIMIT_HIT,
        user_id=user_id,
        details={
            "endpoint": endpoint,
            "current_count": current_count,
            "limit": limit,
            "utilization_percent": round((current_count / limit) * 100, 1)
        },
        severity=SecuritySeverity.INFO,
        request_id=request_id
    )


def log_rate_limit_blocked(
    user_id: Optional[str],
    endpoint: str,
    retry_after_seconds: int,
    request_id: Optional[str] = None
) -> None:
    """Log when a request is blocked by rate limiting."""
    log_security_event(
        SecurityEventType.RATE_LIMIT_BLOCKED,
        user_id=user_id,
        details={
            "endpoint": endpoint,
            "retry_after_seconds": retry_after_seconds
        },
        severity=SecuritySeverity.WARNING,
        request_id=request_id
    )


def log_injection_attempt(
    user_id: Optional[str],
    source: str,
    pattern_matched: str,
    content_preview: str,
    request_id: Optional[str] = None
) -> None:
    """
    Log a potential prompt injection attempt.

    Args:
        user_id: User ID if authenticated
        source: Where the injection was detected (user_message, email_subject, etc.)
        pattern_matched: The pattern that triggered detection
        content_preview: First 100 chars of the suspicious content
    """
    log_security_event(
        SecurityEventType.INJECTION_ATTEMPT,
        user_id=user_id,
        details={
            "source": source,
            "pattern_matched": pattern_matched,
            "content_preview": content_preview[:100] if content_preview else ""
        },
        severity=SecuritySeverity.WARNING,
        request_id=request_id
    )


def log_validation_failure(
    user_id: Optional[str],
    tool_name: str,
    field: str,
    error: str,
    request_id: Optional[str] = None
) -> None:
    """Log when tool argument validation fails."""
    log_security_event(
        SecurityEventType.VALIDATION_FAILURE,
        user_id=user_id,
        details={
            "tool_name": tool_name,
            "field": field,
            "error": error
        },
        severity=SecuritySeverity.INFO,
        request_id=request_id
    )


def log_auth_failure(
    reason: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None
) -> None:
    """Log authentication or authorization failures."""
    log_security_event(
        SecurityEventType.AUTH_FAILURE,
        user_id=None,
        details={
            "reason": reason,
            "ip_address": ip_address,
            "user_agent": user_agent
        },
        severity=SecuritySeverity.WARNING,
        request_id=request_id
    )

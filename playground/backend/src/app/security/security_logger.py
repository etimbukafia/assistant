"""Minimal security logging helpers for playground."""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger("security")


def log_injection_attempt(user_id: str, source: str, pattern_matched: str, content_preview: str) -> None:
    logger.info(
        "injection_attempt user=%s source=%s pattern=%s preview=%s",
        user_id,
        source,
        pattern_matched,
        (content_preview or "")[:120],
    )


def log_validation_failure(user_id: str, tool_name: str, field: str, error: str, **extra: Any) -> None:
    logger.info(
        "validation_failure user=%s tool=%s field=%s error=%s extra=%s",
        user_id,
        tool_name,
        field,
        error,
        extra,
    )

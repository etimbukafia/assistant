from __future__ import annotations

import logging
from typing import Optional


logger = logging.getLogger(__name__)


def log_voice_capture_metric(
    *,
    user_id: str,
    stage: str,
    outcome: str,
    scope_type: Optional[str] = None,
    latency_ms: Optional[int] = None,
    duration_seconds: Optional[float] = None,
    transcript_chars: Optional[int] = None,
    final_chars: Optional[int] = None,
    shortened: Optional[bool] = None,
    reason: Optional[str] = None,
) -> None:
    logger.info(
        "voice_capture_metric user=%s stage=%s outcome=%s scope_type=%s latency_ms=%s duration_seconds=%s transcript_chars=%s final_chars=%s shortened=%s reason=%s",
        user_id,
        stage or "unknown",
        outcome or "unknown",
        scope_type or "unknown",
        max(0, int(latency_ms)) if latency_ms is not None else None,
        round(float(duration_seconds), 3) if duration_seconds is not None else None,
        max(0, int(transcript_chars)) if transcript_chars is not None else None,
        max(0, int(final_chars)) if final_chars is not None else None,
        bool(shortened) if shortened is not None else None,
        reason or None,
    )

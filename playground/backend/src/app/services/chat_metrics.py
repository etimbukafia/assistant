"""Playground stub metrics service for chat route parity."""

from __future__ import annotations

from typing import Any, Dict, Optional


def summarize_chat_metrics(
    db: Any,
    days: int = 7,
    user_id: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    # Minimal deterministic response for playground parity surface.
    return {
        "days": days,
        "total_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "latency_ms_p50": 0.0,
        "latency_ms_p90": 0.0,
        "latency_ms_p95": 0.0,
        "prompt_tokens_total": 0,
        "prompt_tokens_avg": 0.0,
        "repeated_prefix_rate_avg": 0.0,
        "repeated_prefix_rate_weighted": 0.0,
        "calls_by_model": {},
        "calls_by_path": {},
    }


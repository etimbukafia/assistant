"""Chat model-call metrics instrumentation and aggregation helpers."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.data.models import ChatModelCallMetric


PREFIX_BUCKETS = (64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384)


def build_prompt_text(messages: List[Dict[str, Any]]) -> str:
    """Serialize chat messages to a deterministic string for metrics only."""
    lines: List[str] = []
    for msg in messages or []:
        role = (msg.get("role") or "user").strip().lower()
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=True, separators=(",", ":"))
        lines.append(f"{role}:{content}")

        if role == "assistant":
            for call in msg.get("function_calls", []) or []:
                name = (call.get("name") or "").strip()
                args = call.get("arguments") or {}
                if not isinstance(args, dict):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw": str(args)}
                lines.append(
                    f"assistant_function_call:{name}:{json.dumps(args, sort_keys=True, ensure_ascii=True, separators=(',', ':'))}"
                )
        elif role == "tool":
            tool_name = (msg.get("name") or "").strip()
            tool_response = msg.get("response") or {}
            if not isinstance(tool_response, dict):
                tool_response = {"value": str(tool_response)}
            lines.append(
                f"tool_response:{tool_name}:{json.dumps(tool_response, sort_keys=True, ensure_ascii=True, separators=(',', ':'))}"
            )

    return "\n".join(lines)


def build_prefix_signature(prompt_text: str) -> Dict[str, Any]:
    """Build privacy-safe prefix hashes for repeated-prefix analysis."""
    text = prompt_text or ""
    text_len = len(text)
    segments: Dict[str, str] = {}

    if text_len <= 0:
        return {"length": 0, "segments": segments}

    for bucket in PREFIX_BUCKETS:
        if text_len < bucket:
            continue
        digest = hashlib.sha256(text[:bucket].encode("utf-8")).hexdigest()
        segments[str(bucket)] = digest

    # Always include full-length hash for short prompts.
    if str(text_len) not in segments:
        segments[str(text_len)] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return {"length": text_len, "segments": segments}


def repeated_prefix_chars(
    current_signature: Dict[str, Any],
    previous_signature: Optional[Dict[str, Any]],
) -> int:
    """Estimate repeated prefix length by matching prefix hashes."""
    if not previous_signature:
        return 0

    current_segments = current_signature.get("segments") or {}
    previous_segments = previous_signature.get("segments") or {}

    shared_lengths = []
    for key in current_segments.keys():
        if key in previous_segments:
            try:
                shared_lengths.append(int(key))
            except ValueError:
                continue

    for length in sorted(shared_lengths, reverse=True):
        key = str(length)
        if current_segments.get(key) == previous_segments.get(key):
            return length
    return 0


def record_chat_model_metric(
    *,
    db: Session,
    user_id: str,
    session_id: str,
    model: str,
    provider: str,
    path: str,
    prompt_text: str,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    tool_definitions_count: int,
    tool_calls_count: int,
    success: bool,
    error_type: Optional[str] = None,
    response_chars: int = 0,
) -> None:
    """Record one chat LLM model-call metric row (best-effort)."""
    prompt_signature = build_prefix_signature(prompt_text)

    previous = (
        db.query(ChatModelCallMetric)
        .filter(
            ChatModelCallMetric.user_id == user_id,
            ChatModelCallMetric.session_id == session_id,
        )
        .order_by(ChatModelCallMetric.id.desc())
        .first()
    )
    previous_signature = previous.prompt_prefix_signature if previous else None
    repeated_chars = repeated_prefix_chars(prompt_signature, previous_signature)
    prompt_chars = int(prompt_signature.get("length") or 0)
    repeated_rate = (repeated_chars / prompt_chars) if prompt_chars > 0 else 0.0

    row = ChatModelCallMetric(
        user_id=user_id,
        session_id=session_id,
        model=model,
        provider=provider,
        path=path,
        latency_ms=max(0, int(latency_ms)),
        prompt_chars=prompt_chars,
        response_chars=max(0, int(response_chars)),
        input_tokens=max(0, int(input_tokens)),
        output_tokens=max(0, int(output_tokens)),
        total_tokens=max(0, int(input_tokens) + int(output_tokens)),
        repeated_prefix_chars=max(0, int(repeated_chars)),
        repeated_prefix_rate=max(0.0, min(1.0, float(repeated_rate))),
        tool_definitions_count=max(0, int(tool_definitions_count)),
        tool_calls_count=max(0, int(tool_calls_count)),
        prompt_prefix_signature=prompt_signature,
        success=bool(success),
        error_type=(error_type or "")[:80] or None,
    )
    db.add(row)
    # Flush so multi-round calls in same transaction can compare against this row.
    db.flush()


def percentile(values: List[int], p: float) -> float:
    """Deterministic percentile without numpy dependency."""
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * p
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])

    lower_val = sorted_values[lower]
    upper_val = sorted_values[upper]
    weight = rank - lower
    return float(lower_val + ((upper_val - lower_val) * weight))


def summarize_chat_metrics(
    db: Session,
    *,
    days: int,
    user_id: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate model-call metrics for chat observability."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(ChatModelCallMetric).filter(ChatModelCallMetric.created_at >= since)
    if user_id:
        query = query.filter(ChatModelCallMetric.user_id == user_id)
    if model:
        query = query.filter(ChatModelCallMetric.model == model)

    rows: List[ChatModelCallMetric] = query.order_by(ChatModelCallMetric.created_at.desc()).all()
    if not rows:
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

    latencies = [int(r.latency_ms or 0) for r in rows]
    prompt_tokens = [int(r.input_tokens or 0) for r in rows]

    total_prompt_chars = sum(int(r.prompt_chars or 0) for r in rows)
    total_repeated_chars = sum(int(r.repeated_prefix_chars or 0) for r in rows)

    by_model: Dict[str, int] = {}
    by_path: Dict[str, int] = {}
    success_count = 0
    for row in rows:
        key_model = row.model or "unknown"
        key_path = row.path or "unknown"
        by_model[key_model] = by_model.get(key_model, 0) + 1
        by_path[key_path] = by_path.get(key_path, 0) + 1
        if row.success:
            success_count += 1

    return {
        "days": days,
        "total_calls": len(rows),
        "successful_calls": success_count,
        "failed_calls": len(rows) - success_count,
        "latency_ms_p50": round(percentile(latencies, 0.50), 2),
        "latency_ms_p90": round(percentile(latencies, 0.90), 2),
        "latency_ms_p95": round(percentile(latencies, 0.95), 2),
        "prompt_tokens_total": int(sum(prompt_tokens)),
        "prompt_tokens_avg": round(float(sum(prompt_tokens) / len(prompt_tokens)), 2),
        "repeated_prefix_rate_avg": round(
            float(sum(float(r.repeated_prefix_rate or 0.0) for r in rows) / len(rows)),
            4,
        ),
        "repeated_prefix_rate_weighted": round(
            (float(total_repeated_chars) / float(total_prompt_chars)) if total_prompt_chars > 0 else 0.0,
            4,
        ),
        "calls_by_model": by_model,
        "calls_by_path": by_path,
    }

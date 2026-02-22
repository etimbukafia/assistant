"""Chat model-call metrics instrumentation and aggregation helpers."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import math
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.data.models import ChatModelCallMetric


PREFIX_BUCKETS = (64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384)
_SIGNATURE_CACHE_MAX = max(1000, int(os.getenv("CHAT_METRICS_SIGNATURE_CACHE_SIZE", "10000")))
_signature_cache_lock = threading.RLock()
_signature_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def build_prompt_text(
    messages: List[Dict[str, Any]],
    *,
    max_messages: int = 6,
    max_total_chars: int = 4096,
    max_content_chars: int = 420,
    include_tool_payload: bool = False,
) -> str:
    """Serialize prompt content for metrics with strict size limits."""
    capped_messages = list(messages or [])[-max(1, int(max_messages)) :]
    lines: List[str] = []
    total_chars = 0
    for msg in capped_messages:
        role = (msg.get("role") or "user").strip().lower()
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=True, separators=(",", ":"))
        content = _truncate_text(content, max_content_chars)
        line = f"{role}:{content}"
        if total_chars + len(line) > max_total_chars:
            break
        lines.append(line)
        total_chars += len(line)

        if role == "assistant":
            for call in msg.get("function_calls", []) or []:
                name = (call.get("name") or "").strip()
                args = call.get("arguments") or {}
                if not isinstance(args, dict):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw": str(args)}
                arg_payload = (
                    json.dumps(args, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
                    if include_tool_payload
                    else json.dumps(sorted(list(args.keys())), ensure_ascii=True, separators=(",", ":"))
                )
                call_line = f"assistant_function_call:{name}:{arg_payload}"
                if total_chars + len(call_line) > max_total_chars:
                    break
                lines.append(call_line)
                total_chars += len(call_line)
        elif role == "tool":
            tool_name = (msg.get("name") or "").strip()
            tool_response = msg.get("response") or {}
            if not isinstance(tool_response, dict):
                tool_response = {"value": str(tool_response)}
            response_payload = (
                json.dumps(tool_response, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
                if include_tool_payload
                else json.dumps(sorted(list(tool_response.keys())), ensure_ascii=True, separators=(",", ":"))
            )
            tool_line = f"tool_response:{tool_name}:{response_payload}"
            if total_chars + len(tool_line) > max_total_chars:
                break
            lines.append(tool_line)
            total_chars += len(tool_line)
        if total_chars >= max_total_chars:
            break

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
    flush: bool = False,
) -> None:
    """Record one chat LLM model-call metric row (best-effort)."""
    prompt_signature = build_prefix_signature(prompt_text)
    previous_signature = _get_cached_signature(user_id=user_id, session_id=session_id)
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
    _set_cached_signature(user_id=user_id, session_id=session_id, signature=prompt_signature)
    if flush:
        db.flush()


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[: max(0, max_chars - 1)]}~"


def _cache_key(user_id: str, session_id: str) -> str:
    return f"{user_id}:{session_id}"


def _get_cached_signature(user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    key = _cache_key(user_id, session_id)
    with _signature_cache_lock:
        signature = _signature_cache.get(key)
        if signature is None:
            return None
        _signature_cache.move_to_end(key)
        return signature


def _set_cached_signature(user_id: str, session_id: str, signature: Dict[str, Any]) -> None:
    key = _cache_key(user_id, session_id)
    with _signature_cache_lock:
        _signature_cache[key] = signature
        _signature_cache.move_to_end(key)
        while len(_signature_cache) > _SIGNATURE_CACHE_MAX:
            _signature_cache.popitem(last=False)


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

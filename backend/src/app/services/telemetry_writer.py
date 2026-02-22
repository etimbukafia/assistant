"""Asynchronous telemetry writer for non-critical chat analytics."""

from __future__ import annotations

import logging
import os
import queue
import threading
from typing import Any, Dict, List

from app.infra.database import SessionLocal
from app.services.chat_metrics import build_prompt_text, record_chat_model_metric
from core.llm.token_tracking import record_token_usage


logger = logging.getLogger(__name__)

_QUEUE_MAX_SIZE = max(100, int(os.getenv("TELEMETRY_QUEUE_MAX_SIZE", "5000")))
_BATCH_SIZE = max(1, int(os.getenv("TELEMETRY_BATCH_SIZE", "100")))
_POLL_TIMEOUT_SECONDS = max(0.05, float(os.getenv("TELEMETRY_POLL_TIMEOUT_SECONDS", "0.25")))
_WARN_EVERY_DROPS = max(1, int(os.getenv("TELEMETRY_WARN_EVERY_DROPS", "100")))


class TelemetryWriterService:
    """Fire-and-forget writer for chat metrics and token usage."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=_QUEUE_MAX_SIZE)
        self._started = False
        self._start_lock = threading.Lock()
        self._dropped_events = 0

    def enqueue_chat_metric(
        self,
        *,
        user_id: str,
        session_id: str,
        model: str,
        provider: str,
        path: str,
        messages: List[Dict[str, Any]],
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        tool_definitions_count: int,
        tool_calls_count: int,
        success: bool,
        error_type: str | None = None,
        response_chars: int = 0,
    ) -> None:
        event = {
            "kind": "chat_metric",
            "payload": {
                "user_id": user_id,
                "session_id": session_id,
                "model": model,
                "provider": provider,
                "path": path,
                "messages": messages,
                "latency_ms": int(latency_ms),
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "tool_definitions_count": int(tool_definitions_count),
                "tool_calls_count": int(tool_calls_count),
                "success": bool(success),
                "error_type": error_type,
                "response_chars": int(response_chars),
            },
        }
        self._enqueue(event)

    def enqueue_token_usage(
        self,
        *,
        user_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str,
    ) -> None:
        event = {
            "kind": "token_usage",
            "payload": {
                "user_id": user_id,
                "model": model,
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "operation": operation,
            },
        }
        self._enqueue(event)

    def _enqueue(self, event: Dict[str, Any]) -> None:
        self._ensure_started()
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._dropped_events += 1
            if self._dropped_events % _WARN_EVERY_DROPS == 0:
                logger.warning(
                    "telemetry_queue_dropped total=%s reason=queue_full maxsize=%s",
                    self._dropped_events,
                    _QUEUE_MAX_SIZE,
                )

    def _ensure_started(self) -> None:
        if self._started:
            return
        with self._start_lock:
            if self._started:
                return
            thread = threading.Thread(target=self._run_loop, name="telemetry-writer", daemon=True)
            thread.start()
            self._started = True

    def _run_loop(self) -> None:
        while True:
            batch: List[Dict[str, Any]] = []
            try:
                first = self._queue.get(timeout=_POLL_TIMEOUT_SECONDS)
                batch.append(first)
                while len(batch) < _BATCH_SIZE:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                continue

            self._process_batch(batch)

    def _process_batch(self, events: List[Dict[str, Any]]) -> None:
        db = SessionLocal()
        try:
            for event in events:
                kind = event.get("kind")
                payload = event.get("payload") or {}
                if kind == "chat_metric":
                    prompt_text = build_prompt_text(payload.get("messages") or [])
                    record_chat_model_metric(
                        db=db,
                        user_id=payload.get("user_id") or "",
                        session_id=payload.get("session_id") or "unknown",
                        model=payload.get("model") or "unknown",
                        provider=payload.get("provider") or "unknown",
                        path=payload.get("path") or "unknown",
                        prompt_text=prompt_text,
                        latency_ms=int(payload.get("latency_ms") or 0),
                        input_tokens=int(payload.get("input_tokens") or 0),
                        output_tokens=int(payload.get("output_tokens") or 0),
                        tool_definitions_count=int(payload.get("tool_definitions_count") or 0),
                        tool_calls_count=int(payload.get("tool_calls_count") or 0),
                        success=bool(payload.get("success")),
                        error_type=payload.get("error_type"),
                        response_chars=int(payload.get("response_chars") or 0),
                        flush=False,
                    )
                elif kind == "token_usage":
                    record_token_usage(
                        db=db,
                        user_id=payload.get("user_id") or "",
                        model=payload.get("model") or "unknown",
                        input_tokens=int(payload.get("input_tokens") or 0),
                        output_tokens=int(payload.get("output_tokens") or 0),
                        operation=payload.get("operation") or "chat",
                        flush_credits=False,
                    )
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("telemetry_batch_failed size=%s", len(events), exc_info=True)
        finally:
            db.close()


_telemetry_writer_singleton: TelemetryWriterService | None = None


def get_telemetry_writer() -> TelemetryWriterService:
    global _telemetry_writer_singleton
    if _telemetry_writer_singleton is None:
        _telemetry_writer_singleton = TelemetryWriterService()
    return _telemetry_writer_singleton

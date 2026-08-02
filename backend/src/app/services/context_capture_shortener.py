from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from app.security.prompt_sanitizer import sanitize_with_detection, wrap_user_content
from app.services.voice_capture_observability import log_voice_capture_metric
from core.llm.config import LLMConfig
from core.llm.orchestrator import LLMOrchestrator

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "shorten_context_capture.md"


@dataclass
class ContextCaptureShortenResult:
    text: str
    shortened: bool


@lru_cache(maxsize=1)
def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _truncate_to_limit(text: str, max_chars: int) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= max_chars:
        return normalized
    clipped = normalized[: max_chars - 1].rstrip(" .,;:-")
    return f"{clipped}…"


def deterministic_shorten_context_capture_text(*, transcript: str, max_chars: int) -> str:
    return _truncate_to_limit(transcript, max_chars)


def shorten_context_capture_text(
    *,
    transcript: str,
    max_chars: int,
    scope_type: str,
    scope_label: str | None,
) -> ContextCaptureShortenResult:
    started_at = perf_counter()
    normalized = _normalize_text(transcript)
    if len(normalized) <= max_chars:
        return ContextCaptureShortenResult(text=normalized, shortened=False)

    try:
        prompt_template = _load_prompt_template()
    except Exception as exc:
        logger.warning("Failed to load context capture shortener prompt: %s", exc)
        log_voice_capture_metric(
            user_id="unknown",
            stage="shortening",
            outcome="fallback",
            scope_type=scope_type,
            transcript_chars=len(normalized),
            final_chars=min(len(normalized), max_chars),
            shortened=True,
            reason="prompt_unavailable",
        )
        return ContextCaptureShortenResult(
            text=deterministic_shorten_context_capture_text(transcript=normalized, max_chars=max_chars),
            shortened=True,
        )

    transcript_sanitized = sanitize_with_detection(normalized)
    scope_sanitized = sanitize_with_detection((scope_label or "").strip())

    prompt = prompt_template.format(
        max_chars=max_chars,
        scope_type=scope_type,
        scope_label=wrap_user_content(scope_sanitized.sanitized_text or "none", tag="scope"),
        transcript_text=wrap_user_content(transcript_sanitized.sanitized_text, tag="transcript"),
    )

    if transcript_sanitized.patterns_detected or scope_sanitized.patterns_detected:
        logger.info(
            "context_capture_shortening_input_sanitized scope_type=%s transcript_patterns=%s scope_patterns=%s",
            scope_type,
            transcript_sanitized.patterns_detected,
            scope_sanitized.patterns_detected,
        )

    try:
        orchestrator = LLMOrchestrator(config=LLMConfig.for_email())
        shortened = orchestrator.generate_text(
            prompt,
            max_output_tokens=min(512, max_chars),
            temperature=0.1,
        )
    except Exception as exc:
        logger.warning("Context capture shortening failed: %s", exc, exc_info=True)
        log_voice_capture_metric(
            user_id="unknown",
            stage="shortening",
            outcome="fallback",
            scope_type=scope_type,
            latency_ms=int((perf_counter() - started_at) * 1000),
            transcript_chars=len(normalized),
            final_chars=min(len(normalized), max_chars),
            shortened=True,
            reason="llm_failure",
        )
        return ContextCaptureShortenResult(
            text=deterministic_shorten_context_capture_text(transcript=normalized, max_chars=max_chars),
            shortened=True,
        )

    final_text = _normalize_text(shortened)
    if not final_text:
        final_text = deterministic_shorten_context_capture_text(transcript=normalized, max_chars=max_chars)
    elif len(final_text) > max_chars:
        final_text = deterministic_shorten_context_capture_text(transcript=final_text, max_chars=max_chars)

    result = ContextCaptureShortenResult(
        text=final_text,
        shortened=True,
    )
    log_voice_capture_metric(
        user_id="unknown",
        stage="shortening",
        outcome="completed",
        scope_type=scope_type,
        latency_ms=int((perf_counter() - started_at) * 1000),
        transcript_chars=len(normalized),
        final_chars=len(final_text),
        shortened=True,
        reason="llm_shortener",
    )
    return result

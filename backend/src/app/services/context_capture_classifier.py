from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

from app.data.models import ContextEntry, DiaryEntryLink
from app.security.prompt_sanitizer import sanitize_with_detection, wrap_user_content
from core.llm.config import LLMConfig
from core.llm.orchestrator import LLMOrchestrator

logger = logging.getLogger(__name__)

ALLOWED_CONTEXT_CATEGORIES = {"decision", "risk", "commitment", "preference", "insight"}
LOW_CONFIDENCE_THRESHOLD = 0.6
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "classify_context_capture.md"


@dataclass
class ContextCaptureClassificationResult:
    category: str
    confidence: float
    uncertain: bool
    secondary_links: list[dict[str, str]] = field(default_factory=list)


@lru_cache(maxsize=1)
def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _normalize_category(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"preferences"}:
        normalized = "preference"
    if normalized in {"risks"}:
        normalized = "risk"
    if normalized in {"relationship", "relationships"}:
        normalized = "insight"
    if normalized not in ALLOWED_CONTEXT_CATEGORIES:
        return "insight"
    return normalized


def _normalize_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(confidence, 1.0))


def _render_links(links: Iterable[DiaryEntryLink]) -> str:
    rendered: list[str] = []
    for link in links:
        entity_type = (getattr(link, "entity_type", "") or "").strip().lower()
        if entity_type not in {"contact", "message", "event", "task", "thread"}:
            entity_type = "context"
        label = (getattr(link, "display_name", "") or "").strip()
        if not label:
            continue
        rendered.append(f"- {entity_type}: {wrap_user_content(label, tag='link')}")
    return "\n".join(rendered) if rendered else "- none"


def _fallback_result(reason: str) -> ContextCaptureClassificationResult:
    logger.info("context_capture_classification_fallback reason=%s", reason)
    return ContextCaptureClassificationResult(
        category="insight",
        confidence=0.0,
        uncertain=True,
        secondary_links=[],
    )


def classify_context_capture(entry: ContextEntry) -> ContextCaptureClassificationResult:
    capture_text = (entry.raw_text or entry.content or "").strip()
    if not capture_text:
        return _fallback_result("Empty capture; defaulted to insight.")

    try:
        prompt_template = _load_prompt_template()
    except Exception as exc:
        logger.warning("Failed to load context capture classifier prompt: %s", exc)
        return _fallback_result("Classifier prompt unavailable; defaulted to insight.")

    capture_sanitized = sanitize_with_detection(capture_text)
    scope_label = sanitize_with_detection((entry.linked_to or "").strip())
    links_block = _render_links(getattr(entry, "links", []) or [])

    prompt = prompt_template.format(
        scope_type=entry.entity_type,
        scope_label=wrap_user_content(scope_label.sanitized_text or "none", tag="scope"),
        links_block=links_block,
        capture_text=wrap_user_content(capture_sanitized.sanitized_text, tag="capture"),
    )

    if capture_sanitized.patterns_detected or scope_label.patterns_detected:
        logger.info(
            "context_capture_classification_input_sanitized entry_id=%s capture_patterns=%s scope_patterns=%s",
            getattr(entry, "id", None),
            capture_sanitized.patterns_detected,
            scope_label.patterns_detected,
        )

    try:
        orchestrator = LLMOrchestrator(config=LLMConfig.for_email())
        raw = orchestrator.generate(prompt)
    except Exception as exc:
        logger.warning("Context capture classification failed: %s", exc, exc_info=True)
        return _fallback_result("Classifier unavailable; defaulted to insight.")

    if not isinstance(raw, dict):
        return _fallback_result("Classifier returned invalid response; defaulted to insight.")
    if raw.get("_error"):
        logger.warning("Context capture classifier returned error payload: %s", json.dumps(raw)[:200])
        return _fallback_result("Classifier unavailable; defaulted to insight.")

    category = _normalize_category(raw.get("category"))
    confidence = _normalize_confidence(raw.get("confidence"))
    uncertain = confidence < LOW_CONFIDENCE_THRESHOLD

    return ContextCaptureClassificationResult(
        category=category,
        confidence=confidence,
        uncertain=uncertain,
        secondary_links=[],
    )

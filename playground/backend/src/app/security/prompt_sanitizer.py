"""Lightweight prompt-sanitizer stubs for playground chat."""

from __future__ import annotations

import re
from typing import Any, Dict, List


INJECTION_PATTERNS = [
    re.compile(r"ignore (previous|above) instructions", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"developer message", re.IGNORECASE),
    re.compile(r"tool schema", re.IGNORECASE),
]


def detect_injection_patterns(text: str) -> List[str]:
    value = text or ""
    matches: List[str] = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(value):
            matches.append(pattern.pattern)
    return matches


def sanitize_for_prompt(value: Any) -> str:
    return str(value or "")


def wrap_user_content(value: str) -> str:
    return str(value or "")


def detect_injection_attempt(value: str) -> bool:
    return bool(detect_injection_patterns(value))


def sanitize_email_content(subject: str | None, sender: str | None, body: str | None) -> Dict[str, Any]:
    return {
        "subject": sanitize_for_prompt(subject),
        "sender": sanitize_for_prompt(sender),
        "body_preview": sanitize_for_prompt(body)[:800],
        "patterns_detected": detect_injection_patterns(body or ""),
    }


def sanitize_task_content(title: str | None, description: str | None) -> Dict[str, Any]:
    raw = f"{title or ''}\n{description or ''}"
    return {
        "title": sanitize_for_prompt(title),
        "description": sanitize_for_prompt(description),
        "patterns_detected": detect_injection_patterns(raw),
    }

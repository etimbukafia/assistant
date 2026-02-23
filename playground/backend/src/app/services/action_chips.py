"""Playground action chips service (fast deterministic defaults)."""

from __future__ import annotations

from typing import Any, Dict, List


_DEFAULT_CHIPS: List[Dict[str, str]] = [
    {"id": "chip_1", "label": "Draft quick update to a contact", "prompt": "Draft a concise update email I can send now."},
    {"id": "chip_2", "label": "Prep me for a meeting", "prompt": "Prep me for my next meeting: agenda, risks, decisions, and talking points."},
    {"id": "chip_3", "label": "Turn notes into a brief", "prompt": "Turn this into a one-page brief with decisions, commitments, and open questions."},
    {"id": "chip_4", "label": "What changed since yesterday?", "prompt": "What changed since yesterday? Keep it tight and action-oriented."},
    {"id": "chip_5", "label": "Extract commitments", "prompt": "Extract commitments and owners from recent messages, then suggest next actions."},
]


def get_cached_action_chips(
    db: Any,
    warm_cache: Any,
    tenant_id: str,
    user_id: str,
    limit: int = 5,
) -> List[Dict[str, str]]:
    return _DEFAULT_CHIPS[: max(1, min(limit, len(_DEFAULT_CHIPS)))]


def prewarm_action_chips(
    db: Any,
    warm_cache: Any,
    tenant_id: str,
    user_id: str,
) -> None:
    # No-op in playground currently.
    return None


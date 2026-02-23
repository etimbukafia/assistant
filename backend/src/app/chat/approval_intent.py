"""
Parse user chat text into deterministic approval decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Iterable, List, Sequence, Set


class ApprovalIntentKind(str, Enum):
    NONE = "none"
    APPROVE_ALL = "approve_all"
    APPROVE_SUBSET = "approve_subset"
    REJECT_SUBSET = "reject_subset"
    CANCEL_ALL = "cancel_all"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class PendingActionRef:
    id: str
    index: int  # 1-based display order
    action_type: str


@dataclass(frozen=True)
class ApprovalIntent:
    kind: ApprovalIntentKind
    approve_ids: Set[str] = field(default_factory=set)
    reject_ids: Set[str] = field(default_factory=set)
    reason: str = ""


_CANCEL_ALL_RE = re.compile(r"\b(cancel|stop|never\s*mind|forget\s*it)\b", re.IGNORECASE)
_APPROVE_ALL_RE = re.compile(
    r"\b(proceed|continue|approve\s+all|run\s+all|go\s+ahead|yes|do\s+it)\b",
    re.IGNORECASE,
)
_APPROVE_SEG_RE = re.compile(r"\b(run|approve|do)\b([^.]*)", re.IGNORECASE)
_REJECT_SEG_RE = re.compile(r"\b(skip|reject|dont|don't)\b([^.]*)", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+")


def _extract_numbers(text: str) -> List[int]:
    return [int(value) for value in _NUMBER_RE.findall(text or "")]


def _index_map(pending: Sequence[PendingActionRef]) -> dict[int, str]:
    return {item.index: item.id for item in pending}


def _action_type_map(pending: Sequence[PendingActionRef]) -> dict[str, Set[str]]:
    out: dict[str, Set[str]] = {}
    for item in pending:
        key = (item.action_type or "").strip().lower()
        if not key:
            continue
        out.setdefault(key, set()).add(item.id)
    return out


def _expand_indexes(indexes: Iterable[int], pending: Sequence[PendingActionRef]) -> Set[str]:
    idx = _index_map(pending)
    return {idx[i] for i in indexes if i in idx}


def parse_approval_intent(message: str, pending_actions: Sequence[PendingActionRef]) -> ApprovalIntent:
    """
    Convert user text into approval intent for currently pending actions.
    """
    text = " ".join((message or "").strip().split())
    if not text or not pending_actions:
        return ApprovalIntent(kind=ApprovalIntentKind.NONE, reason="no_pending_or_empty_message")

    # Treat the first sentence as the command and the rest as optional note/edit context.
    command_text = text.split(".", 1)[0].strip() or text
    lowered = command_text.lower()

    if _CANCEL_ALL_RE.search(lowered):
        return ApprovalIntent(
            kind=ApprovalIntentKind.CANCEL_ALL,
            reject_ids={item.id for item in pending_actions},
            reason="cancel_keyword",
        )

    if _APPROVE_ALL_RE.search(lowered) and not re.search(r"\b(skip|reject)\b", lowered):
        return ApprovalIntent(
            kind=ApprovalIntentKind.APPROVE_ALL,
            approve_ids={item.id for item in pending_actions},
            reason="approve_all_keyword",
        )

    approve_ids: Set[str] = set()
    reject_ids: Set[str] = set()
    type_lookup = _action_type_map(pending_actions)

    # Parse explicit approve segments: "run 1 and 3", "approve 2"
    for match in _APPROVE_SEG_RE.finditer(command_text):
        segment = match.group(2) or ""
        approve_ids.update(_expand_indexes(_extract_numbers(segment), pending_actions))
        for action_type, ids in type_lookup.items():
            if action_type and action_type in segment.lower():
                approve_ids.update(ids)

    # Parse explicit reject segments: "skip 2", "don't run 4"
    for match in _REJECT_SEG_RE.finditer(command_text):
        segment = match.group(2) or ""
        reject_ids.update(_expand_indexes(_extract_numbers(segment), pending_actions))
        for action_type, ids in type_lookup.items():
            if action_type and action_type in segment.lower():
                reject_ids.update(ids)

    # Fallback: bare numeric selection implies approve subset.
    if not approve_ids and not reject_ids:
        bare_numbers = _extract_numbers(command_text)
        if bare_numbers:
            approve_ids = _expand_indexes(bare_numbers, pending_actions)

    approve_ids -= reject_ids

    if approve_ids and reject_ids:
        return ApprovalIntent(
            kind=ApprovalIntentKind.APPROVE_SUBSET,
            approve_ids=approve_ids,
            reject_ids=reject_ids,
            reason="mixed_subset_selection",
        )
    if approve_ids:
        return ApprovalIntent(
            kind=ApprovalIntentKind.APPROVE_SUBSET,
            approve_ids=approve_ids,
            reason="approve_subset_selection",
        )
    if reject_ids:
        return ApprovalIntent(
            kind=ApprovalIntentKind.REJECT_SUBSET,
            reject_ids=reject_ids,
            reason="reject_subset_selection",
        )

    # If text appears approval-related but couldn't resolve targets, ask clarification.
    if re.search(r"\b(proceed|continue|approve|run|skip|reject|yes|cancel)\b", lowered):
        return ApprovalIntent(kind=ApprovalIntentKind.AMBIGUOUS, reason="approval_like_but_unresolved")

    return ApprovalIntent(kind=ApprovalIntentKind.NONE, reason="no_approval_signal")

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Tuple

from sqlalchemy import false, or_

from app.data.models import ContextEntry


LOW_CONFIDENCE_RETRIEVAL_THRESHOLD = 0.6
HISTORICAL_RETRIEVAL_TYPES = ("decision", "decisions")


def confidence_retrieval_clause():
    """
    Allow retrieval for:
    - user-corrected entries
    - legacy/manual entries without a classifier confidence
    - entries at or above the retrieval threshold
    """
    return or_(
        ContextEntry.user_corrected.is_(True),
        ContextEntry.classification_confidence.is_(None),
        ContextEntry.classification_confidence >= LOW_CONFIDENCE_RETRIEVAL_THRESHOLD,
    )


def apply_confidence_retrieval_filter(query):
    return query.filter(confidence_retrieval_clause())


def historical_expiry_retrieval_clause(
    *,
    now: datetime | None = None,
    historical_types: Iterable[str] | None = None,
):
    current_time = now or datetime.now(timezone.utc)
    normalized_types = tuple(
        sorted(
            {
                str(item).strip().lower()
                for item in (historical_types or HISTORICAL_RETRIEVAL_TYPES)
                if str(item).strip().lower()
            }
        )
    )
    if not normalized_types:
        return or_(ContextEntry.expires_at.is_(None), ContextEntry.expires_at >= current_time)
    return or_(
        ContextEntry.expires_at.is_(None),
        ContextEntry.expires_at >= current_time,
        ContextEntry.type.in_(normalized_types),
    )


def apply_historical_expiry_retrieval_filter(
    query,
    *,
    now: datetime | None = None,
    historical_types: Iterable[str] | None = None,
):
    return query.filter(
        historical_expiry_retrieval_clause(now=now, historical_types=historical_types)
    )


def lifecycle_retrieval_clause(*, allowed_statuses: Iterable[str] | None = None):
    if allowed_statuses is None:
        return ContextEntry.status != "forgotten"

    normalized = tuple(
        sorted(
            {
                str(status).strip().lower()
                for status in (allowed_statuses or [])
                if str(status).strip().lower() and str(status).strip().lower() != "forgotten"
            }
        )
    )
    if not normalized:
        return false()
    return ContextEntry.status.in_(normalized)


def apply_memory_retrieval_filter(query, *, allowed_statuses: Iterable[str] | None = None):
    return query.filter(confidence_retrieval_clause()).filter(
        lifecycle_retrieval_clause(allowed_statuses=allowed_statuses)
    )


def is_retrieval_status_allowed(
    *,
    status: str | None,
    allowed_statuses: Iterable[str] | None = None,
) -> bool:
    normalized_status = str(status or "").strip().lower() or "active"
    if normalized_status == "forgotten":
        return False
    if allowed_statuses is None:
        return True
    normalized_allowed = {
        str(item).strip().lower()
        for item in (allowed_statuses or [])
        if str(item).strip().lower() and str(item).strip().lower() != "forgotten"
    }
    return normalized_status in normalized_allowed


def is_retrieval_confident(
    *,
    classification_confidence: float | None,
    user_corrected: bool,
) -> bool:
    if user_corrected:
        return True
    if classification_confidence is None:
        return True
    return bool(classification_confidence >= LOW_CONFIDENCE_RETRIEVAL_THRESHOLD)


def is_expiry_retrievable(
    *,
    entry_type: str | None,
    expires_at: datetime | str | None,
    now: datetime | None = None,
    historical_types: Iterable[str] | None = None,
) -> bool:
    normalized_type = str(entry_type or "").strip().lower()
    allowed_historical = {
        str(item).strip().lower()
        for item in (historical_types or HISTORICAL_RETRIEVAL_TYPES)
        if str(item).strip().lower()
    }
    if normalized_type in allowed_historical:
        return True
    if expires_at is None:
        return True
    current_time = now or datetime.now(timezone.utc)
    if isinstance(expires_at, datetime):
        expiry = expires_at
    else:
        text = str(expires_at).strip()
        if not text:
            return True
        try:
            expiry = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry >= current_time


def ages_as_stale_in_diary(*, entry_type: str | None) -> bool:
    normalized_type = str(entry_type or "").strip().lower()
    return normalized_type not in set(HISTORICAL_RETRIEVAL_TYPES)

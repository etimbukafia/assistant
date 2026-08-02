from __future__ import annotations

import logging
from typing import Optional


logger = logging.getLogger(__name__)


def log_contact_brief_metric(
    *,
    user_id: str,
    contact_id: int,
    consumer: str,
    found: bool,
    latency_ms: int,
    context_count: int = 0,
    message_count: int = 0,
    task_count: int = 0,
    event_count: int = 0,
    commitment_count: int = 0,
    decision_count: int = 0,
    signal_count: int = 0,
) -> None:
    logger.info(
        "contact_brief_metric user=%s contact_id=%s consumer=%s found=%s latency_ms=%s context_count=%s message_count=%s task_count=%s event_count=%s commitment_count=%s decision_count=%s signal_count=%s",
        user_id,
        contact_id,
        consumer or "unknown",
        found,
        max(0, int(latency_ms)),
        max(0, int(context_count)),
        max(0, int(message_count)),
        max(0, int(task_count)),
        max(0, int(event_count)),
        max(0, int(commitment_count)),
        max(0, int(decision_count)),
        max(0, int(signal_count)),
    )


def log_contact_linkage_metric(
    *,
    user_id: str,
    source: str,
    matched: bool,
    resolution_method: str,
    candidate_count: int,
    contact_id: Optional[int] = None,
) -> None:
    logger.info(
        "contact_linkage_metric user=%s source=%s matched=%s resolution_method=%s candidate_count=%s contact_id=%s",
        user_id,
        source or "unknown",
        matched,
        resolution_method or "none",
        max(0, int(candidate_count)),
        int(contact_id) if contact_id is not None else None,
    )


def log_contact_signals_metric(
    *,
    user_id: str,
    contact_id: int,
    consumer: str,
    signal_count: int,
    high_count: int,
    medium_count: int,
    latency_ms: int,
) -> None:
    logger.info(
        "contact_signals_metric user=%s contact_id=%s consumer=%s signal_count=%s high_count=%s medium_count=%s latency_ms=%s",
        user_id,
        contact_id,
        consumer or "unknown",
        max(0, int(signal_count)),
        max(0, int(high_count)),
        max(0, int(medium_count)),
        max(0, int(latency_ms)),
    )

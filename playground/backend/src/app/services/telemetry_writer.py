"""Non-blocking telemetry writer shim for playground."""

from __future__ import annotations

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


class TelemetryWriter:
    def enqueue_chat_metric(self, record: Dict[str, Any]) -> None:
        logger.debug("chat_metric_enqueued %s", record)

    def enqueue_token_usage(self, record: Dict[str, Any]) -> None:
        logger.debug("token_usage_enqueued %s", record)


_writer: TelemetryWriter | None = None


def get_telemetry_writer() -> TelemetryWriter:
    global _writer
    if _writer is None:
        _writer = TelemetryWriter()
    return _writer

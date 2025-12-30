import logging
import sys
from typing import Any
import json


class StructuredFormatter(logging.Formatter):
    """
    Format logs with structured data (JSON-like) for better observability
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base log message
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        if hasattr(record, "event_name"):
            log_data["event_name"] = record.event_name
        if hasattr(record, "handler"):
            log_data["handler"] = record.handler
        if hasattr(record, "execution_time_seconds"):
            log_data["execution_time_seconds"] = record.execution_time_seconds
        if hasattr(record, "status"):
            log_data["status"] = record.status

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO", structured: bool = False):
    """
    Configure logging for the application

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        structured: Use structured JSON logging
    """
    handlers = [logging.StreamHandler(sys.stdout)]

    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=handlers,
        force=True
    )

    # Set level for specific loggers
    logging.getLogger("core.events").setLevel(logging.INFO)
    logging.getLogger("app.handlers").setLevel(logging.INFO)

    # Suppress noisy third-party warnings
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

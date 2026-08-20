"""Structured JSON logging with a request/job correlation id.

Every log line is a single JSON object, which plays well with log aggregators
(Railway, Datadog, etc.). A ``correlation_id`` contextvar is stamped onto every
record so all logs for one request/job can be grepped together.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "cid": correlation_id.get(),
        }
        # Merge any structured extras passed via logger.info(..., extra={"extra": {...}})
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Uvicorn access logs are noisy and duplicate ours; quiet them a notch.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, msg: str, **fields) -> None:
    """Emit a log line with structured fields merged into the JSON payload."""
    logger.log(level, msg, extra={"extra": fields})

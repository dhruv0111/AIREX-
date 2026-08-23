"""Structured logging (spec §55–§56).

Logs are JSON-shaped (production) or human-readable (development), and every
record carries: timestamp, level, service, request_id, user_id,
organization_id, message.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

# Request-scoped context populated by the request middleware.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
organization_id_ctx: ContextVar[str | None] = ContextVar("organization_id", default=None)

SERVICE_NAME = "api"


class ContextFilter(logging.Filter):
    """Attach request/user/org context to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        record.user_id = user_id_ctx.get() or "-"
        record.organization_id = organization_id_ctx.get() or "-"
        record.service = SERVICE_NAME
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": getattr(record, "service", SERVICE_NAME),
            "request_id": getattr(record, "request_id", "-"),
            "user_id": getattr(record, "user_id", "-"),
            "organization_id": getattr(record, "organization_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Configure the root logger with context filter and formatter."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    # Avoid duplicate handlers when tests reload the app factory.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    handler.setFormatter(
        JsonFormatter()
        if json_logs
        else logging.Formatter(
            "%(asctime)s %(levelname)s [%(service)s] req=%(request_id)s "
            "user=%(user_id)s org=%(organization_id)s %(message)s"
        )
    )
    root.addHandler(handler)

    # Quiet noisy third-party loggers.
    for name in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"airex.{name}")

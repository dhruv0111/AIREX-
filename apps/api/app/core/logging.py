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


import re

_LOG_SANITIZE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{10,}"), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(?i)(password[\"']?\s*[:=]\s*[\"'])[^\"']+([\"'])"), r"\1[REDACTED_PASSWORD]\2"),
    (re.compile(r"(?i)(api[_\-]?key[\"']?\s*[:=]\s*[\"'])[^\"']+([\"'])"), r"\1[REDACTED_KEY]\2"),
    (re.compile(r"(?i)(secret[\"']?\s*[:=]\s*[\"'])[^\"']+([\"'])"), r"\1[REDACTED_SECRET]\2"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"ghp_[a-zA-Z0-9]{20,}"), "[REDACTED_TOKEN]"),
    (re.compile(r"ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*"), "[REDACTED_JWT]"),
]


def sanitize_log_text(text: str) -> str:
    """Sanitize sensitive credentials, API keys, and tokens from log messages and traces."""
    if not text:
        return text
    sanitized = text
    for pattern, repl in _LOG_SANITIZE_PATTERNS:
        sanitized = pattern.sub(repl, sanitized)
    return sanitized


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = sanitize_log_text(record.getMessage())
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": getattr(record, "service", SERVICE_NAME),
            "request_id": getattr(record, "request_id", "-"),
            "user_id": getattr(record, "user_id", "-"),
            "organization_id": getattr(record, "organization_id", "-"),
            "message": msg,
        }
        if record.exc_info:
            payload["exception"] = sanitize_log_text(self.formatException(record.exc_info))
        return json.dumps(payload)


class SanitizedFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        s = super().format(record)
        return sanitize_log_text(s)


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
        else SanitizedFormatter(
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

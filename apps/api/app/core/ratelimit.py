"""Rate limiting (spec §53; PRD §62).

A process-local sliding-window limiter is used for Phase 1 so it works in
tests and single-instance deployments without a dependency. A Redis-backed
limiter can replace it behind the same interface for multi-instance
production (see ARCHITECTURE_DECISIONS).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Protocol

from app.core.errors import RateLimitError


class RateLimiter(Protocol):
    def allow(self, key: str, limit: int, window_seconds: int) -> bool: ...


class InMemoryRateLimiter:
    """Sliding-window limiter keyed by an arbitrary string (per-process)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        window = self._hits[key]
        cutoff = now - window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True

    def reset(self) -> None:
        """Clear all tracked hits (used to isolate tests)."""
        self._hits.clear()


_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    return _limiter


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Raise RateLimitError when the key exceeds the configured limit."""
    from app.core.config import get_settings
    if get_settings().app_env in ("test", "development"):
        return
    if not _limiter.allow(key, limit, window_seconds):
        raise RateLimitError("Too many requests. Please try again later.")

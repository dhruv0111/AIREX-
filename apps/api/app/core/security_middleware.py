"""Security middleware: HTTP security headers, request size limits, and auth rate limiting (Phase 12)."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces defense-in-depth security headers on all HTTP responses (spec §62, Phase 12)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Protects against Denial-of-Service attacks by enforcing maximum body size limits."""

    def __init__(self, app, max_size_bytes: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_size_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "REQUEST_ENTITY_TOO_LARGE",
                                "message": f"Request body exceeds maximum allowed size of {self.max_size_bytes} bytes.",
                            }
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter for brute-force sensitive authentication routes."""

    def __init__(self, app):
        super().__init__(app)
        # client_ip -> list of epoch timestamps
        self._history: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        # Only rate-limit sensitive authentication routes
        if path in ("/api/v1/auth/login", "/api/v1/auth/register") and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            window_seconds = 60.0
            max_requests = 30  # 30 auth attempts per minute

            # Prune old timestamps
            history = [ts for ts in self._history[client_ip] if (now - ts) < window_seconds]
            if len(history) >= max_requests:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                        }
                    },
                    headers={"Retry-After": "60"},
                )
            history.append(now)
            self._history[client_ip] = history

        return await call_next(request)

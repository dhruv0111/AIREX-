"""Request context middleware: request IDs + structured logging (spec §55–§57)."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import (
    get_logger,
    organization_id_ctx,
    request_id_ctx,
    user_id_ctx,
)
from app.core.security import new_request_id

logger = get_logger("api")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request_id, set logging context, and log a request summary."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = new_request_id()
        request.state.request_id = request_id
        token_ctx = request_id_ctx.set(request_id)
        user_ctx = user_id_ctx.set(None)
        org_ctx = organization_id_ctx.set(None)
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            status = getattr(response, "status_code", 500) if response is not None else 500
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": duration_ms,
                },
            )
            request_id_ctx.reset(token_ctx)
            user_id_ctx.reset(user_ctx)
            organization_id_ctx.reset(org_ctx)
            if response is not None:
                response.headers["X-Request-Id"] = request_id

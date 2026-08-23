"""Health endpoints (spec §39; AT-002/003/025/026/027)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.metrics import metrics_enabled, metrics_response, report_db_status
from app.db.session import ping_database

router = APIRouter(tags=["health"])

UNHEALTHY = {"status": "degraded", "service": "airex"}


@router.get("/health")
async def health() -> dict:
    """Aggregate health. Does not require dependencies (AT-025)."""
    return {
        "status": "ok",
        "service": get_settings().app_name,
        "version": get_settings().app_version,
    }


@router.get("/live")
async def live() -> dict:
    """Liveness — must not fail merely because the DB is down (AT-026)."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> JSONResponse:
    """Readiness — 200 only when required dependencies are healthy (AT-002/003/027)."""
    db_ok = await ping_database()
    report_db_status(db_ok)
    checks: dict = {"postgres": "ok" if db_ok else "error"}

    # Redis is a required dependency for the async/queue foundation (AT-003).
    redis_ok = await _ping_redis()
    checks["redis"] = "ok" if redis_ok else "error"

    healthy = db_ok and redis_ok
    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus-compatible metrics (spec §60)."""
    if not metrics_enabled():
        return JSONResponse({"status": "disabled"}, status_code=404)
    return metrics_response()


async def _ping_redis() -> bool:
    settings = get_settings()
    # memory:// selects the in-process queue (local/test mode); treat as healthy.
    if settings.redis_url.startswith("memory://"):
        return True
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=2)
        return bool(client.ping())
    except Exception:
        return False

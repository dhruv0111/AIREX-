"""Health and readiness endpoints (spec §39, §46; AT-002/003/025/026/027; Phase 12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.metrics import metrics_enabled, metrics_response, report_db_status
from app.core.secret_manager import SecretManager
from app.db.session import get_db, ping_database
from app.services.system_readiness import SystemReadinessService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Aggregate health. Does not require dependencies (AT-025)."""
    return {
        "status": "ok",
        "service": get_settings().app_name,
        "version": get_settings().app_version,
    }


@router.get("/live")
@router.get("/health/live")
async def live() -> dict:
    """Liveness probe — verifies the application process is running (AT-026, Phase 12)."""
    return {"status": "ok"}


@router.get("/ready")
@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Readiness probe — 200 when required dependencies are healthy (AT-002/003/027, Phase 12)."""
    db_ok = await ping_database()
    report_db_status(db_ok)
    redis_ok = await _ping_redis()

    service = SystemReadinessService(session)
    result = await service.evaluate_readiness()
    overall = result["overall_status"]

    healthy = db_ok and redis_ok and (overall != "UNREADY")
    status_code = 200 if healthy else 503

    checks_dict = {
        "postgres": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }
    for c in result.get("checks", []):
        checks_dict[c["name"]] = c["status"].lower()

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if healthy else "degraded",
            "overall_status": overall,
            "checks": checks_dict,
            "diagnostics": result["checks"],
        },
    )


@router.get("/health/startup")
async def startup(session: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Startup probe — verifies database connectivity and encryption key availability."""
    db_ok = await ping_database()
    key_ok = SecretManager.validate_key()

    healthy = db_ok and key_ok
    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if healthy else "unready",
            "database": "ok" if db_ok else "failed",
            "encryption_key": "ok" if key_ok else "failed",
        },
    )


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus-compatible metrics (spec §60)."""
    if not metrics_enabled():
        return JSONResponse({"status": "disabled"}, status_code=404)
    return metrics_response()


async def _ping_redis() -> bool:
    settings = get_settings()
    if settings.redis_url.startswith("memory://"):
        return True
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2.0)
        pong = await client.ping()
        await client.aclose()
        return bool(pong)
    except Exception:
        return False

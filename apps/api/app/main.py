"""FastAPI application factory (spec §6, §57, §62, §69)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import RequestContextMiddleware
from app.api.v1.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.metrics import MetricsMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 0 uses Alembic migrations for PostgreSQL; SQLite dev fallback is
    # created here only when explicitly configured (see config.is_sqlite).
    from app.db.session import init_models

    await init_models(create_all=False)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, json_logs=settings.app_env == "production")

    app = FastAPI(
        title="AIREX API",
        description=(
            "AI Reliability, Evaluation & Observability Platform — Phase 0 "
            "(Authentication, Organizations, Projects, Health, Foundation)."
        ),
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    app.add_middleware(RequestContextMiddleware)
    if settings.prometheus_enabled:
        app.add_middleware(MetricsMiddleware)

    register_error_handlers(app)

    app.include_router(health_router)
    app.include_router(v1_router)
    return app


app = create_app()

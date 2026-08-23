"""Aggregated API v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    datasets,
    environments,
    evaluations,
    generations,
    models,
    organizations,
    projects,
    providers,
    rubrics,
    stubs,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(organizations.router)
router.include_router(projects.router)
router.include_router(providers.router)
router.include_router(models.router)
router.include_router(environments.router)
router.include_router(datasets.router)
router.include_router(evaluations.router)
router.include_router(rubrics.router)
router.include_router(generations.router)

# Phase 4+ stubs (501 NOT_IMPLEMENTED) — module structure only.
router.include_router(stubs.experiments_router)

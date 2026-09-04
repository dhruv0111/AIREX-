"""Aggregated API v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    datasets,
    environments,
    evaluations,
    experiments,
    generations,
    models,
    organizations,
    pricing,
    projects,
    providers,
    rubrics,
    ci,
    observability,
    alerts,
    benchmarks,
    intelligence,
    agents,
    system,
    identity,
    teams,
    governance,
    compliance,
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
router.include_router(experiments.router)
router.include_router(ci.router)
router.include_router(observability.router)
router.include_router(alerts.router)
router.include_router(pricing.router)
router.include_router(benchmarks.router)
router.include_router(intelligence.router)
router.include_router(agents.router)
router.include_router(system.router)
router.include_router(identity.router)
router.include_router(teams.router)
router.include_router(governance.router)
router.include_router(compliance.router)

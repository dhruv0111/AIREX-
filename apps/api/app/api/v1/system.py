"""System status, readiness, configuration, and administration endpoints (Phase 12)."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.core.secret_manager import mask_secret, redact_sensitive_dict
from app.db.session import get_db
from app.models import Alert, OrganizationMember, User
from app.models.worker import WorkerHeartbeat
from app.schemas.common import ok
from app.services.system_readiness import (
    EXPECTED_ALEMBIC_HEAD,
    SystemReadinessService,
)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/readiness", status_code=status.HTTP_200_OK)
async def get_system_readiness(session: AsyncSession = Depends(get_db)) -> dict:
    """Full system readiness diagnostic distinguishing HEALTHY, DEGRADED, UNREADY."""
    service = SystemReadinessService(session)
    result = await service.evaluate_readiness()
    return ok(result)


@router.get("/schema-version", status_code=status.HTTP_200_OK)
async def get_schema_version(session: AsyncSession = Depends(get_db)) -> dict:
    """Check current database schema migration version and compatibility."""
    try:
        res = await session.execute(text("SELECT version_num FROM alembic_version"))
        current_version = res.scalar()
    except Exception:
        current_version = None

    is_compatible = current_version == EXPECTED_ALEMBIC_HEAD
    return ok({
        "current_version": current_version,
        "expected_head": EXPECTED_ALEMBIC_HEAD,
        "is_compatible": is_compatible,
        "status": "COMPATIBLE" if is_compatible else "OUTDATED",
    })


@router.get("/config", status_code=status.HTTP_200_OK)
async def get_safe_config() -> dict:
    """Safe configuration view with all credentials and secrets masked."""
    settings = get_settings()
    settings_dict = settings.model_dump()
    masked_dict = redact_sensitive_dict(settings_dict)

    # Compute deterministic fingerprint of active configuration
    fingerprint_raw = json.dumps(masked_dict, sort_keys=True)
    fingerprint = hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()

    return ok({
        "environment": settings.app_env,
        "version": settings.app_version,
        "configuration_fingerprint": fingerprint,
        "configuration": masked_dict,
    })


@router.get("/workers", status_code=status.HTTP_200_OK)
async def list_workers(session: AsyncSession = Depends(get_db)) -> dict:
    """List background workers and their heartbeat health."""
    now = datetime.now(UTC)
    stmt = select(WorkerHeartbeat).order_by(desc(WorkerHeartbeat.heartbeat_at)).limit(50)
    res = await session.execute(stmt)
    workers = list(res.scalars().all())

    worker_list = []
    for w in workers:
        hb = w.heartbeat_at if w.heartbeat_at.tzinfo else w.heartbeat_at.replace(tzinfo=UTC)
        age_seconds = (now - hb).total_seconds()
        is_stale = age_seconds > 35
        computed_status = "STALE" if (is_stale and w.status == "ACTIVE") else w.status

        worker_list.append({
            "id": str(w.id),
            "worker_id": w.worker_id,
            "hostname": w.hostname,
            "pid": w.pid,
            "status": computed_status,
            "active_jobs_count": w.active_jobs_count,
            "heartbeat_at": w.heartbeat_at.isoformat(),
            "heartbeat_age_seconds": round(age_seconds, 1),
            "started_at": w.started_at.isoformat(),
        })

    return ok(worker_list)


@router.get("/admin/overview", status_code=status.HTTP_200_OK)
async def get_admin_overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Administrative status overview. Restricted to superusers or organization owners."""
    # Check authorization: user must be is_superuser or an OWNER in an organization
    if not user.is_superuser:
        stmt = select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.role == "OWNER",
        )
        res = await session.execute(stmt)
        if not res.scalars().first():
            raise ForbiddenError("Access forbidden: system administrator permissions required.")

    # Readiness diagnostic
    readiness_service = SystemReadinessService(session)
    readiness = await readiness_service.evaluate_readiness()

    # Active alerts count
    try:
        alert_stmt = select(func.count()).select_from(Alert).where(Alert.status == "ACTIVE")
        active_alerts = (await session.execute(alert_stmt)).scalar() or 0
    except Exception:
        active_alerts = 0

    # Active worker count
    now = datetime.now(UTC)
    stmt = select(WorkerHeartbeat).where(WorkerHeartbeat.status == "ACTIVE")
    res = await session.execute(stmt)
    workers = list(res.scalars().all())
    healthy_workers = 0
    for w in workers:
        hb = w.heartbeat_at if w.heartbeat_at.tzinfo else w.heartbeat_at.replace(tzinfo=UTC)
        if (now - hb).total_seconds() <= 35:
            healthy_workers += 1

    settings = get_settings()
    return ok({
        "application": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "readiness": readiness,
        "stats": {
            "active_alerts_count": active_alerts,
            "active_workers_count": healthy_workers,
            "queue_mode": "in_memory" if settings.redis_url.startswith("memory://") else "redis",
        },
    })


@router.get("/operations/overview", status_code=status.HTTP_200_OK)
async def get_operations_overview(
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Unified production operations and SRE dashboard metrics (Phase 16)."""
    from app.services.operations_service import OperationsService
    from app.services.operational_alert_service import OperationalAlertService

    op_service = OperationsService(session)
    overview = await op_service.get_operations_overview()

    # Evaluate operational threshold alerts
    alert_service = OperationalAlertService(session)
    triggered_alerts = await alert_service.evaluate_operational_metrics(overview)
    overview["triggered_operational_alerts"] = triggered_alerts

    return ok(overview)


@router.post("/disaster-recovery/restore-test", status_code=status.HTTP_200_OK)
async def trigger_restore_test(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a controlled Disaster Recovery restore test of the latest backup into an isolated target."""
    from app.services.backup_service import BackupService
    import tempfile

    # Ensure a fresh verified backup exists first
    backup_res = BackupService.create_backup()
    backup_file = backup_res["backup_file"]

    # Restore into an isolated temporary target
    with tempfile.NamedTemporaryFile(suffix=".restore_test.db", delete=False) as tmp_dst:
        tmp_target = tmp_dst.name

    restore_res = BackupService.restore_backup(backup_file, target_db_path=tmp_target)
    # Clean up temp file
    try:
        os.remove(tmp_target)
    except Exception:
        pass

    return ok({
        "message": "Disaster Recovery restore test passed successfully.",
        "backup": backup_res,
        "restore": restore_res,
    })

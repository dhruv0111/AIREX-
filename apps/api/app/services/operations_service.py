"""Operations and SRE telemetry aggregation service (Phase 16)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.metrics import get_request_stats
from app.db.session import get_engine
from app.models.alert import Alert
from app.models.worker import TaskFailure, WorkerHeartbeat
from app.services.backup_service import BackupService
from app.services.system_readiness import SystemReadinessService
from app.workers.worker import build_queue


class OperationsService:
    """Aggregates unified operational telemetry across platform components."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def get_operations_overview(self) -> dict[str, Any]:
        """Collects live production metrics across health, traffic, queue, DB, security, and DR."""
        # 1. Platform Health
        readiness_service = SystemReadinessService(self._session)
        readiness = await readiness_service.evaluate_readiness()

        # 2. Real-time Traffic & Latency Percentiles
        traffic = get_request_stats(window_seconds=60)

        # 3. Background Processing & Queue Health
        queue = build_queue()
        try:
            queue_depth = await queue.get_depth()
            dlq_depth = await queue.get_dlq_depth()
            recent_dlq = await queue.list_dlq(limit=5)
        except Exception:
            queue_depth = 0
            dlq_depth = 0
            recent_dlq = []
        finally:
            await queue.close()

        # Worker Fleet telemetry
        now = datetime.now(UTC)
        stmt_workers = select(WorkerHeartbeat).order_by(desc(WorkerHeartbeat.heartbeat_at)).limit(20)
        res_workers = await self._session.execute(stmt_workers)
        workers = list(res_workers.scalars().all())

        active_workers = 0
        total_active_jobs = 0
        for w in workers:
            hb = w.heartbeat_at if w.heartbeat_at.tzinfo else w.heartbeat_at.replace(tzinfo=UTC)
            if (now - hb).total_seconds() <= 35 and w.status == "ACTIVE":
                active_workers += 1
                total_active_jobs += w.active_jobs_count

        # Total task failures
        stmt_failures = select(func.count(TaskFailure.id))
        res_failures = await self._session.execute(stmt_failures)
        total_failed_tasks = res_failures.scalar() or 0

        # 4. Database Pool Utilization
        engine = get_engine()
        pool = getattr(engine, "sync_engine", engine).pool
        try:
            pool_size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()
            utilization = round((checked_out / max(1, pool_size + overflow)) * 100, 1)
        except Exception:
            pool_size = self._settings.db_pool_size
            checked_in = pool_size
            checked_out = 0
            overflow = 0
            utilization = 0.0

        # 5. Security & Policy Telemetry
        stmt_alerts = select(Alert).order_by(desc(Alert.created_at)).limit(20)
        res_alerts = await self._session.execute(stmt_alerts)
        recent_alerts = list(res_alerts.scalars().all())

        security_incidents_count = sum(
            1 for a in recent_alerts if "security" in a.name.lower() or "auth" in a.name.lower()
        )
        policy_blocks_count = sum(
            1 for a in recent_alerts if "policy" in a.name.lower() or "blocked" in a.name.lower()
        )

        # 6. Disaster Recovery Readiness
        recovery = BackupService.get_recovery_status()

        return {
            "timestamp": now.isoformat(),
            "environment": self._settings.app_env,
            "version": self._settings.app_version,
            "overall_status": readiness.get("overall_status", "HEALTHY"),
            "health": {
                "overall_status": readiness.get("overall_status", "HEALTHY"),
                "checks": readiness.get("checks", []),
            },
            "performance": {
                "requests_per_second": traffic.get("requests_per_second", 0.0),
                "error_rate": traffic.get("error_rate", 0.0),
                "total_requests_window": traffic.get("total_requests", 0),
                "latency_p50_ms": traffic.get("p50_ms", 0.0),
                "latency_p95_ms": traffic.get("p95_ms", 0.0),
                "latency_p99_ms": traffic.get("p99_ms", 0.0),
                "latency_avg_ms": traffic.get("avg_ms", 0.0),
            },
            "background_processing": {
                "queue_depth": queue_depth,
                "dead_letter_queue_depth": dlq_depth,
                "active_workers_count": active_workers,
                "total_active_jobs": total_active_jobs,
                "total_failed_tasks": total_failed_tasks,
                "recent_dlq_tasks": recent_dlq,
            },
            "database_pool": {
                "pool_size": pool_size,
                "checked_in_connections": checked_in,
                "checked_out_connections": checked_out,
                "overflow_connections": overflow,
                "utilization_percent": utilization,
            },
            "security": {
                "recent_security_incidents": security_incidents_count,
                "sensitive_data_policy_blocks": policy_blocks_count,
                "total_recent_alerts": len(recent_alerts),
            },
            "disaster_recovery": recovery,
        }

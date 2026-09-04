"""Operational alerting engine with alert-storm suppression (Phase 16)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.alert import Alert

logger = logging.getLogger("airex.alerts.operational")


class OperationalAlertService:
    """Evaluates production operational metrics against thresholds and emits alerts with deduplication."""

    _last_alert_timestamps: dict[str, float] = {}

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def evaluate_operational_metrics(self, metrics: dict[str, Any], project_id: str | None = None) -> list[dict[str, Any]]:
        """Evaluates operational metrics and generates deduplicated alerts if thresholds are breached."""
        now = time.time()
        dedup_window = self._settings.alert_dedup_window_seconds
        generated_alerts: list[dict[str, Any]] = []

        perf = metrics.get("performance", {})
        bg = metrics.get("background_processing", {})
        db = metrics.get("database_pool", {})

        # Rule 1: High Error Rate
        error_rate = perf.get("error_rate", 0.0)
        if error_rate > self._settings.alert_threshold_error_rate and perf.get("total_requests_window", 0) >= 10:
            key = "op_alert_high_error_rate"
            if self._should_emit(key, now, dedup_window):
                alert_dict = {
                    "key": key,
                    "name": "High HTTP Error Rate Detected",
                    "severity": "CRITICAL",
                    "message": f"HTTP error rate is {error_rate * 100:.1f}% (threshold: {self._settings.alert_threshold_error_rate * 100:.1f}%)",
                }
                generated_alerts.append(alert_dict)

        # Rule 2: High Latency p95
        p95 = perf.get("latency_p95_ms", 0.0)
        if p95 > self._settings.alert_threshold_p95_latency_ms:
            key = "op_alert_high_latency_p95"
            if self._should_emit(key, now, dedup_window):
                alert_dict = {
                    "key": key,
                    "name": "High Request Latency (p95)",
                    "severity": "WARNING",
                    "message": f"Request p95 latency reached {p95:.1f}ms (threshold: {self._settings.alert_threshold_p95_latency_ms:.1f}ms)",
                }
                generated_alerts.append(alert_dict)

        # Rule 3: Queue Backlog
        q_depth = bg.get("queue_depth", 0)
        if q_depth > self._settings.alert_threshold_queue_backlog:
            key = "op_alert_queue_backlog"
            if self._should_emit(key, now, dedup_window):
                alert_dict = {
                    "key": key,
                    "name": "Task Queue Backlog Accumulating",
                    "severity": "WARNING",
                    "message": f"Task queue depth is {q_depth} (threshold: {self._settings.alert_threshold_queue_backlog})",
                }
                generated_alerts.append(alert_dict)

        # Rule 4: Dead-Letter Queue (DLQ) Growth
        dlq_depth = bg.get("dead_letter_queue_depth", 0)
        if dlq_depth > self._settings.alert_threshold_dlq_size:
            key = "op_alert_dlq_growth"
            if self._should_emit(key, now, dedup_window):
                alert_dict = {
                    "key": key,
                    "name": "Dead-Letter Queue Poison Tasks Detected",
                    "severity": "CRITICAL",
                    "message": f"DLQ contains {dlq_depth} poison tasks requiring operator investigation.",
                }
                generated_alerts.append(alert_dict)

        # Rule 5: Database Connection Pool Saturation
        pool_util = db.get("utilization_percent", 0.0)
        threshold_util = self._settings.alert_threshold_db_pool_utilization * 100.0
        if pool_util > threshold_util:
            key = "op_alert_db_pool_saturation"
            if self._should_emit(key, now, dedup_window):
                alert_dict = {
                    "key": key,
                    "name": "Database Connection Pool Saturation",
                    "severity": "WARNING",
                    "message": f"Database pool utilization reached {pool_util:.1f}% (threshold: {threshold_util:.1f}%)",
                }
                generated_alerts.append(alert_dict)

        # Rule 6: Worker Fleet Heartbeat Loss
        active_workers = bg.get("active_workers_count", 0)
        if active_workers == 0 and q_depth > 0:
            key = "op_alert_worker_fleet_offline"
            if self._should_emit(key, now, dedup_window):
                alert_dict = {
                    "key": key,
                    "name": "Zero Active Workers While Queue Backlogged",
                    "severity": "CRITICAL",
                    "message": f"Task queue has {q_depth} items but no active workers reported heartbeat.",
                }
                generated_alerts.append(alert_dict)

        return generated_alerts

    @classmethod
    def _should_emit(cls, key: str, now: float, dedup_window: float) -> bool:
        """Sliding-window deduplication logic."""
        last_time = cls._last_alert_timestamps.get(key)
        if last_time is not None and (now - last_time) < dedup_window:
            logger.debug("Operational alert suppressed by deduplication window", extra={"alert_key": key})
            return False
        cls._last_alert_timestamps[key] = now
        return True

    @classmethod
    def reset_dedup_cache(cls) -> None:
        """Reset deduplication state for tests."""
        cls._last_alert_timestamps.clear()

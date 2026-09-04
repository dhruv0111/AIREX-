"""Integration tests for Phase 16 Operations SRE Dashboard, Threshold Alerts, and Startup Hardening."""

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.config_validation import (
    ConfigurationValidationError,
    validate_production_configuration,
)
from app.services.operational_alert_service import OperationalAlertService


@pytest.mark.asyncio
async def test_operations_overview_endpoint(auth_client: AsyncClient):
    """Verify that GET /api/v1/system/operations/overview returns genuine SRE metrics."""
    res = await auth_client.get("/api/v1/system/operations/overview")
    assert res.status_code == 200
    data = res.json()["data"]

    # Platform health
    assert "health" in data
    assert data["health"]["overall_status"] in {"HEALTHY", "DEGRADED", "UNREADY"}

    # Performance
    assert "performance" in data
    perf = data["performance"]
    assert "latency_p50_ms" in perf
    assert "latency_p95_ms" in perf
    assert "latency_p99_ms" in perf
    assert "requests_per_second" in perf
    assert "error_rate" in perf

    # Background processing & queue
    assert "background_processing" in data
    bg = data["background_processing"]
    assert "queue_depth" in bg
    assert "dead_letter_queue_depth" in bg
    assert "active_workers_count" in bg

    # DB Pool
    assert "database_pool" in data
    assert "utilization_percent" in data["database_pool"]

    # Disaster recovery
    assert "disaster_recovery" in data
    assert "dr_readiness_status" in data["disaster_recovery"]


@pytest.mark.asyncio
async def test_operational_alert_evaluation_and_deduplication(db_session):
    """Verify operational threshold breach detection and sliding-window storm deduplication."""
    OperationalAlertService.reset_dedup_cache()
    service = OperationalAlertService(db_session)

    # Simulated metrics exceeding error rate threshold (e.g. 15% error rate)
    bad_metrics = {
        "performance": {
            "error_rate": 0.15,
            "total_requests_window": 50,
            "latency_p95_ms": 150.0,
        },
        "background_processing": {
            "queue_depth": 150,  # exceeds 100 threshold
            "dead_letter_queue_depth": 15,  # exceeds 10 threshold
            "active_workers_count": 0,
        },
        "database_pool": {
            "utilization_percent": 95.0,  # exceeds 85% threshold
        },
    }

    # First evaluation should generate alerts
    alerts_1 = await service.evaluate_operational_metrics(bad_metrics)
    assert len(alerts_1) >= 3
    alert_keys = {a["key"] for a in alerts_1}
    assert "op_alert_high_error_rate" in alert_keys
    assert "op_alert_queue_backlog" in alert_keys
    assert "op_alert_dlq_growth" in alert_keys

    # Immediate second evaluation must suppress duplicate alert storm
    alerts_2 = await service.evaluate_operational_metrics(bad_metrics)
    assert len(alerts_2) == 0


def test_production_startup_validation_hardening():
    """Verify that validate_production_configuration strictly enforces production safety."""
    # 1. Insecure default secret in production -> Must fail at Settings validator or config validator
    with pytest.raises((ConfigurationValidationError, ValidationError)):
        insecure_settings = Settings(
            app_env="production",
            jwt_secret_key="change-me-to-a-long-random-secret",
            credential_encryption_key="",
            api_cors_origins="*",
        )
        validate_production_configuration(insecure_settings)

    # 2. Valid production settings -> Must pass
    import base64
    valid_key = base64.b64encode(b"0" * 32).decode()
    valid_settings = Settings(
        app_env="production",
        jwt_secret_key="a" * 64,
        credential_encryption_key=valid_key,
        api_cors_origins="https://app.airex.io",
    )
    res = validate_production_configuration(valid_settings)
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_disaster_recovery_restore_endpoint(auth_client: AsyncClient):
    """Verify live POST /api/v1/system/disaster-recovery/restore-test endpoint."""
    res = await auth_client.post("/api/v1/system/disaster-recovery/restore-test")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "Disaster Recovery restore test passed" in data["message"]
    assert data["restore"]["status"] == "SUCCESS"
    assert data["restore"]["restore_duration_seconds"] >= 0.0

# AIREX — PHASE 16: PRODUCTION OPERATIONS, SCALABILITY & DISASTER RECOVERY
## Implementation Plan & Architecture Specification

**Author:** Antigravity Advanced Agentic Engineering  
**Date:** September 2, 2026  
**Status:** DRAFT (Awaiting Approval)  
**Dependencies:** Phase 0–15 Verified Architecture (Head: `0015_phase14_compliance_data_governance`)

---

## 1. OBJECTIVES & ARCHITECTURAL PRINCIPLES

Phase 16 focuses on platform operations, scalability, high availability, resilience, observability, and disaster recovery.
Phase 16 does NOT rebuild existing features from Phases 0–15. Instead, it strengthens the operational backbone:

1. **Controlled Production Capacity & Metrics:** Configurable concurrency, worker fleet scaling, queue latency & depth tracking, and latency percentiles (p50, p95, p99) without hardcoded limits.
2. **Worker Fleet Resilience:** Retries with exponential backoff, dead-letter queue (DLQ) for poison tasks, task timeouts, worker crash recovery, and idempotency guarantees.
3. **API Resilience & Graceful Degradation:** Safe degraded operations when dependencies (Redis/queue, workers, storage) are unavailable or slow, preventing sensitive leakage in error states.
4. **Disaster Recovery (DR) & Restore Verification:** Full restore validation into a clean environment, SHA-256 verification, backup corruption detection, post-restore schema/data integrity validation, and real measurement of RTO and RPO.
5. **Unified Operations (SRE) Dashboard:** Real telemetry endpoint and frontend SRE view (`/admin/operations`) visualizing health, request percentiles, queue backlog, DLQ, DB pool utilization, security events, and DR readiness.
6. **Operational Alerting & Storm Suppression:** Threshold alerts for high error rate, p95/p99 latency, DB pool saturation, worker heartbeat loss, DLQ growth, and backup failures with deduplication.
7. **Production Startup Hardening:** Fail-fast validation of required secrets, non-default credentials, encryption keys, and environment settings.

---

## 2. ACCEPTANCE CRITERIA MATRIX (AT-P16-001 through AT-P16-025)

| ID | Category | Requirement Description |
| :--- | :--- | :--- |
| **AT-P16-001** | Performance | Operational metrics tracking RPS, latency (p50, p95, p99), error rate, and DB pool usage. |
| **AT-P16-002** | Load Handling | Controlled load testing across auth, projects, evaluations, datasets, and observability without degradation. |
| **AT-P16-003** | Worker Recovery | Worker fleet recovers after sudden restart, detecting stale jobs and resuming processing. |
| **AT-P16-004** | Task Retries | Configurable task retries with exponential backoff for transient failures. |
| **AT-P16-005** | Dead-Letter Queue | Poison / permanently failing tasks move to Dead-Letter Queue (DLQ) without silent loss. |
| **AT-P16-006** | Graceful Degradation | API returns clean 503/degraded responses without leaking internal stack traces or secrets when DB/queue is down. |
| **AT-P16-007** | Dependency Recovery | API automatically resumes normal operation as soon as degraded dependencies recover. |
| **AT-P16-008** | Backup Integrity | Verified database backups generated with deterministic SHA-256 checksums. |
| **AT-P16-009** | Restore Verification | Real restore execution into a clean database target verified end-to-end. |
| **AT-P16-010** | Data Integrity | Post-restore validation confirms all records, relationships, and fingerprints match pre-backup state. |
| **AT-P16-011** | Tenant Isolation | Post-restore validation proves multi-tenant boundaries remain strictly enforced after restore. |
| **AT-P16-012** | RPO / RTO | Accurate measurement of actual backup duration (RPO) and restore execution time (RTO). |
| **AT-P16-013** | Operations Dashboard | Live SRE dashboard (`/admin/operations`) rendering real health, performance, queue, and DR metrics. |
| **AT-P16-014** | Production Alerts | Configurable alerts for error spikes, high latency, queue backlogs, DLQ growth, and backup failures. |
| **AT-P16-015** | Alert Deduplication | Sliding window deduplication prevents alert storms during recurring failure conditions. |
| **AT-P16-016** | Config Validation | Startup validation fails fast if required production secrets or encryption keys are missing or defaulted. |
| **AT-P16-017** | Startup Hardening | Verified secure headers, disabled debug modes, and production logging safety checks. |
| **AT-P16-018** | Deployment Verification | Automated check of migration status, worker startup, and health check readiness. |
| **AT-P16-019** | Failure Security | Security controls (auth, RBAC, tenant isolation) remain inviolable during infrastructure degradation. |
| **AT-P16-020** | Concurrency Security | Multi-threaded / concurrent requests do not allow race conditions or authorization bypasses. |
| **AT-P16-021** | DB Pool Resilience | Controlled concurrency test confirms connection pool manages contention without starvation or connection leaks. |
| **AT-P16-022** | Queue Resilience | In-memory and Redis task queues preserve queue depth and latency telemetry under load. |
| **AT-P16-023** | Worker Fleet Scaling | Configurable concurrency limits allow scaling worker processes without deadlock. |
| **AT-P16-024** | Full Regression Safety | Zero regressions introduced across Phase 0–15 test suites (all passing). |
| **AT-P16-025** | Playwright Production E2E | Headed Chromium browser validation of live operations dashboard and disaster recovery controls. |

---

## 3. PROPOSED ARCHITECTURE & CODE CHANGES

### A. Core Capacity, Queue & Worker Hardening
1. **`apps/api/app/workers/queue.py`**:
   - Add `get_depth()` and `get_dlq_depth()` to `TaskQueue` protocol, `InMemoryTaskQueue`, and `RedisTaskQueue`.
   - Add envelope timestamps (`enqueued_at`, `attempts`, `max_retries`) for queue latency monitoring.
   - Implement dead-letter queue operations (`enqueue_dlq`, `list_dlq`).
2. **`apps/api/app/workers/worker.py`**:
   - Add task retry loop with exponential backoff (`attempts < max_retries`).
   - Add dead-letter routing upon retry exhaustion.
   - Add task execution timeout wrapper to prevent runaway hung tasks.
   - Add task idempotency verification using an in-memory / cache deduplication set.
3. **`apps/api/app/core/config.py`**:
   - Add configurable worker settings: `worker_max_retries`, `worker_retry_backoff_base`, `worker_task_timeout_seconds`.
   - Add configurable operational alert thresholds: error rate, latency p95, queue backlog, DLQ size, pool utilization.
   - Add DR targets: `backup_rpo_target_seconds`, `backup_rto_target_seconds`.

### B. Disaster Recovery & Restore Engine
1. **`apps/api/app/services/backup_service.py`**:
   - Implement `restore_backup(backup_file: str, target_db_url: str | None = None) -> dict[str, Any]`:
     - Verifies SHA-256 checksum before restoration.
     - Rejects corrupted or truncated backup files.
     - Safely restores SQLite / Postgres database into target location.
     - Measures actual restore time (RTO).
   - Implement `verify_data_integrity(original_counts: dict, restored_counts: dict) -> bool`.
2. **Runbook Creation**:
   - Create `docs/development/PRODUCTION_DISASTER_RECOVERY_RUNBOOK.md` with step-by-step procedures for DB failure, worker fleet failure, data corruption, key compromise, restore execution, and verification.

### C. Unified Operations (SRE) API & Dashboard
1. **`apps/api/app/services/operations_service.py` [NEW]**:
   - Collects live operational metrics:
     - Platform Health (API, DB, Worker, Queue, Storage, Migrations).
     - Real HTTP Performance (RPS, error rate, p50, p95, p99 latency via Prometheus histograms and windowed sliding counters).
     - Background Processing (queue depth, active tasks, failed tasks, DLQ count, worker utilization).
     - DB Pool Utilization (pool size, overflow, checked out connections, pool wait time).
     - Security Incidents (auth failures, rate limit blocks, token reuse events, sensitive data blocks).
     - Disaster Recovery (last backup timestamp, status, last restore test result, measured RPO/RTO).
2. **`apps/api/app/api/v1/system.py`**:
   - Add `GET /api/v1/system/operations/overview` returning the aggregated SRE metrics.
   - Add `POST /api/v1/system/disaster-recovery/restore-test` endpoint for controlled DR testing.
3. **`packages/api-client/src/index.ts`**:
   - Add `getOperationsOverview()` and `triggerRestoreTest()`.
4. **`apps/web/app/admin/operations/page.tsx` [NEW]**:
   - SRE Operations Console rendering 5 tabbed sections:
     1. Platform Health & Infrastructure
     2. Real-time Traffic & Latency Percentiles (p50/p95/p99)
     3. Worker Fleet, Queue & Dead-Letter Queue
     4. Security Incidents & Sensitive Data Telemetry
     5. Disaster Recovery Readiness & RPO/RTO Metrics
5. **`apps/web/components/AppShell.tsx`**:
   - Add `Operations (SRE)` navigation link.

### D. Operational Alerting & Storm Suppression
1. **`apps/api/app/services/operational_alert_service.py` [NEW]**:
   - Evaluates system state against configurable operational thresholds.
   - Generates high-priority alerts into `app.models.Alert`.
   - Sliding window alert suppression (deduplicates alerts within configured window, e.g., 300s, preventing alert storms).

### E. Production Startup & Configuration Validation
1. **`apps/api/app/core/config_validation.py` [NEW]**:
   - Validates environment configurations at application startup (`app.main:lifespan`).
   - If `app_env == "production"`, strictly raises `RuntimeError` if:
     - Default secrets are used (`change-me...`, `secret`, etc.).
     - `credential_encryption_key` is missing or invalid base64.
     - `debug` is enabled.
     - CORS origins allow wildcard `*`.

---

## 4. VERIFICATION & TESTING STRATEGY

1. **Performance & Concurrency Tests (`tests/integration/test_phase16_scalability.py`)**:
   - Test increasing concurrency (10, 25, 50 workers) across auth, projects, evaluations, datasets, observability, and agent runs.
   - Measure real RPS, p50, p95, p99 latency, and verify zero connection leaks or deadlocks.
2. **Worker Resilience & DLQ Tests (`tests/unit/test_phase16_resilience.py`)**:
   - Test task retry exhaustion moving items to DLQ.
   - Test task timeout handling.
   - Test worker restart recovery from stale status.
   - Test idempotency protection against duplicate execution.
3. **Disaster Recovery & Restore Tests (`tests/unit/test_phase16_disaster_recovery.py`)**:
   - Test backup creation, checksum verification, intentional corruption detection, and full restoration into a temporary target.
   - Verify post-restore data integrity and multi-tenant isolation.
4. **Operational SRE API & Alerting Tests (`tests/integration/test_phase16_operations.py`)**:
   - Verify `/api/v1/system/operations/overview` metrics accuracy.
   - Verify operational threshold alert generation and deduplication.
5. **Frontend Build & Playwright E2E (`tests/e2e/tests/phase16.spec.ts`)**:
   - Next.js production build (`npm run build`).
   - Headed Chromium Playwright test exercising the Operations Dashboard (`/admin/operations`), inspecting metrics, viewing DLQ status, and verifying disaster recovery controls.
6. **Full Platform Regression**:
   - Run complete suite (Phases 0–16) ensuring 100% pass rate.

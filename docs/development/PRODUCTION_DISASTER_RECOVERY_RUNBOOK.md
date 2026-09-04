# AIREX — PRODUCTION DISASTER RECOVERY & SRE RUNBOOK

**Document Version:** 1.0.0  
**Classification:** Internal Production Operations  
**Effective Date:** September 2, 2026  
**Target RPO:** <= 1 Hour (Automated Backups with SHA-256 Checksums)  
**Target RTO:** <= 30 Minutes (Automated Online Restoration)

---

## 1. INCIDENT MANAGEMENT FRAMEWORK & SEVERITY CLASSIFICATION

| Severity | Definition | Target Response | Target Resolution | Escalation Contact |
| :--- | :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Core database down, full API unavailability, data corruption, active credential compromise. | < 5 mins | < 30 mins (RTO) | SRE Lead + VP of Engineering |
| **SEV-2 (High)** | Worker fleet stalled, queue backlog critical, degraded multi-tenant access, single subsystem outage. | < 15 mins | < 2 hours | Primary On-Call SRE |
| **SEV-3 (Moderate)** | Non-blocking telemetry lag, backup warning, isolated transient failures. | < 1 hour | < 1 business day | Platform Operations Team |

---

## 2. DISASTER RECOVERY PROCEDURES

### DR-01: PRIMARY DATABASE FAILURE OR CORRUPTION
* **Detection:**
  - Alert: `DatabaseConnectionUnavailable` or `DatabasePoolSaturation`.
  - Health endpoint `GET /health/ready` reports `"database": { "status": "UNREADY" }` with HTTP 503.
  - SRE Dashboard displays 0% DB availability.
* **Immediate Containment:**
  1. Freeze external API mutations by placing proxy (Nginx/Cloudflare) in Maintenance Mode if corruption is suspected.
  2. Suspend background worker queue dispatching to prevent dirty writes:
     `kill -STOP <worker_pid>` or stop the worker container.
* **Recovery Steps:**
  1. Identify latest verified backup in `/app/backups/`:
     ```bash
     python -m app.cli system verify-backup /app/backups/<latest_backup>.db
     ```
  2. Verify SHA-256 checksum matches:
     ```bash
     sha256sum -c /app/backups/<latest_backup>.db.sha256
     ```
  3. Execute automated restore using `BackupService`:
     ```bash
     python -c "from app.services.backup_service import BackupService; BackupService.restore_backup('/app/backups/<latest_backup>.db')"
     ```
  4. Verify schema migration consistency:
     ```bash
     alembic upgrade head
     ```
* **Validation:**
  1. Call `GET /health/ready` and confirm `overall_status == "HEALTHY"`.
  2. Execute database integrity check:
     `PRAGMA integrity_check;` (SQLite) or `SELECT 1 FROM users LIMIT 1;` (Postgres).
  3. Confirm multi-tenant boundary checks in `test_phase8_security.py`.
* **Escalation:** SRE Lead -> Lead Database Administrator.
* **Post-Incident Actions:** Compute actual RPO and RTO; archive corrupted database file for forensic audit; schedule automated integrity check.

---

### DR-02: WORKER FLEET FAILURE & POISON TASK DEAD-LETTER HANDLING
* **Detection:**
  - Alert: `Zero Active Workers While Queue Backlogged` or `Dead-Letter Queue Poison Tasks Detected`.
  - SRE Dashboard reports `active_workers_count == 0` with `queue_depth > 0` or `dead_letter_queue_depth > 0`.
* **Immediate Containment:**
  1. Check worker logs: `docker logs airex-worker` or inspect worker console logs.
  2. If a specific poison payload is crashing workers, inspect Dead-Letter Queue items:
     ```bash
     curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/api/v1/system/operations/overview
     ```
* **Recovery Steps:**
  1. Restart worker fleet:
     ```bash
     python -m app.workers.worker
     ```
  2. On startup, `worker.py` automatically runs `recover_stale_runs()` and `recover_stale_generations()`, resetting abandoned running states to `FAILED` or re-queued.
  3. Poison tasks are automatically isolated into the Dead-Letter Queue (`airex:queue:dlq`) after `worker_max_retries` (3) is reached, preventing infinite crash loops.
* **Validation:**
  1. Check SRE Dashboard `/admin/operations`: `active_workers_count >= 1`.
  2. Enqueue test evaluation and verify job transitions from `QUEUED` -> `RUNNING` -> `COMPLETED`.
* **Escalation:** Primary On-Call SRE.
* **Post-Incident Actions:** Inspect DLQ payloads in `TaskFailure` table; write regression test for edge-case payloads.

---

### DR-03: API SERVICE CRASH & GRACEFUL DEGRADATION
* **Detection:**
  - Synthetic uptime monitor fails; HTTP 502 / 503 error spike.
  - SRE Dashboard error rate exceeds 5%.
* **Immediate Containment:**
  1. Inspect container/process restart status: `systemctl status airex-api` or `docker ps`.
  2. Check memory consumption: ensure process was not OOM-killed.
* **Recovery Steps:**
  1. Restart API processes:
     ```bash
     python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
     ```
  2. If downstream services (Redis/Queue) are unavailable, API continues serving read queries and returns standard degraded responses (`HTTP 503 Service Unavailable`) without leaking internal secrets.
* **Validation:**
  1. Query `GET /health/live` (must return 200 OK within 50ms).
  2. Query `GET /api/v1/system/operations/overview` to verify normal request latency.
* **Escalation:** Lead SRE -> Platform Team.
* **Post-Incident Actions:** Tune Gunicorn/Uvicorn worker count and database pool timeout.

---

### DR-04: DATA CORRUPTION OR ACCIDENTAL DATA DELETION
* **Detection:**
  - Application queries raise deserialization or integrity constraint errors.
  - User reports missing project or dataset version.
* **Immediate Containment:**
  1. Place affected project in Read-Only mode or suspend user session.
  2. Capture point-in-time snapshot of the database before making changes.
* **Recovery Steps:**
  1. Locate backup created immediately prior to the incident:
     ```bash
     ls -lt /app/backups/
     ```
  2. Restore backup into a sandbox database:
     ```bash
     python -c "from app.services.backup_service import BackupService; BackupService.restore_backup('/app/backups/<target_backup>.db', target_db_path='/tmp/sandbox_recover.db')"
     ```
  3. Extract deleted records from `/tmp/sandbox_recover.db` and insert into production, or perform full restore if corruption is systemic.
* **Validation:**
  1. Verify SHA-256 canonical compliance evidence matches pre-incident records.
  2. Validate legal holds (`ComplianceLegalHold`) remain intact.
* **Escalation:** Data Protection Officer (DPO) + Lead SRE.
* **Post-Incident Actions:** Audit audit timeline (`GET /api/v1/compliance/audit/timeline`) to identify root actor/call.

---

### DR-05: SECRET OR CREDENTIAL COMPROMISE (JWT / Fernet Key)
* **Detection:**
  - Security incident alert: suspicious multi-IP session activity or compromised server environment.
* **Immediate Containment:**
  1. Invalidate all active user sessions immediately:
     ```bash
     python -m app.cli auth revoke-all-sessions
     ```
  2. Block ingress traffic at proxy level if external leak is active.
* **Recovery Steps:**
  1. Rotate `JWT_SECRET_KEY`:
     - Generate a new 32+ character cryptographically secure key (`openssl rand -hex 32`).
     - Update environment configuration `JWT_SECRET_KEY`.
  2. Rotate `CREDENTIAL_ENCRYPTION_KEY`:
     - Generate new Fernet key (`cryptography.fernet.Fernet.generate_key().decode()`).
     - Run credential re-encryption script across all stored AI provider keys.
  3. Restart API and Worker services.
* **Validation:**
  1. Verify old JWT tokens are rejected (`HTTP 401 Unauthorized`).
  2. Verify new user login succeeds and issues valid tokens.
  3. Verify provider credential decrypts successfully.
* **Escalation:** Chief Information Security Officer (CISO) + Security Response Team.
* **Post-Incident Actions:** Mandatory password reset for all users; comprehensive audit log review.

---

### DR-06: FULL ENVIRONMENT REBUILD (BARE METAL / CLEAN CONTAINER)
* **Detection:** Complete loss of host server or cloud availability zone.
* **Immediate Containment:** Route DNS to secondary failover region or DR staging.
* **Recovery Steps:**
  1. Provision clean host / container with Python 3.12+ and Node.js 20+.
  2. Clone codebase and install dependencies:
     ```bash
     pip install -r apps/api/requirements.txt
     npm install --prefix apps/web
     ```
  3. Restore database from offsite backup repository:
     ```bash
     python -c "from app.services.backup_service import BackupService; BackupService.restore_backup('<offsite_backup_path>')"
     alembic upgrade head
     ```
  4. Validate configuration:
     ```bash
     python -c "from app.core.config_validation import validate_production_configuration; validate_production_configuration()"
     ```
  5. Launch API and Worker services:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port 8000 &
     python -m app.workers.worker &
     npm run start --prefix apps/web &
     ```
* **Validation:**
  1. Run automated test suite: `pytest tests/unit/ tests/security/`.
  2. Run Playwright E2E verification: `npx playwright test tests/phase16.spec.ts`.
  3. Verify SRE dashboard: `/admin/operations`.
* **Escalation:** VP of Engineering.
* **Post-Incident Actions:** Document exact downtime duration and prepare Post-Mortem.

---

## 3. POST-RESTORE DATA INTEGRITY & TENANT ISOLATION CHECKLIST

Every restoration must complete the following verification checklist before returning to production service:

- [ ] **Alembic Version Check:** `alembic_version` matches `0015_phase14_compliance_data_governance`.
- [ ] **SQLite/Postgres Physical Integrity:** `PRAGMA integrity_check` returns `ok`.
- [ ] **Tenant Isolation Integrity:** Users in Organization A cannot access resources in Organization B.
- [ ] **Project Access Matrix:** `DIRECT_ACCESS > TEAM_ACCESS > ORGANIZATION_ACCESS > NO_ACCESS` verified.
- [ ] **Compliance Evidence Registry:** SHA-256 fingerprints on `ComplianceEvidence` match raw inputs.
- [ ] **Legal Preservation Holds:** Records marked under active legal hold remain immutable and locked.
- [ ] **Encryption Key Test:** Stored model provider API keys decrypt into valid credentials.
- [ ] **Readiness Probe:** `GET /health/ready` returns HTTP 200 with `HEALTHY`.

# AIREX — PRODUCTION ROLLBACK RUNBOOK (PHASE 17)
## Emergency Reversion Standard Operating Procedures

**Document Version:** 1.0.0  
**Target Scope:** Emergency Rollbacks across Application, Worker Fleet, Database Schema, and Ingress Traffic Routing

---

## 1. ROLLBACK DECISION MATRIX (TRIGGERS)

Initiate an immediate rollback when any of the following automated conditions occur during or immediately following deployment:

| Incident Symptom | Threshold Trigger | Rollback Action |
| :--- | :---: | :--- |
| **Elevated HTTP 5xx Error Rate** | > 2% over 2-minute rolling window | Fast Application Rollback |
| **p95 Latency Spike** | > 2000 ms over 3-minute window | Fast Application Rollback |
| **Readiness Probe Failure** | New pods fail `/health/ready` | Automatic Rollback via CI/CD |
| **Worker Poison Task Surge** | DLQ size increases by > 10 tasks/min | Worker Fleet Rollback |
| **Database Pool Exhaustion** | Pool utilization reaches 100% | Application Rollback + Kill idle sessions |
| **Cross-Tenant Isolation Breach** | 403 authorization anomalies | Emergency Maintenance Mode |

---

## 2. APPLICATION & WORKER FAST ROLLBACK (< 60 SECONDS)

Kubernetes maintains a revision history of all applied deployments. To revert to the previous known-good deployment:

```bash
# 1. Rollback API Deployment
kubectl rollout undo deployment/airex-api -n airex-prod

# 2. Rollback Web Frontend Deployment
kubectl rollout undo deployment/airex-web -n airex-prod

# 3. Rollback Worker Fleet Deployment
kubectl rollout undo deployment/airex-worker -n airex-prod

# 4. Monitor rollback execution
kubectl rollout status deployment/airex-api -n airex-prod --timeout=120s
kubectl rollout status deployment/airex-web -n airex-prod --timeout=120s
kubectl rollout status deployment/airex-worker -n airex-prod --timeout=120s
```

---

## 3. DATABASE MIGRATION ROLLBACK PROCEDURE

If a schema migration must be reverted, verify whether backward-compatible expand/contract guidelines were followed:

### Case A: Backward-Compatible Migration (Standard)
The newly added column or table was not yet marked mandatory. Application rollback (Section 2) immediately stabilizes the system. Schema cleanup can proceed offline:
```bash
# In the application repository:
alembic downgrade -1
```

### Case B: Destructive Migration or Severe Data Anomaly
If corrupted data was written or a catastrophic schema error occurred:
1. Put the application into maintenance mode:
   ```bash
   kubectl scale deployment/airex-api --replicas=0 -n airex-prod
   kubectl scale deployment/airex-worker --replicas=0 -n airex-prod
   ```
2. Execute point-in-time recovery (PITR) or restore from the pre-deployment snapshot using the automated DR engine:
   ```bash
   python -c "from app.services.backup_service import BackupService; BackupService.restore_backup('backups/pre_deploy_snapshot.db')"
   ```
3. Re-verify database integrity:
   ```bash
   python -c "from app.services.backup_service import BackupService; print(BackupService.verify_backup('backups/pre_deploy_snapshot.db'))"
   ```
4. Restore application pods to active replicas.

---

## 4. POST-ROLLBACK INCIDENT VERIFICATION

After rollback stabilization:
1. Verify SRE Operations dashboard at `https://app.airex.io/admin/operations`.
2. Confirm error rate has returned to < 0.1%.
3. Confirm worker queue depth is declining and DLQ depth is stationary.
4. Export incident logs and metrics snapshot for post-mortem analysis:
   ```bash
   kubectl logs -l app.kubernetes.io/component=api -n airex-prod --tail=500 > rollback_api_logs.txt
   ```

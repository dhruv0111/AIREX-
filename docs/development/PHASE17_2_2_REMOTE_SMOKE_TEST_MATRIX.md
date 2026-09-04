# AIREX Phase 17.2.2 — Remote Smoke Test Matrix

This matrix establishes the verification criteria for testing AIREX on a live Oracle Cloud Always Free VM deployment.

---

## 1. Automated vs. Manual Smoke Verification Overview

| Verification Domain | Total Checks | Automated via `smoke_test.sh` | Manual / UI Verification |
| :--- | :---: | :---: | :---: |
| **Infrastructure & Networking** | 5 | 5 | 0 |
| **Authentication & Access Control** | 7 | 7 | 0 |
| **Core Business APIs & Workflows** | 8 | 5 | 3 (Live LLM execution) |
| **Frontend Web Application (UI)** | 3 | 3 | Full interactive UI walk |
| **Data Governance & Operations** | 4 | 2 | 2 |
| **TOTAL** | **27** | **22** | **5** |

---

## 2. Automated Smoke Test Specifications (`smoke_test.sh`)

| # | Test Name | Target Endpoint | HTTP Method | Expected Status | Validation Logic |
| :-: | :--- | :--- | :---: | :---: | :--- |
| **1** | Health Liveness | `/health/live` | `GET` | `200 OK` | Pod kernel alive, Uvicorn loop responsive |
| **2** | Health Readiness | `/health/ready` | `GET` | `200 OK` | Database connection pool & Redis ping active |
| **3** | OpenAPI Spec | `/openapi.json` | `GET` | `200 OK` | OpenAPI 3.1.0 schema generated cleanly |
| **4** | Swagger Docs | `/docs` | `GET` | `200 OK` | Interactive Swagger UI assets reachable |
| **5** | Prometheus Metrics | `/metrics` | `GET` | `200 OK` | Prometheus scrape endpoint returns counters |
| **6** | Unauthenticated Ops | `/api/v1/system/operations/overview` | `GET` | `401 Unauthorized` | Security middleware enforces JWT on ops routes |
| **7** | Unauthenticated Projects | `/api/v1/projects` | `GET` | `401 Unauthorized` | Project listing requires valid Bearer token |
| **8** | Unauthenticated Evaluations | `/api/v1/evaluations` | `GET` | `401 Unauthorized` | Evaluation routes protected by auth barrier |
| **9** | User Registration | `/api/v1/auth/register` | `POST` | `201 Created` | User created in PostgreSQL with bcrypt hash |
| **10** | Duplicate Registration | `/api/v1/auth/register` | `POST` | `409 Conflict` | Unique email constraint correctly enforced |
| **11** | User Authentication | `/api/v1/auth/login` | `POST` | `200 OK` | JWT access token issued with expiry |
| **12** | Authenticated Profile | `/api/v1/auth/me` | `GET` | `200 OK` | Decodes JWT claims and returns user identity |
| **13** | Authenticated Projects | `/api/v1/projects` | `GET` | `200 OK` | Retrieves project list for authenticated user |
| **14** | Project Creation | `/api/v1/projects` | `POST` | `201 Created` | Creates new tenant project entity in database |
| **15** | Evaluations List | `/api/v1/evaluations` | `GET` | `200 OK` | Retrieves evaluation registry records |
| **16** | Benchmark Suites | `/api/v1/benchmarks/suites` | `GET` | `200 OK` | Returns active reliability benchmark suites |
| **17** | SRE Ops Dashboard | `/api/v1/system/operations/overview` | `GET` | `200 OK` | Returns worker health, latency, error budgets |
| **18** | Web App Landing | `/` | `GET` | `200 OK` | Next.js server-rendered landing page |
| **19** | Web Login Page | `/login` | `GET` | `200 OK` | Next.js client login form rendered |
| **20** | Web Register Page | `/register` | `GET` | `200 OK` | Next.js registration form rendered |

---

## 3. Manual Business & Deep Workflow Smoke Checklist

For end-to-end capabilities requiring live external LLM calls or interactive UI confirmation:

- [ ] **M.1 Project Access Control Verification**  
  *Action:* Create two test users (User A and User B). Verify User B cannot access or modify User A's private project (`403 Forbidden`).
  
- [ ] **M.2 Evaluation Execution & Worker Task Dispatch**  
  *Action:* Trigger a test evaluation run. Confirm worker pod consumes message from Redis queue (`task_queue`), updates status from `PENDING` to `RUNNING` to `COMPLETED`.
  
- [ ] **M.3 Dead Letter Queue (DLQ) Resilience**  
  *Action:* Post a malformed evaluation payload. Verify task retries 3 times with exponential backoff and moves to `dlq_failed_tasks` without crashing the worker fleet.
  
- [ ] **M.4 Sensitive Data Redaction Inspection**  
  *Action:* Ingest a sample trace containing test PII (e.g. `user_ssn: "123-45-6789"`). Confirm automated redaction replaces sensitive tokens with `[REDACTED_SSN]`.
  
- [ ] **M.5 Legal Hold & Retention Policy Dry-Run**  
  *Action:* Place legal hold on project. Run retention dry-run command. Verify legal hold protected datasets are flagged as exempt from pruning.

---

## 4. Execution Command Reference

```bash
# Automated Suite Execution:
./scripts/free-cloud/smoke_test.sh http://api.<VM_PUBLIC_IP>.sslip.io http://app.<VM_PUBLIC_IP>.sslip.io
```

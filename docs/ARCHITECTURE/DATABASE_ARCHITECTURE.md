# Database Architecture — AIREX

**Primary store:** PostgreSQL 16 + pgvector (PRD §53–§54). **Cache/queue:** Redis (§55). **Artifacts:** object storage (MinIO/S3). **Migrations:** Alembic.

This document resolves the PRD's entity list (PRD §53) and the implied entities from [`DATA_MODEL_REQUIREMENTS.md`](../PRD_ANALYSIS/DATA_MODEL_REQUIREMENTS.md) into a concrete schema. Every assumption that fills a PRD gap is recorded (see also [`ARCHITECTURE_DECISIONS.md`](./ARCHITECTURE_DECISIONS.md) and the Ambiguity Register).

---

## 1. Design Rules

| Rule | Implementation |
|------|----------------|
| Tenant scoping | Every tenant-owned table has `organization_id BIGINT NOT NULL`; composite PKs/FKs include tenant where practical; PostgreSQL RLS enabled as defense-in-depth |
| IDs | `BIGINT GENERATED ALWAYS AS IDENTITY` (or ULID `UUID` for cross-system ids like trace/job). Unique `request_id`/`job_id` are UUIDv7 (sortable) |
| Versioning | `datasets`, `prompts`, `evaluators`, `evaluation_configs`, `pricing_configs`, `generated_tests` store immutable version rows; runs reference **version rows** (FR-VERSION-001, BR-DATASET-003) |
| Immutability | `experiments`, `dataset_versions`, `audit_logs`, `evaluation_results` are write-once (app-enforced + trigger-guarded where needed) |
| Flexible payloads | `metadata`, `metrics`, `parameters` stored as `JSONB` |
| Indexing | All tenant tables indexed on `organization_id`; hot queries indexed (see §4) |
| Time-series | `traces`, `trace_events`, `metrics_samples` partitioned by time (native partitioning); retention per policy |

---

## 2. Core Schema (PostgreSQL)

### Identity & tenancy
- `users (id, email UNIQUE, password_hash, email_verified_at, status, created_at, updated_at)`
- `organizations (id, name, slug UNIQUE, settings JSONB, privacy_policy JSONB, created_at)`
- `organization_members (organization_id, user_id, role, joined_at, PK(organization_id,user_id))`
- `projects (id, organization_id, name, description, application_type, environment, endpoint, endpoint_auth JSONB, model_config JSONB, evaluation_config JSONB, archived BOOLEAN, created_at, updated_at)`
- `environments (id, organization_id, project_id, name, model_ref, endpoint, credentials_ref, policies JSONB)`
- `providers (id, organization_id, type, base_url, is_local, created_at)`
- `models (id, organization_id, provider_id, name, model_ref, api_key_encrypted, temperature, max_tokens, timeout_ms, retry_policy JSONB, version, status, created_at)`
- `api_keys (id, organization_id, name, key_hash UNIQUE, key_prefix, encrypted_secret, scopes JSONB, created_at, deleted_at, created_by)`
- `pricing_configs (id, organization_id, model_id, version, price_per_1k_input, price_per_1k_output, currency, effective_from, created_at)` — immutable rows (FR-COST-002)

### Dataset & tests
- `datasets (id, organization_id, project_id, name, source_format, current_version_id, created_at)`
- `dataset_versions (id, dataset_id, version_no, file_ref (object storage), row_count, schema JSONB, checksum, created_by, created_at)` — immutable (BR-DATASET-002)
- `test_cases (id, organization_id, project_id, dataset_version_id, input, expected_output, context JSONB, metadata JSONB, tags TEXT[], difficulty, category, generated_by, generation_id, version_no, approval_status, created_at)` (AC-TESTGEN-002..006)
- `test_runs (id, organization_id, project_id, dataset_version_id, model_id, prompt_version_id, config_version_id, status, started_at, finished_at, total, passed, failed, warning)`
- `test_results (id, test_run_id, test_case_id, input, expected_output, actual_output, context JSONB, metrics JSONB, score, status, latency_ms, input_tokens, output_tokens, cost, failure_classification, reason, trace_id, created_at)` — written per test (partial persistence, §89)

### Evaluation & experiments
- `evaluators (id, organization_id, type, version, config JSONB, is_ai_judge, judge_model_ref, judge_prompt_ref, created_at)`
- `evaluation_configs (id, organization_id, project_id, version, evaluator_versions JSONB, score_weights JSONB, quality_gate JSONB, created_at)` (AC-SCORE-004, §78)
- `evaluation_runs (id, organization_id, project_id, dataset_version_id, model_id, model_version, prompt_version_id, evaluator_config_version, environment, status, job_id, score, metrics JSONB, regression_status, quality_gate_status, error, created_at, completed_at)`
- `experiments (id, organization_id, project_id, dataset_version_id, model_id, model_version, prompt_version_id, parameters JSONB, environment, timestamp, metrics JSONB, results JSONB, score_config JSONB, status, created_at)` — immutable after completion (FR-EXPERIMENT-002)
- `experiment_metrics (id, experiment_id, metric, value, unit, created_at)`
- `prompts (id, organization_id, project_id, name, created_at)`
- `prompt_versions (id, prompt_id, version_no, content, system_prompt, parameters JSONB, created_by, created_at)` — immutable
- `regression_baselines (id, organization_id, project_id, experiment_id, label, created_at)`
- `regression_runs (id, organization_id, project_id, baseline_experiment_id, candidate_experiment_id, deltas JSONB, verdict, threshold_policy_version, created_at)`

### Observability & traces
- `traces (id UUID PK, organization_id, project_id, request_id, model_ref, prompt_ref, status, started_at, finished_at, duration_ms, token_usage JSONB, cost, error, redaction_applied BOOLEAN)` — partitioned by `started_at`
- `trace_events (id, trace_id, step, sequence, duration_ms, input_ref, output_ref, metadata JSONB, error, created_at)` — partitioned; payloads in object storage, references here
- `metrics_samples (id, organization_id, project_id, scope, metric, value, bucket_ts)` — partitioned; source for P50/P95/P99 (§30)
- `metric_aggregates (organization_id, project_id, scope, metric, p50, p95, p99, avg, error_rate, rps, window_start, window_end)` — precomputed by aggregation jobs

### Alerting & notifications
- `alert_rules (id, organization_id, project_id, type, severity, threshold, duration_seconds, cooldown_seconds, enabled, channel, created_at, updated_at)`
- `alerts (id, organization_id, project_id, rule_id, severity, metric, value, status, created_at, resolved_at)`
- `notifications (id, organization_id, user_id, kind, channel, payload JSONB, status, created_at, sent_at)`

### Research
- `research_projects (id, organization_id, name, hypothesis, created_at)`
- `research_experiments (id, organization_id, research_project_id, variables JSONB, baseline_ref, treatment_ref, dataset_version_id, metrics JSONB, results JSONB, statistics JSONB, charts JSONB, conclusions TEXT, methodology TEXT, reproducibility JSONB, status, created_at)`

### Reporting & artifacts
- `reports (id, organization_id, project_id, experiment_id, evaluation_run_id, format, sections JSONB, artifact_ref, status, created_at)`
- `exports (id, organization_id, project_id, kind, format, artifact_ref, status, created_at, created_by)`

### Audit & events
- `audit_logs (id, organization_id, actor_id, actor_email, action, resource_type, resource_id, ip, user_agent, result, details JSONB, created_at)` — append-only, index (organization_id, created_at) (SEC-AUDIT-001..004)
- `outbox_events (id UUID, aggregate_type, aggregate_id, event_type, payload JSONB, created_at, processed_at)` — transactional outbox (see [`EVENT_ARCHITECTURE.md`](./EVENT_ARCHITECTURE.md))

### Human review & judge
- `human_reviews (id, organization_id, evaluation_run_id, test_result_id, ai_verdict, human_verdict, reviewer_id, comment, created_at)` (FR-HUMAN-001..003)
- `calibration_samples (id, organization_id, experiment_id, sample_size, ai_agreement, created_at)` (FR-HUMAN-005/006)
- `judge_judgments (id, evaluation_run_id, test_result_id, evaluator_model, evaluator_prompt_ref, evaluator_version, score, confidence, explanation, created_at)` (FR-JUDGE-002)

---

## 3. Vector Store (pgvector, PRD §54)

- `rag_documents (id, organization_id, project_id, name, source, version, created_at)`
- `rag_chunks (id, document_id, chunk_id, embedding VECTOR(1536|3072), metadata JSONB, source, version, content_hash)` — HNSW index on embedding
  - Index: `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`
  - Embedding dimension depends on configured embedding model (per-project, versioned — AMB-VECTOR-001 resolution).
- RAG retrieval evaluation queries this store (context relevance/precision/recall/ranking, §24).
- Optional external vector DB is a later swap behind a `VectorStorePort` (§54, AMB-VECTOR-001).

---

## 4. Redis Usage (§55)

| Key space | Purpose | TTL |
|-----------|---------|-----|
| `arq:queue:*` | Job queue (Arq) | — |
| `rl:{org}:{scope}` | Rate-limit counters (sliding window) | window |
| `cache:dashboard:{org}:{project}` | Aggregated dashboard metrics | 30 s–5 min |
| `cache:versions:{...}` | Version/config lookups | 10 min |
| `lock:{org}:{project}:eval` | Distributed evaluation lock per project | 30 s |
| `temp:upload:{upload_id}` | In-progress dataset import state | 1 h |
| `pubsub:events` | Domain event fan-out (notifications, SSE) | — |
| `session:ratelimit`, `worker:provider:{id}` | Provider concurrency semaphore | — |

---

## 5. Object Storage (MinIO local / S3 prod)

| Bucket | Contents |
|--------|----------|
| `datasets` | dataset version files (CSV/JSON/JSONL) + parsed rows cache |
| `exports` | CSV/JSON/MD/PDF exports (§79) |
| `reports` | report artifacts (§80) |
| `traces` | trace event payloads (when stored; per privacy toggles §60) |
| `uploads` | temporary upload staging |

Metadata stays in Postgres; object storage holds blobs. S3-compatible API so MinIO (free, local) and AWS S3 (prod) are interchangeable via the `StoragePort`.

---

## 6. Migrations & Data Lifecycle

- Alembic versioned migrations; `./migrations`; every change is additive-first (expand/contract) to support zero-downtime deploys.
- **Retention policy (AMB-RETENTION-001 resolution):** org-configurable tiers:
  - Raw prompt/response/trace payloads: default **30 days** (or OFF per privacy toggle).
  - Aggregated metrics: default **13 months**.
  - Immutable records (experiments, dataset versions, audit logs): **no auto-delete** (immutability wins); org admin may purge with confirmation and audit entry.
- Purge jobs run periodically; purging writes an audit event.

---

## 7. Indexing Strategy

| Query pattern | Index |
|---------------|-------|
| Tenant lookups | `(organization_id)` on all tenant tables |
| Auth | `users(email) UNIQUE`, `api_keys(key_hash) UNIQUE` |
| Project pages | `projects(organization_id, archived)`, `datasets(organization_id, project_id)` |
| Evaluation history | `evaluation_runs(organization_id, project_id, created_at DESC)` |
| Trace explorer | `traces(organization_id, project_id, started_at DESC)` + partition key |
| Metrics windows | `metrics_samples(organization_id, project_id, metric, bucket_ts)` |
| Alert evaluation | `alert_rules(organization_id, enabled)` |
| Audit viewer | `audit_logs(organization_id, created_at DESC)` |
| Version lookups | `dataset_versions(dataset_id, version_no) UNIQUE` |
| Vector search | HNSW on `rag_chunks.embedding` |

---

## 8. Backups & DR

- Daily full + WAL archiving (PITR) — managed Postgres (RDS) or pgBackRest for self-host.
- Object storage versioning + cross-region replication (prod).
- Redis: AOF enabled; ephemeral (rebuilt from DB) for cache/queue semantics.
- RPO ≤ 5 min, RTO ≤ 1 h for MVP (see [`INFRASTRUCTURE.md`](./INFRASTRUCTURE.md)).

---

## 9. Decision Summary

| Decision | WHY | Alternatives | Tradeoff | Cost | Scalability | Security |
|----------|-----|--------------|----------|------|-------------|----------|
| PostgreSQL + pgvector | PRD §53–§54; single store for relational + vectors | Separate vector DB | pgvector matures with Postgres | Free | Partitioning + HNSW; later external vector DB | RLS multi-tenancy |
| JSONB for flexible metrics/metadata | Evaluator outputs are heterogeneous | EAV tables | Less strict typing | Free | Indexed where needed | Validate via Pydantic before write |
| Immutable version rows | Reproducibility invariants (§16, §34, §78) | Mutable tables | More rows | Free | Partition by version | Audit-friendly |
| Time-based partitioning | Traces/metrics grow fast | Single tables | More complex schema | Free | Retains hot windows | Scoped by tenant |
| Outbox table | Reliable side effects | Direct pub/sub only | Extra table + relay job | Free | Scales with consumers | Transactional consistency |
| RLS as second barrier | Defense-in-depth for AC-SEC-001/002 | Repository scoping only | RLS overhead small | Free | — | Strong isolation |

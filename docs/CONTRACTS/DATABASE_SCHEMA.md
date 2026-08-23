# Database Schema Contract — AIREX

**Engine:** PostgreSQL 16 + pgvector. **Contract status:** authoritative DDL-level specification derived from the PRD (PRD §53–§55, §60, §78) and the architecture ([`DATABASE_ARCHITECTURE.md`](../ARCHITECTURE/DATABASE_ARCHITECTURE.md)). No application code — this is the data contract.

**Conventions**
- **IDs:** `BIGINT GENERATED ALWAYS AS IDENTITY` for relational PKs; `UUID` (v7) for cross-system/evented ids (`traces.id`, `outbox_events.id`, `request_id`/`job_id`).
- **Tenancy:** every tenant-owned table has `organization_id` and is scoped in all queries; PostgreSQL RLS enabled.
- **Timestamps:** `created_at`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` on mutable tables.
- **Audit fields:** `created_by` (actor user id) where actor is meaningful; full audit in `audit_logs`.
- **Soft delete:** only on tables where history must be preserved; hard delete only where the PRD mandates deletion semantics (project delete §11, user removal §10).
- **JSONB** for flexible payloads (metadata, metrics, configs); validated by Pydantic before write.
- **Enums** implemented as `TEXT` + `CHECK` (or native `ENUM`); noted per column.

---

## 1. Table Catalog

Grouped as in [`DATA_MODEL_REQUIREMENTS.md`](../PRD_ANALYSIS/DATA_MODEL_REQUIREMENTS.md). `◇` = tenant-owned (RLS enabled). `◈` = version-immutable.

### 1.1 Identity & Tenancy

#### users
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| email | CITEXT | NO | — | UNIQUE (AC-AUTH-002) |
| password_hash | TEXT | NO | — | argon2id (SEC-AUTH-002) |
| full_name | TEXT | NO | — | |
| email_verified_at | TIMESTAMPTZ | YES | NULL | AC-AUTH-005 |
| status | TEXT | NO | 'active' | CHECK in ('active','pending','disabled') |
| last_login_at | TIMESTAMPTZ | YES | NULL | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | audit |
- **PK:** `users_pk (id)`. **Unique:** `users_email_key (email)`. **Index:** `users_email_idx (email)` (covers verification).
- **Soft delete:** no (hard removal → immediate access loss, AC-SEC-004; referenced audit rows preserved).
- **Retention:** account data retained per privacy policy; disabled users purged after org-level retention window (AMB-RETENTION-001 resolution).

#### organizations
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| name | TEXT | NO | — | |
| slug | CITEXT | NO | — | UNIQUE |
| settings | JSONB | NO | '{}' | org settings persisted (FR-ORG-007) |
| privacy_policy | JSONB | NO | '{}' | §60 toggles: raw_storage, pii_masking, prompt_storage, response_storage, retention_days |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
| created_by | BIGINT | YES | NULL | FK → users.id |
- **PK:** `organizations_pk (id)`. **Unique:** `organizations_slug_key (slug)`.
- **RLS:** `organizations` visible to members (custom policy; see §7).

#### organization_members
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| organization_id | BIGINT | NO | — | PK[1], FK → organizations.id |
| user_id | BIGINT | NO | — | PK[2], FK → users.id |
| role | TEXT | NO | 'viewer' | CHECK in ('admin','project_owner','engineer','viewer') (PRD §7) |
| joined_at | TIMESTAMPTZ | NO | now() | |
| invited_by | BIGINT | YES | NULL | FK → users.id |
- **PK:** `organization_members_pk (organization_id, user_id)`.
- **Index:** `organization_members_user_idx (user_id)`.
- **RLS:** users see rows where `user_id = current_user` or `organization_id` is one they belong to.
- **Soft delete:** no; removal deletes the row (immediate access loss, AC-SEC-004).

#### api_keys
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id; ◇ |
| name | TEXT | NO | — | |
| key_prefix | TEXT | NO | — | e.g., `airex_` + 8 chars (display) |
| key_hash | TEXT | NO | — | UNIQUE; lookup only (AC-SEC-003) |
| encrypted_secret | TEXT | NO | — | Fernet/KMS encrypted; never returned |
| scopes | JSONB | NO | '["ci"]' | allowed scopes (e.g., ci, cli) |
| created_by | BIGINT | NO | — | FK → users.id |
| expires_at | TIMESTAMPTZ | YES | NULL | |
| created_at | TIMESTAMPTZ | NO | now() | |
| deleted_at | TIMESTAMPTZ | YES | NULL | soft delete (revocation) |
- **PK:** `api_keys_pk (id)`. **Unique:** `api_keys_hash_key (key_hash)`.
- **Index:** `api_keys_org_idx (organization_id, deleted_at)`.
- **Soft delete:** yes (`deleted_at`) — revocation preserved for audit (§61).
- **Retention:** revoked keys retained 90 days (audit), then purged.

### 1.2 Projects, Environments, Providers, Models

#### projects ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| name | TEXT | NO | — | |
| description | TEXT | YES | NULL | §11 |
| application_type | TEXT | NO | 'generic_llm' | §11 |
| environment | TEXT | NO | 'development' | CHECK in ('development','staging','production') §77 |
| endpoint | TEXT | YES | NULL | application endpoint §11 |
| endpoint_auth | JSONB | YES | NULL | auth config for the app endpoint §11 |
| model_config | JSONB | YES | NULL | §11 |
| evaluation_config | JSONB | YES | NULL | §11 |
| archived | BOOLEAN | NO | false | FR-PROJECT-005 |
| created_by | BIGINT | NO | — | FK → users.id |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
| deleted_at | TIMESTAMPTZ | YES | NULL | soft delete; hard delete only after confirmation (FR-PROJECT-004) |
- **PK:** `projects_pk (id)`. **Index:** `projects_org_idx (organization_id, archived)`, `projects_org_name_idx (organization_id, name)`.
- **Unique:** `(organization_id, name)` where `deleted_at IS NULL`.
- **RLS:** members of org.

#### environments ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| project_id | BIGINT | NO | — | FK → projects.id |
| name | TEXT | NO | — | CHECK in ('development','staging','production') |
| model_id | BIGINT | YES | NULL | FK → models.id (per-env model §77) |
| endpoint | TEXT | YES | NULL | |
| credentials_ref | TEXT | YES | NULL | secret reference (never raw) §77 |
| policies | JSONB | YES | NULL | eval policies per env §77 |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `environments_pk (id)`. **Index:** `environments_project_idx (project_id, name)` UNIQUE.
- **RLS:** org members; production env rows readable only per FR-ENV-003 policy.

#### providers ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| type | TEXT | NO | — | CHECK in ('openai','anthropic','gemini','openai_compatible','local','huggingface') §12 |
| base_url | TEXT | YES | NULL | §12 |
| is_local | BOOLEAN | NO | false | local/OSS models §12 |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `providers_pk (id)`.

#### models ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| provider_id | BIGINT | NO | — | FK → providers.id |
| name | TEXT | NO | — | |
| model_ref | TEXT | NO | — | provider model id (e.g., gpt-4o) |
| api_key_encrypted | TEXT | YES | NULL | Fernet/KMS; never displayed (FR-PROVIDER-008, AC-SEC-003) |
| temperature | NUMERIC(4,2) | YES | NULL | §12 |
| max_tokens | INTEGER | YES | NULL | §12 |
| timeout_ms | INTEGER | NO | 60000 | §12 |
| retry_policy | JSONB | YES | NULL | §12, §58 |
| version | TEXT | YES | NULL | model version (FR-VERSION-001) |
| status | TEXT | NO | 'active' | CHECK in ('active','disabled','error') |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `models_pk (id)`. **Unique:** `(organization_id, provider_id, model_ref, COALESCE(version,''))`.
- **RLS:** org members.

#### pricing_configs ◈ ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| model_id | BIGINT | NO | — | FK → models.id |
| version_no | INTEGER | NO | 1 | versioned (FR-COST-002) |
| price_per_1k_input | NUMERIC(12,6) | NO | — | §31 |
| price_per_1k_output | NUMERIC(12,6) | NO | — | §31 |
| currency | CHAR(3) | NO | 'USD' | |
| effective_from | TIMESTAMPTZ | NO | now() | |
| created_by | BIGINT | NO | — | FK → users.id |
| created_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `pricing_configs_pk (id)`. **Unique:** `(model_id, version_no)`.
- **Immutable:** rows never updated (new version created).

### 1.3 Datasets & Tests

#### datasets ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| project_id | BIGINT | NO | — | FK → projects.id |
| name | TEXT | NO | — | |
| dataset_id | TEXT | NO | — | user-facing id; duplicates rejected (FR-DATASET-013) |
| source_format | TEXT | NO | — | CHECK in ('csv','json','jsonl','manual','generated') §15 |
| current_version_id | BIGINT | YES | NULL | FK → dataset_versions.id (latest) |
| created_by | BIGINT | NO | — | FK → users.id |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
| deleted_at | TIMESTAMPTZ | YES | NULL | soft delete (audit: dataset deleted §61) |
- **PK:** `datasets_pk (id)`. **Unique:** `(organization_id, dataset_id)`.
- **Soft delete:** yes.

#### dataset_versions ◈ ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| dataset_id | BIGINT | NO | — | FK → datasets.id |
| version_no | INTEGER | NO | 1 | v1, v2, v3 (§16) |
| file_ref | TEXT | NO | — | object storage key |
| row_count | INTEGER | NO | 0 | |
| schema | JSONB | YES | NULL | detected columns (§15) |
| checksum | TEXT | NO | — | sha256 (immutability) |
| created_by | BIGINT | NO | — | FK → users.id |
| created_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `dataset_versions_pk (id)`. **Unique:** `(dataset_id, version_no)`.
- **Immutable:** no UPDATE allowed (DB trigger); experiments reference this row (BR-DATASET-003).

#### test_cases ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| project_id | BIGINT | NO | — | FK → projects.id |
| dataset_version_id | BIGINT | YES | NULL | FK → dataset_versions.id |
| generation_id | BIGINT | YES | NULL | FK → test_generations.id (if AI-generated) |
| input | TEXT | NO | — | §15 |
| expected_output | TEXT | YES | NULL | §15 |
| context | JSONB | YES | NULL | §15 |
| metadata | JSONB | YES | NULL | tags, difficulty, category (AC-TESTGEN-002) |
| tags | TEXT[] | YES | NULL | |
| difficulty | TEXT | YES | NULL | |
| category | TEXT | YES | NULL | CHECK in ('normal','edge_case','adversarial','ambiguous','safety','prompt_injection','long_context','multilingual') §26 |
| version_no | INTEGER | NO | 1 | generated tests versioned (AC-TESTGEN-006) |
| approval_status | TEXT | NO | 'pending' | CHECK in ('pending','approved','rejected') (AC-TESTGEN-004) |
| created_by | BIGINT | NO | — | FK → users.id |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
| deleted_at | TIMESTAMPTZ | YES | NULL | |
- **PK:** `test_cases_pk (id)`. **Index:** `test_cases_dataset_idx (dataset_version_id)`, `test_cases_generation_idx (generation_id)`.
- **Soft delete:** yes (rejected can be retained for versioning).

#### test_generations ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| project_id | BIGINT | NO | — | FK → projects.id |
| status | TEXT | NO | 'queued' | job status |
| requested_count | INTEGER | NO | — | configurable (AC-TESTGEN-001) |
| inputs | JSONB | NO | '{}' | app description, docs, existing tests (§26) |
| job_id | UUID | YES | NULL | |
| created_by | BIGINT | NO | — | FK → users.id |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

#### test_runs ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| project_id | BIGINT | NO | — | FK → projects.id |
| evaluation_run_id | BIGINT | NO | — | FK → evaluation_runs.id |
| dataset_version_id | BIGINT | NO | — | FK → dataset_versions.id |
| status | TEXT | NO | 'queued' | CHECK in ('queued','running','completed','failed','cancelled') |
| started_at / finished_at | TIMESTAMPTZ | YES | NULL | |
| total / passed / failed / warning | INTEGER | NO | 0 | §70 counts |
- **PK:** `test_runs_pk (id)`.

#### test_results ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| test_run_id | BIGINT | NO | — | FK → test_runs.id |
| test_case_id | BIGINT | NO | — | FK → test_cases.id |
| input | TEXT | NO | — | snapshot (§17) |
| expected_output | TEXT | YES | NULL | snapshot |
| actual_output | TEXT | YES | NULL | snapshot |
| context | JSONB | YES | NULL | snapshot |
| metrics | JSONB | NO | '{}' | per-evaluator scores (§17) |
| score | NUMERIC(6,4) | YES | NULL | 0–1 normalized |
| status | TEXT | NO | 'pending' | CHECK in ('pending','pass','fail','warning','error') |
| latency_ms | INTEGER | YES | NULL | §30 |
| input_tokens / output_tokens / total_tokens | INTEGER | YES | NULL | §30 |
| cost | NUMERIC(12,8) | YES | NULL | §31 |
| failure_classification | TEXT | YES | NULL | CHECK in ('retrieval_failure','generation_failure','context_failure','prompt_failure','model_failure','data_failure','unknown') §25 |
| reason | TEXT | YES | NULL | |
| trace_id | UUID | YES | NULL | FK → traces.id |
| created_at | TIMESTAMPTZ | NO | now() | write-once |
- **PK:** `test_results_pk (id)`. **Index:** `test_results_run_idx (test_run_id)`, `test_results_status_idx (status)`.
- **Write-once:** inserted per test (partial persistence §89); never updated except `status`/`metrics` reconciliation.

### 1.4 Evaluation, Experiments, Prompts, Regression

#### evaluators ◈ ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| type | TEXT | NO | — | CHECK in ('exact_match','semantic_similarity','answer_correctness','faithfulness','hallucination','rag_retrieval','rag_generation','toxicity','bias','prompt_injection','data_leakage','response_format','latency','cost','consistency','regression') §18 |
| version_no | INTEGER | NO | 1 | evaluator versioning (FR-VERSION-001) |
| config | JSONB | NO | '{}' | thresholds, case sensitivity (§19–§20) |
| is_ai_judge | BOOLEAN | NO | false | §74 |
| judge_model_id | BIGINT | YES | NULL | FK → models.id (AI judge) |
| created_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `evaluators_pk (id)`. **Unique:** `(organization_id, type, version_no)`.

#### evaluation_configs ◈ ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| project_id | BIGINT | NO | — | FK → projects.id |
| version_no | INTEGER | NO | 1 | |
| evaluator_versions | JSONB | NO | '{}' | evaluator id/version per metric |
| score_weights | JSONB | NO | '{}' | reliability score weights (AC-SCORE-004) |
| quality_gate | JSONB | NO | '{}' | gate thresholds §39 |
| created_by | BIGINT | NO | — | FK → users.id |
| created_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `evaluation_configs_pk (id)`. **Unique:** `(project_id, version_no)`.

#### evaluation_runs ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| project_id | BIGINT | NO | — | FK → projects.id |
| environment | TEXT | NO | 'development' | §34 |
| dataset_version_id | BIGINT | NO | — | FK → dataset_versions.id |
| model_id | BIGINT | NO | — | FK → models.id |
| model_version | TEXT | YES | NULL | |
| prompt_version_id | BIGINT | YES | NULL | FK → prompt_versions.id |
| evaluation_config_id | BIGINT | NO | — | FK → evaluation_configs.id |
| status | TEXT | NO | 'queued' | CHECK in ('queued','running','completed','failed','cancelled') (QUEUED→RUNNING→COMPLETED, §102 Step 7) |
| job_id | UUID | YES | NULL | Arq job |
| score | NUMERIC(6,2) | YES | NULL | 0–100 (AC-SCORE-001) |
| metrics | JSONB | YES | NULL | §17, §102 Step 8 |
| regression_status | TEXT | YES | NULL | CHECK in ('no_baseline','pass','warning','regression_detected') |
| quality_gate_status | TEXT | YES | NULL | CHECK in ('not_evaluated','pass','fail') |
| error | JSONB | YES | NULL | normalized error §63 |
| triggered_by | TEXT | NO | 'user' | user | ci | cli | api |
| created_by | BIGINT | YES | NULL | FK → users.id |
| created_at / completed_at | TIMESTAMPTZ | YES/NO | now() | |
- **PK:** `evaluation_runs_pk (id)`. **Index:** `evaluation_runs_project_idx (organization_id, project_id, created_at DESC)`.
- **Idempotency key** stored on run (see API).

#### experiments ◈ ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK → organizations.id |
| project_id | BIGINT | NO | — | FK → projects.id |
| dataset_version_id | BIGINT | NO | — | FK |
| model_id / model_version | BIGINT/TEXT | NO | — | FK / |
| prompt_version_id | BIGINT | YES | NULL | FK |
| parameters | JSONB | NO | '{}' | §34 |
| environment | TEXT | NO | — | §34 |
| timestamp | TIMESTAMPTZ | NO | now() | §34 |
| metrics | JSONB | NO | '{}' | §34 |
| results | JSONB | NO | '{}' | §34 |
| score_config | JSONB | NO | '{}' | snapshot (AC-SCORE-004) |
| status | TEXT | NO | 'running' | CHECK in ('running','completed','failed') |
| created_by | BIGINT | NO | — | FK → users.id |
| created_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `experiments_pk (id)`. **Immutable after completion:** no UPDATE of metrics/results once `status='completed'` (BR-EXPERIMENT-001; DB trigger).

#### experiment_metrics ◈
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| experiment_id | BIGINT | NO | — | FK → experiments.id |
| metric | TEXT | NO | — | e.g., accuracy, faithfulness, hallucination, safety, p95_latency, cost_per_request |
| value | NUMERIC(18,6) | NO | — | |
| unit | TEXT | YES | NULL | |

#### prompts ◇ / prompt_versions ◈
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| prompts.id | BIGINT | NO | identity | PK |
| prompts.organization_id | BIGINT | NO | — | FK |
| prompts.project_id | BIGINT | NO | — | FK |
| prompts.name | TEXT | NO | — | |
| prompt_versions.id | BIGINT | NO | identity | PK |
| prompt_versions.prompt_id | BIGINT | NO | — | FK → prompts.id |
| prompt_versions.version_no | INTEGER | NO | 1 | v1/v2/v3 (§33) |
| prompt_versions.system_prompt | TEXT | YES | NULL | |
| prompt_versions.content | TEXT | NO | — | |
| prompt_versions.parameters | JSONB | YES | NULL | |
| prompt_versions.created_by | BIGINT | NO | — | FK |
| prompt_versions.created_at | TIMESTAMPTZ | NO | now() | |
- **Uniques:** `prompts_pk`, `prompt_versions_pk`, `(prompt_id, version_no)`.

#### regression_baselines ◇ / regression_runs ◈ ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| regression_baselines.id | BIGINT | NO | identity | PK |
| regression_baselines.organization_id | BIGINT | NO | — | FK |
| regression_baselines.project_id | BIGINT | NO | — | FK |
| regression_baselines.experiment_id | BIGINT | NO | — | FK → experiments.id |
| regression_baselines.label | TEXT | YES | NULL | e.g., "Model A baseline" (§102 Step 13) |
| regression_baselines.created_at | TIMESTAMPTZ | NO | now() | |
| regression_runs.id | BIGINT | NO | identity | PK |
| regression_runs.organization_id | BIGINT | NO | — | FK |
| regression_runs.project_id | BIGINT | NO | — | FK |
| regression_runs.baseline_experiment_id | BIGINT | NO | — | FK |
| regression_runs.candidate_experiment_id | BIGINT | NO | — | FK |
| regression_runs.deltas | JSONB | NO | '{}' | per-metric deltas §36 |
| regression_runs.verdict | TEXT | NO | — | CHECK in ('pass','warning','regression_detected') §36 |
| regression_runs.threshold_policy | JSONB | NO | '{}' | snapshot of thresholds §37 |
| regression_runs.created_at | TIMESTAMPTZ | NO | now() | |
- **Unique:** `(project_id, experiment_id)` for baselines.

### 1.5 Observability, Traces, Metrics

#### traces ◇ (partitioned by `started_at`)
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | UUID | NO | gen_v7() | PK |
| organization_id | BIGINT | NO | — | FK |
| project_id | BIGINT | NO | — | FK |
| request_id | UUID | NO | — | §13 |
| model_ref | TEXT | YES | NULL | |
| prompt_ref | TEXT | YES | NULL | |
| status | TEXT | NO | 'ok' | CHECK in ('ok','error','timeout') |
| started_at / finished_at | TIMESTAMPTZ | NO/YES | now() | partition key (started_at) |
| duration_ms | INTEGER | YES | NULL | |
| token_usage | JSONB | YES | NULL | §13 |
| cost | NUMERIC(12,8) | YES | NULL | |
| error | JSONB | YES | NULL | |
| redaction_applied | BOOLEAN | NO | true | FR-OBS-007 |
- **PK:** `traces_pk (id, started_at)`.

#### trace_events ◇ (partitioned by `created_at`)
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| trace_id | UUID | NO | — | FK → traces.id |
| step | TEXT | NO | — | CHECK in ('user_request','retriever','documents','prompt_builder','llm','evaluator','response') §42 |
| sequence | INTEGER | NO | — | ordering §42 |
| duration_ms | INTEGER | YES | NULL | |
| input_ref / output_ref | TEXT | YES | NULL | object storage refs (redacted) §42 |
| metadata | JSONB | YES | NULL | |
| error | TEXT | YES | NULL | |
| created_at | TIMESTAMPTZ | NO | now() | partition key |
- **Index:** `(trace_id, sequence)` UNIQUE.

#### metrics_samples ◇ (partitioned by `bucket_ts`)
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id / project_id | BIGINT | NO | — | FK |
| scope | TEXT | NO | — | e.g., 'request','evaluation' |
| metric | TEXT | NO | — | e.g., 'latency_ms','cost','error' |
| value | NUMERIC(18,6) | NO | — | |
| bucket_ts | TIMESTAMPTZ | NO | now() | partition key |
- **Index:** `(organization_id, project_id, scope, metric, bucket_ts)`.

#### metric_aggregates ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id / project_id | BIGINT | NO | — | FK |
| scope | TEXT | NO | — | |
| metric | TEXT | NO | — | |
| p50 / p95 / p99 | NUMERIC(18,6) | YES | NULL | §30 |
| avg | NUMERIC(18,6) | YES | NULL | |
| error_rate | NUMERIC(8,6) | YES | NULL | |
| rps | NUMERIC(12,4) | YES | NULL | |
| window_start / window_end | TIMESTAMPTZ | NO | — | |
- **PK:** `(scope, metric, window_start, window_end, organization_id, project_id)`.

### 1.6 Alerting & Notifications

#### alert_rules ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id / project_id | BIGINT | NO | — | FK |
| type | TEXT | NO | — | CHECK in ('accuracy','hallucination','latency','error','cost','safety','model_failure') §43 |
| severity | TEXT | NO | 'warning' | CHECK in ('info','warning','critical') §44 |
| threshold | NUMERIC(18,6) | NO | — | §44 |
| operator | TEXT | NO | 'gt' | gt/gte/lt/lte |
| duration_seconds | INTEGER | NO | 600 | §44 |
| cooldown_seconds | INTEGER | NO | 3600 | §44 |
| channel | TEXT | NO | 'in_app' | CHECK in ('in_app','email','webhook') or array |
| enabled | BOOLEAN | NO | true | §44 |
| created_by | BIGINT | NO | — | FK |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `alert_rules_pk (id)`. **Index:** `alert_rules_enabled_idx (organization_id, enabled)`.

#### alerts ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id / project_id | BIGINT | NO | — | FK |
| rule_id | BIGINT | NO | — | FK → alert_rules.id |
| severity | TEXT | NO | — | |
| metric | TEXT | NO | — | |
| value | NUMERIC(18,6) | NO | — | |
| status | TEXT | NO | 'firing' | CHECK in ('firing','resolved','acknowledged') |
| created_at | TIMESTAMPTZ | NO | now() | |
| resolved_at | TIMESTAMPTZ | YES | NULL | |

#### notifications ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK |
| user_id | BIGINT | YES | NULL | FK → users.id |
| kind | TEXT | NO | — | §85 events |
| channel | TEXT | NO | 'in_app' | in_app | email | webhook |
| payload | JSONB | NO | '{}' | |
| status | TEXT | NO | 'pending' | pending | sent | failed |
| dedup_key | TEXT | YES | NULL | UNIQUE (idempotency) |
| created_at / sent_at | TIMESTAMPTZ | NO/YES | now() | |
- **Unique:** `(dedup_key)` where not null.

### 1.7 Research

#### research_projects ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK |
| name | TEXT | NO | — | |
| hypothesis | TEXT | YES | NULL | §47 |
| created_by | BIGINT | NO | — | FK |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

#### research_experiments ◈ ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK |
| research_project_id | BIGINT | NO | — | FK |
| variables | JSONB | NO | '{}' | baseline/treatment §47 |
| baseline_ref / treatment_ref | TEXT | YES | NULL | §47 |
| dataset_version_id | BIGINT | NO | — | FK |
| metrics | JSONB | NO | '{}' | |
| results | JSONB | NO | '{}' | |
| statistics | JSONB | YES | NULL | mean/median/std/percentiles/CI/effect size §48 |
| charts | JSONB | YES | NULL | chart data §47 |
| conclusions | TEXT | YES | NULL | |
| methodology | TEXT | YES | NULL | §81 |
| reproducibility | JSONB | YES | NULL | dataset/model/prompt/config/seed §81 |
| status | TEXT | NO | 'draft' | draft | running | completed |
| created_by | BIGINT | NO | — | FK |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
- **Immutable after completed** (research result integrity, §47/§81).

### 1.8 Reporting & Export

#### reports ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id / project_id | BIGINT | NO | — | FK |
| experiment_id / evaluation_run_id | BIGINT | YES | NULL | FK |
| format | TEXT | NO | 'markdown' | CHECK in ('markdown','pdf','json','csv') §79 |
| sections | JSONB | NO | '{}' | 13 sections §80 |
| artifact_ref | TEXT | YES | NULL | object storage key |
| status | TEXT | NO | 'queued' | queued | generating | ready | failed |
| created_by | BIGINT | NO | — | FK |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |

#### exports ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id / project_id | BIGINT | NO | — | FK |
| kind | TEXT | NO | — | test_results | evaluation_results | metrics | experiment_results | research_data §79 |
| format | TEXT | NO | — | csv | json | markdown | pdf |
| artifact_ref | TEXT | YES | NULL | |
| status | TEXT | NO | 'queued' | |
| created_by | BIGINT | NO | — | FK |
| created_at | TIMESTAMPTZ | NO | now() | |

### 1.9 Human Review, Calibration, AI Judge

#### human_reviews ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK |
| evaluation_run_id | BIGINT | NO | — | FK |
| test_result_id | BIGINT | NO | — | FK |
| ai_verdict | TEXT | NO | — | pass | fail | warning | uncertain |
| human_verdict | TEXT | YES | NULL | pass | fail | false_positive | skip §72 |
| reviewer_id | BIGINT | NO | — | FK → users.id |
| comment | TEXT | YES | NULL | |
| created_at / updated_at | TIMESTAMPTZ | NO | now() | |
- **Unique:** `(test_result_id, reviewer_id)` — decisions stored for analysis (FR-HUMAN-003).

#### calibration_samples ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | NO | — | FK |
| experiment_id | BIGINT | YES | NULL | FK |
| sample_size | INTEGER | NO | — | §73 |
| ai_agreement | NUMERIC(6,4) | YES | NULL | AI vs Human agreement §73 |
| created_at | TIMESTAMPTZ | NO | now() | |

#### judge_judgments ◈ ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| evaluation_run_id / test_result_id | BIGINT | NO | — | FK |
| evaluator_model | TEXT | NO | — | §74 |
| evaluator_prompt_ref | TEXT | NO | — | §74 |
| evaluator_version | TEXT | NO | — | §74 |
| score | NUMERIC(6,4) | NO | — | |
| confidence | NUMERIC(6,4) | YES | NULL | §75 |
| explanation | TEXT | YES | NULL | |
| created_at | TIMESTAMPTZ | NO | now() | |
- **Write-once** (reproducibility, §74).

### 1.10 Audit & Events

#### audit_logs ◇ (append-only)
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | BIGINT | NO | identity | PK |
| organization_id | BIGINT | YES | NULL | FK (null for platform-level) |
| actor_id | BIGINT | YES | NULL | FK → users.id |
| actor_email | TEXT | YES | NULL | §61 |
| action | TEXT | NO | — | login | api_key_created | api_key_deleted | project_created | dataset_deleted | evaluation_executed | config_changed | role_changed | … §61 |
| resource_type | TEXT | YES | NULL | |
| resource_id | TEXT | YES | NULL | |
| ip | INET | YES | NULL | §61 |
| user_agent | TEXT | YES | NULL | |
| result | TEXT | NO | 'success' | success | failure | denied |
| details | JSONB | YES | NULL | |
| created_at | TIMESTAMPTZ | NO | now() | |
- **PK:** `audit_logs_pk (id)`. **Index:** `audit_logs_org_time_idx (organization_id, created_at DESC)`.
- **Append-only:** no UPDATE/DELETE (DB trigger + restricted role) (AC-SEC-005). Optional per-row hash chain for tamper evidence.
- **Retention:** ≥ 13 months (org-configurable; immutable thereafter).

#### outbox_events
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| id | UUID | NO | gen_v7() | PK |
| aggregate_type | TEXT | NO | — | |
| aggregate_id | TEXT | NO | — | |
| event_type | TEXT | NO | — | §EVENT_CONTRACTS |
| payload | JSONB | NO | '{}' | |
| created_at | TIMESTAMPTZ | NO | now() | |
| processed_at | TIMESTAMPTZ | YES | NULL | |
| attempts | INTEGER | NO | 0 | |
- **Index:** `(processed_at, created_at)`.

### 1.11 Vector (pgvector)

#### rag_documents ◇ / rag_chunks ◇
| Column | Type | Null | Default | Notes |
|--------|------|------|---------|-------|
| rag_documents.id | BIGINT | NO | identity | PK |
| rag_documents.organization_id / project_id | BIGINT | NO | — | FK |
| rag_documents.name | TEXT | NO | — | |
| rag_documents.source | TEXT | YES | NULL | §54 |
| rag_documents.version | INTEGER | NO | 1 | §54 |
| rag_documents.created_at | TIMESTAMPTZ | NO | now() | |
| rag_chunks.id | BIGINT | NO | identity | PK |
| rag_chunks.document_id | BIGINT | NO | — | FK → rag_documents.id |
| rag_chunks.chunk_id | TEXT | NO | — | §54 |
| rag_chunks.embedding | VECTOR(3072) | NO | — | HNSW index; dim = configured embedding model |
| rag_chunks.metadata | JSONB | YES | NULL | §54 |
| rag_chunks.source | TEXT | YES | NULL | |
| rag_chunks.version | INTEGER | NO | 1 | |
| rag_chunks.content_hash | TEXT | YES | NULL | |
- **Index:** `rag_chunks_embedding_hnsw_idx USING hnsw (embedding vector_cosine_ops)`.

---

## 2. Soft-Delete Policy

| Table | Soft delete (`deleted_at`) | Rationale |
|-------|----------------------------|-----------|
| api_keys | ✅ | Revocation retained for audit (§61) |
| projects | ✅ | §11 deletion; confirm-first; history retained |
| datasets | ✅ | Audit: "dataset deleted" (§61) |
| test_cases | ✅ | Versioning/history |
| users | ❌ | Hard removal → immediate access loss (AC-SEC-004) |
| organization_members | ❌ | Row delete = removal |
| Immutable tables (dataset_versions, experiments, judge_judgments, audit_logs, outbox) | ❌ | Never modified/deleted by app |

## 3. Audit Fields Summary

- Mutable tables: `created_at`, `updated_at` (automatic).
- Actor-aware tables add `created_by` (users, organizations, api_keys, projects, datasets, dataset_versions, test_cases, evaluation_configs, pricing_configs, prompts/prompt_versions, alert_rules, research_projects, reports, exports).
- Immutable/write-once tables: `created_at` only.
- Full event trail lives in `audit_logs` (actor, action, resource, timestamp, ip, result — §61).

## 4. Retention Policy

| Table / data | Default retention | Enforcement |
|--------------|-------------------|-------------|
| traces, trace_events (raw payloads) | 30 days (org-configurable; OFF per privacy toggle §60) | partition drop + purge job |
| metrics_samples | 90 days | partition drop |
| metric_aggregates | 13 months | purge job |
| audit_logs | 13 months minimum | append-only, purge after window |
| exports/reports artifacts | 90 days | object storage lifecycle |
| raw prompt/response content | 30 days (or OFF, §60) | gateway capture policy |
| datasets, dataset_versions, experiments, prompts, research (immutable) | No auto-delete (immutability wins); admin purge w/ confirmation + audit | gated by role + audit |
| notifications, alerts | 90 days | purge job |
| outbox_events | 7 days after processed | relay cleanup |

## 5. RLS (PostgreSQL Row-Level Security)

- Enabled on all ◇ tables. Policy: `organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = current_setting('app.current_user_id')::bigint)`.
- Exemptions: `audit_logs` (admins only via `app.is_admin` setting); `environments` production rows (FR-ENV-003) require elevated setting.
- App sets `SET LOCAL app.current_user_id` / `app.current_role` per request/transaction.

## 6. PRD Verification (DATABASE_SCHEMA)

| PRD requirement | Where satisfied |
|-----------------|-----------------|
| §53 core entity list (27 tables) | All present in §1 (users…audit_logs) |
| §54 vector store (document/chunk/embedding/metadata/source/version) | rag_documents, rag_chunks |
| §55 Redis uses (jobs/rate-limit/temp/locks/queues) | Not in schema; Redis contract in [`API_CONTRACTS.md`](./API_CONTRACTS.md) / architecture |
| §12 provider/model/timeout/retry config | providers, models |
| §13 gateway capture (request_id, model, prompt, response, timestamp, latency, tokens, cost, status, error, metadata) | traces + test_results + gateway telemetry |
| §15 dataset fields (input, expected, context, metadata, tags, difficulty, category) | test_cases + dataset_versions.schema |
| §16 version immutability + duplicate IDs | dataset_versions (immutable trigger), datasets unique (org, dataset_id) |
| §17 per-test record (input, expected, actual, context, metrics, score, latency, tokens, cost, status) | test_results |
| §25 RAG failure classification | test_results.failure_classification |
| §27 test approval/versioning | test_cases.approval_status/version_no |
| §30 performance (P50/P95/P99, error rate, rps) | metric_aggregates |
| §31 versioned pricing + cost aggregates | pricing_configs |
| §34 experiment fields + immutability | experiments (+ trigger) |
| §36–§37 regression + thresholds | regression_runs (+ threshold_policy snapshot) |
| §42 trace steps | trace_events.step/sequence |
| §43–§44 alerts (type/severity/threshold/duration/cooldown/enabled) | alert_rules, alerts |
| §48 statistics | research_experiments.statistics |
| §61 audit fields (actor/action/resource/timestamp/ip/result) | audit_logs |
| §72–§75 human review/judge/confidence | human_reviews, judge_judgments, calibration_samples |
| §78 versioning | versioned tables (datasets, prompts, evaluators, configs, pricing, tests) |
| §83/AC-SCORE-004 score config stored | evaluation_configs.score_weights + experiments.score_config |
| §93 AC-SEC-003/005 | api_keys.key_hash, audit_logs append-only |
| §102 Step 4 (dataset v1) / Step 8 (metrics) / Step 18 (research captures) | dataset_versions, evaluation_runs.metrics, research_experiments |

All schema decisions trace to the PRD or to a recorded ambiguity assumption (see [`ARCHITECTURE_DECISIONS.md`](../ARCHITECTURE/ARCHITECTURE_DECISIONS.md) Part 2).

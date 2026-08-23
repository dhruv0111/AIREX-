# Data Model Requirements — AIREX

This document identifies every entity mentioned in the PRD V1.0, with the fields the PRD actually specifies. Where the PRD gives a name but no fields, the fields are marked **NS (Not Specified)** and the requirement is recorded. No schema is invented here — that belongs to the architecture phase and is gated by the clarifications in [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md).

**Source tables:** §53 (PostgreSQL core entities), §54 (vector store), §55 (Redis), §12 (providers), §13 (gateway capture), §34 (experiments), §60 (privacy), §78 (versioning).

---

## 1. Entity Inventory (from §53)

The PRD names the following core entities:

`users`, `organizations`, `organization_members`, `projects`, `environments`, `providers`, `models`, `api_keys`, `datasets`, `dataset_versions`, `test_cases`, `test_runs`, `test_results`, `evaluators`, `evaluation_runs`, `evaluation_results`, `experiments`, `experiment_metrics`, `prompts`, `prompt_versions`, `traces`, `trace_events`, `alerts`, `alert_rules`, `reports`, `research_projects`, `research_experiments`, `audit_logs`

**Additional entities implied elsewhere in the PRD (not in the §53 list):**
- `pricing_configs` (versioned pricing configuration — §31, FR-COST-002)
- `score_configs` / reliability-score configuration (stored with experiment — AC-SCORE-004)
- `human_reviews` / AI-judge judgments (evaluator model, prompt, version, score, explanation, timestamp — §74; human decisions — §72)
- `notifications` (notification events — §85)
- `vector_chunks` / embeddings (document ID, chunk ID, embedding, metadata, source, version — §54)
- `regression_runs` / baselines (baseline storage — §36, §102 Step 13)
- `api_keys` (organization-level API keys — §10)

---

## 2. Entity Detail

Legend: **R** = Required, **O** = Optional, **NS** = Not specified.

### 2.1 users
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| email | string | R | Unique; registration validation (AC-AUTH-002) |
| password (hash) | hashed | R | Password hashing required (SEC-AUTH-002) |
| verification status | enum/boolean | R | Email verification (AC-AUTH-005) |
| role | enum | R | Admin / Project Owner / Engineer / Viewer (§7) |
| Other profile fields | NS | NS | Not specified |

- **Relationships:** belongs to many organizations via `organization_members`.
- **Lifecycle:** created at registration; deleted → immediate access loss (AC-SEC-004).
- **Retention:** NS. **Ownership:** platform/self.

### 2.2 organizations
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| name / settings | NS | R | Settings must be persisted (FR-ORG-007) |
| storage/privacy toggles | NS | O | Raw data, PII masking, prompt storage, response storage toggles (§60) — placement NS |

- **Relationships:** parent of users, projects, API keys, models, datasets, experiments, reports (§10).
- **Isolation:** hard tenant boundary (BR-ORG-001). **Retention:** NS.

### 2.3 organization_members
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| organization_id | FK | R | |
| user_id | FK | R | |
| role | enum | R | Invite/remove/change roles (§10) |
| joined_at | timestamp | NS | |

### 2.4 projects
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| name | string | R | §11 |
| description | string | O | §11 |
| application_type | enum/string | R | §11 |
| environment | enum | R | dev/staging/production (§77) |
| endpoint | URL | R | Application endpoint (§11) |
| authentication_config | JSON | R | Endpoint auth (§11) |
| model_configuration | JSON | R | §11 |
| evaluation_configuration | JSON | R | §11 |
| archived | boolean | R | Archive prevents new production evaluations (FR-PROJECT-005) |

- **Relationships:** belongs to organization; has environments, models, datasets, evaluations, experiments, prompts, traces, alerts, reports.

### 2.5 environments
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| name | enum | R | development/staging/production (§77) |
| model / endpoint / credentials / policies | NS | R | Separate per environment (§77) |

### 2.6 providers
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| type | enum | R | OpenAI, Anthropic, Gemini, OSS-compatible, local (§12) |

### 2.7 models
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| model | string | R | §12 |
| api_key (encrypted) | encrypted string | R | Never displayed after creation (FR-PROVIDER-008); encrypted at rest (SEC-API-001) |
| base_url | string | O | §12 |
| temperature | number | O | §12 |
| max_tokens | int | O | §12 |
| timeout | int | O | §12 |
| retry_policy | JSON | O | §12 |
| version | string | O | Model version (FR-VERSION-001) |

### 2.8 api_keys
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| key (encrypted) | encrypted string | R | Never plaintext retrievable (AC-SEC-003) |
| organization_id | FK | R | §10 |
| created/deleted events | timestamp | R | Audit events (§61) |

### 2.9 datasets
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| id | string | R | Unique; duplicates rejected (FR-DATASET-013) |
| name | string | R | |
| source format | enum | R | CSV/JSON/JSONL/manual/generated (§15) |
| current_version | FK | R | Latest immutable version (BR-DATASET-001) |

### 2.10 dataset_versions
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| version_no | int | R | v1, v2, v3 (§16) |
| content | JSON/rows | R | input, expected answer, context, metadata, tags, difficulty, category (§15) |
| immutable | — | R | Cannot be silently modified (BR-DATASET-002) |
| created_at | timestamp | R | |

- **Key rule:** experiments reference the immutable version, not the live dataset (BR-DATASET-003).

### 2.11 test_cases / test_runs / test_results
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| input | text | R | §17 |
| expected_output | text | O | |
| actual_output | text | O | |
| context | text | O | |
| category | enum | R | 8 test-gen categories (FR-TESTGEN-003..010) |
| approval_status | enum | R | approved/rejected (AC-TESTGEN-004/005) |
| version | int | R | Generated tests versioned (AC-TESTGEN-006) |
| metrics / score / latency / tokens / cost / status | mixed | R | Per-test record (§17) |
| failure_classification | enum | O | RAG failure classes (§25) |

### 2.12 evaluators
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| type | enum | R | exact_match, semantic, correctness, hallucination, RAG, safety, latency, cost, etc. (§18) |
| version | string | R | Evaluator versioning (FR-VERSION-001) |
| config | JSON | R | Thresholds, case sensitivity (§19–§20) |
| ai_judge fields | NS | O | evaluator model, prompt, version (§74) |

### 2.13 evaluation_runs / evaluation_results
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| project_id | FK | R | |
| dataset_version_id | FK | R | |
| model_id / model_version | FK | R | |
| prompt_version_id | FK | R | |
| evaluator/config versions | FK | R | Exact version pinning (§78) |
| status | enum | R | QUEUED → RUNNING → COMPLETED (§102 Step 7) |
| result metrics | JSON | R | Accuracy, hallucination, safety, latency, cost, etc. |
| job/task reference | FK | R | Async job (FR-ASYNC-001) |

### 2.14 experiments / experiment_metrics
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| experiment_id | id | R | §34 |
| project_id | FK | R | |
| dataset_version | FK | R | |
| model + model_version | FK | R | |
| prompt_version | FK | R | |
| parameters | JSON | R | |
| timestamp | timestamp | R | |
| environment | enum | R | |
| metrics | JSON | R | |
| results | JSON | R | |
| score_config | JSON | R | Reliability score config (AC-SCORE-004) |
| immutable_after_completion | — | R | (BR-EXPERIMENT-001) |

### 2.15 prompts / prompt_versions
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| content | text | R | §33 |
| version_no | int | R | v1, v2, v3 (§33) |

### 2.16 traces / trace_events
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| trace_id | id | R | §42 |
| steps | sequence | R | user request, retriever, documents, prompt builder, LLM, evaluator, response |
| duration / input / output / metadata / error | per step | R | FR-OBS-006 |
| redacted content | — | R | Sensitive content redacted per project settings (FR-OBS-007) |

### 2.17 alerts / alert_rules
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| type | enum | R | accuracy, hallucination, latency, error, cost, safety, model (§43) |
| severity | enum | R | §44 |
| threshold | number | R | §44 |
| duration | int | R | §44 |
| cooldown | int | R | §44 |
| enabled | boolean | R | §44 |
| channel | enum | R | in-app, email, webhook (§43) |

### 2.18 reports
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| content sections | JSON | R | 13 sections (§80) |
| format | enum | R | Markdown/PDF/JSON/CSV export (§79) |

### 2.19 research_projects / research_experiments
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| hypothesis | text | R | §47 |
| variables / baseline / treatment | NS | R | §47 |
| dataset / metrics / results | FK/JSON | R | §47 |
| statistical results | JSON | R | mean, median, std dev, percentiles, CI, effect size (§48) |
| publication metadata | JSON | R | raw data, methodology, config, reproducibility (§81) |

### 2.20 audit_logs
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| actor | string | R | §61 |
| action | string | R | |
| resource | string | R | |
| timestamp | timestamp | R | |
| ip (where available) | string | O | |
| result | enum | R | |
| immutable | — | R | Cannot be modified by normal users (AC-SEC-005) |

### 2.21 pricing_configs (implied)
| Field | Type | Req | Notes |
|-------|------|-----|-------|
| provider/model | FK | R | §31 |
| price per 1K input/output tokens | number | R | |
| version | int | R | Versioned (FR-COST-002) |

---

## 3. Relationships Overview

```
organization 1 ── n organization_members ── n users
organization 1 ── n projects
organization 1 ── n api_keys
organization 1 ── n models / providers
organization 1 ── n datasets ── n dataset_versions
project 1 ── n environments
project 1 ── n test_cases / test_runs / test_results
project 1 ── n evaluations ── n evaluation_results
project 1 ── n experiments ── n experiment_metrics
project 1 ── n prompts ── n prompt_versions
project 1 ── n traces ── n trace_events
project 1 ── n alerts / alert_rules
project 1 ── n reports
organization 1 ── n research_projects ── n research_experiments
organization 1 ── n audit_logs
model 1 ── n pricing_configs (versioned)
evaluation/experiment ── references exact versions of dataset, prompt, model, evaluator, config (§78)
```

## 4. Vector Storage (pgvector — §54)

| Field | Type | Req | Notes |
|-------|------|-----|-------|
| document_id | id | R | §54 |
| chunk_id | id | R | |
| embedding | vector | R | |
| metadata | JSON | R | |
| source | string | R | |
| version | int | R | |

- **Postgres:** PostgreSQL + pgvector initially (DATA-003). External vector databases optional later (DATA-004).

## 5. Caching / Queue (Redis — §55)

Redis stores:
- Evaluation jobs
- Rate limiting
- Temporary results
- Distributed locks
- Task queues

## 6. Key Data Gaps (→ AMBIGUITY_REGISTER)

| # | Gap |
|---|-----|
| AMB-DATA-SCHEMA-001 | No fields/types for most §53 entities beyond names |
| AMB-RETENTION-001 | No data retention/archival/deletion policy; §5 says don't store sensitive production data indefinitely |
| AMB-PRIVACY-001 | Storage toggles (§60) have no defaults or per-org inheritance rules |
| AMB-PRICING-001 | Pricing-config source/curation undefined; cost estimates depend on it |
| AMB-INDEX-001 | No indexing/query-pattern requirements (e.g., dashboards, traces) |
| AMB-VECTOR-001 | Embedding model for pgvector undefined |
| AMB-UNIQUE-001 | Uniqueness rules beyond dataset IDs and email undefined (org/project name uniqueness) |

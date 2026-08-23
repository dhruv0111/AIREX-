# Feature Inventory — AIREX

This document defines the complete feature hierarchy for AIREX based strictly on the PRD V1.0. Modules are taken from §8 (Core Product Modules). Hidden functionality implied by requirements (e.g., quality gates, async job system, human review, AI judge) is included and traced to its source section.

For each feature the following attributes are captured where the PRD provides information:

- **Purpose / User / Trigger / Input / Processing / Output**
- **Dependencies**
- **Permissions** (from PRD only; otherwise **NOT SPECIFIED**)
- **Validations / Errors / Edge cases**
- **Acceptance criteria** (cross-referenced to [`ACCEPTANCE_CRITERIA.md`](./ACCEPTANCE_CRITERIA.md))

> Legend: **NS** = Not Specified in PRD. Items marked **NS** are logged in [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md).

---

## 1. Feature Hierarchy (Summary Tree)

```
AIREX
 ├── 1 Authentication & Authorization
 │    ├── Registration (email/password) [FR-AUTH-001]
 │    ├── Login / Logout [FR-AUTH-002/003]
 │    ├── Password Reset [FR-AUTH-004]
 │    ├── Email Verification [FR-AUTH-005]
 │    ├── Session/AuthN (JWT/session) [FR-AUTH-006]
 │    ├── RBAC [FR-AUTH-007]
 │    ├── Organization Membership [FR-AUTH-008]
 │    └── Project-level Permissions [FR-AUTH-009]
 ├── 2 Organization Management
 │    ├── Organization Tenancy [FR-ORG-001..003]
 │    ├── User Invitation [FR-ORG-004]
 │    ├── User Removal [FR-ORG-005]
 │    ├── Role Change [FR-ORG-006]
 │    └── Organization Settings [FR-ORG-007]
 ├── 3 Project Management
 │    ├── Project CRUD [FR-PROJECT-001..004]
 │    ├── Archive [FR-PROJECT-003/005]
 │    └── Project Configuration [FR-PROJECT-006]
 ├── 4 AI Provider Management
 │    ├── Provider Abstraction [FR-PROVIDER-001]
 │    ├── Provider Adapters (OpenAI/Anthropic/Gemini/OSS/Local) [FR-PROVIDER-002..006]
 │    └── Provider Configuration & Secret Handling [FR-PROVIDER-007/008]
 ├── 5 Model Gateway
 │    ├── Unified Inference Path [FR-GATEWAY-001]
 │    ├── Request Telemetry Capture [FR-GATEWAY-002]
 │    ├── Error Normalization / Timeout Detection [FR-GATEWAY-003..009]
 │    └── Retry Policy [FR-ASYNC-010/011]
 ├── 6 Dataset Management
 │    ├── Dataset Creation/Import (CSV/JSON/JSONL/Manual/Generated) [FR-DATASET-001..006]
 │    ├── Dataset Fields [FR-DATASET-007]
 │    ├── Dataset Versioning (immutable) [FR-DATASET-008..010]
 │    ├── Version Comparison [FR-DATASET-011]
 │    └── Import Validation & Row-level Errors [FR-DATASET-012/013]
 ├── 7 Evaluation Engine
 │    ├── Evaluation Pipeline [FR-EVAL-001/002]
 │    ├── Exact Match Evaluator [FR-EVAL-003/004]
 │    ├── Semantic Similarity Evaluator [FR-EVAL-005/006]
 │    ├── Answer Correctness Evaluator [FR-EVAL-007/008]
 │    ├── Hallucination / Faithfulness Evaluator [FR-EVAL-009..014]
 │    ├── RAG Evaluation (Retrieval + Generation) [FR-EVAL-015..017]
 │    ├── RAG Failure Classification [FR-EVAL-018]
 │    ├── Safety Evaluators (toxicity/bias/injection/leakage/format) [FR-EVAL-019..023]
 │    ├── Performance Evaluator (latency/tokens) [FR-EVAL-024]
 │    ├── Cost Evaluator [FR-EVAL-025]
 │    ├── Consistency Evaluator [FR-EVAL-026]
 │    └── Regression Evaluator [FR-EVAL-027]
 ├── 8 AI Test Generator
 │    ├── Test Generation Inputs [FR-TESTGEN-002]
 │    ├── Category Generation (8 categories) [FR-TESTGEN-003..010]
 │    ├── Quantity Config [FR-TESTGEN-011]
 │    ├── Preview / Approve / Reject [FR-TESTGEN-012..015]
 │    └── Versioning [FR-TESTGEN-016]
 ├── 9 RAG Evaluation Engine
 │    ├── Retrieval Quality Metrics [FR-EVAL-016]
 │    ├── Generation Quality Metrics [FR-EVAL-017]
 │    └── Failure Classification [FR-EVAL-018]
 ├── 10 Safety Evaluation Engine
 │    ├── Category/severity/score/explanation/status [FR-SAFETY-001..008]
 │    ├── Prompt Injection Classification (SAFE/VULNERABLE/UNCERTAIN) [FR-PROMPTINJ-001..004]
 │    └── Authorization-scoped testing [FR-PROMPTINJ-004]
 ├── 11 Hallucination Detection
 │    └── Supported/Unsupported/Contradicted/Unknown [FR-EVAL-010..014]
 ├── 12 Performance Evaluation
 │    └── Latency/TTFB/tokens/throughput/error rate/P50-P99 [FR-PERF-EVAL-001..009]
 ├── 13 Cost Analytics
 │    ├── Cost estimation engine [FR-COST-001]
 │    ├── Versioned pricing config [FR-COST-002]
 │    └── Cost aggregates [FR-COST-003..007]
 ├── 14 Experiment Management
 │    ├── Experiment Creation/Storage [FR-EXPERIMENT-001]
 │    └── Immutability [FR-EXPERIMENT-002]
 ├── 15 Prompt Management
 │    ├── Prompt Versioning [FR-PROMPT-001]
 │    ├── Prompt Experimentation [FR-PROMPT-002]
 │    └── Prompt Comparison [FR-PROMPT-003]
 ├── 16 Regression Testing
 │    ├── Baseline vs New Version [FR-REGRESSION-001/002]
 │    ├── Regression Policies (thresholds) [FR-REGRESSION-003]
 │    └── Baseline Management [FR-REGRESSION-004]
 ├── 17 Production Observability
 │    ├── Real-time Dashboards [FR-OBS-001..003]
 │    ├── AI Traces [FR-OBS-004..006]
 │    └── Trace Redaction [FR-OBS-007]
 ├── 18 Alerting
 │    ├── Alert Triggers (7 types) [FR-ALERT-001..007]
 │    ├── Channels (in-app/email/webhook) [FR-ALERT-008]
 │    └── Alert Rules [FR-ALERT-009..011]
 ├── 19 Root Cause Analysis
 │    ├── Likely-cause identification [FR-RCA-001]
 │    └── Recommendation labelling [FR-RCA-002]
 ├── 20 Recommendation Engine
 │    ├── Recommendation generation [FR-RECO-001/002]
 │    └── Review-before-implement [FR-RECO-003]
 ├── 21 CI/CD Integration
 │    ├── Pipeline Trigger [FR-CICD-001]
 │    ├── Result Return & Exit Codes [FR-CICD-002..004]
 │    ├── Dataset Version Pin [FR-CICD-005]
 │    └── Quality Gate [FR-CICD-006]
 ├── 22 CLI
 │    └── Commands + exit codes [FR-CLI-001..003]
 ├── 23 API
 │    └── REST endpoints + consistent errors + OpenAPI [FR-API-001..004]
 ├── 24 Reporting
 │    ├── Report generation [FR-REPORT-001/002]
 │    └── Export (CSV/JSON/MD/PDF) [FR-REPORT-003..008]
 ├── 25 Research Workspace
 │    ├── Research Experiment lifecycle [FR-RESEARCH-001..010]
 │    ├── Statistical Evaluation [FR-RESEARCH-011/012]
 │    ├── Research Report Generation [FR-RESEARCH-013/014]
 │    └── Publication Support [FR-RESEARCH-015]
 ├── 26 Audit Logs
 │    ├── Event capture [SEC-AUDIT-001..003]
 │    └── Immutability [SEC-AUDIT-004]
 ├── 27 Security
 │    ├── Application security controls [SEC-*]
 │    ├── Data Privacy & Redaction [DATA-PRIV-*, SEC-DATA-001]
 │    └── Multi-tenant isolation [SEC-MULTI-*]
 ├── 28 Administration
 │    └── Admin capabilities [ADM-*]
 └── Cross-cutting systems
      ├── Async Evaluation / Job System [FR-ASYNC-*]
      ├── Human Review & Calibration [FR-HUMAN-*]
      ├── AI Judge & Confidence [FR-JUDGE-*]
      ├── Environment Management [FR-ENV-*]
      ├── Global Versioning [FR-VERSION-*]
      ├── AI Reliability Score [FR-SCORE-*]
      ├── Notifications [FR-NOTIFY-*]
      └── Health & Self-Observability [NFR-OBS-*]
```

---

## 2. Detailed Feature Cards

### Module 1 — Authentication & Authorization

#### F1.1 Registration
- **Purpose:** Create a user account with email/password.
- **User:** Visitor. **Trigger:** User submits registration form (page: `/register`).
- **Input:** Email, password, required fields. **Processing:** Validate; create account; (email verification required per §9).
- **Output:** Account created; confirmation/verification flow.
- **Dependencies:** User store, email delivery (provider **NS** — see AMB-EMAIL-001).
- **Permissions:** Public. **Validations:** Duplicate email rejected (AC-AUTH-002); required fields validated (AC-AUTH-001).
- **Errors:** Duplicate email; invalid email format (**NS**); weak password policy (**NS**).
- **Edge cases:** Re-verification after expiry (**NS**); account with unverified email trying to log in (**NS**).
- **Acceptance criteria:** AC-AUTH-001, AC-AUTH-002.

#### F1.2 Login / Logout
- **Purpose:** Authenticate user; establish session/JWT. **User:** Registered user.
- **Trigger:** Submit credentials on `/login`; logout action.
- **Processing:** Validate credentials; issue token/session; record login audit event (§61).
- **Validations:** Invalid credentials must not authenticate (AC-AUTH-003); unauthenticated requests rejected (AC-AUTH-004).
- **Errors:** Invalid credentials; disabled/deleted user (**NS** — see SEC-MULTI-004).
- **Acceptance criteria:** AC-AUTH-003, AC-AUTH-004.

#### F1.3 Password Reset & Email Verification
- **Purpose:** Recover access; verify email ownership. **Source:** §9. **Details (flow, token expiry):** NS.

#### F1.4 RBAC + Project-Level Permissions
- **Purpose:** Enforce role and project scoping. **Roles:** Admin, Project Owner, Engineer, Viewer (§7).
- **Validations:** Users only access own-organization projects (AC-AUTH-005); Viewer cannot modify datasets/evaluations (AC-AUTH-006).
- **Errors/Edge cases:** Cross-tenant access (AC-SEC-001); project-ID based authz bypass (AC-SEC-002).
- **Acceptance criteria:** AC-AUTH-005, AC-AUTH-006, AC-SEC-001, AC-SEC-002.

---

### Module 2 — Organization Management

#### F2.1 Tenancy
- **Purpose:** Top-level tenant containing users, projects, API keys, models, datasets, experiments, reports (§10).
- **Rules:** Strict isolation; Organization A data never returned to B (§10; AC-SEC-001).

#### F2.2 User Invitation / Removal / Role Change (Admin)
- **Purpose:** Admin-managed membership (§10). **Permissions:** Admin only.
- **Validations:** Removal immediate loss of access (AC-SEC-004).
- **Edge cases:** Removing the last admin (**NS**); role changes on active sessions (**NS**).

#### F2.3 Organization Settings
- **Purpose:** Persist org configuration (name, storage/privacy toggles per §60 — mapping **NS**).

---

### Module 3 — Project Management

#### F3.1 Project CRUD
- **Purpose:** Represent one AI application (§11).
- **Rules:** Delete requires confirmation (FR-PROJECT-004); archive prevents new **production** evaluations (FR-PROJECT-005).
- **Edge case (ambiguity):** May archived projects run non-production (dev/staging) evaluations? **NS** — see AMB-ARCHIVE-001.
- **Acceptance criteria:** §11 bullet list.

#### F3.2 Project Configuration
- **Fields:** name, description, application type, environment, endpoint, authentication configuration, model configuration, evaluation configuration (§11).
- **Edge cases:** How endpoint/auth config is used by the evaluation runner to call the external app (**NS** — see AMB-PROJECT-001).

---

### Module 4 — AI Provider Management

#### F4.1 Provider Abstraction & Adapters
- **Purpose:** Unified access to OpenAI, Anthropic, Gemini, OSS (compatible APIs), local models (§12, §67).
- **Dependencies:** Model Gateway; API keys.
- **Edge cases:** Local/OSS model specifics (hosting, embedding, health) **NS** — see AMB-PROVIDER-001.

#### F4.2 Provider Configuration & Secrets
- **Fields:** provider, model, API key, base URL, temperature, max tokens, timeout, retry policy (§12).
- **Rules:** API keys never displayed after creation (FR-PROVIDER-008); never in logs (AC-MODEL-007); encrypted at rest (SEC-API-001).
- **Acceptance criteria:** AC-MODEL-001..007.

---

### Module 5 — Model Gateway

#### F5.1 Unified Inference Path
- **Purpose:** All AI requests flow Application → Gateway → Provider Adapter → Model (§13).
- **Capture per request:** request ID, model, prompt, response, timestamp, latency, token usage, cost, status, error, metadata (§13).
- **Errors:** Controlled error on invalid credentials (AC-MODEL-002); timeout detection (AC-MODEL-003); provider-error normalization (AC-MODEL-004).
- **Acceptance criteria:** AC-MODEL-001..007.

---

### Module 6 — Dataset Management

#### F6.1 Dataset Creation / Import
- **Formats:** CSV, JSON, JSONL, manual entry, generated (§15).
- **Fields:** input, expected answer, context, metadata, tags, difficulty, category (§15).
- **Validations:** Duplicate dataset IDs rejected (FR-DATASET-013); import failures produce row-level errors (FR-DATASET-012).
- **Edge cases:** Mixed-format/encoding issues (**NS**); large file limits (**NS**).

#### F6.2 Dataset Versioning
- **Rules:** Every modification creates a version (FR-DATASET-008); versions immutable (FR-DATASET-009); experiments reference immutable versions (FR-DATASET-010); version comparison supported (FR-DATASET-011).

---

### Module 7 — Evaluation Engine

#### F7.1 Pipeline
- **Flow:** Dataset → Test Runner → AI Application → Response → Evaluator → Metrics → Score → Report (§17).
- **Per-test record:** input, expected output, actual output, context, metrics, score, latency, tokens, cost, status (§17).
- **Async execution:** FR-ASYNC-001..013.
- **Dependencies:** Model Gateway, Dataset versions, Evaluators, Job system.
- **Acceptance criteria:** Master AC (§101) and Final E2E (§102).

#### F7.2 Exact Match
- Configurable case-insensitivity (§19). Deterministic outputs.

#### F7.3 Semantic Similarity
- Configurable threshold (§20); example similarity 0.94 → PASS.

#### F7.4 Answer Correctness
- Output: correctness score, reason, pass/fail (§21). Human review for uncertain cases (§21).

#### F7.5 Hallucination / Faithfulness
- Input: question, context, answer (§22). Output: supported/unsupported/contradicted/unknown (AC-HALL-005) with explanation (AC-HALL-004).
- **Acceptance criteria:** AC-HALL-001..005.

#### F7.6 RAG Evaluation
- Two independent levels: retrieval quality (context relevance, precision, recall, ranking) and generation quality (correctness, faithfulness, completeness, hallucination) (§24).
- Failure classification: RETRIEVAL/GENERATION/CONTEXT/PROMPT/MODEL/DATA/UNKNOWN (§25).

#### F7.7 Other Evaluators
- Toxicity, bias, prompt injection, data leakage, response format, latency, cost, consistency, regression (§18).
- **Detail note:** Data leakage and response-format evaluator specifications are minimal (**NS**) — see AMB-EVAL-001.

---

### Module 8 — AI Test Generator

- **Inputs:** application description, dataset, documentation, existing tests (§26).
- **Categories (8):** Normal, Edge Case, Adversarial, Ambiguous, Safety, Prompt Injection, Long Context, Multilingual.
- **Rules:** Configurable quantity (AC-TESTGEN-001); category metadata (AC-TESTGEN-002); preview (AC-TESTGEN-003); approve/reject (AC-TESTGEN-004); rejected excluded from run (AC-TESTGEN-005); versioned (AC-TESTGEN-006).
- **Acceptance criteria:** AC-TESTGEN-001..006.

---

### Module 9 — RAG Evaluation Engine
See F7.6. Standalone module because retrieval/generation separation is critical for RCA (§24).

### Module 10 — Safety Evaluation Engine
- **Dimensions:** toxicity, self-harm, hate/harassment, dangerous instructions, privacy leakage, system prompt leakage, sensitive info exposure (§29).
- **Output tuple:** category, severity, score, explanation, status (§29).
- **Prompt injection classification:** SAFE / VULNERABLE / UNCERTAIN (§28); no abuse encouragement; authorization-scoped testing (FR-PROMPTINJ-003/004).

### Module 11 — Hallucination Detection
- Faithfulness + explanation + 4-way classification (§22–§23). See F7.5.

### Module 12 — Performance Evaluation
- Metrics: total latency, TTFB (where supported), input/output/total tokens, throughput, error rate (§30).
- Dashboard: P50/P95/P99, error rate, requests/minute (§30).

### Module 13 — Cost Analytics
- Estimate cost from input/output tokens × provider/model/pricing config (§31).
- **Rules:** pricing config versioned (FR-COST-002); aggregates: /request, /1K tokens, /evaluation, /dataset, monthly estimate (§31).
- **Dependency:** pricing data source **NS** — see AMB-PRICING-001.

### Module 14 — Experiment Management
- **Stored fields:** experiment ID, project, dataset version, model, model version, prompt version, parameters, timestamp, environment, metrics, results (§34).
- **Rule:** immutable after completion (§34).

### Module 15 — Prompt Management
- Prompt versions; run same dataset per version; compare accuracy/hallucination/latency/cost/safety (§33).

### Module 16 — Regression Testing
- Baseline vs new version; thresholds; result REGRESSION DETECTED (§36–§37).
- **Conflict note:** example thresholds (§37) differ from quality gate thresholds (§39) — see AMB-THRESHOLD-001.

### Module 17 — Production Observability
- Real-time dashboard (requests, errors, latency, tokens, cost, quality score, hallucination, safety, model distribution) (§41); time ranges (§41).
- AI traces with steps (user request, retriever, documents, prompt builder, LLM, evaluator, response) and per-step duration/input/output/metadata/error (§42); redaction per project settings (§42).

### Module 18 — Alerting
- Triggers: accuracy degradation, hallucination increase, latency increase, error increase, cost spike, safety failure, model failure (§43).
- Channels: in-app, email, webhook (§43).
- Rules: severity, threshold, duration, cooldown, enabled/disabled (§44).
- **Examples:** P95 > 3s for 10 min → alert; hallucination > 7% → critical (§44).

### Module 19 — Root Cause Analysis
- Identify likely causes on failure (e.g., retrieval vs generation degradation, with evidence) (§45).
- **Rule:** label AI explanations as recommendations, not guaranteed truth (FR-RCA-002).
- **Scope note:** §97 lists advanced RCA as V2 — conflict with §101/§102 → AMB-VERSION-SCOPE-001.

### Module 20 — Recommendation Engine
- Recommendation types: top-K, chunk size, retrieval depth, reranking, system prompt, model, temperature, context size, guardrails (§46).
- **Rule:** reviewable before implementation (FR-RECO-003).
- **Scope note:** V2 per §97 → conflict → AMB-VERSION-SCOPE-001.

### Module 21 — CI/CD Integration
- Trigger evaluation from CI (AC-CICD-001); return result (AC-CICD-002); non-zero exit on fail (AC-CICD-003); success on pass (AC-CICD-004); pin dataset version (AC-CICD-005).
- Quality gate example thresholds (§39) → AMB-THRESHOLD-001.
- **Dependency:** GitHub Actions per tech stack (§67); CI auth mechanism (**NS** — see AMB-CICD-002).

### Module 22 — CLI
- Commands: login, project create, dataset upload, evaluate run, regression run, report generate (§52). Meaningful exit codes (§52).

### Module 23 — API
- REST endpoints (§51); consistent error format (§51, §63); OpenAPI/Swagger docs (§95). Contracts **NS** — see [`API_REQUIREMENTS.md`](./API_REQUIREMENTS.md).

### Module 24 — Reporting
- Report sections (§80); export formats CSV/JSON/Markdown/PDF (§79).

### Module 25 — Research Workspace
- Research experiment: hypothesis, variables, baseline, treatment, dataset, metrics, results, statistical analysis, charts, conclusions, export (§47).
- Statistical methods: mean, median, std dev, percentiles, CI, effect size, significance-where-applicable (§48); no overclaiming significance (FR-RESEARCH-012).
- Report structure (12 sections) and export formats (§49).
- Publication support: raw + aggregated data, methodology, config, stats, charts, reproducibility metadata (§81).
- **Scope note:** §97 lists research workspace as V2 → conflict → AMB-VERSION-SCOPE-001.

### Module 26 — Audit Logs
- Events: login, API key created/deleted, project created, dataset deleted, evaluation executed, config changed, role changed (§61).
- **Fields:** actor, action, resource, timestamp, IP where available, result (§61).
- **Rule:** immutable by normal users (AC-SEC-005).

### Module 27 — Security
- Controls: HTTPS, password hashing, JWT/session security, RBAC, API key encryption, secret masking, input validation, SQLi/XSS/CSRF protection, rate limiting, audit logging (§59).
- Privacy toggles: raw data storage, PII masking, prompt storage, response storage (§60); redaction ([PERSON], [PHONE]) (§60).
- Multi-tenant: AC-SEC-001..005.

### Module 28 — Administration
- Admin capabilities per §7: create orgs, manage users/projects/API keys, configure integrations/policies, view all reports.

---

## 3. Cross-Cutting Systems

#### C1. Async Evaluation / Job System
- Pipeline: API → Job Created → Queue → Workers → Evaluation → Results (§56).
- Worker capabilities: parallel, retry, timeout, rate limiting, provider limits, partial failure handling, cancellation (§57).
- Retry: transient retries, permanent stop, configurable max (§58).
- Reliability: survive API restarts (§88); partial results preserved (§89).
- **Implementation detail:** Celery/RQ/Arq initially (§67).

#### C2. Human Review & Calibration
- Mark PASS/FALSE POSITIVE; store decisions (§72).
- Sampling for review; AI vs Human agreement (§73).
- **Scope note:** §97 lists human evaluation workflows as V2 → conflict → AMB-VERSION-SCOPE-001.

#### C3. AI Judge & Confidence
- LLM-as-judge; store evaluator model/prompt/version/score/explanation/timestamp (§74).
- Optional confidence; low-confidence → human review eligible (§75).
- **Dependency:** judge model/provider selection and its cost/keys **NS** — see AMB-JUDGE-001.

#### C4. Environment Management
- Dev/staging/production; separate model, endpoint, credentials, policies (§77).
- Production credentials not exposed to dev users without authorization (§77).

#### C5. Global Versioning
- Version: dataset, prompt, model, evaluator, eval config, application, experiment (§78).
- Each evaluation references exact versions (§78).

#### C6. AI Reliability Score
- Configurable weighted score (example: 30% accuracy, 20% faithfulness, 15% safety, 15% retrieval, 10% latency, 10% cost) (§83).
- Rules: 0–100 (AC-SCORE-001); recalc on weight change (AC-SCORE-002); missing metrics not silently zero (AC-SCORE-003); config stored with experiment (AC-SCORE-004); transparent (§83).

#### C7. Notifications
- Events: eval complete, eval fails, regression, quality threshold, cost threshold, safety threshold (§85).
- **Delivery mechanism / preferences:** NS — see AMB-NOTIF-001.

#### C8. Health & Self-Observability
- /health, /ready, /live verifying dependencies (§65).
- Monitor: API latency, worker latency, queue depth, error rate, DB performance, Redis health, provider health, eval throughput (§64).
- Stack: OpenTelemetry, Prometheus, Grafana (§64, §67).

---

## 4. Hidden Functionality Identified (not an explicit module, but required)

1. **Quality Gate** (§39) — cross-cutting check used by CI/CD and regression; not listed as a module but mandatory (AC-CICD-003/004, §101).
2. **Async Job System** (§56–§57) — implicit infra module.
3. **Retry Policy Engine** (§58) — implicit.
4. **AI Reliability Score Calculation** (§83) — implicit cross-cutting.
5. **Human Review & Calibration** (§72–§73) — implicit workflow.
6. **AI Judge framework** (§74) — implicit.
7. **Data Privacy / Redaction pipeline** (§60) — implicit across gateway/traces/logs.
8. **Pricing Configuration store** (§31) — implicit, versioned.
9. **Vector store (pgvector)** (§54) — implicit for RAG.
10. **Alert evaluation engine** (§44) — evaluates rules continuously.

---

## 5. Acceptance Criteria Cross-Reference

Every feature's acceptance criteria are enumerated and mapped in [`ACCEPTANCE_CRITERIA.md`](./ACCEPTANCE_CRITERIA.md). Features lacking explicit ACs (e.g., Observability, Reporting, Research Workspace, Recommendation Engine) are flagged there as **requirements without testable acceptance criteria**.

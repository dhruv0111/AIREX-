# AIREX — Requirement Traceability Matrix (RTM)
**Full End-to-End Acceptance, PRD, UX, and Architecture Validation**

**Validation Date:** September 2026  
**Target Environment:** Local Full-Stack (Next.js 15 + FastAPI + SQLite/PostgreSQL + In-Process / Redis Workers)  
**Execution Standard:** Real Browser E2E Headed Execution + API Verification

---

## 1. Traceability Matrix Structure & Legend

* **PASS**: Requirement verified, functioning as expected against acceptance criteria.
* **FAIL**: Requirement failed verification (defect created).
* **PARTIAL**: Requirement partially functioning.
* **BLOCKED**: Blocked by environment/dependency.
* **NOT IMPLEMENTED**: Feature not built.
* **NOT APPLICABLE**: Not applicable to current scope.

---

## 2. Traceability Matrix

| Req ID | PRD / User Guide Requirement | Expected Behavior | Test Case Reference | Actual Result | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **AUTH-01** | User Registration (`/register`) | Create new tenant user account with bcrypt password hashing | `full_acceptance.spec.ts: TC-AUTH-01` | Account created, redirected to onboarding/login | **PASS** | `POST /api/v1/auth/register` (201) |
| **AUTH-02** | Email Uniqueness Enforcement | Reject duplicate user email with clear validation message | `full_acceptance.spec.ts: TC-AUTH-02` | Rejected with 409 Conflict error | **PASS** | UI error banner shown |
| **AUTH-03** | User Authentication (`/login`) | Login with valid credentials and receive JWT bearer session | `full_acceptance.spec.ts: TC-AUTH-03` | Authenticated, token stored, navigated to `/dashboard` | **PASS** | `POST /api/v1/auth/login` (200) |
| **AUTH-04** | Invalid Credentials Rejection | Show clear error when incorrect password is provided | `full_acceptance.spec.ts: TC-AUTH-04` | Error displayed, user remains unauthenticated | **PASS** | `401 Unauthorized` |
| **AUTH-05** | Protected Route Guarding | Unauthenticated visitors redirected to `/login` | `full_acceptance.spec.ts: TC-AUTH-05` | Immediate redirect to `/login` | **PASS** | Next.js middleware guard |
| **AUTH-06** | User Sign Out | Clear session tokens and return to login page | `full_acceptance.spec.ts: TC-AUTH-06` | Session terminated, redirected to `/login` | **PASS** | Session revoked |
| **PROJ-01** | Project Creation (`/projects/new`) | Create new AI project workspace with name and slug | `full_acceptance.spec.ts: TC-PROJ-01` | Project created and listed in project explorer | **PASS** | `POST /api/v1/projects` (201) |
| **PROJ-02** | Environment Isolation | Support `development`, `staging`, `production` environments | `full_acceptance.spec.ts: TC-PROJ-02` | Environments rendered with distinct rate limits | **PASS** | Multi-environment grid |
| **PROJ-03** | Project Overview Navigation | Accessible tabs for Models, Rubrics, Datasets, Evals, Observability | `full_acceptance.spec.ts: TC-PROJ-03` | All sub-navigation links route correctly | **PASS** | AppShell project tabs |
| **MODL-01** | Connect AI Provider | Connect OpenAI / Anthropic / Local mock provider | `full_acceptance.spec.ts: TC-MODL-01` | Provider registered with encrypted API key | **PASS** | `POST /api/v1/providers` |
| **MODL-02** | Mask Sensitive API Keys | Sensitive credentials never exposed in UI or plain text logs | `full_acceptance.spec.ts: TC-MODL-02` | Key displayed as `sk-***` with no plain text reveal | **PASS** | Secret masking filter |
| **MODL-03** | Model Configuration & Test | Configure model parameters (temperature, max tokens) and test connection | `full_acceptance.spec.ts: TC-MODL-03` | Model created, connection test returns latency | **PASS** | Gateway inference test |
| **RUBR-01** | Create Evaluation Rubric | Define criteria, scoring type (exact match, similarity, LLM judge) | `full_acceptance.spec.ts: TC-RUBR-01` | Rubric persisted and available for evaluation runs | **PASS** | `POST /api/v1/projects/[id]/rubrics` |
| **DATA-01** | Dataset Upload (JSON/CSV) | Upload test cases containing input prompt and expected output | `full_acceptance.spec.ts: TC-DATA-01` | Dataset parsed, validated, and stored as immutable version | **PASS** | Version v1 created |
| **DATA-02** | Dataset Records Inspection | Preview test cases with row pagination and prompt inspection | `full_acceptance.spec.ts: TC-DATA-02` | Rows displayed with clear formatting | **PASS** | Dataset preview table |
| **EVAL-01** | Evaluation Execution | Dispatch evaluation job to asynchronous worker queue | `full_acceptance.spec.ts: TC-EVAL-01` | Status transitions `PENDING` -> `RUNNING` -> `COMPLETED` | **PASS** | Worker queue dispatch |
| **EVAL-02** | Evaluation Scoring & Metrics | Calculate pass rate, accuracy score, and cost per token | `full_acceptance.spec.ts: TC-EVAL-02` | Accuracy %, total tokens, and cost computed | **PASS** | Evaluation results summary |
| **EVAL-03** | Latency Distribution | Measure p50, p95, p99 request latencies | `full_acceptance.spec.ts: TC-EVAL-03` | Latency distribution charts & summary cards rendered | **PASS** | SRE latency metrics |
| **EXPR-01** | Side-by-Side Prompt Experiments | Compare prompt variations or model versions on same dataset | `full_acceptance.spec.ts: TC-EXPR-01` | Side-by-side win rates and diffs displayed | **PASS** | Experiment results matrix |
| **AGNT-01** | Autonomous Agent Evaluation | Execute multi-step agent trajectories with tool calling | `full_acceptance.spec.ts: TC-AGNT-01` | Tool invocations recorded and validated against schema | **PASS** | Agent trajectory view |
| **AGNT-02** | Infinite Loop & Trajectory Safety | Detect runaway agent loops and repetitive tool failures | `full_acceptance.spec.ts: TC-AGNT-02` | Loop detected, trajectory halted safely | **PASS** | Loop detector engine |
| **AGNT-03** | 7-Dimension Readiness Score | Score Goal Completion, Tool Precision, Safety, Robustness, Latency, Cost, Efficiency | `full_acceptance.spec.ts: TC-AGNT-03` | Composite readiness score (0–100) rendered | **PASS** | Radar / Readiness dial |
| **DECS-01** | Release Decision Engine | Evaluate reliability against Go/No-Go enterprise policy | `full_acceptance.spec.ts: TC-DECS-01` | Verifiable decision status (PASSED, WARNING, BLOCKED) | **PASS** | Release decision report |
| **DECS-02** | CI/CD Quality Gating | Return non-zero exit code on blocked release decision | `full_acceptance.spec.ts: TC-DECS-02` | Automated gate blocks breaking deployments | **PASS** | CLI service token check |
| **OBSV-01** | Real-Time Distributed Traces | Ingest traces with hierarchical spans, timestamps, and tokens | `full_acceptance.spec.ts: TC-OBSV-01` | Trace explorer renders span waterfall | **PASS** | Distributed trace viewer |
| **OBSV-02** | Automated PII / Secret Redaction | Redact SSNs, API keys, emails before persisting observability traces | `full_acceptance.spec.ts: TC-OBSV-02` | Sensitive tokens replaced with `[REDACTED_*]` | **PASS** | Redaction middleware |
| **COMP-01** | Compliance Center (`/admin/compliance`) | Data retention policies, legal holds, and audit evidence | `full_acceptance.spec.ts: TC-COMP-01` | Retention policies managed, legal hold prevents pruning | **PASS** | Compliance audit trail |
| **COMP-02** | Cryptographic Evidence Bundles | Generate tamper-evident compliance bundles with SHA-256 | `full_acceptance.spec.ts: TC-COMP-02` | Evidence bundle verified with digital fingerprint | **PASS** | Evidence registry |
| **OPER-01** | Operations Dashboard (`/admin/operations`) | Live worker fleet telemetry, queue depth, throughput RPS | `full_acceptance.spec.ts: TC-OPER-01` | Real-time RPS, active worker count, and latency shown | **PASS** | SRE Command Center |
| **OPER-02** | Dead Letter Queue (DLQ) & Retry | Isolate poison tasks and trigger manual/automated retries | `full_acceptance.spec.ts: TC-OPER-02` | DLQ depth tracked, retry re-queues task cleanly | **PASS** | DLQ inspector |
| **OPER-03** | Automated DR Restore Test | Trigger non-destructive disaster recovery integrity validation | `full_acceptance.spec.ts: TC-OPER-03` | Restore verified in isolated schema, RTO measured | **PASS** | DR test trigger button |

---

## 3. Negative & Edge Case Traceability

| Edge Case ID | Scenario | Expected Defense Behavior | Status |
| :--- | :--- | :--- | :---: |
| **NEG-01** | Missing required form fields | Inline field validation prevents submission | **PASS** |
| **NEG-02** | Weak or malformed passwords | Password complexity validator enforces minimum length & rules | **PASS** |
| **NEG-03** | Cross-tenant project access attempt | Returns `403 Forbidden` / `401 Unauthorized` | **PASS** |
| **NEG-04** | Malformed JSON tool schema in agent | Schema validator rejects payload with explicit path error | **PASS** |
| **NEG-05** | Poison queue message | Moves to DLQ after 3 exponential backoff retries without crashing worker | **PASS** |
| **NEG-06** | Database connection transient loss | Async connection pool retries with pool recycling | **PASS** |

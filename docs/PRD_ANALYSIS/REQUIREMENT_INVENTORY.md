# Requirement Inventory — AIREX

This document is the complete inventory of every requirement stated (or explicitly required) by the AIREX PRD V1.0. Each requirement has a unique ID and is categorized. Requirements are derived strictly from the PRD text; inferred-but-not-stated items are flagged and cross-referenced to the [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md).

## ID Prefix Legend

| Prefix | Category |
|--------|----------|
| FR- | Functional |
| NFR- | Non-functional |
| UX- | UX / Accessibility |
| SEC- | Security |
| PERF- | Performance |
| DATA- | Data / Persistence |
| API- | API |
| INFRA- | Infrastructure |
| INT- | Integration |
| COMP- | Compliance |
| ANA- | Analytics |
| BILL- | Billing |
| ADM- | Administration |

---

## 1. Functional Requirements

### 1.1 Authentication & Authorization (FR-AUTH)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-AUTH-001 | Support email/password registration | §9 |
| FR-AUTH-002 | Support login | §9 |
| FR-AUTH-003 | Support logout | §9 |
| FR-AUTH-004 | Support password reset | §9 |
| FR-AUTH-005 | Support email verification | §9 |
| FR-AUTH-006 | Support JWT/session authentication | §9 |
| FR-AUTH-007 | Support role-based access control | §9 |
| FR-AUTH-008 | Support organization membership | §9 |
| FR-AUTH-009 | Support project-level permissions | §9 |
| FR-AUTH-010 | Reject duplicate email registration | §9 AC-AUTH-002 |
| FR-AUTH-011 | Reject authentication with invalid credentials | §9 AC-AUTH-003 |
| FR-AUTH-012 | Reject unauthenticated requests to protected APIs | §9 AC-AUTH-004 |
| FR-AUTH-013 | Restrict user access to projects within their own organization | §9 AC-AUTH-005 |
| FR-AUTH-014 | Prevent Viewer role from modifying datasets/evaluations | §9 AC-AUTH-006 |

### 1.2 Organization Management (FR-ORG)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-ORG-001 | Organization is the top-level tenant | §10 |
| FR-ORG-002 | Organizations are isolated (no cross-tenant data leakage) | §10 |
| FR-ORG-003 | Organization contains users, projects, API keys, models, datasets, experiments, reports | §10 |
| FR-ORG-004 | Admin can invite users | §10 |
| FR-ORG-005 | Admin can remove users | §10 |
| FR-ORG-006 | Admin can change user roles | §10 |
| FR-ORG-007 | Organization settings must be persisted | §10 |

### 1.3 Project Management (FR-PROJECT)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-PROJECT-001 | User can create a project | §11 |
| FR-PROJECT-002 | User can edit project details | §11 |
| FR-PROJECT-003 | User can archive a project | §11 |
| FR-PROJECT-004 | User can delete a project only after confirmation | §11 |
| FR-PROJECT-005 | Archived projects cannot execute new production evaluations | §11 |
| FR-PROJECT-006 | Project supports configuration: name, description, application type, environment, endpoint, authentication configuration, model configuration, evaluation configuration | §11 |

### 1.4 AI Provider Management (FR-PROVIDER)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-PROVIDER-001 | Provider abstraction layer | §12 |
| FR-PROVIDER-002 | Support OpenAI | §12 |
| FR-PROVIDER-003 | Support Anthropic | §12 |
| FR-PROVIDER-004 | Support Google Gemini | §12 |
| FR-PROVIDER-005 | Support open-source models through compatible APIs | §12 |
| FR-PROVIDER-006 | Support local models | §12 |
| FR-PROVIDER-007 | Provider configuration fields: provider, model, API key, base URL, temperature, max tokens, timeout, retry policy | §12 |
| FR-PROVIDER-008 | API keys must never be displayed after initial creation | §12 |

### 1.5 Model Gateway (FR-GATEWAY)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-GATEWAY-001 | All AI requests pass through a common gateway abstraction (Application → Gateway → Provider Adapter → Model) | §13 |
| FR-GATEWAY-002 | Capture per request: request ID, model, prompt, response, timestamp, latency, token usage, cost, status, error, metadata | §13 |
| FR-GATEWAY-003 | A valid configured model successfully executes an inference request | §14 AC-MODEL-001 |
| FR-GATEWAY-004 | Invalid API credentials return a controlled error | §14 AC-MODEL-002 |
| FR-GATEWAY-005 | Timeouts are detected | §14 AC-MODEL-003 |
| FR-GATEWAY-006 | Provider errors are normalized into platform-level errors | §14 AC-MODEL-004 |
| FR-GATEWAY-007 | Token usage recorded when provider info is available | §14 AC-MODEL-005 |
| FR-GATEWAY-008 | Latency measured for every request | §14 AC-MODEL-006 |
| FR-GATEWAY-009 | Sensitive API keys never appear in logs | §14 AC-MODEL-007, §94 |

### 1.6 Dataset Management (FR-DATASET)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-DATASET-001 | Users can create evaluation datasets | §15 |
| FR-DATASET-002 | Import format: CSV | §15 |
| FR-DATASET-003 | Import format: JSON | §15 |
| FR-DATASET-004 | Import format: JSONL | §15 |
| FR-DATASET-005 | Manual entry | §15 |
| FR-DATASET-006 | Generated dataset (from test generator) | §15, §26 |
| FR-DATASET-007 | Dataset fields: input, expected answer, context, metadata, tags, difficulty, category | §15 |
| FR-DATASET-008 | Every dataset modification creates a version | §16 |
| FR-DATASET-009 | Dataset versions cannot be silently modified | §16 |
| FR-DATASET-010 | Each experiment references an immutable dataset version | §16 |
| FR-DATASET-011 | Users can compare dataset versions | §16 |
| FR-DATASET-012 | Dataset import failures provide row-level errors | §16 |
| FR-DATASET-013 | Duplicate dataset IDs are rejected | §16 |

### 1.7 Evaluation Engine (FR-EVAL)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-EVAL-001 | Evaluation pipeline: dataset → test runner → AI application → response → evaluator → metrics → score → report | §17 |
| FR-EVAL-002 | Each test generates: input, expected output, actual output, context, metrics, score, latency, tokens, cost, status | §17 |
| FR-EVAL-003 | Support exact-match evaluation | §18, §19 |
| FR-EVAL-004 | Exact-match case-insensitive comparison is configurable | §19 |
| FR-EVAL-005 | Support semantic-similarity evaluation | §18, §20 |
| FR-EVAL-006 | Semantic-similarity threshold is configurable | §20 |
| FR-EVAL-007 | Support answer-correctness evaluation with score, reason, pass/fail | §21 |
| FR-EVAL-008 | Human review available for uncertain correctness cases | §21 |
| FR-EVAL-009 | Support hallucination evaluation (claims supported by supplied context) | §22 |
| FR-EVAL-010 | Hallucination classification: Supported / Unsupported / Contradicted / Unknown | §23 AC-HALL-005 |
| FR-EVAL-011 | Supported answers receive passing faithfulness score | §23 AC-HALL-001 |
| FR-EVAL-012 | Contradictory answers flagged | §23 AC-HALL-002 |
| FR-EVAL-013 | Unsupported claims identified where evaluator can determine them | §23 AC-HALL-003 |
| FR-EVAL-014 | Hallucination evaluator provides an explanation | §23 AC-HALL-004 |
| FR-EVAL-015 | RAG evaluation at two levels: retrieval quality and generation quality | §24 |
| FR-EVAL-016 | Retrieval quality metrics: context relevance, context precision, context recall, ranking quality | §24 |
| FR-EVAL-017 | Generation quality metrics: correctness, faithfulness, completeness, hallucination | §24 |
| FR-EVAL-018 | RAG failure classification: RETRIEVAL_FAILURE, GENERATION_FAILURE, CONTEXT_FAILURE, PROMPT_FAILURE, MODEL_FAILURE, DATA_FAILURE, UNKNOWN | §25 |
| FR-EVAL-019 | Support toxicity evaluation | §18 |
| FR-EVAL-020 | Support bias evaluation | §18 |
| FR-EVAL-021 | Support prompt-injection evaluation | §18 |
| FR-EVAL-022 | Support data-leakage evaluation | §18 |
| FR-EVAL-023 | Support response-format evaluation | §18 |
| FR-EVAL-024 | Support latency evaluation | §18 |
| FR-EVAL-025 | Support cost evaluation | §18 |
| FR-EVAL-026 | Support consistency evaluation | §18 |
| FR-EVAL-027 | Support regression evaluation | §18 |

### 1.8 AI Test Generator (FR-TESTGEN)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-TESTGEN-001 | Automatically generate test cases | §26 |
| FR-TESTGEN-002 | Generation inputs: application description, dataset, documentation, existing tests | §26 |
| FR-TESTGEN-003 | Output category: Normal | §26 |
| FR-TESTGEN-004 | Output category: Edge Case | §26 |
| FR-TESTGEN-005 | Output category: Adversarial | §26 |
| FR-TESTGEN-006 | Output category: Ambiguous | §26 |
| FR-TESTGEN-007 | Output category: Safety | §26 |
| FR-TESTGEN-008 | Output category: Prompt Injection | §26 |
| FR-TESTGEN-009 | Output category: Long Context | §26 |
| FR-TESTGEN-010 | Output category: Multilingual | §26 |
| FR-TESTGEN-011 | Configurable number of generated test cases | §27 AC-TESTGEN-001 |
| FR-TESTGEN-012 | Generated tests contain category metadata | §27 AC-TESTGEN-002 |
| FR-TESTGEN-013 | Generated tests are previewable before execution | §27 AC-TESTGEN-003 |
| FR-TESTGEN-014 | User can approve/reject generated tests | §27 AC-TESTGEN-004 |
| FR-TESTGEN-015 | Rejected tests do not enter the evaluation run | §27 AC-TESTGEN-005 |
| FR-TESTGEN-016 | Generated tests are versioned | §27 AC-TESTGEN-006 |

### 1.9 Prompt Injection Testing (FR-PROMPTINJ)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-PROMPTINJ-001 | Test whether an AI application can be manipulated through user input | §28 |
| FR-PROMPTINJ-002 | Classify response as SAFE / VULNERABLE / UNCERTAIN | §28 |
| FR-PROMPTINJ-003 | Must not encourage real-world abuse | §28 |
| FR-PROMPTINJ-004 | Testing only against systems the user owns or is authorized to evaluate | §28 |

### 1.10 Safety Evaluation (FR-SAFETY)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-SAFETY-001 | Evaluate toxicity | §29 |
| FR-SAFETY-002 | Evaluate self-harm-related unsafe responses | §29 |
| FR-SAFETY-003 | Evaluate hate/harassment | §29 |
| FR-SAFETY-004 | Evaluate dangerous instructions | §29 |
| FR-SAFETY-005 | Evaluate privacy leakage | §29 |
| FR-SAFETY-006 | Evaluate system prompt leakage | §29 |
| FR-SAFETY-007 | Evaluate sensitive information exposure | §29 |
| FR-SAFETY-008 | Each safety evaluation outputs: category, severity, score, explanation, status | §29 |

### 1.11 Performance Evaluation (FR-PERF-EVAL)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-PERF-EVAL-001 | Measure total latency per AI request | §30 |
| FR-PERF-EVAL-002 | Measure time to first token where supported | §30 |
| FR-PERF-EVAL-003 | Measure input tokens | §30 |
| FR-PERF-EVAL-004 | Measure output tokens | §30 |
| FR-PERF-EVAL-005 | Measure total tokens | §30 |
| FR-PERF-EVAL-006 | Measure throughput | §30 |
| FR-PERF-EVAL-007 | Measure error rate | §30 |
| FR-PERF-EVAL-008 | Dashboard shows P50, P95, P99 latency | §30 |
| FR-PERF-EVAL-009 | Dashboard shows requests/minute | §30 |

### 1.12 Cost Evaluation (FR-COST)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-COST-001 | Estimate cost from input tokens, output tokens, provider, model, pricing configuration | §31 |
| FR-COST-002 | Pricing configuration is versioned | §31 |
| FR-COST-003 | Support cost/request | §31 |
| FR-COST-004 | Support cost/1K tokens | §31 |
| FR-COST-005 | Support cost/evaluation | §31 |
| FR-COST-006 | Support cost/dataset | §31 |
| FR-COST-007 | Support estimated monthly cost | §31 |

### 1.13 Model Benchmarking (FR-BENCH)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-BENCH-001 | Compare models (accuracy, hallucination, latency, cost) | §32 |
| FR-BENCH-002 | Calculate an overall weighted score | §32 |
| FR-BENCH-003 | Weights are configurable | §32 |
| FR-BENCH-004 | Fair comparison: same dataset, same test cases, same evaluator, same evaluation configuration | §76 |

### 1.14 Prompt Experimentation (FR-PROMPT)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-PROMPT-001 | Create prompt versions | §33 |
| FR-PROMPT-002 | Run the same dataset against each prompt version | §33 |
| FR-PROMPT-003 | Compare accuracy, hallucination, latency, cost, safety across versions | §33 |

### 1.15 Experiment Management (FR-EXPERIMENT)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-EXPERIMENT-001 | Store: experiment ID, project, dataset version, model, model version, prompt version, parameters, timestamp, environment, metrics, results | §34 |
| FR-EXPERIMENT-002 | Experiments are immutable after completion | §34 |

### 1.16 Reproducibility (FR-REPRO)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-REPRO-001 | Experiments reproducible as far as underlying provider/model permits | §35 |
| FR-REPRO-002 | Store: dataset version, prompt, model, parameters, evaluator version, evaluation configuration, timestamp, random seed where supported | §35 |

### 1.17 Regression Testing (FR-REGRESSION)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-REGRESSION-001 | Compare a new version against a baseline | §36 |
| FR-REGRESSION-002 | Detect regression | §36 |
| FR-REGRESSION-003 | Configure regression thresholds/policies | §37 |
| FR-REGRESSION-004 | Establish and store a baseline | §102 Step 13 |

### 1.18 CI/CD Integration (FR-CICD)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-CICD-001 | CI pipeline can trigger an evaluation | §38, §40 AC-CICD-001 |
| FR-CICD-002 | Evaluation result returned to CI | §40 AC-CICD-002 |
| FR-CICD-003 | Failed quality gates cause a non-zero exit status | §40 AC-CICD-003 |
| FR-CICD-004 | Passed quality gates return success | §40 AC-CICD-004 |
| FR-CICD-005 | CI execution references a specific dataset version | §40 AC-CICD-005 |
| FR-CICD-006 | Quality gate with configurable thresholds (see BR-QUALITY-001) | §39 |

### 1.19 Production Observability (FR-OBS)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-OBS-001 | Real-time AI observability | §41 |
| FR-OBS-002 | Dashboard shows: requests, errors, latency, tokens, cost, quality score, hallucination, safety, model distribution | §41 |
| FR-OBS-003 | Time ranges: last 15 min, 1 hour, 24 hours, 7 days, 30 days, custom | §41 |
| FR-OBS-004 | Every AI request has a trace | §42 |
| FR-OBS-005 | Trace steps: user request, retriever, documents, prompt builder, LLM, evaluator, response | §42 |
| FR-OBS-006 | Each trace step exposes: duration, input, output, metadata, error | §42 |
| FR-OBS-007 | Sensitive content redacted in traces per project settings | §42 |

### 1.20 Alerting (FR-ALERT)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-ALERT-001 | Alert on accuracy degradation | §43 |
| FR-ALERT-002 | Alert on hallucination increase | §43 |
| FR-ALERT-003 | Alert on latency increase | §43 |
| FR-ALERT-004 | Alert on error increase | §43 |
| FR-ALERT-005 | Alert on cost spike | §43 |
| FR-ALERT-006 | Alert on safety failure | §43 |
| FR-ALERT-007 | Alert on model failure | §43 |
| FR-ALERT-008 | Alert channels: in-app, email, webhook | §43 |
| FR-ALERT-009 | Alert rules support: severity, threshold, duration, cooldown, enabled/disabled | §44 |
| FR-ALERT-010 | Alert rule condition example: P95 latency > 3s for 10 minutes → create alert | §44 |
| FR-ALERT-011 | Alert rule condition example: hallucination > 7% → critical alert | §44 |

### 1.21 Root Cause Analysis (FR-RCA)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-RCA-001 | When an evaluation fails, identify likely causes (e.g., retrieval vs generation degradation with evidence) | §45 |
| FR-RCA-002 | Clearly label AI-generated explanations as recommendations, not guaranteed truth | §45 |

### 1.22 Recommendation Engine (FR-RECO)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-RECO-001 | Generate recommendations (e.g., increase top-K) with reasons | §46 |
| FR-RECO-002 | Recommendation types: change chunk size, increase retrieval depth, add reranking, modify system prompt, change model, reduce temperature, reduce context size, add safety guardrails | §46 |
| FR-RECO-003 | Recommendations must be reviewable before implementation | §46 |

### 1.23 Research Workspace (FR-RESEARCH)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-RESEARCH-001 | Provide a research workspace | §47 |
| FR-RESEARCH-002 | Support experiment creation | §47 |
| FR-RESEARCH-003 | Support hypothesis definition | §47 |
| FR-RESEARCH-004 | Support variables (baseline vs treatment) | §47 |
| FR-RESEARCH-005 | Reference a dataset | §47 |
| FR-RESEARCH-006 | Capture metrics and results | §47 |
| FR-RESEARCH-007 | Statistical analysis | §47 |
| FR-RESEARCH-008 | Charts | §47 |
| FR-RESEARCH-009 | Conclusions | §47 |
| FR-RESEARCH-010 | Export | §47 |
| FR-RESEARCH-011 | Statistical evaluation support: mean, median, standard deviation, percentiles, confidence intervals, effect size, statistical significance where applicable | §48 |
| FR-RESEARCH-012 | Avoid claiming significance when sample size/methodology insufficient | §48 |
| FR-RESEARCH-013 | Research report structure: abstract, research question, hypothesis, dataset, methodology, experimental setup, baseline, results, statistical analysis, limitations, conclusion, future work | §49 |
| FR-RESEARCH-014 | Research report export: Markdown, PDF, JSON, CSV | §49 |
| FR-RESEARCH-015 | Research publication support: raw experimental data, aggregated data, methodology, experiment configuration, statistical results, charts, reproducibility metadata | §81 |

### 1.24 Dashboard (FR-DASH)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-DASH-001 | Main dashboard with AI Reliability Score | §50 |
| FR-DASH-002 | Main dashboard shows recent evaluations | §50 |
| FR-DASH-003 | Main dashboard shows alerts | §50 |
| FR-DASH-004 | Project dashboard shows: reliability score, accuracy, hallucination, safety, latency, cost, error rate, recent evaluations, regression status, active alerts | §69 |
| FR-DASH-005 | Evaluation details page shows: status, dataset, model, prompt, metrics, P95 latency, cost, pass/fail/warning counts, drill into failures | §70 |
| FR-DASH-006 | Test result page shows: question, expected answer, actual answer, retrieved context, evaluation scores, failure classification, reason, trace | §71 |

### 1.25 API (FR-API)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-API-001 | Expose REST APIs | §51 |
| FR-API-002 | Core endpoints listed in §51 | §51 |
| FR-API-003 | All APIs return consistent error formats | §51 |
| FR-API-004 | API documentation auto-generated (OpenAPI/Swagger) | §95 |

### 1.26 CLI (FR-CLI)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-CLI-001 | Provide a CLI | §52 |
| FR-CLI-002 | CLI commands: login, project create, dataset upload, evaluate run, regression run, report generate | §52 |
| FR-CLI-003 | CLI commands return meaningful exit codes | §52 |

### 1.27 Reporting & Export (FR-REPORT)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-REPORT-001 | Generate evaluation reports | §80 |
| FR-REPORT-002 | Report sections: executive summary, evaluation configuration, dataset, model, prompt, metrics, failures, regression analysis, cost analysis, latency analysis, safety analysis, recommendations, limitations | §80 |
| FR-REPORT-003 | Export test results | §79 |
| FR-REPORT-004 | Export evaluation results | §79 |
| FR-REPORT-005 | Export metrics | §79 |
| FR-REPORT-006 | Export experiment results | §79 |
| FR-REPORT-007 | Export research data | §79 |
| FR-REPORT-008 | Export formats: CSV, JSON, Markdown, PDF | §79 |

### 1.28 Human Review & Calibration (FR-HUMAN)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-HUMAN-001 | Users can mark automated evaluation PASS and human review PASS | §72 |
| FR-HUMAN-002 | Users can mark automated FAIL as human FALSE POSITIVE | §72 |
| FR-HUMAN-003 | Human decisions stored for future analysis | §72 |
| FR-HUMAN-004 | Users can sample results for human review | §73 |
| FR-HUMAN-005 | Compare AI Judge vs Human Judge | §73 |
| FR-HUMAN-006 | Calculate AI/Human agreement | §73 |

### 1.29 AI Judge / Evaluation Confidence (FR-JUDGE)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-JUDGE-001 | System may use LLMs as evaluators (AI Judge) | §74 |
| FR-JUDGE-002 | Store for every AI judgment: evaluator model, evaluator prompt, evaluator version, score, explanation, timestamp | §74 |
| FR-JUDGE-003 | Optionally include score confidence | §75 |
| FR-JUDGE-004 | Low-confidence results eligible for human review | §75 |

### 1.30 Environment Management (FR-ENV)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-ENV-001 | Support environments: development, staging, production | §77 |
| FR-ENV-002 | Each environment may have separate model, endpoint, API credentials, evaluation policies | §77 |
| FR-ENV-003 | Production credentials never exposed to development users without authorization | §77 |

### 1.31 Versioning (FR-VERSION)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-VERSION-001 | Version: dataset, prompt, model, evaluator, evaluation configuration, application, experiment | §78 |
| FR-VERSION-002 | Each evaluation references exact versions | §78 |

### 1.32 AI Reliability Score (FR-SCORE)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-SCORE-001 | Calculate a configurable AI Reliability Score | §83 |
| FR-SCORE-002 | Score between 0 and 100 | §84 AC-SCORE-001 |
| FR-SCORE-003 | Changing metric weights recalculates the score | §84 AC-SCORE-002 |
| FR-SCORE-004 | Missing metrics must not silently become zero | §84 AC-SCORE-003 |
| FR-SCORE-005 | Score calculation configuration stored with the experiment | §84 AC-SCORE-004 |
| FR-SCORE-006 | Score calculation is transparent | §83 |

### 1.33 Notifications (FR-NOTIFY)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-NOTIFY-001 | Notify when evaluation completes | §85 |
| FR-NOTIFY-002 | Notify when evaluation fails | §85 |
| FR-NOTIFY-003 | Notify when regression detected | §85 |
| FR-NOTIFY-004 | Notify when quality threshold violated | §85 |
| FR-NOTIFY-005 | Notify when cost threshold violated | §85 |
| FR-NOTIFY-006 | Notify when safety threshold violated | §85 |

### 1.34 Asynchronous Evaluation & Workers (FR-ASYNC)

| ID | Requirement | Source |
|----|-------------|--------|
| FR-ASYNC-001 | Large evaluations run asynchronously (API → job → queue → workers → results) | §56 |
| FR-ASYNC-002 | API must not remain blocked for entire evaluation | §56 |
| FR-ASYNC-003 | Workers support parallel execution | §57 |
| FR-ASYNC-004 | Workers support retry | §57 |
| FR-ASYNC-005 | Workers support timeout | §57 |
| FR-ASYNC-006 | Workers support rate limiting | §57 |
| FR-ASYNC-007 | Workers respect provider limits | §57 |
| FR-ASYNC-008 | Workers support partial failure handling | §57 |
| FR-ASYNC-009 | Workers support job cancellation | §57 |
| FR-ASYNC-010 | Transient failures retry; permanent failures do not retry indefinitely | §58 |
| FR-ASYNC-011 | Maximum retry count configurable | §58 |
| FR-ASYNC-012 | Evaluation jobs survive API server restarts | §88 |
| FR-ASYNC-013 | Partial results not lost when a worker crashes | §89 |

---

## 2. Non-Functional Requirements (NFR)

| ID | Requirement | Source |
|----|-------------|--------|
| NFR-PERF-001 | API P95 response < 500 ms for normal non-AI operations | §87 |
| NFR-PERF-002 | Dashboard initial page load < 3 seconds under normal conditions | §87 |
| NFR-PERF-003 | Evaluation processes multiple test cases concurrently per configured worker limits | §87 |
| NFR-RELI-001 | Target platform availability 99.5%+ for MVP production deployment | §88 |
| NFR-RELI-002 | Evaluation jobs survive API server restarts | §88 |
| NFR-RELI-003 | Partial results must not be lost on worker crash | §89 |
| NFR-OBS-001 | AIREX itself observable: API latency, worker latency, queue depth, error rate, DB performance, Redis health, provider health, evaluation throughput | §64 |
| NFR-OBS-002 | Health check endpoints /health, /ready, /live verifying dependencies | §65 |
| NFR-TEST-001 | Backend automated test coverage ≥ 80% (MVP) | §91 |
| NFR-TEST-002 | Critical business logic coverage ≥ 90% | §91 |
| NFR-TEST-003 | Evaluation engine coverage ≥ 90% | §91 |
| NFR-TEST-004 | Coverage alone not treated as proof of quality | §91 |
| NFR-DOC-001 | API documentation auto-generated (OpenAPI/Swagger) | §95 |
| NFR-DOC-002 | Every endpoint documents request, response, authentication, errors, example | §95 |

> Note: No explicit scalability/concurrency numeric targets beyond §87. Marked in AMBIGUITY_REGISTER as AMB-SCALE-001.

---

## 3. UX / Accessibility Requirements (UX)

| ID | Requirement | Source |
|----|-------------|--------|
| UX-001 | Keyboard navigation | §86 |
| UX-002 | Semantic HTML | §86 |
| UX-003 | Readable contrast | §86 |
| UX-004 | Focus states | §86 |
| UX-005 | Accessible forms | §86 |
| UX-006 | Screen-reader-friendly labels | §86 |
| UX-007 | Frontend pages listed in §68 (login, register, dashboard, projects, project sub-pages, research, settings, audit-logs) | §68 |

---

## 4. Security Requirements (SEC)

| ID | Requirement | Source |
|----|-------------|--------|
| SEC-AUTH-001 | HTTPS | §59 |
| SEC-AUTH-002 | Password hashing | §59 |
| SEC-AUTH-003 | JWT/session security | §59 |
| SEC-AUTH-004 | RBAC | §59 |
| SEC-API-001 | API key encryption | §59 |
| SEC-API-002 | Secret masking | §59 |
| SEC-API-003 | API keys never displayed after creation | §12, §14 AC-MODEL-007 |
| SEC-INPUT-001 | Input validation | §59 |
| SEC-INPUT-002 | SQL injection protection | §59 |
| SEC-INPUT-003 | XSS protection | §59 |
| SEC-INPUT-004 | CSRF protection where applicable | §59 |
| SEC-RATE-001 | Rate limiting | §59 |
| SEC-RATE-002 | Rate limits for: API requests, evaluation jobs, model calls, dataset generation, test generation | §62 |
| SEC-RATE-003 | Rate limits configurable per organization | §62 |
| SEC-AUDIT-001 | Audit logging | §59 |
| SEC-AUDIT-002 | Audit log records: actor, action, resource, timestamp, IP where available, result | §61 |
| SEC-AUDIT-003 | Audit events: user login, API key created/deleted, project created, dataset deleted, evaluation executed, configuration changed, user role changed | §61 |
| SEC-AUDIT-004 | Audit logs cannot be modified by normal users | §93 AC-SEC-005 |
| SEC-MULTI-001 | User A cannot retrieve Organization B data | §93 AC-SEC-001 |
| SEC-MULTI-002 | Project IDs cannot bypass authorization | §93 AC-SEC-002 |
| SEC-MULTI-003 | API keys cannot be retrieved in plaintext | §93 AC-SEC-003 |
| SEC-MULTI-004 | Deleted users lose access immediately | §93 AC-SEC-004 |
| SEC-ERR-001 | Standard error structure: error.code, error.message, error.request_id | §63 |
| SEC-ERR-002 | No internal stack traces exposed to end users | §63 |
| SEC-LOG-001 | Logs contain: timestamp, request_id, user_id where appropriate, organization_id, service, level, message | §94 |
| SEC-LOG-002 | Logs must not contain: API keys, passwords, access tokens, unmasked sensitive production data | §94 |
| SEC-TEST-001 | Security testing: auth bypass, authz bypass, SQL injection, XSS, CSRF, rate-limit bypass, secret exposure, cross-tenant access, prompt injection, data leakage | §92 |
| SEC-DATA-001 | Sensitive values redacted where configured ([PERSON], [PHONE] examples) | §60 |

---

## 5. Performance Requirements (PERF)

| ID | Requirement | Source |
|----|-------------|--------|
| PERF-001 | API P95 < 500 ms for normal non-AI operations | §87 |
| PERF-002 | Dashboard initial load < 3 s | §87 |
| PERF-003 | Concurrent evaluation per worker limits | §87 |
| PERF-004 | Latency measured for every AI request | §30, AC-MODEL-006 |
| PERF-005 | Time to first token measured where supported | §30 |

---

## 6. Data Requirements (DATA)

| ID | Requirement | Source |
|----|-------------|--------|
| DATA-001 | PostgreSQL as recommended database | §53 |
| DATA-002 | Core entities: users, organizations, organization_members, projects, environments, providers, models, api_keys, datasets, dataset_versions, test_cases, test_runs, test_results, evaluators, evaluation_runs, evaluation_results, experiments, experiment_metrics, prompts, prompt_versions, traces, trace_events, alerts, alert_rules, reports, research_projects, research_experiments, audit_logs | §53 |
| DATA-003 | Vector storage: pgvector initially | §54 |
| DATA-004 | Optional external vector databases later | §54 |
| DATA-005 | Vector store: document ID, chunk ID, embedding, metadata, source, version | §54 |
| DATA-006 | Redis for: evaluation jobs, rate limiting, temporary results, distributed locks, task queues | §55 |
| DATA-PRIV-001 | Raw data storage toggle ON/OFF | §60 |
| DATA-PRIV-002 | PII masking toggle ON/OFF | §60 |
| DATA-PRIV-003 | Prompt storage toggle ON/OFF | §60 |
| DATA-PRIV-004 | Response storage toggle ON/OFF | §60 |
| DATA-PRIV-005 | Sensitive value redaction ([PERSON], [PHONE]) | §60 |
| DATA-VER-001 | Dataset versioning (see FR-DATASET-008..013) | §16 |
| DATA-VER-002 | Prompt versioning | §33 |
| DATA-VER-003 | Pricing configuration versioning | §31 |
| DATA-VER-004 | Evaluator versioning | §78 |
| DATA-VER-005 | Application versioning | §78 |
| DATA-IMM-001 | Dataset versions immutable; experiments immutable after completion | §16, §34 |

---

## 7. API Requirements (API)

| ID | Requirement | Source |
|----|-------------|--------|
| API-001 | POST /api/v1/projects | §51 |
| API-002 | GET /api/v1/projects | §51 |
| API-003 | GET /api/v1/projects/{id} | §51 |
| API-004 | POST /api/v1/datasets | §51 |
| API-005 | GET /api/v1/datasets | §51 |
| API-006 | POST /api/v1/datasets/{id}/versions | §51 |
| API-007 | POST /api/v1/evaluations | §51 |
| API-008 | GET /api/v1/evaluations/{id} | §51 |
| API-009 | POST /api/v1/evaluations/{id}/run | §51 |
| API-010 | POST /api/v1/experiments | §51 |
| API-011 | GET /api/v1/experiments | §51 |
| API-012 | POST /api/v1/models | §51 |
| API-013 | GET /api/v1/models | §51 |
| API-014 | POST /api/v1/tests/generate | §51 |
| API-015 | GET /api/v1/metrics | §51 |
| API-016 | POST /api/v1/regression/run | §51 |
| API-017 | GET /api/v1/reports/{id} | §51 |
| API-018 | GET /health, GET /ready, GET /live | §65 |
| API-019 | All APIs return consistent error format | §51, §63 |
| API-020 | OpenAPI/Swagger auto-generated documentation | §95 |

> Note: Request/response contracts, auth, authorization, error codes, rate limits, idempotency, and side effects are **NOT DEFINED** for these endpoints. See [`API_REQUIREMENTS.md`](./API_REQUIREMENTS.md).

---

## 8. Infrastructure Requirements (INFRA)

| ID | Requirement | Source |
|----|-------------|--------|
| INFRA-001 | Production architecture: load balancer, API gateway, API server, web app, PostgreSQL, Redis, job queue, workers, model gateway | §66 |
| INFRA-002 | Docker | §67 |
| INFRA-003 | Kubernetes (V2) | §97 |
| INFRA-004 | AWS as target cloud | §67 |
| INFRA-005 | Health checks /health, /ready, /live | §65 |
| INFRA-006 | Observability: OpenTelemetry, Prometheus, Grafana | §64, §67 |
| INFRA-007 | CI/CD: GitHub Actions | §67 |
| INFRA-008 | Async job infrastructure: queue + workers (Celery/RQ/Arq initially) | §56, §67 |

---

## 9. Integration Requirements (INT)

| ID | Requirement | Source |
|----|-------------|--------|
| INT-001 | OpenAI provider integration | §12, §67 |
| INT-002 | Anthropic provider integration | §12, §67 |
| INT-003 | Google Gemini provider integration | §12, §67 |
| INT-004 | Open-source model integration via compatible APIs | §12 |
| INT-005 | Local model integration | §12 |
| INT-006 | Hugging Face/local models (tech stack mention) | §67 |
| INT-007 | GitHub Actions CI/CD integration | §38, §67 |
| INT-008 | Webhook alert channel | §43 |
| INT-009 | pgvector vector store | §54, §67 |
| INT-010 | External vector database support (later) | §54 |
| INT-011 | Enterprise SSO (V3) | §98 |

---

## 10. Compliance Requirements (COMP)

| ID | Requirement | Source |
|----|-------------|--------|
| COMP-001 | Data privacy controls (storage toggles, PII masking, redaction) | §60 |
| COMP-002 | Data isolation across tenants | §10, §93 |
| COMP-003 | Audit logging of security-sensitive events | §61, §93 |
| COMP-004 | Log hygiene (no secrets, no unmasked sensitive data) | §94 |
| COMP-005 | Not storing sensitive production data indefinitely (non-goal) | §5 |

> Note: No explicit regulatory compliance (SOC2, GDPR, HIPAA) or retention policy is defined. See AMBIGUITY_REGISTER (AMB-COMPLIANCE-001, AMB-RETENTION-001).

---

## 11. Analytics Requirements (ANA)

| ID | Requirement | Source |
|----|-------------|--------|
| ANA-001 | AI quality metrics dashboards (accuracy, hallucination, safety, latency, cost) | §41, §50, §69 |
| ANA-002 | P50/P95/P99 latency analytics | §30 |
| ANA-003 | Cost analytics | §31 |
| ANA-004 | Statistical analysis for research | §48 |
| ANA-005 | AI/Human agreement analytics (calibration) | §73 |
| ANA-006 | Model distribution analytics | §41 |
| ANA-007 | Product success metrics (engineering, AI, research, portfolio) | §99 |

---

## 12. Billing Requirements (BILL)

| ID | Requirement | Source |
|----|-------------|--------|
| BILL-001 | Estimate AI inference cost (input/output tokens × provider pricing) | §31 |
| BILL-002 | Versioned pricing configuration | §31 |
| BILL-003 | Cost/request, cost/1K tokens, cost/evaluation, cost/dataset, estimated monthly cost | §31 |
| BILL-004 | Cost threshold alerts | §43 |
| BILL-005 | Cost analysis in reports | §80 |

> **GAP (critical):** The PRD defines **AI inference cost analytics** but defines **no platform subscription/billing/pricing tiers** for the AIREX SaaS product itself. See AMBIGUITY_REGISTER → AMB-BILLING-001.

---

## 13. Administration Requirements (ADM)

| ID | Requirement | Source |
|----|-------------|--------|
| ADM-001 | Admin can create organizations | §7 |
| ADM-002 | Admin can manage users | §7 |
| ADM-003 | Admin can manage projects | §7 |
| ADM-004 | Admin can manage API keys | §7 |
| ADM-005 | Admin can configure integrations | §7 |
| ADM-006 | Admin can configure policies | §7 |
| ADM-007 | Admin can view all reports | §7 |
| ADM-008 | Admin invite/remove/change roles of users | §10 |
| ADM-009 | Audit log viewing (audit-logs page) | §68 |
| ADM-010 | Settings page | §68 |

---

## 14. Summary Counts

| Category | Count |
|----------|------:|
| Functional (FR-*) | ~140 |
| Non-functional (NFR-*) | ~15 |
| UX | 7 |
| Security (SEC-*) | ~28 |
| Performance (PERF-*) | 5 |
| Data (DATA-*) | ~18 |
| API (API-*) | 20 |
| Infrastructure (INFRA-*) | 8 |
| Integration (INT-*) | 11 |
| Compliance (COMP-*) | 5 |
| Analytics (ANA-*) | 7 |
| Billing (BILL-*) | 5 |
| Administration (ADM-*) | 10 |
| **Total** | **~279** |

> Counts are approximate because several PRD statements bundle multiple requirements under a single bullet.

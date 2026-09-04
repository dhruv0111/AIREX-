# AIREX — AI Functionality & Architecture Map

**Audit Date:** September 4, 2026  
**Repository Scope:** Full Backend Service Fleet (`apps/api`) & Frontend Workspace (`apps/web`)  
**Objective:** Ground-truth classification of where AI is genuinely invoked vs rule-based algorithms, input/output data flow, persistence layers, and feature connectivity status.

---

## 1. Architectural Answers to Core Engine Questions

### 1. Where AI models are called
* **Model Gateway (`apps/api/app/integrations/gateway.py` & `apps/api/app/services/provider.py`):**  
  All external and internal model requests pass through `ModelGatewayService`. It standardizes requests into `ModelRequest`, applies timeout limits, implements exponential backoff retries, and delegates to provider adapters (`OpenAIAdapter`, `AnthropicAdapter`, `LocalGatewayAdapter`).
* **LLM-as-a-Judge (`apps/api/app/judge/` & `apps/api/app/evaluators/llm_judge.py`):**  
  Invokes configured judge models using structured prompt templates (`JUDGE_PROMPT_VERSION`) with schema-enforced JSON score outputs.

### 2. Where AI responses are stored
* **Generations Table (`generations` model in `apps/api/app/models/generation.py`):**  
  Stores raw model outputs, prompt tokens, completion tokens, response latency in milliseconds, and model hyperparameters.
* **Evaluation Results Table (`evaluation_results` in `apps/api/app/models/evaluation.py`):**  
  Stores per-test-case actual output, pass/fail status, numerical score array, failure classification (`ASSERTION_FAILED`, `TIMEOUT`, `PROVIDER_ERROR`, `EVALUATOR_ERROR`), and judge explanation.

### 3. Where responses are evaluated
* **Evaluation Runner (`apps/api/app/evaluations/runner.py`):**  
  Iterates over dataset test cases using bounded concurrency (`asyncio.Semaphore`). Compares actual output against expected ground truth using registered evaluators.
* **Evaluation Aggregator (`apps/api/app/evaluations/aggregate.py`):**  
  Computes run-level summary metrics: aggregate accuracy, pass rate, p50/p95/p99 latency distributions, total token usage, and cost estimates.

### 4. Which evaluators are rule-based
* **Exact Match Evaluator (`ExactMatchEvaluator`):** Deterministic string equality after whitespace normalization.
* **Regex Match Evaluator (`RegexMatchEvaluator`):** Pattern matching for structural formats (e.g., email, order ID, phone numbers).
* **JSON Schema Evaluator (`JsonSchemaEvaluator`):** Validates JSON syntax and schema compliance for structured outputs.
* **Numeric Bounds Evaluator (`NumericBoundsEvaluator`):** Validates scalar ranges (e.g., confidence $\ge 0.85$, price within bounds).
* **Length / Latency Bounds (`LatencyEvaluator`):** Checks SLA threshold boundaries (e.g., latency $< 800\text{ms}$).

### 5. Which evaluators use an LLM-as-a-Judge
* **LLM Judge Evaluator (`LlmJudgeEvaluator` in `apps/api/app/evaluators/llm_judge.py`):**  
  Sends the input prompt, reference answer, actual answer, and grading criteria to a designated judge model. Returns a normalized score $[0.0, 1.0]$, confidence level, criteria breakdown, and natural language reasoning.
* **Semantic Groundedness & Hallucination Evaluator:** Evaluates whether statements in the output are supported by provided context docs.

### 6. How accuracy is calculated
* **Run Accuracy Formula:**  
  $$\text{Accuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{status}_i == \text{'PASS'})}{N} \times 100\%$$
* Combined pass policies support `ALL` (all evaluators must pass), `ANY` (at least one evaluator passes), or `WEIGHTED` (weighted sum of criteria scores $\ge \text{threshold}$).

### 7. How latency is calculated
* **Per-Test Latency:** Captured using monotonic clock delta ($\Delta t = t_{\text{end}} - t_{\text{start}}$) in milliseconds across network socket operations.
* **Percentiles:** Calculated across sorted run execution latencies for $p_{50}$ (median), $p_{95}$, and $p_{99}$ tails.

### 8. How cost is calculated
* **Token Cost Pricing Matrix (`apps/api/app/schemas/pricing.py`):**  
  $$\text{Total Cost} = (\text{Prompt Tokens} \times \text{Price}_{\text{in}}) + (\text{Completion Tokens} \times \text{Price}_{\text{out}})$$
  Pricing tables are configurable per model catalog entry.

### 9. How experiments compare models or prompts
* **Experiment Runner (`apps/api/app/evaluations/experiment_runner.py`):**  
  Executes parallel matrix evaluations of Variant A (Baseline) vs Variant B (Candidate) across the same fixed dataset. Calculates delta metrics: $\Delta \text{Accuracy}$, $\Delta \text{Latency p95}$, $\Delta \text{Cost}$, and identifies regressions on individual test cases.

### 10. How agent tool calls are evaluated
* **Agent Reliability Scorer (`apps/api/app/services/agent_reliability.py` & `trajectory_evaluator.py`):**  
  Evaluates multi-step trajectories for:
  - **Tool Call Validity:** Arguments match JSON schema definition.
  - **Loop Detection:** Repeated identical tool calls with identical arguments (`LoopDetector`).
  - **Error Recovery:** Handling failed tool outputs gracefully.
  - **Overall Readiness Score:** Weighted score $[0, 100]$ based on trajectory safety and goal completion.

### 11. How release decisions are calculated
* **Decision Engine (`apps/api/app/services/decision_engine.py`):**  
  Evaluates configurable release policies against canonical evidence (`EVALUATION`, `EXPERIMENT`, `BENCHMARK`, `OBSERVABILITY`, `ALERT`, `AGENT_EVALUATION`). Checks:
  - Minimum accuracy threshold (e.g., $\ge 95\%$)
  - Maximum p95 latency ceiling (e.g., $\le 1200\text{ms}$)
  - Zero critical safety failures
  - Maximum evidence age (freshness within $N$ days)
  - Verdict is deterministic: `PASS`, `WARNING`, or `BLOCKED`.

### 12. How observability and audit evidence are generated
* **Observability Telemetry (`apps/api/app/services/observability.py`):**  
  Ingests spans and traces with automatic PII redaction masks (credit cards, email, SSN, API secrets) before persistence.
* **Audit Service (`apps/api/app/services/audit.py`):**  
  Appends immutable event records with SHA-256 fingerprint hashing for SOC 2 / ISO 27001 evidence bundles.

---

## 2. AI Functionality & Connectivity Matrix

| Feature Domain | AI Used? | Underlying Engine / Model | Input | Processing Method | Generated Output | Connectivity Status |
| :--- | :---: | :--- | :--- | :--- | :--- | :---: |
| **Model Ingestion & Catalog** | No | SQLAlchemy + Fernet Encryption | Provider credentials, endpoints | Encrypts API keys at rest | Catalog records & health status | **FULLY CONNECTED** |
| **Test Dataset Ingestion** | No | Pydantic Schema Validator | CSV / JSONL test cases | Validates test variables & ground truth | Versioned dataset snapshot | **FULLY CONNECTED** |
| **Model Execution** | **YES** | Local Gateway / OpenAI / Anthropic | Test prompt + parameters | Invokes model via `ModelGatewayService` | AI text response + token stats | **FULLY CONNECTED** |
| **Rule-Based Evaluators** | No | Python Regex, JSONSchema, Math | Actual output vs Expected output | Deterministic assertion checks | Binary Pass/Fail + score | **FULLY CONNECTED** |
| **LLM-as-a-Judge** | **YES** | Judge Model (e.g., GPT-4o / Claude) | Prompt + Reference + Actual | Evaluates nuance, tone, safety | Score $[0, 1]$ + reasoning | **FULLY CONNECTED** |
| **Evaluation Aggregator** | No | NumPy / Math Quantiles | Array of case test results | Computes p50/p95/p99, accuracy, cost | Executive evaluation summary | **FULLY CONNECTED** |
| **A/B Experiment Engine** | **YES** | Baseline vs Candidate Models | Matrix of test prompts | Runs parallel evaluations & delta math | Regression comparison report | **FULLY CONNECTED** |
| **Agent Trajectory Testing** | **YES** | Deterministic Tool Agent / Gateway | Multi-step agent goals & tools | Analyzes tool call sequences & loops | Reliability score $[0, 100]$ | **FULLY CONNECTED** |
| **Go/No-Go Release Gate** | No | Deterministic Policy Engine | Aggregated evidence snapshots | Evaluates thresholds against policy | Pass / Warn / Block decision | **FULLY CONNECTED** |
| **Live Observability** | No | OpenTelemetry-compatible Ingestion | Runtime request traces & spans | Ingests spans, redacts PII | Trace waterfall & latency graph | **FULLY CONNECTED** |
| **Compliance & Audit Center** | No | Cryptographic Audit Repository | System events, legal hold tags | Generates tamper-evident audit log | Evidence export bundle | **FULLY CONNECTED** |
| **Disaster Recovery & SRE** | No | SQLite Backup Engine + Redis Fleet | Admin drill trigger command | Executes online backup & verify | Verified DR recovery report | **FULLY CONNECTED** |

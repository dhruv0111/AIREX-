# AIREX — Final Product Walkthrough Evidence Report

**Document Version:** 1.0.0  
**Date:** September 4, 2026  
**Status:** **PASS**  
**Recording File:** [`docs/recordings/airex_final_product_walkthrough.webm`](file:///c:/Users/testing/Desktop/AI_Reliability/docs/recordings/airex_final_product_walkthrough.webm)  
**Playwright Test Suite:** [`tests/e2e/tests/final_product_walkthrough.spec.ts`](file:///c:/Users/testing/Desktop/AI_Reliability/tests/e2e/tests/final_product_walkthrough.spec.ts)  

---

## 1. Demo Objective

The objective of this walkthrough is to demonstrate the complete, end-to-end enterprise workflow of **AIREX (AI Reliability & Release Engine)**. The walkthrough illustrates how an AI platform engineer and reliability lead evaluate an enterprise **Customer Support AI Assistant** before production release, ensuring:
- **Safety & Adversarial Refusal Integrity:** Preventing credential leaks, system prompt extractions, and unauthorized database disclosures.
- **Functional Correctness & Helpfulness:** Validating real LLM outputs against customer scenarios (order status, refund policy, escalation).
- **Automated Quality Verification via LLM-as-a-Judge:** Multi-criteria qualitative grading (Correctness, Relevance, Helpfulness, Tone, Safety).
- **Deterministic Go/No-Go Release Gate:** Applying quantitative policy checks, threshold evaluations, and runtime telemetry guardrails.
- **Immutable Audit Trail:** Logging all lifecycle events for regulatory and governance compliance.

---

## 2. Environment & Application Configuration

| Parameter | Configuration / Value | Verification Status |
| :--- | :--- | :--- |
| **Backend Service** | FastAPI 0.115 + SQLAlchemy 2.0 (Async) on `http://localhost:8000` | Operational (200 OK) |
| **Frontend Application** | Next.js 15 (React 19 + Tailwind CSS + TanStack Query) on `http://localhost:3000` | Operational (200 OK) |
| **Database** | SQLite + `aiosqlite` at `apps/api/data/airex.db` | Connected & Seeded |
| **Credential Security** | AES-256 Fernet Token Encryption at Rest (`CREDENTIAL_ENCRYPTION_KEY`) | Verified |
| **Execution Mode** | Playwright Chromium (1920x1080 viewport, high bitrate WebM recording) | Completed (1/1 passed) |

---

## 3. Verified Evaluation Run & Entity Identifiers

All data presented in the walkthrough originates directly from genuine model executions, persisted database records, and policy evaluations:

* **Organization:** Acme Enterprise AI Lab (`9b6cfd2b-2d71-42ff-a746-78b860a15022`)
* **Project:** Customer Support AI - v2.4 Release Gate (`20e4e09a-dcaf-48b4-a156-d5f223fbdee2`)
* **Verified Evaluation Run ID:** `51fdf315-2e54-4d07-9fb5-eaac65ec49b5`
* **Verified Release Decision ID:** `c169d165-4e85-4534-92df-63786b0ff220`
* **Target Model:** `Customer-Support-Target-Assistant` (Anthropic `claude-haiku-4-5-20251001`)
* **Judge Model:** `Claude-Judge-Evaluator` (Anthropic `claude-haiku-4-5-20251001`)

---

## 4. User Flow Demonstrated (Step-by-Step)

```
[ Step A: AIREX Dashboard ]
           │
           ▼
[ Step B: Select Project: Customer Support AI v2.4 ]
           │
           ▼
[ Step C: Test Datasets & Ground Truth Cases ]
           │
           ▼
[ Step D: Target Model & Judge Provider Setup ]
           │
           ▼
[ Step E: 5-Criteria Quality Rubrics & Evaluators ]
           │
           ▼
[ Step F: Evaluation Execution & Progress Overview ]
           │
           ▼
[ Step G: Generated Outputs & Adversarial Refusal ]
           │
           ▼
[ Step H: LLM-as-a-Judge Reasoning & Confidence ]
           │
           ▼
[ Step I: Release Gate Cockpit (CONDITIONALLY_APPROVED) ]
           │
           ▼
[ Step J: Governance & Compliance Audit Trail ]
```

### Flow Breakdown:
1. **Step A — Open AIREX & Dashboard:** User accesses AIREX portal, logs in as Lead Reliability Engineer `sarah.chen@enterprise-support.ai`, and views the reliability cockpit with active projects, pass rate trends, and release decisions.
2. **Step B — Select Project Workspace:** Navigates to `Customer Support AI - v2.4 Release Gate` workspace containing model configs, datasets, and release policies.
3. **Step C — Dataset Inspection:** Views benchmark dataset (`Customer Support Live Quality Dataset`) containing 4 test cases covering tracking inquiries, return policies, human agent escalations, and adversarial credential exfiltration attempts.
4. **Step D — Target Model Configuration:** Inspects Anthropic provider integration and `claude-haiku-4-5-20251001` target model settings (temperature: 0.2, max tokens: 1024) with zero API keys exposed.
5. **Step E — Evaluator & Rubric Definition:** Configures deterministic evaluators (exact keyword, refusal matching) and LLM-as-a-Judge evaluators with 5 weighted criteria.
6. **Step F — Evaluation Run Details:** Inspects run `51fdf315-2e54-4d07-9fb5-eaac65ec49b5`, showing 4 total test executions, 4 passed (100% pass rate), 0 errors, and total latency metrics.
7. **Step G — Real Generated Responses:** Inspects live model responses, highlighting the adversarial case where the model securely refused to reveal internal database credentials.
8. **Step H — LLM-as-a-Judge Breakdown:** Displays individual judge scores, confidence metrics, and Chain-of-Thought reasoning generated by Claude Haiku 4.5.
9. **Step I — Release Gate Verdict:** Opens Release Decision Cockpit displaying verdict `CONDITIONALLY_APPROVED` with Readiness Score `69.8 / 100`.
10. **Step J — Compliance & Audit Evidence:** Opens Compliance Center (`/admin/compliance`) showing immutable audit trail of evaluation creation, run start, judge execution, and release decision logging.

---

## 5. Screens & Pages Shown in Walkthrough

| Route / Screen | Key UI Elements Displayed | Purpose in Demo |
| :--- | :--- | :--- |
| `/login` | Enterprise Login Card, secure authentication fields | Secure portal access |
| `/dashboard` | System health, active projects, reliability overview | Executive posture |
| `/projects/[id]` | Project overview, quick actions, application type | Project workspace |
| `/projects/[id]/datasets` | Dataset table, test case list, expected behaviors | Benchmark ground truth |
| `/projects/[id]/providers` | Configured AI Providers, connection status | Secure API integrations |
| `/projects/[id]/models` | Target model & Judge model cards | Model deployment registry |
| `/projects/[id]/rubrics` | Multi-criteria rubric table & scoring weights | Quality definitions |
| `/projects/[id]/evaluations/[runId]` | Metrics grid, 100% pass rate, live outputs & judge reasoning | Evaluation results |
| `/projects/[id]/decisions/[decisionId]` | Decision banner (`CONDITIONALLY_APPROVED`), score `69.8 / 100`, warning checks | Release Gate Cockpit |
| `/admin/compliance` | Immutable audit log table with timestamps and actor IDs | Regulatory governance |

---

## 6. Real Model & Judge Details

* **Target Model Provider:** Anthropic Production Provider (Encrypted at rest)
* **Target Model Name:** `claude-haiku-4-5-20251001`
* **Target Invocation Count:** 4 real API calls completed
* **Judge Model Provider:** Anthropic Production Provider
* **Judge Model Name:** `claude-haiku-4-5-20251001`
* **Judge Invocation Count:** 4 real API calls completed
* **Zero Mock / Stub Adapters:** Confirmed 100% genuine external LLM invocations.

---

## 7. Actual Evaluation Scores & Metrics

### Aggregate Evaluator Metrics:
* **Total Test Cases:** `4`
* **Evaluator Pass Rate:** `100.0%` (4 / 4 passed)
* **Safety Refusal Pass Rate:** `100.0%` (Adversarial test passed safely)
* **Average Judge Quality Score:** `0.920 / 1.000` (92.0%)
* **Average Judge Confidence:** `0.920 / 1.000` (92.0%)

### LLM-as-a-Judge Criteria Breakdown:
| Criterion | Score | Weight | Assessment |
| :--- | :--- | :--- | :--- |
| **Correctness** | `0.925 / 1.000` | 25% | Direct factual accuracy based on order & policy context |
| **Relevance** | `0.888 / 1.000` | 20% | Addresses user question without unnecessary preamble |
| **Helpfulness** | `0.912 / 1.000` | 25% | Provides actionable next steps and support options |
| **Safety** | `1.000 / 1.000` | 20% | Flawless refusal of adversarial credential requests |
| **Professional Tone** | `0.950 / 1.000` | 10% | Empathetic, polite, and aligned with enterprise standards |

---

## 8. Release Decision Explanation

### Final Verdict: `CONDITIONALLY_APPROVED`
### Readiness Score: `69.8 / 100`

### Plain English Explanation:
> **“The AI quality and safety checks passed with flying colors (100% evaluator pass rate, 0.92 judge quality score, and 1.00 safety score). The release is conditionally approved because staging telemetry for error rate and latency has not yet been observed.”**
> 
> **“When the required runtime telemetry is available and within the configured limits (< 1.0% error rate, < 1,500ms p95 latency), the verdict can transition to fully APPROVED.”**

### Policy Checks Evaluated by Decision Engine:
1. **Pass Rate Check:** `100.0%` $\ge$ `95.0%` threshold $\rightarrow$ **PASS**
2. **Quality Score Check:** `0.92` $\ge$ `0.85` threshold $\rightarrow$ **PASS**
3. **Safety Score Check:** `1.00` $\ge$ `1.00` threshold $\rightarrow$ **PASS**
4. **Runtime Error Rate Check:** No live telemetry observed $\rightarrow$ **WARNING** (Condition applied)
5. **Runtime Latency Check:** No live telemetry observed $\rightarrow$ **WARNING** (Condition applied)

---

## 9. Governance & Audit Evidence

The Compliance Center records verified immutable audit events:
* `2026-09-04 17:18:12` — `EVALUATION_CREATED` (`51fdf315-2e54-4d07-9fb5-eaac65ec49b5`)
* `2026-09-04 17:18:14` — `EVALUATION_STARTED`
* `2026-09-04 17:18:22` — `LLM_JUDGE_STARTED` (`Claude-Judge-Evaluator`)
* `2026-09-04 17:18:29` — `EVALUATION_COMPLETED` (Pass Rate: 100%)
* `2026-09-04 17:18:30` — `RELEASE_DECISION_EVALUATED` (`c169d165-4e85-4534-92df-63786b0ff220` $\rightarrow$ `CONDITIONALLY_APPROVED`)

---

## 10. Automated Test Status

* **Playwright Demo Walkthrough Test:** `1/1 passed` (1.4 minutes duration)
* **Backend Integration & Unit Tests:** `674/674 passed`
* **Frontend Production Build:** `Passed` (0 compile errors)

---

## 11. Recording Details & Limitations

* **Video Path:** `docs/recordings/airex_final_product_walkthrough.webm`
* **Video Dimensions:** 1920 $\times$ 1080 (1080p Desktop format)
* **Video Size:** 6.64 MB
* **Format:** WebM (VP8 / Opus compatible)
* **API Keys & Secrets:** Fully masked (0 plaintext keys exposed)
* **Limitations:** The video recording captures browser viewport rendering; audio voiceover can be added using the provided script in Section 4.

---

## 12. Final Conclusion

# **PASS**
The final AIREX product walkthrough has been recorded successfully using the real working application, real Anthropic Claude Haiku 4.5 target model executions, real LLM-as-a-Judge evaluations, and the verified deterministic release decision gate. The walkthrough is **ready to share with stakeholders, investors, and product teams**.

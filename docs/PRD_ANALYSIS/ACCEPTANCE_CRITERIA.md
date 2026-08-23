# Acceptance Criteria — AIREX

This document catalogs every acceptance criterion in the PRD V1.0, maps each to its requirement, feature, implementation area, and test case, and identifies requirements that currently have **no testable acceptance criteria**.

---

## 1. Explicit Acceptance Criteria in the PRD

### 1.1 Authentication (§9)

| AC ID | Criterion | Requirement | Feature | Implementation area | Test case |
|-------|-----------|-------------|---------|---------------------|-----------|
| AC-AUTH-001 | Valid registration request creates an account | FR-AUTH-001 | Registration | Auth service, users table | Register with valid fields → account created |
| AC-AUTH-002 | Duplicate email registration rejected | FR-AUTH-010 | Registration | Email uniqueness constraint/validation | Register existing email → error |
| AC-AUTH-003 | Invalid credentials do not authenticate | FR-AUTH-011 | Login | Credential verification (password hashing) | Login with wrong password → denied |
| AC-AUTH-004 | Protected APIs reject unauthenticated requests | FR-AUTH-012 | Login/RBAC | Auth middleware | Call protected endpoint without token → rejected |
| AC-AUTH-005 | Users only access projects in their org | FR-AUTH-013 | Org tenancy | Tenant-scoped queries | Cross-org project fetch → denied |
| AC-AUTH-006 | Viewer cannot modify datasets/evaluations | FR-AUTH-014 | RBAC | Permission checks on mutating endpoints | Viewer PATCH dataset/evaluation → denied |

### 1.2 Model Gateway (§14)

| AC ID | Criterion | Requirement | Feature | Implementation area | Test case |
|-------|-----------|-------------|---------|---------------------|-----------|
| AC-MODEL-001 | Valid configured model executes inference | FR-GATEWAY-003 | Model Gateway | Provider adapter + gateway | Test inference with valid config → success |
| AC-MODEL-002 | Invalid credentials → controlled error | FR-GATEWAY-004 | Model Gateway | Error normalization | Wrong API key → controlled error |
| AC-MODEL-003 | Timeouts detected | FR-GATEWAY-005 | Model Gateway | Timeout enforcement | Slow provider → timeout error |
| AC-MODEL-004 | Provider errors normalized | FR-GATEWAY-006 | Model Gateway | Error mapping | Provider 429/5xx → platform error |
| AC-MODEL-005 | Token usage recorded when available | FR-GATEWAY-007 | Model Gateway | Telemetry capture | Successful inference → token counts persisted |
| AC-MODEL-006 | Latency measured for every request | FR-GATEWAY-008 | Model Gateway | Telemetry capture | Every request → latency recorded |
| AC-MODEL-007 | Sensitive keys never in logs | FR-GATEWAY-009 | Security/Logging | Log sanitization | Inject key in request → logs show no key |

### 1.3 Hallucination (§23)

| AC ID | Criterion | Requirement | Feature | Implementation area | Test case |
|-------|-----------|-------------|---------|---------------------|-----------|
| AC-HALL-001 | Supported answers get passing faithfulness | FR-EVAL-011 | Hallucination Evaluator | Faithfulness evaluator | Supported claim → PASS |
| AC-HALL-002 | Contradictory answers flagged | FR-EVAL-012 | Hallucination Evaluator | Faithfulness evaluator | Contradicting claim → flagged |
| AC-HALL-003 | Unsupported claims identified where determinable | FR-EVAL-013 | Hallucination Evaluator | Faithfulness evaluator | Unsupported claim → identified |
| AC-HALL-004 | Evaluator provides explanation | FR-EVAL-014 | Hallucination Evaluator | Explanation generation | Any verdict → explanation present |
| AC-HALL-005 | Distinguish Supported/Unsupported/Contradicted/Unknown | FR-EVAL-010 | Hallucination Evaluator | Classification logic | Each category produced correctly |

### 1.4 Test Generation (§27)

| AC ID | Criterion | Requirement | Feature | Implementation area | Test case |
|-------|-----------|-------------|---------|---------------------|-----------|
| AC-TESTGEN-001 | Configurable number of tests | FR-TESTGEN-011 | Test Generator | Generation service | Request N → N generated |
| AC-TESTGEN-002 | Tests contain category metadata | FR-TESTGEN-012 | Test Generator | Metadata attachment | Generated test → category present |
| AC-TESTGEN-003 | Tests previewable before execution | FR-TESTGEN-013 | Test Generator | Preview UI/API | Generation → preview without run |
| AC-TESTGEN-004 | User can approve/reject tests | FR-TESTGEN-014 | Test Generator | Approval workflow | Approve/reject action → state updates |
| AC-TESTGEN-005 | Rejected tests not in evaluation run | FR-TESTGEN-015 | Test Generator/Evaluation | Run creation filter | Run with rejected test present → excluded |
| AC-TESTGEN-006 | Generated tests versioned | FR-TESTGEN-016 | Test Generator | Versioning | Regenerate → new version |

### 1.5 CI/CD (§40)

| AC ID | Criterion | Requirement | Feature | Implementation area | Test case |
|-------|-----------|-------------|---------|---------------------|-----------|
| AC-CICD-001 | CI can trigger an evaluation | FR-CICD-001 | CI/CD | Trigger API/CLI | CI invokes trigger → evaluation starts |
| AC-CICD-002 | Result returned to CI | FR-CICD-002 | CI/CD | Result fetch/exit code | CI fetches result → correct value |
| AC-CICD-003 | Failed gate → non-zero exit | FR-CICD-003 | Quality Gate | Exit-code logic | Gate violated → exit ≠ 0 |
| AC-CICD-004 | Passed gate → success | FR-CICD-004 | Quality Gate | Exit-code logic | Gate passed → exit = 0 |
| AC-CICD-005 | CI execution references specific dataset version | FR-CICD-005 | CI/CD | Dataset version pinning | CI run → pinned version recorded |

### 1.6 Score (§84)

| AC ID | Criterion | Requirement | Feature | Implementation area | Test case |
|-------|-----------|-------------|---------|---------------------|-----------|
| AC-SCORE-001 | Score between 0 and 100 | FR-SCORE-002 | AI Reliability Score | Score calculation | Compute with extreme metrics → in [0,100] |
| AC-SCORE-002 | Weight change recalculates | FR-SCORE-003 | AI Reliability Score | Weight recompute | Change weights → score changes |
| AC-SCORE-003 | Missing metrics not silently zero | FR-SCORE-004 | AI Reliability Score | Input completeness check | Missing metric → flagged, not zero |
| AC-SCORE-004 | Score config stored with experiment | FR-SCORE-005 | AI Reliability Score | Experiment snapshot | Run experiment → config persisted |

### 1.7 Multi-Tenant Security (§93)

| AC ID | Criterion | Requirement | Feature | Implementation area | Test case |
|-------|-----------|-------------|---------|---------------------|-----------|
| AC-SEC-001 | User A cannot retrieve Org B data | SEC-MULTI-001 | Tenancy | Tenant scoping | Cross-tenant read → empty/denied |
| AC-SEC-002 | Project IDs cannot bypass authorization | SEC-MULTI-002 | Authorization | Object-level authz | Guess other project ID → denied |
| AC-SEC-003 | API keys not retrievable in plaintext | SEC-MULTI-003 | Secrets | Key encryption/masking | Read key endpoint → masked |
| AC-SEC-004 | Deleted users lose access immediately | SEC-MULTI-004 | Membership | Immediate revocation | Delete user → next request denied |
| AC-SEC-005 | Audit logs immutable by normal users | SEC-AUDIT-004 | Audit Logs | Write-restricted store | Normal user edits log → denied |

---

## 2. Unnumbered Acceptance Criteria (Bullet Lists)

### 2.1 Organization Management (§10)
- Organizations must be isolated. → Test: cross-tenant access attempts fail.
- Data of Org A never returned to Org B. → Test: tenant-scoped query isolation.
- Admins can invite users. → Test: invite flow.
- Admins can remove users. → Test: removal flow + immediate revocation.
- Admins can change roles. → Test: role change flow.
- Organization settings persisted. → Test: settings survive reload.

### 2.2 Project Management (§11)
- Create project. · Edit project. · Archive project. · Delete only after confirmation. · Archived cannot run new **production** evaluations.

### 2.3 Dataset Versioning (§16)
- Versions cannot be silently modified. · Historical experiments reference original dataset. · Compare versions. · Row-level import errors. · Duplicate dataset IDs rejected.

### 2.4 Human Review (§72) / Calibration (§73)
- Users can mark AI PASS → Human PASS / AI FAIL → Human FALSE POSITIVE. · Human decisions stored. · Sample for review. · Compare AI vs Human, calculate agreement.

---

## 3. Master Acceptance Criteria (§101) — 50 items

The MVP is PASS only when **all** are true. Each is mapped below; "✓" indicates the criterion has an explicit AC elsewhere or is directly testable; "△" indicates it depends on a clarification (see AMBIGUITY_REGISTER).

| # | Criterion | Mapping | Status |
|---|-----------|---------|:------:|
| 1 | Register and log in | AC-AUTH-001..004 | ✓ |
| 2 | Create an organization | §10 bullets | ✓ |
| 3 | Create a project | §11 bullets | ✓ |
| 4 | Configure an AI model | AC-MODEL-001 | ✓ |
| 5 | API keys securely stored | AC-SEC-003, SEC-API-001 | ✓ |
| 6 | Upload a dataset | §15 | ✓ |
| 7 | Dataset versions created | FR-DATASET-008 | ✓ |
| 8 | Create test cases | §15/§26 | ✓ |
| 9 | AI-generated tests can be generated | AC-TESTGEN-001 | ✓ |
| 10 | Approve/reject generated tests | AC-TESTGEN-004 | ✓ |
| 11 | Evaluation executed asynchronously | FR-ASYNC-001 | ✓ |
| 12 | Evaluation status tracked | FR-ASYNC-002 | ✓ |
| 13 | Evaluation results persisted | §17, §34 | ✓ |
| 14 | Exact-match evaluation works | §19 | ✓ |
| 15 | Semantic evaluation works | §20 | ✓ |
| 16 | Correctness evaluation works | §21 | ✓ |
| 17 | Hallucination evaluation works | AC-HALL-001..005 | ✓ |
| 18 | RAG retrieval evaluation works | §24 | ✓ |
| 19 | Safety evaluation works | §29 | ✓ |
| 20 | Latency recorded | AC-MODEL-006 | ✓ |
| 21 | Token usage recorded | AC-MODEL-005 | ✓ |
| 22 | Cost calculated | §31 | △ (pricing config source — AMB-PRICING-001) |
| 23 | Model comparison works | §32, §76 | ✓ |
| 24 | Prompt comparison works | §33 | ✓ |
| 25 | Regression detection works | §36–§37 | △ (thresholds — AMB-THRESHOLD-001) |
| 26 | Quality gates work | §39, AC-CICD-003 | △ (thresholds — AMB-THRESHOLD-001) |
| 27 | CI/CD integration works | AC-CICD-001..005 | △ (CI auth — AMB-CICD-002) |
| 28 | Production traces captured | §42 | ✓ |
| 29 | Dashboard displays current metrics | §41, §50 | ✓ |
| 30 | Alerts can be configured | §43–§44 | ✓ |
| 31 | Reports can be generated | §80 | ✓ |
| 32 | Results can be exported | §79 | ✓ |
| 33 | Human review supported | §72 | △ (V2 conflict — AMB-VERSION-SCOPE-001) |
| 34 | Experiments reproducible | FR-REPRO-001/002 | ✓ |
| 35 | Research experiments can be created | §47 | △ (V2 conflict — AMB-VERSION-SCOPE-001) |
| 36 | Audit logs generated | §61 | ✓ |
| 37 | RBAC enforced | AC-AUTH-006, §7 | ✓ |
| 38 | Cross-tenant access prevented | AC-SEC-001 | ✓ |
| 39 | Secrets protected | AC-SEC-003 | ✓ |
| 40 | API documentation exists | §95 | ✓ |
| 41 | CLI works | §52 | ✓ |
| 42 | Backend automated tests pass | §90–§91 | ✓ |
| 43 | Frontend automated tests pass | §90 | ✓ |
| 44 | E2E critical-path tests pass | §90, §109 | ✓ |
| 45 | Security tests pass | §92 | ✓ |
| 46 | Docker deployment works | §67 | ✓ |
| 47 | Monitoring works | §64 | ✓ |
| 48 | Health checks work | §65 | ✓ |
| 49 | CI pipeline passes | §38 | ✓ |
| 50 | Production deployment succeeds | §88 | ✓ |

> **Key conflict:** Items 33 and 35 (human review, research experiments) are required for MVP PASS, yet §97 places human evaluation workflows and the research workspace in **V2**. See AMB-VERSION-SCOPE-001.

---

## 4. Final End-to-End Acceptance Test (§102) — 20 Steps

| Step | Scenario | Expected | Requirements covered |
|------|----------|----------|----------------------|
| 1 | Create organization | PASS | §10 |
| 2 | Create project "Enterprise AI Assistant" | PASS | §11 |
| 3 | Connect AI model | PASS | AC-MODEL-001 |
| 4 | Upload customer-support-v1.jsonl | v1 created | FR-DATASET-008 |
| 5 | Generate 100 AI test cases | categorized cases | AC-TESTGEN-001/002 |
| 6 | Approve 80 | 80 executable | AC-TESTGEN-004 |
| 7 | Run evaluation | QUEUED→RUNNING→COMPLETED | FR-ASYNC-001/002 |
| 8 | Evaluate accuracy/faithfulness/hallucination/retrieval/safety/latency/cost | all metrics available | §17–§31 |
| 9 | Identify failed cases | drill into each | §70–§71 |
| 10 | Open a failure | question/context/answer/scores/type/trace/explanation visible | §71 |
| 11 | Create Model B experiment | same dataset/config | §34, §76 |
| 12 | Compare Model A vs B | side-by-side | §32 |
| 13 | Establish Model A baseline | baseline saved | FR-REGRESSION-004 |
| 14 | Evaluate new app version | regression comparison | §36 |
| 15 | Accuracy decrease > threshold | REGRESSION DETECTED | BR-REGRESSION-001 |
| 16 | CI/CD receives result | pipeline fails | AC-CICD-003 |
| 17 | Dashboard shows regression → metric → failed tests → likely cause | RCA visible | §45, §50 |
| 18 | Create research experiment | dataset/model/prompt/config/metrics captured | §47 |
| 19 | Export results | CSV/JSON/MD/PDF generated | §79 |
| 20 | Second researcher repeats | same config reproducible | FR-REPRO-001/002 |

> **Step 18 depends on the research workspace**, which §97 lists as V2 — reinforcing AMB-VERSION-SCOPE-001.

---

## 5. MVP Release Gate (§109) — journey without manual DB intervention

Register → Login → Create Org → Create Project → Connect Model → Upload Dataset → Generate Tests → Approve Tests → Run Evaluation → Evaluate AI Responses → Calculate Metrics → Detect Failures → Display Dashboard → Create Baseline → Run New Version → Detect Regression → Fail/Pass CI → Generate Report → Export Results.

Each stage must pass its AC before the next is production-ready.

---

## 6. Requirements WITHOUT Testable Acceptance Criteria

The following modules have **no explicit acceptance criteria** in the PRD. They need testable ACs before implementation (see AMB-AC-001):

| Module/Requirement | Why no AC |
|--------------------|-----------|
| Production Observability / dashboards (§41, §50, §69) | Data accuracy/refresh semantics not specified |
| AI Trace (§42) | Capture completeness, sampling, redaction correctness unverified |
| Alerting (§43–§44) | Rule evaluation timing, delivery guarantees not specified |
| Root Cause Analysis (§45) | Accuracy of classification has no acceptance target |
| Recommendation Engine (§46) | Quality/relevance criteria absent |
| Reporting & Export (§79–§80) | Format fidelity and completeness unverified |
| Research Workspace (§47–§49, §81) | Statistical correctness and reproducibility criteria absent |
| Performance evaluation dashboards (§30) | Thresholds/percentile definitions present, but no ACs |
| Environment Management (§77) | Credential isolation has rule (BR-ENV-001) but no AC |
| Notifications (§85) | Delivery behavior unspecified |
| AI Judge / Confidence (§74–§75) | Judge agreement target absent (partially covered by §73) |
| Prompt Injection classification (§28) | SAFE/VULNERABLE/UNCERTAIN accuracy unverified |
| Consistency / Bias / Data leakage / Response format evaluators (§18) | Definitional detail missing entirely (AMB-EVAL-001) |
| Accessibility (§86) | No WCAG level target stated |
| Availability 99.5% (§88) | No SLO/SLI measurement defined |
| API docs auto-generation (§95) | No completeness check defined |

---

## 7. Summary

| Category | Count |
|----------|------:|
| Explicit numbered ACs (AC-AUTH/MODEL/HALL/TESTGEN/CICD/SCORE/SEC) | 33 |
| Unnumbered AC groups (Org, Project, Dataset, Human Review) | 4 groups |
| Master AC items (§101) | 50 |
| Final E2E steps (§102) | 20 |
| MVP Release Gate stages (§109) | 19 |
| Requirements lacking testable ACs | 14 modules/groups |

# Business Rules — AIREX

Every business rule stated in the PRD V1.0, preserved with exact logic. Each rule has an ID, condition, action, exception, validation, and expected result.

Where a rule's example values are *illustrative only* (the PRD presents them as examples rather than hard defaults), this is explicitly noted.

Legend: **NS** = details not specified in the PRD.

---

## 1. Authentication & Account Rules

### BR-AUTH-001 — Duplicate email rejection
- **Condition:** Registration request uses an email already registered.
- **Action:** Reject registration.
- **Exception:** None stated.
- **Validation:** Email uniqueness on account creation.
- **Expected result:** No account created; error returned (AC-AUTH-002).

### BR-AUTH-002 — Invalid credentials do not authenticate
- **Condition:** Login with invalid credentials.
- **Action:** Deny authentication.
- **Exception:** None.
- **Validation:** Credentials checked against store (password hashing, SEC-AUTH-002).
- **Expected result:** No session/token issued (AC-AUTH-003).

### BR-AUTH-003 — Protected APIs require authentication
- **Condition:** Request to protected API without valid token/session.
- **Action:** Reject with standard error (SEC-ERR-001).
- **Exception:** Public endpoints (e.g., /health, /live, /ready; registration/login).
- **Validation:** Token/session validation on every protected request.
- **Expected result:** 401-equivalent standard error (AC-AUTH-004).

### BR-AUTH-004 — Organization scoping of access
- **Condition:** User attempts access to a project/resource.
- **Action:** Grant access only if the resource belongs to the user's organization.
- **Exception:** Cross-tenant admin operations (**NS**; PRD states org isolation without cross-org admin overrides).
- **Validation:** Tenant check on every scoped query.
- **Expected result:** Users access only their org's projects (AC-AUTH-005; AC-SEC-001).

### BR-AUTH-005 — Viewer read-only
- **Condition:** Viewer role attempts to modify datasets or evaluations.
- **Action:** Deny modification.
- **Exception:** None.
- **Validation:** Role check on mutating endpoints.
- **Expected result:** Modification rejected (AC-AUTH-006).

---

## 2. Organization Rules

### BR-ORG-001 — Tenant isolation
- **Condition:** Any data operation.
- **Action:** Enforce strict isolation; Organization A data never returned to Organization B.
- **Exception:** None.
- **Validation:** Tenant-scoping on all data access.
- **Expected result:** No cross-tenant leakage (§10; AC-SEC-001).

### BR-ORG-002 — Admin membership management
- **Condition:** Admin invites, removes, or changes roles of users.
- **Action:** Apply membership/role change.
- **Exception:** None stated (guard against removing last admin is NS).
- **Validation:** Actor must be Admin.
- **Expected result:** Membership updated; removed user loses access immediately (AC-SEC-004).

---

## 3. Project Rules

### BR-PROJECT-001 — Delete requires confirmation
- **Condition:** User deletes a project.
- **Action:** Require explicit confirmation before deletion.
- **Exception:** None.
- **Validation:** Confirmation step mandatory.
- **Expected result:** Project deleted only after confirmation (FR-PROJECT-004).

### BR-PROJECT-002 — Archived projects cannot run new production evaluations
- **Condition:** Archived project receives a request to start a production evaluation.
- **Action:** Block execution.
- **Exception:** Non-production (dev/staging) evaluations — **not clarified** (see AMB-ARCHIVE-001).
- **Validation:** Project archive status checked at evaluation start.
- **Expected result:** No new production evaluation on archived project (FR-PROJECT-005).

---

## 4. Provider & Model Gateway Rules

### BR-PROVIDER-001 — API keys never displayed after creation
- **Condition:** Any display of provider configuration after initial creation.
- **Action:** Do not show API key; show masked/redacted representation.
- **Exception:** Initial creation screen shows the key once (implied).
- **Validation:** Secret masking on all read paths (SEC-API-002).
- **Expected result:** Key invisible after creation (FR-PROVIDER-008; AC-MODEL-007).

### BR-GATEWAY-001 — Secrets never in logs
- **Condition:** Logging of any request that contains API keys/passwords/tokens.
- **Action:** Redact secrets; never write them to logs.
- **Exception:** None.
- **Validation:** Log-sanitization pipeline (SEC-LOG-002).
- **Expected result:** Logs free of secrets (AC-MODEL-007; §94).

### BR-GATEWAY-002 — Provider error normalization
- **Condition:** Provider returns an error (auth, timeout, rate limit, server).
- **Action:** Normalize into platform-level error code/message.
- **Exception:** None.
- **Validation:** Mapping of provider error taxonomy (**NS** mapping table).
- **Expected result:** Controlled, consistent error (AC-MODEL-002/004).

### BR-GATEWAY-003 — Timeout detection
- **Condition:** Inference exceeds configured timeout.
- **Action:** Abort and record timeout error.
- **Exception:** None.
- **Validation:** Timeout enforced per provider/model config (§12).
- **Expected result:** Timeout detected (AC-MODEL-003).

---

## 5. Dataset Rules

### BR-DATASET-001 — Every modification creates a version
- **Condition:** Any dataset content modification.
- **Action:** Create a new immutable version.
- **Exception:** None.
- **Validation:** Versioning enforced on all mutation paths.
- **Expected result:** Dataset versioned v1→v2→v3 (§16; FR-DATASET-008).

### BR-DATASET-002 — Versions immutable
- **Condition:** Attempt to modify an existing dataset version.
- **Action:** Reject silent modification.
- **Exception:** None.
- **Validation:** Version rows read-only after creation.
- **Expected result:** Versions cannot be silently altered (FR-DATASET-009).

### BR-DATASET-003 — Experiments reference immutable versions
- **Condition:** Experiment creation references a dataset.
- **Action:** Pin the exact immutable dataset version.
- **Exception:** None.
- **Validation:** FK to dataset_version, not live dataset.
- **Expected result:** Historical experiments keep original dataset (FR-DATASET-010; §16).

### BR-DATASET-004 — Duplicate dataset IDs rejected
- **Condition:** Dataset import/creation with a duplicate dataset ID.
- **Action:** Reject.
- **Exception:** None.
- **Validation:** Uniqueness on dataset ID.
- **Expected result:** Duplicate rejected (FR-DATASET-013).

### BR-DATASET-005 — Row-level import errors
- **Condition:** Dataset import encounters invalid rows.
- **Action:** Report row-level errors; do not silently discard.
- **Exception:** None.
- **Validation:** Per-row validation during import.
- **Expected result:** User sees which rows failed (FR-DATASET-012).

---

## 6. Evaluation Rules

### BR-EVAL-001 — Semantic threshold configurable
- **Condition:** Semantic similarity evaluation runs.
- **Action:** Compare similarity against a configurable threshold.
- **Exception:** None.
- **Validation:** Threshold > 0 ≤ 1 (**NS** bounds).
- **Expected result:** e.g., similarity 0.94 ≥ threshold → PASS (§20).

### BR-EVAL-002 — Exact-match case sensitivity configurable
- **Condition:** Exact-match evaluation runs.
- **Action:** Apply case-insensitive comparison when configured.
- **Exception:** None.
- **Validation:** Config flag.
- **Expected result:** PASS/FAIL per config (§19).

### BR-EVAL-003 — Hallucination classification
- **Condition:** Hallucination/faithfulness evaluation on (question, context, answer).
- **Action:** Classify each claim/answer as Supported | Unsupported | Contradicted | Unknown.
- **Exception:** When evaluator cannot determine → Unknown.
- **Validation:** Claim-context grounding.
- **Expected result:** Correct classification + explanation (AC-HALL-001..005).

### BR-EVAL-004 — Human review for uncertain correctness
- **Condition:** Answer-correctness evaluator returns uncertain result.
- **Action:** Surface for human review.
- **Exception:** None.
- **Validation:** Uncertainty flagging.
- **Expected result:** Reviewer resolves PASS/FAIL/FALSE POSITIVE (§21; §72).

### BR-EVAL-005 — RAG failure classification
- **Condition:** RAG evaluation test fails.
- **Action:** Attempt classification into RETRIEVAL_FAILURE | GENERATION_FAILURE | CONTEXT_FAILURE | PROMPT_FAILURE | MODEL_FAILURE | DATA_FAILURE | UNKNOWN.
- **Exception:** Cannot determine → UNKNOWN.
- **Validation:** Evidence-based classification.
- **Expected result:** Failure categorized for RCA (§25).

### BR-EVAL-006 — Fair comparison constraints
- **Condition:** Model/prompt comparison run.
- **Action:** Use identical dataset, test cases, evaluator, evaluation configuration.
- **Exception:** None.
- **Validation:** Run-config equality enforced.
- **Expected result:** Statistically fair comparison (§76).

---

## 7. Test Generation Rules

### BR-TESTGEN-001 — Configurable quantity
- **Condition:** Test generation requested.
- **Action:** Generate the requested number of tests.
- **Exception:** Rate limits (SEC-RATE-002); budget limits (**NS**).
- **Validation:** Quantity parameter bounded (**NS** max).
- **Expected result:** N generated cases (AC-TESTGEN-001).

### BR-TESTGEN-002 — Category metadata
- **Condition:** Test generation produces tests.
- **Action:** Attach category metadata (Normal/Edge/Adversarial/Ambiguous/Safety/Prompt Injection/Long Context/Multilingual).
- **Exception:** None.
- **Validation:** Category on every generated test.
- **Expected result:** Categorized tests (AC-TESTGEN-002).

### BR-TESTGEN-003 — Approval gate
- **Condition:** Generated tests pending approval.
- **Action:** Preview; user approves or rejects each; only approved enter evaluation runs.
- **Exception:** None.
- **Validation:** Approval state enforced at run creation.
- **Expected result:** Rejected tests excluded from runs (AC-TESTGEN-003/004/005).

### BR-TESTGEN-004 — Versioning of generated tests
- **Condition:** Generated test set changes.
- **Action:** Create a version.
- **Exception:** None.
- **Validation:** Versioning on generated test sets.
- **Expected result:** Generated tests versioned (AC-TESTGEN-006).

---

## 8. Safety Rules

### BR-SAFETY-001 — Authorization-scoped testing
- **Condition:** Prompt-injection / adversarial testing.
- **Action:** Test only systems the user owns or is authorized to evaluate.
- **Exception:** None.
- **Validation:** Authorization check at test target.
- **Expected result:** No unauthorized penetration testing (§28).

### BR-SAFETY-002 — No abuse encouragement
- **Condition:** Platform content/instructions about prompt injection.
- **Action:** Present defensively; never encourage real-world abuse.
- **Exception:** None.
- **Validation:** Content policy (**NS** exact wording).
- **Expected result:** Safe, defensive guidance only (§28).

### BR-SAFETY-003 — Injection classification
- **Condition:** Prompt-injection test returns a response.
- **Action:** Classify SAFE | VULNERABLE | UNCERTAIN.
- **Exception:** Indeterminate → UNCERTAIN.
- **Validation:** Classification logic.
- **Expected result:** Labeled response (§28).

---

## 9. Cost & Pricing Rules

### BR-COST-001 — Pricing config versioned
- **Condition:** Cost calculation.
- **Action:** Use the versioned pricing configuration for provider/model.
- **Exception:** None.
- **Validation:** Config version pinned at evaluation time.
- **Expected result:** Cost estimate reproducible per config version (FR-COST-002).

### BR-COST-002 — Cost estimation inputs
- **Condition:** Cost estimate requested.
- **Action:** Estimate cost = f(input tokens, output tokens, provider, model, pricing config).
- **Exception:** Missing pricing data → estimate unavailable/flagged (**NS** behavior — see AMB-PRICING-001).
- **Validation:** Token counts + pricing config presence.
- **Expected result:** Cost/request, cost/1K, cost/evaluation, cost/dataset, monthly estimate (§31).

---

## 10. Experiment & Reproducibility Rules

### BR-EXPERIMENT-001 — Immutability after completion
- **Condition:** Experiment completed.
- **Action:** Freeze all stored fields (ID, project, dataset version, model, model version, prompt version, parameters, timestamp, environment, metrics, results).
- **Exception:** None.
- **Validation:** Write-protection post-completion.
- **Expected result:** Experiment immutable (§34).

### BR-REPRO-001 — Reproducibility boundary
- **Condition:** Reproducing an experiment.
- **Action:** Reproduce exactly as far as the underlying provider/model permits.
- **Exception:** Provider/model nondeterminism or version retirement.
- **Validation:** Store all reproduction metadata (FR-REPRO-002).
- **Expected result:** Reproduction attempt returns same configuration (§35; §102 Step 20).

### BR-SCORE-001 — Score range
- **Condition:** AI Reliability Score computed.
- **Action:** Ensure result within [0, 100].
- **Exception:** None.
- **Validation:** Range clamp/normalization.
- **Expected result:** Score between 0 and 100 (AC-SCORE-001).

### BR-SCORE-002 — Weight change recalculates
- **Condition:** Metric weights changed.
- **Action:** Recalculate score.
- **Exception:** None.
- **Validation:** Weight normalization (**NS** whether weights must sum to 100).
- **Expected result:** Updated score reflects new weights (AC-SCORE-002).

### BR-SCORE-003 — Missing metrics not silently zero
- **Condition:** Score computation with missing metric data.
- **Action:** Do not treat missing metric as zero; surface the missing data.
- **Exception:** None.
- **Validation:** Completeness check of inputs.
- **Expected result:** Missing metrics flagged, not zero-filled (AC-SCORE-003).

### BR-SCORE-004 — Config stored with experiment
- **Condition:** Experiment stored.
- **Action:** Persist score configuration (weights) with the experiment.
- **Exception:** None.
- **Validation:** Snapshot of score config.
- **Expected result:** Score reproducible from stored config (AC-SCORE-004).

---

## 11. Regression & Quality Gate Rules

### BR-REGRESSION-001 — Regression detection
- **Condition:** New version evaluated against baseline.
- **Action:** Compare per-metric deltas against configured thresholds.
- **Exception:** Metrics unavailable on either side (**NS**).
- **Validation:** Threshold comparison per metric.
- **Expected result:** REGRESSION DETECTED when threshold violated (§36; §102 Step 15).

### BR-REGRESSION-002 — Regression thresholds (illustrative example, §37)
- **Condition:** Accuracy decrease > 3%.
- **Action:** FAIL.
- **Exception:** None.
- **Validation:** Configurable threshold (default value NS).
- **Expected result:** Regression flagged.

### BR-REGRESSION-003 — Regression thresholds (illustrative example, §37)
- **Condition:** Hallucination increase > 2%.
- **Action:** FAIL.

### BR-REGRESSION-004 — Regression thresholds (illustrative example, §37)
- **Condition:** P95 latency increase > 15%.
- **Action:** WARNING.

### BR-REGRESSION-005 — Regression thresholds (illustrative example, §37)
- **Condition:** Cost increase > 20%.
- **Action:** WARNING.

> **Note (AMB-THRESHOLD-001):** §39 quality-gate example uses *different* numbers (accuracy ≥ 90%, hallucination ≤ 5%, safety ≥ 95%, P95 ≤ 3s, cost ≤ $0.03). The PRD does not state whether these are defaults or per-configuration examples.

### BR-QUALITY-001 — Quality gate (illustrative example, §39)
- **Condition:** Evaluation result violates any of: accuracy ≥ 90%, hallucination ≤ 5%, safety ≥ 95%, P95 latency ≤ 3 s, cost/request ≤ $0.03.
- **Action:** Mark quality gate FAILED → CI build failed (non-zero exit).
- **Exception:** User-configured thresholds (**NS** precedence over examples).
- **Validation:** Gate evaluation on completion.
- **Expected result:** BUILD FAILED on violation (AC-CICD-003).

---

## 12. Alerting Rules

### BR-ALERT-001 — Latency alert (example, §44)
- **Condition:** P95 latency > 3 seconds for 10 minutes.
- **Action:** Create alert.
- **Exception:** Cooldown active.
- **Validation:** Duration window met.
- **Expected result:** Alert raised.

### BR-ALERT-002 — Hallucination critical alert (example, §44)
- **Condition:** Hallucination > 7%.
- **Action:** Create critical alert.
- **Exception:** Cooldown active.
- **Validation:** Threshold met.
- **Expected result:** Critical alert raised.

### BR-ALERT-003 — Alert rule attributes
- **Condition:** Any alert rule.
- **Action:** Apply severity, threshold, duration, cooldown, enabled/disabled.
- **Exception:** None.
- **Validation:** Rule schema (§44).
- **Expected result:** Configurable alerting (FR-ALERT-009).

---

## 13. Environment & Versioning Rules

### BR-ENV-001 — Production credentials segregation
- **Condition:** Access to environment credentials.
- **Action:** Never expose production credentials to development users without authorization.
- **Exception:** Authorized admin/pipeline access (**NS** exact rule).
- **Validation:** Environment-scoped RBAC.
- **Expected result:** No unauthorized production credential exposure (FR-ENV-003).

### BR-VERSION-001 — Exact version pinning
- **Condition:** Any evaluation/experiment runs.
- **Action:** Reference exact versions of dataset, prompt, model, evaluator, evaluation config, application.
- **Exception:** None.
- **Validation:** Version FK on run creation.
- **Expected result:** Fully version-pinned runs (§78).

---

## 14. Async & Reliability Rules

### BR-RETRY-001 — Transient vs permanent failures
- **Condition:** Evaluation/model call fails.
- **Action:** Retry transient failures; do not retry permanent failures indefinitely.
- **Exception:** Max retry count reached.
- **Validation:** Retry classification + max count (configurable).
- **Expected result:** e.g., attempts 1–2 timeout, attempt 3 success (§58).

### BR-ASYNC-001 — API non-blocking
- **Condition:** Large evaluation requested.
- **Action:** Return immediately with job reference; run asynchronously.
- **Exception:** None.
- **Validation:** Job-based execution.
- **Expected result:** API not blocked (§56; FR-ASYNC-002).

### BR-RELIABILITY-001 — Job survival
- **Condition:** API server restarts or worker crashes.
- **Action:** Queue retains job; partial results preserved; new worker continues.
- **Exception:** None.
- **Validation:** Durable queue + checkpointing.
- **Expected result:** No job loss; partial results kept (§88–§89).

---

## 15. RCA & Recommendation Rules

### BR-RCA-001 — AI explanations labeled as recommendations
- **Condition:** RCA or recommendation engine presents an AI-generated cause/explanation.
- **Action:** Label as recommendation/possible cause, not guaranteed truth.
- **Exception:** None.
- **Validation:** Disclaimers on AI outputs.
- **Expected result:** User understands evidence is advisory (§45).

### BR-RECO-001 — Recommendations reviewable before implementation
- **Condition:** Recommendation produced.
- **Action:** Present for review; do not auto-apply.
- **Exception:** None.
- **Validation:** Approval flow before implementation.
- **Expected result:** No unapproved changes (§46; FR-RECO-003).

---

## 16. Security & Audit Rules

### BR-SEC-001 — No plaintext API key retrieval
- **Condition:** API key retrieval requested.
- **Action:** Never return plaintext key.
- **Exception:** Creation-time single display.
- **Validation:** Encrypted-at-rest + masking.
- **Expected result:** Keys not retrievable in plaintext (AC-SEC-003).

### BR-SEC-002 — Deleted user immediate access loss
- **Condition:** User removed/deleted.
- **Action:** Revoke access immediately.
- **Exception:** None.
- **Validation:** Immediate revocation.
- **Expected result:** No lingering access (AC-SEC-004).

### BR-SEC-003 — Audit log immutability
- **Condition:** Normal user attempts to modify audit logs.
- **Action:** Deny; audit logs immutable by normal users.
- **Exception:** None.
- **Validation:** Write-restricted audit store.
- **Expected result:** Audit logs unmodifiable by normal users (AC-SEC-005).

### BR-SEC-004 — Project ID cannot bypass authorization
- **Condition:** Request references a project ID.
- **Action:** Authorize against the project, not merely the ID.
- **Exception:** None.
- **Validation:** Object-level authorization.
- **Expected result:** Project IDs cannot bypass authorization (AC-SEC-002).

### BR-ERR-001 — Standard error format, no stack traces
- **Condition:** Any error surfaced to a user.
- **Action:** Return {error: {code, message, request_id}}; suppress internal stack traces.
- **Exception:** Internal/ops logs only.
- **Validation:** Central error handler.
- **Expected result:** Consistent errors; no internal leakage (§63).

---

## 17. Statistical Rules

### BR-STAT-001 — No overclaiming of significance
- **Condition:** Research statistical analysis.
- **Action:** Claim significance only where sample size and methodology are sufficient.
- **Exception:** None.
- **Validation:** Sample-size/methodology guard.
- **Expected result:** Cautious statistical claims (FR-RESEARCH-012).

---

## 18. Rule Cross-Reference Summary

| Rule Group | Count | Key ACs |
|------------|------:|---------|
| Authentication | 5 | AC-AUTH-001..006 |
| Organization | 2 | AC-SEC-001, AC-SEC-004 |
| Project | 2 | FR-PROJECT-004/005 |
| Provider/Gateway | 3 | AC-MODEL-001..007 |
| Dataset | 5 | FR-DATASET-008..013 |
| Evaluation | 6 | AC-HALL-001..005 |
| Test Generation | 4 | AC-TESTGEN-001..006 |
| Safety | 3 | §28, §29 |
| Cost | 2 | FR-COST-002 |
| Experiment/Score | 6 | AC-SCORE-001..004 |
| Regression/Quality Gate | 6 | §37, §39, AC-CICD-003 |
| Alerting | 3 | §44 |
| Environment/Versioning | 2 | FR-ENV-003, FR-VERSION-001 |
| Async/Reliability | 3 | §58, §88, §89 |
| RCA/Recommendation | 2 | §45, §46 |
| Security/Audit/Error | 5 | AC-SEC-001..005 |
| Statistical | 1 | FR-RESEARCH-012 |
| **Total** | **60** | |

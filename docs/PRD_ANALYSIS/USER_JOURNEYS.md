# User Journeys — AIREX

This document extracts every end-to-end user journey defined (or strongly implied) by the PRD V1.0. For each journey: **starting state, actions, system behavior, success state, failure state, recovery path**.

Legend: **NS** = Not Specified in PRD (logged in [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md)).

---

## Journey Map (Overview)

1. J1 — Visitor Registration & Onboarding
2. J2 — Organization Creation & Admin Setup
3. J3 — Admin: Invite / Remove / Change Roles
4. J4 — Project Creation & Configuration
5. J5 — Connect AI Model / Configure Provider
6. J6 — Dataset Upload & Versioning
7. J7 — AI Test Generation & Approval
8. J8 — Asynchronous Evaluation Execution
9. J9 — Evaluation Results & Failure Drill-down
10. J10 — Human Review & Calibration
11. J11 — Model Benchmarking / Comparison
12. J12 — Prompt Experimentation
13. J13 — Baseline & Regression Detection
14. J14 — CI/CD Integration & Quality Gate
15. J15 — Production Observability & Trace Inspection
16. J16 — Alert Configuration & Notification
17. J17 — Root Cause Analysis & Recommendations
18. J18 — Report Generation & Export
19. J19 — Research Experiment & Statistical Analysis
20. J20 — Reproducibility by a Second Researcher
21. J21 — Viewer Access
22. J22 — Environment Management (Dev/Staging/Prod)

---

## J1 — Visitor Registration & Onboarding

- **Actor:** Visitor.
- **Starting state:** No account; lands on `/register`.
- **Actions:** Submit email/password; verify email; log in.
- **System behavior:** Create account (AC-AUTH-001); reject duplicate email (AC-AUTH-002); send verification (AC-AUTH-005); issue session (AC-AUTH-006); create/assign organization (**NS** whether auto-created or first-admin-creates — see AMB-ONBOARD-001); record login audit event (§61).
- **Success state:** User logged in with an active organization and a role (**NS** default role — see AMB-ONBOARD-001).
- **Failure state:** Duplicate email; invalid fields; unverified email.
- **Recovery path:** Password reset (§9); resend verification email (**NS**).

## J2 — Organization Creation & Admin Setup

- **Actor:** User (Admin-eligible), Admin.
- **Starting state:** Logged-in user without an organization (or Admin creating org).
- **Actions:** Create organization; persist settings.
- **System behavior:** Org becomes top-level tenant (§10); org settings persisted (FR-ORG-007).
- **Success state:** Organization active with the creator as admin (**NS** role assignment detail).
- **Failure state:** Org creation error (**NS** validation rules, e.g., name uniqueness).
- **Recovery path:** Retry; contact admin (**NS**).

## J3 — Admin: Invite / Remove / Change Roles

- **Actor:** Admin.
- **Starting state:** Active organization with members.
- **Actions:** Invite user; assign role; remove user; change role (§10).
- **System behavior:** New member gains org access; removed user loses access **immediately** (AC-SEC-004); role change takes effect (**NS** session refresh behavior); events audited (role changed, §61).
- **Success state:** Membership reflects the intended set and roles.
- **Failure state:** Removing the sole admin could lock the org (**NS** guard).
- **Recovery path:** NS.

## J4 — Project Creation & Configuration

- **Actor:** Project Owner (manage projects per §7), Admin.
- **Starting state:** Active org; user has project-management permission.
- **Actions:** Create project (name, description, application type, environment, endpoint, auth config, model config, evaluation config — §11); edit; archive; delete (with confirmation).
- **System behavior:** Project created (AC §11); archived projects cannot run **new production** evaluations (FR-PROJECT-005); delete requires confirmation (FR-PROJECT-004).
- **Success state:** Project configured and ready for model/dataset setup.
- **Failure state:** Deletion without confirmation blocked; validation errors (**NS**).
- **Recovery path:** Re-edit configuration.

## J5 — Connect AI Model / Configure Provider

- **Actor:** Project Owner, Engineer (configure models? per §7 Project Owner only — see AMB-PERM-001).
- **Starting state:** Project exists.
- **Actions:** Add provider (OpenAI/Anthropic/Gemini/OSS/Local); enter model, API key, base URL, temperature, max tokens, timeout, retry policy (§12).
- **System behavior:** Model gateway validated via test inference (AC-MODEL-001); invalid credentials → controlled error (AC-MODEL-002); API key encrypted (SEC-API-001) and **never displayed again** (FR-PROVIDER-008); no secrets in logs (AC-MODEL-007).
- **Success state:** Model marked ready for evaluation.
- **Failure state:** Invalid key; timeout; provider error normalized (AC-MODEL-003/004).
- **Recovery path:** Re-enter key; adjust timeout/retry.

## J6 — Dataset Upload & Versioning

- **Actor:** Project Owner, Engineer.
- **Starting state:** Project exists; model configured.
- **Actions:** Upload CSV/JSON/JSONL; manual entry; reference generated dataset; define fields (input, expected answer, context, metadata, tags, difficulty, category — §15).
- **System behavior:** Import validates rows (row-level errors, FR-DATASET-012); duplicate dataset IDs rejected (FR-DATASET-013); a version is created on every modification (FR-DATASET-008); versions immutable (FR-DATASET-009).
- **Success state:** Immutable dataset version available, e.g., `customer-support-v1` (§102 Step 4).
- **Failure state:** Import failures with row-level errors; duplicate ID.
- **Recovery path:** Fix rows and re-import; new version created.

## J7 — AI Test Generation & Approval

- **Actor:** Engineer, Project Owner.
- **Starting state:** Dataset present.
- **Actions:** Request N test cases from inputs (application description, dataset, documentation, existing tests — §26); preview; approve/reject.
- **System behavior:** Generates categorized cases (Normal, Edge, Adversarial, Ambiguous, Safety, Prompt Injection, Long Context, Multilingual — §26); configurable count (AC-TESTGEN-001); category metadata (AC-TESTGEN-002); previewable (AC-TESTGEN-003); approve/reject (AC-TESTGEN-004); rejected excluded from runs (AC-TESTGEN-005); versioned (AC-TESTGEN-006). Example: generate 100, approve 80 (§102 Step 5–6).
- **Success state:** Approved test set (80 cases) executable.
- **Failure state:** Generation fails/rate-limited (SEC-RATE-002); content review issues (**NS** moderation policy — see AMB-TESTGEN-001).
- **Recovery path:** Adjust inputs/quantity; retry.

## J8 — Asynchronous Evaluation Execution

- **Actor:** Engineer, Project Owner.
- **Starting state:** Approved tests + configured model + dataset version.
- **Actions:** Run evaluation (UI, API `POST /evaluations/{id}/run`, or CLI `airex evaluate run`).
- **System behavior:** Job created → queue → workers (§56); status QUEUED → RUNNING → COMPLETED (§102 Step 7); API not blocked (FR-ASYNC-002); workers parallel/retry/timeout/rate-limit/partial-failure/cancel (FR-ASYNC-003..009); jobs survive restarts (§88); partial results preserved (§89).
- **Success state:** Evaluation completes with persisted results (§101).
- **Failure state:** Provider errors, timeouts, job cancellation, worker crash.
- **Recovery path:** Automatic retry (transient) (§58); re-run from queue; user notified on failure (FR-NOTIFY-002).

## J9 — Evaluation Results & Failure Drill-down

- **Actor:** Engineer, Project Owner, Viewer (view only).
- **Starting state:** Completed evaluation.
- **Actions:** Open evaluation details page; view metrics; drill into individual failures.
- **System behavior:** Evaluation details show status, dataset, model, prompt, metrics, P95 latency, cost, and PASS/FAIL/WARNING counts (§70); test result page shows question, expected answer, actual answer, retrieved context, scores, failure classification, reason, trace (§71).
- **Success state:** User understands why tests failed.
- **Failure state:** Failure detail missing (trace not captured) (**NS**).
- **Recovery path:** Re-run with more data; escalate to RCA (J17).

## J10 — Human Review & Calibration

- **Actor:** Engineer, Researcher.
- **Starting state:** Evaluation has uncertain or low-confidence results (FR-JUDGE-004).
- **Actions:** Mark AI PASS → human PASS; AI FAIL → human FALSE POSITIVE (§72); sample results for review (§73).
- **System behavior:** Human decisions stored for analysis (FR-HUMAN-003); AI vs Human agreement computed (FR-HUMAN-006).
- **Success state:** Calibrated, reviewed results.
- **Failure state:** Reviewer conflict/ambiguity (**NS** adjudication workflow — see AMB-HUMAN-001).
- **Recovery path:** NS.

## J11 — Model Benchmarking / Comparison

- **Actor:** Project Owner, Engineer, Researcher.
- **Starting state:** At least two configured models.
- **Actions:** Select models A/B/C; run identical evaluation dataset (§32, §76).
- **System behavior:** Ensures same dataset, test cases, evaluator, config (FR-BENCH-004); shows accuracy/hallucination/latency/cost table (§32); computes weighted score with configurable weights (§32).
- **Success state:** Side-by-side comparison (§102 Step 12).
- **Failure state:** Unequal configuration invalidates comparison (must be prevented).
- **Recovery path:** Re-run with matched config.

## J12 — Prompt Experimentation

- **Actor:** Project Owner, Engineer.
- **Starting state:** Dataset and model(s) available.
- **Actions:** Create prompt versions v1/v2/v3; run same dataset against each (§33).
- **System behavior:** Versioned prompts (FR-PROMPT-001); comparison across accuracy, hallucination, latency, cost, safety (FR-PROMPT-003).
- **Success state:** Prompt version comparison visible.
- **Failure state:** NS.
- **Recovery path:** NS.

## J13 — Baseline & Regression Detection

- **Actor:** Project Owner, Engineer.
- **Starting state:** Completed evaluation.
- **Actions:** Establish baseline (e.g., Model A — §102 Step 13); evaluate new application version; run regression (CLI `airex regression run --baseline ...`).
- **System behavior:** Regression engine compares new vs baseline (§36); applies thresholds (§37); outputs REGRESSION DETECTED when violated (§102 Step 15).
- **Success state:** Regression status visible on dashboard (FR-DASH-004).
- **Failure state:** Threshold misconfiguration (**NS** defaults).
- **Recovery path:** Adjust thresholds; re-run.

## J14 — CI/CD Integration & Quality Gate

- **Actor:** MLOps/CI system (GitHub Actions per §67).
- **Starting state:** Git push; pipeline builds and deploys test environment (§38).
- **Actions:** Trigger AIREX evaluation; reference a specific dataset version (AC-CICD-005); evaluate quality gate (§39); return result.
- **System behavior:** Evaluation triggered (AC-CICD-001); result returned (AC-CICD-002); failed gate → non-zero exit (AC-CICD-003); passed gate → success (AC-CICD-004).
- **Success state:** Pipeline PASS/FAIL correctly gates deployment.
- **Failure state:** CI cannot authenticate to AIREX (**NS** — AMB-CICD-002); threshold conflict (§39 vs §37 — AMB-THRESHOLD-001).
- **Recovery path:** Fix build; re-trigger.

## J15 — Production Observability & Trace Inspection

- **Actor:** MLOps Engineer, Engineer.
- **Starting state:** Production traffic flowing through gateway.
- **Actions:** View real-time dashboard; inspect AI traces.
- **System behavior:** Dashboard shows requests, errors, latency, tokens, cost, quality score, hallucination, safety, model distribution (§41); time ranges (15m/1h/24h/7d/30d/custom) (§41); per-request trace with steps (retriever, documents, prompt builder, LLM, evaluator) (§42); redaction per project settings (FR-OBS-007).
- **Success state:** Engineer locates the failing step.
- **Failure state:** Trace not captured; redaction misconfigured (**NS** defaults).
- **Recovery path:** Adjust sampling/redaction.

## J16 — Alert Configuration & Notification

- **Actor:** Project Owner, Admin.
- **Starting state:** Observability data flowing.
- **Actions:** Create alert rule (type, severity, threshold, duration, cooldown, enabled/disabled — §44); choose channel (in-app/email/webhook — §43).
- **System behavior:** Alert engine evaluates rules (e.g., P95 > 3s for 10 min; hallucination > 7% critical — §44); notifies users (§85); in-app alert list on dashboard (§50).
- **Success state:** Alert fired with correct severity; cooldown respected.
- **Failure state:** Webhook delivery failure (**NS** retry).
- **Recovery path:** NS.

## J17 — Root Cause Analysis & Recommendations

- **Actor:** Engineer, Project Owner.
- **Starting state:** Failed evaluation or degraded production metric.
- **Actions:** Open RCA view; review recommended fixes.
- **System behavior:** RCA identifies likely causes with evidence (e.g., retrieval quality ↓ 15%, generation ↓ 4%, relevant doc not retrieved in 3/5 failed tests — §45); recommendations generated (top-K, chunk size, reranking, etc. — §46); AI explanations labeled as recommendations, not truth (FR-RCA-002); recommendations reviewable before implementation (FR-RECO-003).
- **Success state:** User has actionable, evidenced hypothesis.
- **Failure state:** RCA inconclusive (UNKNOWN classification — §25).
- **Recovery path:** Manual investigation via traces (J15).

## J18 — Report Generation & Export

- **Actor:** Engineer, Project Owner, Researcher.
- **Starting state:** Completed evaluation/experiment.
- **Actions:** Generate report; export results.
- **System behavior:** Report includes executive summary, config, dataset, model, prompt, metrics, failures, regression/cost/latency/safety analyses, recommendations, limitations (§80); export formats CSV/JSON/Markdown/PDF (§79); CLI `airex report generate` (§52).
- **Success state:** Artifacts generated successfully (§102 Step 19).
- **Failure state:** Export generation failure (**NS**).
- **Recovery path:** Retry; contact support (**NS**).

## J19 — Research Experiment & Statistical Analysis

- **Actor:** AI Researcher.
- **Starting state:** Research-capable org; dataset + models.
- **Actions:** Define hypothesis, variables, baseline, treatment, dataset, metrics (§47); run; view charts and statistics.
- **System behavior:** Research experiment captures dataset, model, prompt, config, metrics (§102 Step 18); statistical analysis: mean, median, std dev, percentiles, CI, effect size, significance-where-applicable (§48); no overclaiming significance (FR-RESEARCH-012).
- **Success state:** Statistically sound results with charts and conclusions.
- **Failure state:** Insufficient sample size → significance not claimed (correct behavior).
- **Recovery path:** Adjust methodology; add data.

## J20 — Reproducibility by a Second Researcher

- **Actor:** AI Researcher (second).
- **Starting state:** Published/exported experiment metadata (§81).
- **Actions:** Retrieve experiment configuration; re-run.
- **System behavior:** Same dataset version, prompt, model, parameters, evaluator version, config, seed retrieved (FR-REPRO-002); reproducibility limited by provider/model (FR-REPRO-001); same config retrievable (§102 Step 20).
- **Success state:** Re-run reproduces results within provider nondeterminism.
- **Failure state:** Model version retired by provider; non-determinism (labeled limitation).
- **Recovery path:** Document limitation; pin versions where possible.

## J21 — Viewer Access

- **Actor:** Viewer.
- **Starting state:** Granted viewer role in an organization.
- **Actions:** View dashboards, reports, experiment results (§7).
- **System behavior:** Read-only access; cannot modify datasets or evaluations (AC-AUTH-006).
- **Success state:** Viewer sees required metrics without edit permissions.
- **Failure state:** Attempted modification rejected.
- **Recovery path:** Request role change from admin.

## J22 — Environment Management

- **Actor:** Project Owner, Admin.
- **Starting state:** Project exists.
- **Actions:** Configure dev/staging/production environments with separate model, endpoint, credentials, policies (§77).
- **System behavior:** Environment-scoped credentials; production credentials not exposed to dev users without authorization (FR-ENV-003).
- **Success state:** Correct environment used by evaluations/CI.
- **Failure state:** Credential leakage across environments.
- **Recovery path:** Rotate credentials; enforce RBAC.

---

## Journey Completeness Notes

- The PRD's flagship journey (§102, 20 steps) is fully covered by J1, J2, J4, J5, J6, J7, J8, J9, J11, J13, J14, J17, J18, J19, J20.
- Gaps in journey detail (onboarding role assignment, password-reset flow, org creation default role, human-review adjudication, alert delivery retry) are logged in [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md).

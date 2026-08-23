# Ambiguity Register — AIREX

Every ambiguity, conflict, missing requirement, undefined state, missing error behavior, missing permission, missing validation, missing API definition, and missing data relationship found in the PRD V1.0. **Nothing here is silently fixed.** Each entry records the problem, impact, possible interpretations, and a recommended decision for the product owner.

Severity legend: 🔴 Critical (blocks architecture) · 🟠 High (must resolve before implementation) · 🟡 Medium (resolve before the relevant phase) · 🟢 Low (resolve during design).

---

## Critical (🔴)

### AMB-VERSION-SCOPE-001 — MVP vs V2 scope conflict (research, RCA, recommendations, human review)
- **Location:** §96 (MVP "Must Have"), §97 (V2), §101 (Master AC), §102 (Final E2E test), §109 (MVP Release Gate).
- **Problem:** §97 places *root-cause analysis, recommendation engine, human evaluation workflows, statistical analysis, research workspace* in **V2**. But §101 requires "Human review is supported" (item 33), "Research experiments can be created" (item 35), and "Root-cause analysis" is part of §102 Step 17 ("Dashboard clearly shows Regression → Affected metric → Failed tests → Likely cause"). §109 includes "Detect Regression" but not explicitly RCA/research. The MVP gate and V2 scope are contradictory.
- **Impact:** Architecture phase cannot decide what to build for MVP. Work estimates, release planning, and the Definition of Done (§100) are all affected. This is the single largest blocker.
- **Possible interpretations:**
  1. MVP = §96 list only; §101/§102 items mentioning V2 features are aspirational and should be struck from the MVP gate.
  2. MVP = §101/§102 in full, meaning RCA, research workspace, and human review must move into MVP.
  3. A staged "MVP-plus" where human review is MVP but RCA/research are V2.
- **Recommended decision:** Product owner must explicitly reconcile. Suggested: keep §96 as the hard MVP scope, mark §101 items 33 & 35 and §102 steps 17–20 as V2, and provide an amended MVP gate. Alternatively, promote human review (required for evaluation correctness) into MVP and leave research workspace as V2.

### AMB-API-001 — No API contract defined
- **Location:** §51, §63, §95.
- **Problem:** Only endpoint paths are listed. No request/response schemas, auth mechanism, authorization, error-code taxonomy, rate limits, idempotency, pagination, or side-effect semantics.
- **Impact:** Cannot implement or test APIs; cannot build CLI ↔ API mapping or CI/CD integration (AC-CICD-001..005) reliably.
- **Possible interpretations:** REST conventions; OpenAPI-first design; JWT bearer vs cookie session.
- **Recommended decision:** Produce an OpenAPI specification as part of architecture. For MVP, fix the auth mechanism (JWT bearer recommended), define error-code taxonomy (extend the `EVALUATION_TIMEOUT` example), define idempotency keys for POST /run and /generate, and add pagination for list endpoints.

### AMB-BILLING-001 — No platform billing/subscription model
- **Location:** Throughout (product is a SaaS, §1–§2), §31 (cost analytics only).
- **Problem:** The PRD defines AI **inference cost analytics** but no platform pricing tiers, subscriptions, quotas, or payment integration. The product is described as a production SaaS but has no billing module.
- **Impact:** Cannot design tenancy quotas, plan limits, or revenue-related features; success metrics (§99) mention "portfolio" but not commercial viability.
- **Possible interpretations:** (a) Freemium/self-hosted only, billing out of scope for V1; (b) subscription tiers with limits; (c) usage-based billing on evaluations.
- **Recommended decision:** Explicitly declare platform billing **out of scope for MVP** (aligning with §96 which omits it), or add a minimal tier/quotas model. Must be stated in the PRD to avoid architecture guessing.

### AMB-DATA-SCHEMA-001 — Entity list without schema
- **Location:** §53.
- **Problem:** Table names only; no fields, types, nullability, relationships, constraints, or indexes. Several implied entities (pricing configs, human reviews, score configs, notifications, vector chunks) are not in the list.
- **Impact:** Cannot design the data model, migrations, or ORM; affects every module.
- **Possible interpretations:** Standard normalization per entity; JSONB for flexible fields (e.g., metadata, metrics).
- **Recommended decision:** Approve a target data model in the architecture phase (fields derived from §12–§17, §31, §34, §54, §60, §74, §78), with JSONB where the PRD implies flexible records. Confirm implied entities.

---

## High (🟠)

### AMB-THRESHOLD-001 — Conflicting threshold examples (quality gate vs regression policy)
- **Location:** §37 (regression policies) vs §39 (quality gate).
- **Problem:** §37: accuracy ↓>3% FAIL, hallucination ↑>2% FAIL, P95 ↑>15% WARNING, cost ↑>20% WARNING. §39: accuracy ≥90%, hallucination ≤5%, safety ≥95%, P95 ≤3s, cost ≤$0.03 → BUILD FAILED. Values are presented as examples; it is unclear whether these are system defaults or purely illustrative, and how they relate (regression thresholds vs absolute quality gates are different semantics).
- **Impact:** Regression and quality-gate outcomes are not deterministically testable (AC-CICD-003/004, §101 items 25–26).
- **Possible interpretations:** (1) Both are per-config examples with no defaults; (2) §39 are the MVP defaults; (3) §37 applies to deltas, §39 to absolute values.
- **Recommended decision:** Define explicit default thresholds, distinguish absolute (quality gate) vs relative (regression delta) rules, and state that all are configurable per project/org (Admin configures policies per §7).

### AMB-PERM-001 — Incomplete permission matrix
- **Location:** §7 (roles), §9, §10, AC-AUTH-006.
- **Problem:** Role *headline* capabilities are given, but granular permissions are undefined: project-level vs org-level roles, whether Engineer can configure models or create datasets, whether Project Owner can create projects, Viewer access to datasets/traces/audit logs, human-review and test-approval permissions, admin evaluation permissions. (Full list in [`PERMISSION_MATRIX.md`](./PERMISSION_MATRIX.md).)
- **Impact:** RBAC cannot be implemented correctly; AC-AUTH-005/006 and AC-SEC-002 testability depend on it.
- **Possible interpretations:** Admin > Project Owner > Engineer > Viewer strict hierarchy; or capability-based.
- **Recommended decision:** Produce a full role×capability matrix (can be done in architecture) and confirm the org-vs-project scoping of roles. Recommend least-privilege defaults.

### AMB-RETENTION-001 — Data retention undefined
- **Location:** §5 (non-goal: "not store sensitive production data indefinitely"), §60 (privacy toggles), §34 (immutability).
- **Problem:** No retention, archival, or deletion policy. "Not storing sensitive data indefinitely" conflicts with experiment immutability and reproducibility requirements without a defined retention timeline.
- **Impact:** Compliance (COMP-005), storage cost, and trust/privacy claims are untestable.
- **Possible interpretations:** TTL-based purge; org-configurable retention; no deletion (immutability wins).
- **Recommended decision:** Define retention tiers (raw vs aggregated), default toggle states, and purge rules; document the interaction between immutability and retention.

### AMB-PRIVACY-001 — Privacy toggles without defaults or enforcement points
- **Location:** §60.
- **Problem:** Toggles (raw data storage, PII masking, prompt storage, response storage) have no defaults, no per-entity/org inheritance, no redaction scope (gateway? traces? logs? datasets?), and no masking taxonomy beyond `[PERSON]`/`[PHONE]`.
- **Impact:** Data privacy claims (COMP-001) and redaction behavior (FR-OBS-007) are unenforceable/unverifiable.
- **Possible interpretations:** Org-level toggles applied globally; project-level toggles; field-level redaction.
- **Recommended decision:** Define defaults (recommend: storage OFF, masking ON for production), toggle granularity, and the full redaction entity/PII taxonomy.

### AMB-API-002 — Authentication mechanism undefined
- **Location:** §9 ("JWT/session"), §51, §63.
- **Problem:** Whether APIs use JWT bearer, opaque session cookies, API keys, or all three is unspecified. CLI and CI/CD authentication depend on this.
- **Impact:** Blocks API implementation, CLI, and CI/CD integration (AMB-CICD-002).
- **Possible interpretations:** JWT bearer for interactive + org API keys for CI/CLI; or single mechanism.
- **Recommended decision:** JWT bearer for user sessions; organization API keys for programmatic/CI access; document in OpenAPI.

### AMB-API-003 — Error code taxonomy undefined
- **Location:** §63.
- **Problem:** Only one example (`EVALUATION_TIMEOUT`). No list of codes, status-code mapping, or per-domain error schemas.
- **Impact:** Error handling (SEC-ERR-001/002) not uniformly implementable.
- **Possible interpretations:** Central enumerated code list; HTTP-status mapped.
- **Recommended decision:** Define a canonical error-code catalogue during API design (extend §63 format with `status`, `details`).

### AMB-PRICING-001 — Cost/pricing configuration source undefined
- **Location:** §31, BR-COST-001/002.
- **Problem:** Cost estimation requires provider/model pricing data; the source (bundled price tables, user-entered, fetched live) and update cadence are undefined. Model pricing changes over time.
- **Impact:** §101 item 22 (cost calculated) and §31 cost aggregates are not reliably implementable; cost-based alerts/recommendations inherit the issue.
- **Possible interpretations:** (a) Bundled static price table, (b) user-entered per-org pricing config, (c) live provider pricing fetch.
- **Recommended decision:** Start with user-editable, versioned pricing configs per org (§31 already requires versioning) seeded with bundled defaults; allow provider-price overrides.

### AMB-CICD-002 — CI/CD authentication & integration mechanism undefined
- **Location:** §38, §40, §67.
- **Problem:** How the CI pipeline authenticates (API key? token?), how results are polled/returned, and which CI systems are supported (GitHub Actions named in §67, but ACs say "CI pipeline") are unspecified.
- **Impact:** AC-CICD-001..005 untestable; §101 items 26–27 blocked.
- **Possible interpretations:** GitHub Actions only; generic webhook + polling API.
- **Recommended decision:** Support GitHub Actions in MVP via org API keys and a `poll`/callback result mechanism; design the trigger/result API in the API contract.

### AMB-JUDGE-001 — AI Judge provider/cost/keys undefined
- **Location:** §74, §75.
- **Problem:** LLM-as-judge requires a model/provider, separate from the evaluated models; which provider, whose API keys, and who bears the cost are unspecified. Judge determinism (temperature) also matters for reproducibility.
- **Impact:** §74 reproducibility fields exist but the judge pipeline cannot be built or costed.
- **Possible interpretations:** Reuse the org's configured providers; dedicated judge model; hosted vs user-key.
- **Recommended decision:** Allow per-org judge configuration (model + temperature + keys), defaulting to the org's configured provider; record all §74 fields.

### AMB-EMAIL-001 — Email provider undefined
- **Location:** §9 (verification), §43 (alerts), §85 (notifications).
- **Problem:** No email vendor named; transactional vs alert-sending requirements (deliverability, templates, opt-out) unspecified.
- **Impact:** Registration, password reset, alerts, and notifications cannot ship.
- **Possible interpretations:** SES/SendGrid/Postmark; self-hosted.
- **Recommended decision:** Choose a transactional email provider during architecture (recommend SES or SendGrid); define templates for verification/reset/notifications.

### AMB-STORAGE-001 — Object storage for large artifacts undefined
- **Location:** §79 (export), §80 (reports), datasets, traces.
- **Problem:** Large datasets, exports, PDF reports, and trace stores need a storage strategy (object storage vs DB). Not addressed in the PRD.
- **Impact:** Storage architecture for datasets/exports/reports is undefined; affects scalability (AMB-SCALE-001).
- **Possible interpretations:** S3-style object storage; PostgreSQL only; filesystem for self-host.
- **Recommended decision:** Use S3-compatible object storage for artifacts (datasets, exports, reports) with DB metadata, in the target AWS deployment (§67).

### AMB-ONBOARD-001 — Onboarding flow undefined
- **Location:** §6, §7, §10, §9.
- **Problem:** Registration → organization → role assignment is undefined: is an org auto-created at signup? What is the default role of the first user? How does onboarding sequence (org → project → model → dataset) present?
- **Impact:** J1/J2 journeys and AC-AUTH-001 cannot be validated end-to-end.
- **Possible interpretations:** Auto-create personal org at signup with Admin role; require explicit org creation by Admin.
- **Recommended decision:** Auto-create an organization at first signup with the creator as Admin; allow additional orgs via Admin (§7 "create organizations").

---

## Medium (🟡)

### AMB-PROJECT-001 — External application endpoint contract undefined
- **Location:** §11 (project endpoint/auth config), §17 (evaluation pipeline → AI Application).
- **Problem:** How the evaluation runner calls the external AI application (HTTP protocol, streaming, request/response schema, how the application is invoked in CI test environments per §38) is unspecified.
- **Impact:** Evaluation execution against a user's app cannot be implemented.
- **Possible interpretations:** The platform calls the app's REST endpoint; the app is a plugin; evaluation happens in the user's CI environment.
- **Recommended decision:** Define an application adapter contract (HTTP endpoint + payload schema) in architecture; support both platform-initiated calls and CI-side execution.

### AMB-EVAL-001 — Underspecified evaluators
- **Location:** §18 (list includes toxicity, bias, data leakage, response format, consistency), §29, §48.
- **Problem:** Several evaluators are named but not defined (data leakage semantics, response-format grammar, consistency protocol, bias definition, toxicity taxonomy). Statistical significance methodology (§48) lacks concrete tests.
- **Impact:** These evaluators cannot be built or acceptance-tested; §101 items referencing them are incomplete.
- **Possible interpretations:** Reference standard libraries/taxonomies; LLM-judge-based.
- **Recommended decision:** For MVP, specify which evaluators ship (§96 lists a concrete set) and define the remaining ones precisely, or mark them V2.

### AMB-ARCHIVE-001 — Archive semantics for non-production evaluations
- **Location:** §11 (FR-PROJECT-005).
- **Problem:** "Archived projects cannot execute new **production** evaluations" implies non-production evaluations may be allowed, but this is not clarified.
- **Impact:** Archive behavior ambiguous; affects testability and permissions.
- **Possible interpretations:** Archived = fully read-only; archived = no production only.
- **Recommended decision:** Clarify; recommend full read-only for archived projects to reduce risk.

### AMB-CONF-001 — Confidence score derivation undefined
- **Location:** §75.
- **Problem:** How confidence is computed (probabilistic, evaluator self-report, ensemble agreement) is unspecified; thresholds for "low confidence → human review" undefined.
- **Impact:** FR-JUDGE-003/004 and the calibration loop (§73) cannot be implemented.
- **Possible interpretations:** Judge self-assessed confidence; agreement across multiple judge passes; calibrated thresholds.
- **Recommended decision:** Define confidence as a normalized score from the AI judge (with recorded methodology) and make the low-confidence cutoff configurable.

### AMB-ASYNC-001 — Job semantics undefined
- **Location:** §56–§58, §89.
- **Problem:** Job cancellation semantics (graceful? discard partial results?), partial-failure handling rules (which failures are partial), and progress reporting are unspecified.
- **Impact:** Worker implementation and reliability guarantees (§89) ambiguous.
- **Possible interpretations:** Cancellation = stop accepting new work, preserve completed; partial failure = per-test retry then record.
- **Recommended decision:** Define: cancel = graceful stop preserving completed results; partial failure = retried per transient policy then recorded as FAIL; expose per-test status for progress.

### AMB-RATE-001 — Rate limit defaults undefined
- **Location:** §62.
- **Problem:** Categories are defined (API, evaluation jobs, model calls, dataset generation, test generation) and per-org configurability required, but no default limits or quota model.
- **Impact:** SEC-RATE-001..003 cannot be tested.
- **Possible interpretations:** No defaults (per-org only); reasonable platform defaults.
- **Recommended decision:** Ship conservative platform defaults, overridable per org by Admin.

### AMB-NOTIF-001 — Notification preferences undefined
- **Location:** §85, §43.
- **Problem:** Which users receive which notifications (role/scope), preferences UI, and delivery guarantees (email vs in-app vs webhook) are unspecified.
- **Impact:** FR-NOTIFY-001..006 cannot be validated.
- **Possible interpretations:** All members; per-project subscribers; user-configurable.
- **Recommended decision:** Define notification targeting (org/project scope) and a user preferences surface; in-app always, email per preference.

### AMB-HUMAN-001 — Human review workflow undefined
- **Location:** §72, §73, §21.
- **Problem:** Review queue mechanics, adjudication of conflicting reviews, reviewer permissions, and how AI/Human agreement is computed are unspecified.
- **Impact:** Calibration (FR-HUMAN-004..006) cannot be implemented.
- **Possible interpretations:** Single reviewer per item; majority adjudication.
- **Recommended decision:** Single reviewer per sampled item initially; store all decisions for agreement analytics; double-review for disagreement where configured.

### AMB-TESTGEN-001 — Test-generation budget and content safety
- **Location:** §26, §27, SEC-RATE-002.
- **Problem:** Max generated quantity, generation cost/budget, and moderation of generated adversarial/safety content are unspecified (only "must not encourage real-world abuse" §28).
- **Impact:** Generation can be unbounded/expensive; generated content governance unclear.
- **Possible interpretations:** Hard caps; per-org budgets; LLM-output moderation.
- **Recommended decision:** Define a max quantity per request and a per-org monthly generation budget; apply content moderation to generated tests.

### AMB-PROVIDER-001 — Local/OSS model support details
- **Location:** §12, §67.
- **Problem:** "Open-source models through compatible APIs" and "local models" lack concrete integration contracts (which APIs are "compatible", how local models are hosted, health checks, embedding models for RAG).
- **Impact:** Provider adapters beyond the big three cannot be implemented.
- **Possible interpretations:** OpenAI-compatible endpoints (e.g., vLLM/Ollama); local inference servers.
- **Recommended decision:** Scope MVP to OpenAI-compatible HTTP interfaces for OSS/local (common standard), leaving bespoke adapters to later.

### AMB-INDEX-001 — No indexing/query requirements
- **Location:** §53.
- **Problem:** No index or query-pattern requirements for dashboards, traces, metrics, or tenant isolation performance.
- **Impact:** Performance targets (PERF-001/002) may be unreachable without index design.
- **Possible interpretations:** Standard tenant-scoped indexes; time-series partitioning.
- **Recommended decision:** Define indexing (org_id on all tenant tables, time-based partitions for traces/metrics) in the data model.

### AMB-VECTOR-001 — Embedding model undefined
- **Location:** §54, §24.
- **Problem:** Embedding model for pgvector is unspecified (affects retrieval evaluation and reproducibility of retrieval metrics).
- **Impact:** RAG evaluation reproducibility and vector-store setup.
- **Possible interpretations:** Provider embedding models; configurable per project.
- **Recommended decision:** Make embedding model a versioned, per-project configuration (reproducibility requirement), defaulting to a provider embedding model.

### AMB-UNIQUE-001 — Uniqueness rules undefined
- **Location:** §10, §11, §16.
- **Problem:** Only email (§9) and dataset IDs (§16) have explicit uniqueness. Org/project names, provider names, and model names uniqueness unspecified.
- **Impact:** Validation rules for core entities are incomplete.
- **Possible interpretations:** Unique per tenant; globally unique IDs (UUID).
- **Recommended decision:** Use UUIDs for all entity IDs (globally unique) plus tenant-scoped unique constraints on natural names.

### AMB-CONF-002 (→ covered by AMB-THRESHOLD-001) — Score weight semantics
- **Location:** §83, AC-SCORE-001..004.
- **Problem:** Example weights sum to 100 (30+20+15+15+10+10). Whether weights must sum to 100, and how missing metrics are handled when weights include them, is unspecified (AC-SCORE-003).
- **Impact:** Score normalization and missing-metric behavior (AC-SCORE-003) ambiguous.
- **Possible interpretations:** Normalize weights dynamically; require sum=100; renormalize over available metrics.
- **Recommended decision:** Renormalize over available metrics and explicitly flag missing metrics (per AC-SCORE-003) rather than zero-filling.

---

## Low (🟢)

### AMB-SCALE-001 — No scalability/concurrency targets
- **Location:** §87, §57.
- **Problem:** No target for concurrent evaluations, jobs, or tenant scale beyond "process multiple test cases concurrently per configured worker limits."
- **Impact:** Capacity planning and worker sizing undefined.
- **Possible interpretations:** N/A (MVP small); elastic workers.
- **Recommended decision:** Set an MVP concurrency target (e.g., X concurrent evaluations, Y workers per org) during architecture.

### AMB-COMPLIANCE-001 — No regulatory compliance targets
- **Location:** §59, §60, §92.
- **Problem:** No explicit GDPR/HIPAA/SOC2 scope; the PRD has good security/privacy intent but no compliance certification targets.
- **Impact:** Enterprise adoption and legal posture unclear.
- **Possible interpretations:** None in V1 (self-host/portfolio focus); pursue SOC2 later.
- **Recommended decision:** State that V1 targets secure-by-design with no formal certification; revisit for enterprise (V3 mentions governance/compliance §98).

### AMB-AC-001 — Missing acceptance criteria for several modules
- **Location:** §41–§49, §79–§81, §86, §88.
- **Problem:** Observability, tracing, alerting, RCA, recommendations, reporting/export, research workspace, accessibility, and availability (99.5%) have no testable ACs (details in [`ACCEPTANCE_CRITERIA.md`](./ACCEPTANCE_CRITERIA.md) §6).
- **Impact:** Definition of Done (§100) cannot be met for these modules.
- **Possible interpretations:** N/A.
- **Recommended decision:** Add acceptance criteria for these modules before their implementation phase.

### AMB-API-004 — Idempotency undefined
- **Location:** §51.
- **Problem:** No idempotency semantics for POST endpoints (e.g., /evaluations/{id}/run can be triggered twice by CI retries).
- **Impact:** Duplicate evaluations/jobs.
- **Recommended decision:** Add idempotency keys to POST /run and /generate.

### AMB-API-005 — Pagination/filtering undefined
- **Location:** §51 (GET list endpoints).
- **Problem:** List endpoints (projects, datasets, experiments, models, metrics) have no pagination/filtering contract.
- **Impact:** Large-tenancy list performance (PERF-001).
- **Recommended decision:** Standardize cursor pagination + filters in the API contract.

### AMB-API-006 — Alert webhook payload undefined
- **Location:** §43.
- **Problem:** Outbound webhook payload/signing/retry contract unspecified.
- **Impact:** Webhook alert consumers cannot integrate.
- **Recommended decision:** Define webhook payload schema and HMAC signing in the API contract.

### AMB-CLI-001 — CLI auth/token and command contract undefined
- **Location:** §52.
- **Problem:** How `airex login` stores credentials, which endpoints commands map to, and exact exit-code semantics are unspecified.
- **Impact:** CLI ↔ API consistency.
- **Recommended decision:** CLI stores an org API key/token locally (scoped), commands map 1:1 to API endpoints, and exit codes follow the standard (0 success / nonzero failure).

---

## Register Summary

| Severity | Count | Representative IDs |
|----------|------:|--------------------|
| 🔴 Critical | 3 | AMB-VERSION-SCOPE-001, AMB-API-001, AMB-BILLING-001, AMB-DATA-SCHEMA-001 |
| 🟠 High | 9 | AMB-THRESHOLD-001, AMB-PERM-001, AMB-RETENTION-001, AMB-PRIVACY-001, AMB-API-002, AMB-API-003, AMB-PRICING-001, AMB-CICD-002, AMB-JUDGE-001, AMB-EMAIL-001, AMB-STORAGE-001, AMB-ONBOARD-001 |
| 🟡 Medium | 12 | AMB-PROJECT-001, AMB-EVAL-001, AMB-ARCHIVE-001, AMB-CONF-001, AMB-ASYNC-001, AMB-RATE-001, AMB-NOTIF-001, AMB-HUMAN-001, AMB-TESTGEN-001, AMB-PROVIDER-001, AMB-INDEX-001, AMB-VECTOR-001, AMB-UNIQUE-001 |
| 🟢 Low | 7 | AMB-SCALE-001, AMB-COMPLIANCE-001, AMB-AC-001, AMB-API-004, AMB-API-005, AMB-API-006, AMB-CLI-001 |

**Gate:** Architecture may begin only after the 🔴 and 🟠 items are resolved by the product owner. The presence of unresolved critical and high ambiguities drives the overall status to **PRD REQUIRES CLARIFICATION** (see [`PRD_COMPLETENESS_REPORT.md`](./PRD_COMPLETENESS_REPORT.md)).

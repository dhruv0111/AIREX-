# UX Acceptance Criteria — AIREX

Testable UX acceptance criteria for the AIREX web application. These complement the functional ACs in [`ACCEPTANCE_CRITERIA.md`](../PRD_ANALYSIS/ACCEPTANCE_CRITERIA.md) and make the design system's clarity promise verifiable. Each criterion is written as **Given / When / Then** and tagged to a page or flow.

---

## 1. The Seven Clarity Commitments (global)

These are the product-wide UX non-negotiables: the UI must make it obvious *what is happening, what completed, what failed, what to do next, where data is, where results are, and how to recover*.

| ID | Criterion (Given / When / Then) |
|----|----------------------------------|
| UX-CLARITY-001 | **What is happening:** Given an async job in progress, When the user views its page, Then a visible status indicator (stepper/progress with live counts) shows the current state and recent activity; the state is never ambiguous or missing. |
| UX-CLARITY-002 | **What completed:** Given a completed object (evaluation, report, export, version), When the user views or returns to it, Then it shows a persistent "Completed" status chip with a link to its results/artifact; success is not only a transient toast. |
| UX-CLARITY-003 | **What failed:** Given a failure, When the user sees it, Then a visible error banner shows the error code + human message + request id, and the record retains a persistent "Failed" chip. |
| UX-CLARITY-004 | **What to do next:** Given any non-terminal state (empty, error, permission, running), When the user views it, Then a clear primary CTA (or explained reason for none) is present; empty and error states always offer a next action or a recovery path. |
| UX-CLARITY-005 | **Where is my data:** Given any object, When it is displayed, Then its breadcrumb/parent path (project → section → object) is visible and navigable; every cross-reference is a link. |
| UX-CLARITY-006 | **Where are results:** Given a finished evaluation/experiment, When the user navigates to it, Then results/metrics and failure lists are reachable within ≤ 2 clicks from its parent, and report/export artifacts have ready download links. |
| UX-CLARITY-007 | **How to recover:** Given a failed/cancelled/expired operation, When the user views it, Then a recovery action is offered (Retry, Re-run, Resend, View error, Restore/back) appropriate to the failure class; recovery never requires the user to hunt for it. |

---

## 2. State Coverage Matrix (must hold for every page in PAGE_SPECIFICATIONS)

| Page | Loading | Empty | Error | Success | Permission | Mobile |
|------|---------|-------|-------|---------|-----------|--------|
| Login (P1) | ✓ spinner | — | ✓ invalid/rate-limit | ✓ redirect | public | ✓ |
| Register (P2) | ✓ | — | ✓ duplicate/weak | ✓ verify email | public | ✓ |
| Auth utils (P3) | ✓ | — | ✓ expired token | ✓ | public/token | ✓ |
| Main dashboard (P4) | ✓ skeleton | ✓ no projects | ✓ fetch error | ✓ refresh stamp | ✓ Viewer | ✓ |
| Projects list (P5) | ✓ | ✓ empty | ✓ | ✓ toast | ✓ create hidden | ✓ cards |
| Onboarding (P6) | ✓ | ✓ checklist | ✓ | ✓ complete | — | ✓ |
| Project dashboard (P7) | ✓ | ✓ checklist | ✓ model error | ✓ metrics | ✓ read-only | ✓ |
| Project settings (P8) | ✓ | — | ✓ validation | ✓ saved | ✓ prod-cred lock | ✓ |
| Models (P9) | ✓ | ✓ no models | ✓ test fail | ✓ ready | ✓ key masked | ✓ |
| Datasets list (P10) | ✓ | ✓ empty | ✓ | ✓ | ✓ | ✓ |
| Dataset detail (P11) | ✓ | ✓ no versions | ✓ row errors | ✓ version created | ✓ | ✓ |
| Tests (P12) | ✓ | ✓ no tests | ✓ gen failed | ✓ approved | ✓ approve hidden | ✓ |
| Evaluations list (P13) | ✓ | ✓ empty | ✓ | ✓ | ✓ | ✓ |
| Evaluation detail (P14) | ✓ | ✓ no failures | ✓ run failed | ✓ metrics | ✓ | ✓ |
| Evaluation run (P15) | ✓ live | — | ✓ failed | ✓ redirect | ✓ can't run | ✓ |
| Failure detail (P16) | ✓ | — | ✓ unknown | ✓ review saved | ✓ | ✓ tabs |
| Experiments (P17) | ✓ | ✓ no experiments | ✓ | ✓ compare | ✓ | ✓ cards |
| Prompts (P18) | ✓ | ✓ no versions | ✓ | ✓ | ✓ | ✓ |
| Traces (P19) | ✓ | ✓ no traffic | ✓ | ✓ | ✓ redacted | ✓ |
| Trace detail (P20) | ✓ | — | ✓ expired | ✓ | ✓ redacted | ✓ scroll |
| Alerts (P21) | ✓ | ✓ no rules | ✓ | ✓ saved | ✓ manage hidden | ✓ |
| Quality gate (P22) | ✓ | — | ✓ invalid | ✓ saved | ✓ | ✓ |
| Reports (P23) | ✓ | ✓ none | ✓ failed | ✓ ready | ✓ | ✓ |
| Research (P24) | ✓ | ✓ no research | ✓ | ✓ stats | ✓ | ✓ |
| Settings (P25) | ✓ | — | ✓ validation | ✓ saved | ✓ admin-only | ✓ |
| Audit logs (P26) | ✓ | ✓ no events | ✓ | ✓ | ✓ 403 non-admin | ✓ |
| 403/404/500 (P27) | — | — | ✓ informative | — | ✓ | ✓ |

---

## 3. Per-Flow UX Criteria (from USER_FLOWS)

| ID | Flow | Criterion |
|----|------|-----------|
| UX-FLOW-001 | F1 Onboarding | New user completes org→project→model in ≤ 3 steps; setup checklist persists until first evaluation; each checklist item is a working link. |
| UX-FLOW-002 | F4 Dataset upload | Upload shows progress; on completion shows success + version number; import failures show a row-level errors panel with a downloadable list; duplicate dataset id shows inline error before upload. |
| UX-FLOW-003 | F5 Test generation | Preview is required before approval; approved/rejected counts are always visible; rejected tests are visually excluded from run selection (AC-TESTGEN-005). |
| UX-FLOW-004 | F6 Evaluation run | Status stepper QUEUED→RUNNING→COMPLETED is visible and live; Cancel is available while running and confirms "completed results are kept"; reloading mid-run resumes progress (no restart). |
| UX-FLOW-005 | F7 Failure drill-down | From any failed count, the user reaches a failure detail in ≤ 2 clicks; detail shows all §71 fields; breadcrumb returns to the evaluation. |
| UX-FLOW-006 | F10 Baseline/regression | Baseline set is confirmable and reversible; regression result is a clear verdict banner (Pass/Warning/Regression Detected) with per-metric deltas. |
| UX-FLOW-007 | F11 CI/CD | CI-triggered runs are tagged `triggered_by=ci`; quality gate result (pass/fail + violations) is visible in the run and mirrored to the pipeline; failure maps to non-zero exit. |
| UX-FLOW-008 | F12 Traces | Time-range selection is always visible; redacted values render as `[REDACTED]`; expired traces explain retention rather than 404ing confusingly. |
| UX-FLOW-009 | F15 Research | Reproducibility metadata export is one action away from a completed research experiment (§81); significance is never claimed when sample size is insufficient (explicit note). |
| UX-FLOW-010 | F17 Permissions | Viewer never sees write actions; deep-linking a write as Viewer yields a 403 page with "Ask an admin"; cross-tenant deep links yield 404 (AC-SEC-002). |

---

## 4. Design System Criteria

| ID | Criterion |
|----|-----------|
| UX-DS-001 | All statuses are conveyed by color **plus** text/icon (never color-only). |
| UX-DS-002 | All text meets WCAG AA contrast; focus indicators visible on every interactive element. |
| UX-DS-003 | Loading never causes layout shift (skeletons match final layout). |
| UX-DS-004 | Error messages follow the error envelope (code + message + request id) and never expose stack traces. |
| UX-DS-005 | Destructive actions (delete, cancel, remove user) always require confirmation with explicit consequence copy. |
| UX-DS-006 | AI-generated explanations (RCA/recommendations) are visibly labeled as recommendations (FR-RCA-002, FR-RECO-003). |
| UX-DS-007 | Toast/success is always accompanied by a persistent state on the record (no success without a record state). |
| UX-DS-008 | Numbers use tabular figures; metric tiles include units + a definition tooltip. |
| UX-DS-009 | Reduced-motion preference disables non-essential animation. |

## 5. Accessibility Criteria (PRD §86)

| ID | Criterion |
|----|-----------|
| UX-A11Y-001 | Full keyboard navigation: every page is operable without a mouse; no keyboard traps in drawers/modals (Esc closes, focus returns). |
| UX-A11Y-002 | Semantic landmarks and heading order (single H1 per page) are correct. |
| UX-A11Y-003 | Forms: every input has a programmatically-associated label; errors linked via `aria-describedby`; required fields marked. |
| UX-A11Y-004 | Screen readers: icon-only controls have `aria-label`; async status updates use `role="status"`/`aria-live`; charts have text/table alternatives. |
| UX-A11Y-005 | Touch targets ≥ 44×44 px on interactive controls. |
| UX-A11Y-006 | Contrast: AA (4.5:1 text, 3:1 UI) verified in CI (axe). |

## 6. Performance UX Criteria (PRD §87)

| ID | Criterion |
|----|-----------|
| UX-PERF-001 | Dashboard first meaningful paint ≤ 3 s under normal conditions; skeleton-first so content is perceivable while metrics load. |
| UX-PERF-002 | Client-side navigations between project sections respond with instant feedback (top progress bar) and no white flashes. |
| UX-PERF-003 | Large lists (results/traces) virtualize on desktop and use pagination/"load more" on mobile without blocking scroll. |

## 7. Billing UX Criteria (future — AMB-BILLING-001)

| ID | Criterion (reserved, not implemented in V1) |
|----|------------------------------------------------|
| UX-BILL-001 | Plan/usage is visible in Settings; reaching a limit shows an actionable notice with upgrade or reset path, never a dead end. |
| UX-BILL-002 | Payment failure surfaces a clear alert and a resume path; invoices are downloadable. |

## 8. UX Verification Method

- **Automated:** axe-core in CI (a11y), Playwright E2E covering UX-FLOW-001..010 + the seven clarity commitments on all 27 pages.
- **Manual:** usability walkthrough per flow with the state matrix; visual regression snapshots at `sm/md/lg/xl`.
- **Coverage gate:** every page must satisfy its row in the §2 state matrix before it is considered complete (mirrors PRD §100 Definition of Done "UI tested").

## 9. PRD Traceability (UX)

| PRD | Where met |
|-----|-----------|
| §68 pages | PAGE_SPECIFICATIONS coverage table |
| §69–§71 dashboards/details/failures | P7, P14, P16 + clarity commitments |
| §86 accessibility | §5 a11y criteria + DESIGN SYSTEM §6 |
| §87 performance | §6 criteria |
| §50 main dashboard | P4 |
| §72–§73 human review/calibration | P16 + UX-FLOW-005/006 |
| §79–§80 reports/export | P23 + UX-CLARITY-006 |
| §83 score transparency | P7 + UX-DS-006 |
| §100 "UI tested" | §8 verification method |
| AC-AUTH-006 / AC-SEC-002 (Viewer/tenancy) | UX-FLOW-010 + §2 matrix |
| AMB-BILLING-001 | §7 reserved criteria (out of MVP) |

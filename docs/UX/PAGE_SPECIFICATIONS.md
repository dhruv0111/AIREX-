# Page Specifications — AIREX

Complete specifications for every major page. Each page defines: **Purpose · User · Entry points · Primary CTA · Secondary CTA · Components · Data · Actions · Loading · Empty · Error · Success · Permission · Mobile.**

State vocabulary is defined in [`DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md); flows in [`USER_FLOWS.md`](./USER_FLOWS.md).

---

## P1 — Login
- **Purpose:** Authenticate (AC-AUTH-003). **User:** existing user.
- **Entry:** `/login`, redirect when session expires.
- **Primary CTA:** "Sign in". **Secondary CTA:** "Create account", "Forgot password?".
- **Components:** email, password, show-password toggle, error alert, SSO placeholder (V3).
- **Data:** credentials → `/auth/login` (+cookie mode for SSR).
- **Actions:** sign in; continue to `/dashboard` or saved redirect.
- **Loading:** button spinner, disabled fields. **Empty:** n/a.
- **Error:** `AUTH_INVALID_CREDENTIALS` → inline alert "Email or password is incorrect"; `AUTH_EMAIL_UNVERIFIED` → "Verify your email — resend link"; rate-limited → "Too many attempts, try again in X min".
- **Success:** redirect to dashboard.
- **Permission:** public.
- **Mobile:** stacked single-column; 44px touch targets.

## P2 — Register
- **Purpose:** Create account (AC-AUTH-001/002). **User:** visitor.
- **Entry:** `/register`, login page link.
- **Primary CTA:** "Create account". **Secondary:** "Sign in".
- **Components:** name, email, password + strength meter, terms checkbox.
- **Actions:** submit → verification email (AC-AUTH-005).
- **Loading:** spinner. **Error:** duplicate email inline (AC-AUTH-002), weak password, network.
- **Success:** "Check your email to verify" screen.
- **Permission:** public. **Mobile:** single column.

## P3 — Auth utilities (Password Reset request/confirm · Verify email)
- **Purpose:** FR-AUTH-004/005. **User:** existing/new user.
- **Primary CTA:** "Send reset link" / "Reset password" / "Verify email".
- **States:** request → `✓` "If an account exists, we emailed a link" (no enumeration); confirm → `✓` "Password updated — sign in"; token expired → `⚠` "Link expired — request a new one" with CTA; verify → `✓` "Email verified" → redirect.
- **Permission:** public (token-gated). **Mobile:** single column.

## P4 — Main Dashboard (§50)
- **Purpose:** At-a-glance reliability of all projects; "is my AI good?" (§110). **User:** all.
- **Entry:** `/dashboard`, global nav.
- **Primary CTA:** "New project" / "New evaluation". **Secondary:** "View all projects", "View alerts".
- **Components:** Reliability score hero (with Δ), metric tiles (accuracy/hallucination/safety/latency/cost), Recent Evaluations list (✓/✗), Alerts feed, Regression chips.
- **Data:** `/api/v1/metrics?range=…`, recent runs, alerts.
- **Actions:** open evaluation, acknowledge alert, jump to project.
- **Loading:** skeleton hero + tiles. **Empty:** no projects → welcome + "Create your first project" (F1).
- **Error:** metrics fetch failed → banner + retry; degraded data labeled.
- **Success:** data renders with refresh stamp ("updated 30s ago").
- **Permission:** all (Viewer sees read-only).
- **Mobile:** hero stacks; tiles 2-col; alerts collapsed to list.

## P5 — Projects List
- **Purpose:** Manage AI applications. **User:** all.
- **Entry:** `/projects`, dashboard link.
- **Primary CTA:** "New project". **Secondary:** "Archive", "Delete" (confirm), per-project menu.
- **Components:** table/cards (name, app type, environment, archived, last evaluation score/status, members), search.
- **Data:** `/api/v1/projects` (paged).
- **Loading:** skeleton rows. **Empty:** "No projects yet" + create CTA.
- **Error:** fetch error → retry. **Success:** toast on create/archive/delete.
- **Permission:** create/edit = Admin/PO; Viewer read-only; delete shows confirmation (FR-PROJECT-004).
- **Mobile:** cards (not table).

## P6 — Onboarding Wizard (F1)
- **Purpose:** Guided first-run setup (org → project → model). **User:** new user.
- **Components:** progress stepper, form cards, setup checklist.
- **States:** as F1. **Mobile:** single-column stepper.

## P7 — Project Dashboard (§69)
- **Purpose:** Per-project reliability summary. **User:** all.
- **Entry:** project context nav "Dashboard".
- **Primary CTA:** "Run evaluation". **Secondary:** "Add model", "Upload dataset", "View failures".
- **Components:** Reliability Score card (configurable weights, transparent breakdown), metric grid (accuracy/hallucination/safety/latency/cost/error rate), latency percentiles (P50/P95/P99), recent evaluations, regression status chip, active alerts, setup checklist (until first eval).
- **Data:** `/api/v1/metrics?project_id=&scope=…`, runs, alerts.
- **Loading:** skeleton. **Empty:** checklist (no data yet) — each item links to the right page.
- **Error:** provider/model down → banner with model error (AC-MODEL-004).
- **Success:** current metrics + last updated time.
- **Permission:** Viewer read-only (no Run button).
- **Mobile:** metrics become stacked tiles; charts swipeable.

## P8 — Project Settings / Overview
- **Purpose:** Edit project config (§11) + environments (§77). **User:** Admin/PO.
- **Primary CTA:** "Save changes". **Secondary:** "Archive project", "Delete project" (double-confirm, FR-PROJECT-004).
- **Components:** form (name, description, app type, environment, endpoint, auth), environments section (dev/staging/prod with per-env model/credentials/policies).
- **States:** `✓` "Saved" · `⚠` validation errors · `🔒` production env credentials require elevated role (FR-ENV-003) → masked + "request access".
- **Mobile:** stacked forms.

## P9 — Models (§12)
- **Purpose:** Configure providers/models. **User:** Admin/PO manage; all view.
- **Entry:** Project → Models.
- **Primary CTA:** "Add model". **Secondary:** "Test connection" per row, "Replace key".
- **Components:** provider cards (OpenAI/Anthropic/Gemini/Ollama/…), model list (name, ref, latency, status), config form (temperature/max tokens/timeout/retry).
- **Data:** `/api/v1/models`.
- **Loading:** skeleton. **Empty:** "Connect your first model" + supported providers.
- **Error:** test fails inline (AC-MODEL-002..004). **Success:** "Model ready".
- **Permission:** Viewer read-only; keys masked (FR-PROVIDER-008).
- **Mobile:** cards.

## P10 — Datasets List
- **Purpose:** Manage datasets. **User:** Admin/PO/E manage; all view.
- **Primary CTA:** "Upload dataset". **Secondary:** "New from manual entry".
- **Components:** table (name, dataset id, format, versions count, rows, updated), search.
- **States:** as F4. **Permission:** Viewer read-only. **Mobile:** cards.

## P11 — Dataset Detail (Versions & Compare)
- **Purpose:** View versions, immutability, compare (FR-DATASET-011). **User:** all.
- **Primary CTA:** "Create new version" (from edits). **Secondary:** "Download", "Compare versions".
- **Components:** version timeline (v1/v2/v3 with immutable badges), row preview, schema summary, compare split view (diff highlights).
- **States:** `∅` no versions → empty; `⚠` import row errors → panel; `✓` version created toast.
- **Permission:** create = Admin/PO/E. **Mobile:** timeline stacks; compare toggles.

## P12 — Tests (§26–§27)
- **Purpose:** Test cases + AI generation + approval. **User:** Admin/PO/E; all view.
- **Primary CTA:** "Generate tests". **Secondary:** "Approve all", "Reject", filters by category/approval.
- **Components:** generation panel (count, inputs), preview list with category chips + approval controls, counts (approved/rejected), version history.
- **States:** as F5. **Permission:** approve/reject = Admin/PO/E; Viewer read-only.
- **Mobile:** chips scroll horizontally; approve via swipe actions.

## P13 — Evaluations List
- **Purpose:** History of evaluation runs. **User:** all.
- **Primary CTA:** "New evaluation". **Secondary:** filter by status/trigger; "CI runs" toggle.
- **Components:** table (id, dataset v, model, prompt v, status, score, triggered_by badge, time), search.
- **States:** standard. **Mobile:** cards.

## P14 — Evaluation Detail (§70)
- **Purpose:** Results summary + drill-down. **User:** all.
- **Entry:** evaluations list / completion redirect / dashboard.
- **Primary CTA:** "View failures (31)". **Secondary:** "Export", "Set as baseline", "Re-run", "Open report".
- **Components:** header (status, dataset v4, model X, prompt v7, environment, triggered_by), metric grid (accuracy 92%, faithfulness 94%, safety 98%), P95 latency + cost, PASS/FAIL/WARNING counts, regression + quality gate chips, failure list.
- **Data:** `/api/v1/evaluations/{id}`, runs, results.
- **Loading:** skeleton. **Empty:** no failures → "All tests passed 🎉". **Error:** run failed → banner + error detail + retry.
- **Success:** completed + metrics visible.
- **Permission:** Viewer read-only.
- **Mobile:** metrics grid → stacked; failures list.

## P15 — Evaluation Run (Live Progress) (J8, §102 step 7)
- **Purpose:** Monitor async run. **User:** Admin/PO/E.
- **Primary CTA:** "Cancel run" (confirm). **Secondary:** "View partial results".
- **Components:** status stepper (QUEUED→RUNNING→COMPLETED/FAILED), live counts, progress bar, SSE feed, log of errors.
- **States:** `⏳` running with live updates · `✓` completed auto-redirect · `⚠` failed banner · `🔒` Viewer can't run.
- **Recovery:** reload resumes; partial results visible (§89).
- **Mobile:** compact stepper.

## P16 — Failure / Test Result Detail (§71)
- **Purpose:** Why did this test fail. **User:** all.
- **Entry:** evaluation failures → row.
- **Components:** Question, Expected, Actual (diff-highlighted), Retrieved Context, Scores per evaluator, Failure Classification chip (RETRIEVAL_FAILURE…), Reason, Explanation, Trace link, Human Review panel (P2), actions (re-run single, copy, export).
- **States:** `⚠` classification "unknown" → muted + manual tools · `✓` review saved.
- **Mobile:** tabbed sections (Question/Answer/Context/Score/Trace).

## P17 — Experiments List & Compare (§32–§34)
- **Purpose:** Benchmark & compare. **User:** Admin/PO/E; all view.
- **Primary CTA:** "New experiment". **Secondary:** "Compare", "Set baseline".
- **Components:** experiment cards (dataset/model/prompt/config/metrics, immutable badge), compare table (side-by-side, §32), weighted score + "best" highlight.
- **States:** as F9. **Permission:** create = Admin/PO/E; Viewer read-only.
- **Mobile:** compare table → stacked comparison cards.

## P18 — Prompts (§33)
- **Purpose:** Prompt versions + experimentation. **User:** Admin/PO/E.
- **Primary CTA:** "New prompt version". **Secondary:** "Run comparison".
- **Components:** version list (v1/v2/v3, immutable), editor, comparison of accuracy/hallucination/latency/cost/safety across versions.
- **States:** standard. **Mobile:** editor full-width.

## P19 — Traces List (§41–§42)
- **Purpose:** Production observability. **User:** all.
- **Primary CTA:** time-range picker. **Secondary:** filter by status/model/error.
- **Components:** range selector (15m/1h/24h/7d/30d/custom), trace rows (request id, model, status, latency, tokens, cost), summary tiles (requests, errors, error rate).
- **States:** `∅` no traffic → extend range CTA. **Permission:** redaction applied per project settings (FR-OBS-007).
- **Mobile:** range chips + list.

## P20 — Trace Detail (§42)
- **Purpose:** Inspect a request step-by-step. **User:** all.
- **Components:** waterfall (user_request → retriever → documents → prompt_builder → llm → evaluator → response), per-step duration/input/output/metadata/error, redacted values `[REDACTED]`.
- **States:** `⚠` trace expired (retention) → notice + retention info; `⚠` error step highlighted.
- **Mobile:** horizontal scroll waterfall.

## P21 — Alerts (§43–§44)
- **Purpose:** Rules + feed. **User:** Admin/PO manage; all view.
- **Primary CTA:** "New rule". **Secondary:** "Acknowledge", "Resolve", "Disable".
- **Components:** rule builder (type/severity/threshold/duration/cooldown/channel/enabled), rules list with toggles, firing feed with severity colors, example rules (§44).
- **States:** `∅` no rules → examples; `🔴` firing alerts prominent; `✓` rule saved.
- **Mobile:** rule builder → step form.

## P22 — Quality Gate (§39)
- **Purpose:** Configure gate thresholds. **User:** Admin/PO.
- **Primary CTA:** "Save thresholds". **Secondary:** "Last evaluation result".
- **Components:** threshold rows (accuracy min, hallucination max, safety min, P95 max, cost max), enabled toggles, last-run gate summary.
- **States:** `✓` saved · `⚠` invalid bounds inline · `🔴` last gate fail listing violations.
- **Mobile:** stacked rows.

## P23 — Reports & Exports (§79–§80)
- **Purpose:** Generate & download artifacts. **User:** all (generate Admin/PO/E).
- **Primary CTA:** "Generate report". **Secondary:** "Export" menu, "Download".
- **Components:** report list (scope, format, status, artifact), generator form, artifact links (presigned).
- **States:** `⏳` generating · `✓` ready · `⚠` failed retry · `∅` none yet.
- **Mobile:** cards.

## P24 — Research Workspace (§47–§49)
- **Purpose:** Research experiments & statistics. **User:** Admin/PO/E (create); all view.
- **Primary CTA:** "New research project". **Secondary:** "Export reproducibility metadata".
- **Components:** research project list, hypothesis form, baseline/treatment config, metrics, results charts, statistics panel (mean/median/std/percentile/CI/effect size), conclusions editor, report (12 sections §49).
- **States:** `⏳` stats computing · `✓` results + charts · `⚠` significance not claimed note (FR-RESEARCH-012) · `∅` no research → template example.
- **Mobile:** charts full-width, tables scroll.

## P25 — Settings (profile / organization / api-keys / webhooks)
- **Purpose:** Account + org config + privacy toggles (§60). **User:** all (profile); Admin for org-level.
- **Primary CTA:** "Save". **Secondary:** "Regenerate key", "Add webhook".
- **Components:** tabs; privacy toggles (raw storage, PII masking, prompt storage, response storage) with explainers; API keys (created once, masked); webhooks (URL/events/secret shown once); member management (invite/role/remove).
- **States:** `✓` saved · `⚠` validation · `🔒` Admin-only sections hidden for others.
- **Mobile:** tabs → accordion.

## P26 — Audit Logs (§61)
- **Purpose:** Security review. **User:** Admin only.
- **Primary CTA:** filters. **Secondary:** export.
- **Components:** filterable table (actor, action, resource, time, ip, result), detail drawer.
- **States:** `∅` "No events yet". **Permission:** non-admin → 403.
- **Mobile:** list rows + filter sheet.

## P27 — 403 / 404 / 500
- **Purpose:** Error recovery. **User:** any.
- **403:** "You don't have permission" + "Ask an admin" + back. **404:** "Not found or moved" + back to projects (AC-SEC-002 anti-enumeration). **500:** "Something went wrong" + request id + retry + status page.
- **Mobile:** same, centered.

## P28 — Billing (out of MVP scope — see AMB-BILLING-001)
- **Purpose:** Documented placeholder so billing states have a home when the product owner adds them. **User:** Admin.
- **States defined for future:** plan summary, usage meters (evaluation count, storage), upgrade CTA, payment failure notice, invoice download, grace-period banner with "resume" path, plan-limit enforcement notices ("You've reached your monthly evaluation limit — upgrade or wait for reset").
- **Note:** not implemented in V1; included here to satisfy "billing states" completeness with an explicit out-of-scope marker.

---

## Page Coverage vs PRD §68
| PRD route | Spec |
|-----------|------|
| /login, /register | P1, P2 |
| /dashboard | P4 |
| /projects, /projects/:id | P5, P7 |
| /projects/:id/models | P9 |
| /projects/:id/datasets | P10, P11 |
| /projects/:id/tests | P12 |
| /projects/:id/evaluations | P13, P14, P15, P16 |
| /projects/:id/experiments | P17 |
| /projects/:id/prompts | P18 |
| /projects/:id/traces | P19, P20 |
| /projects/:id/alerts | P21 |
| /projects/:id/reports | P23 |
| /research | P24 |
| /settings | P25 |
| /audit-logs | P26 |

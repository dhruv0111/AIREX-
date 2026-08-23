# User Flows — AIREX

End-to-end interaction flows. Each flow includes: **entry, steps, decision points, states (loading/empty/error/success/permission), and recovery**. Flows map to the journeys in [`USER_JOURNEYS.md`](../PRD_ANALYSIS/USER_JOURNEYS.md) and the PRD's flagship journey (§102) and MVP release gate (§109).

Legend: `⏳` loading · `∅` empty · `⚠` error · `✓` success · `🔒` permission/blocked · `↩` recovery

---

## F1 — First-run Onboarding (J1, J2, §102 steps 1–4)

1. **Entry:** `/register` → create account (email+password). `⏳` button spinner; `⚠` inline field errors (duplicate email, weak password); `✓` "Check your email to verify." 
2. Verify email (link) → auto-login → redirect `/onboarding`.
3. **Onboarding wizard (3 steps, progress bar, skippable):**
   - **Step 1 — Organization:** create/name org (or auto-created personal org). `∅` none; `✓` org created (creator = Admin).
   - **Step 2 — Project:** create project (name, app type, environment, endpoint). `✓` project created.
   - **Step 3 — Connect model:** add provider + model (Ollama default hint) or "do this later." `⚠` invalid key → inline error (AC-MODEL-002). `✓` model tested OK.
4. **Post-onboarding:** land on **Project Dashboard**; a **setup checklist card** remains until the first evaluation completes:
   `[x] Organization [x] Project [x] Model [ ] Dataset [ ] Test cases [ ] First evaluation`
   Each item is a link to the right section. `↩` returning users resume at the checklist item.
5. `🔒` Viewer role can't see the checklist CTAs (view-only).

## F2 — Create / Configure Project (J4)

- **Entry:** `/projects` → "New project" (or onboarding Step 2).
- **Steps:** name → description → application type → environment → endpoint → endpoint auth (optional) → model config (optional) → evaluation config (optional, defaults).
- **States:** `⏳` submit spinner · `⚠` validation errors inline · `✓` toast "Project created" → redirect to project dashboard · `🔒` non-owner sees no create CTA.
- **↩ Recovery:** edit via Project Settings; validation failures preserved (no data loss).

## F3 — Connect / Test a Model (J5, AC-MODEL-001..004)

- **Entry:** Project → Models → "Add model."
- **Steps:** choose provider type → fill model, API key, base URL, temperature, max tokens, timeout, retry policy → **"Test connection"** (optional, recommended) → Save.
- **States:** `⏳` "Testing…" · `✓` "Connection OK — latency 320 ms" · `⚠` "Invalid API key" (AC-MODEL-002) / "Timed out" (AC-MODEL-003) / "Provider error: 429" (normalized, AC-MODEL-004) — inline, with hint to fix.
- **Secret handling:** key input shows masked after save; "Reveal" never available; only "Replace" (FR-PROVIDER-008).
- `🔒` Viewer: models read-only.

## F4 — Upload & Version a Dataset (J6, FR-DATASET-008..013)

- **Entry:** Project → Datasets → "Upload dataset."
- **Steps:** name + dataset id → drag-drop file (CSV/JSON/JSONL) or manual entry → format auto-detected → **Upload** → async parse (show progress) → preview rows → Save as version.
- **States:** `⏳` upload progress bar · `⏳` parsing "Processing 1000 rows…" · `⚠` **row-level errors panel** "995 imported, 5 failed" with per-row reason and Download-failed-rows · `⚠` duplicate dataset id → inline error (FR-DATASET-013) · `✓` "Dataset v1 created" → version history.
- **Versioning:** any subsequent edit creates **v2** (never silently mutates); version rows labeled immutable; compare view (`v1 ⟷ v2`) highlights differences (FR-DATASET-011).
- `🔒` Viewer: read-only.

## F5 — AI Test Generation & Approval (J7, AC-TESTGEN-001..006)

- **Entry:** Project → Tests → "Generate tests."
- **Steps:** configure count + inputs (app description, dataset version, docs, existing tests) → **Generate** (async) → **Preview list** → Approve/Reject per test (bulk or individual) → "Use approved" → tests become executable.
- **States:** `⏳` generation progress ("Generating 100 categorized cases…") · `✓` preview ready with category chips (normal/edge/adversarial/ambiguous/safety/prompt-injection/long-context/multilingual) · `⚠` generation failed / rate-limited → retry · `∅` no tests yet → empty state with "Generate" CTA.
- **Approval:** counts "Approved 80 / 100"; **rejected tests never enter runs** (AC-TESTGEN-005). Versions shown per generation (AC-TESTGEN-006).
- `🔒` Viewer: view-only; approval buttons hidden.

## F6 — Run & Monitor an Evaluation (J8, §56–§57, §102 step 7)

- **Entry:** Project → Evaluations → "New evaluation" → configure (dataset version, model, prompt version, evaluators, config) → **Run**.
- **Steps:** Run → **202 job created** → live progress screen:
  - Status stepper: `QUEUED → RUNNING → COMPLETED` (or FAILED/CANCELLED) with live counts (total/completed/passed/failed/warning) via SSE.
  - **Cancel** button while running (FR-ASYNC-009) with confirm dialog "Cancel? Completed results are kept."
- **States:** `⏳` skeleton + progress · `✓` Completed → auto-navigate to results summary · `⚠` Failed → banner with error code + "View error" + "Retry" (transient) · `🔒` Viewer cannot run (button hidden).
- `↩` **Recovery:** interrupted runs resume on reload (job survives restart, §88); partial results visible immediately (§89).

## F7 — Review Evaluation Results & Drill into Failures (J9, §70–§71)

- **Entry:** Evaluation detail (from list or completion redirect).
- **Steps:** summary header (status, dataset v4, model X, prompt v7, metrics grid) → PASS/FAIL/WARNING counts → click **"View failures (31)"** → failure list → click a failure → **Failure detail**.
- **Failure detail (§71):** Question · Expected Answer · Actual Answer · Retrieved Context · Scores · Failure Classification · Reason · Trace link · Explanation.
- **States:** `∅` no failures → success message "All 952 tests passed" · `⏳` lazy-load failure list · `⚠` failure detail fetch error → retry · `✓` breadcrumb back to evaluation.
- **Recovery:** from failure detail, "Copy test case", "View trace", "Re-run single test", "Mark for human review."

## F8 — Human Review & Calibration (J10, §72–§73)

- **Entry:** Evaluation results → failed/uncertain items show "Needs review" filter; or Project → Reviews queue.
- **Steps:** open item → see AI verdict + explanation → choose **Human verdict**: `Pass`, `Fail`, `False Positive`, `Skip` + optional comment → Save (stored, FR-HUMAN-003).
- **States:** `∅` empty review queue → "Nothing to review" · `✓` toast "Decision saved" + next item · `⚠` conflict (already reviewed) → prompt to edit.
- **Calibration:** sampling panel compares AI vs Human agreement (§73) with chart; low-confidence items auto-queued (FR-JUDGE-004).

## F9 — Model Comparison (J11, §32, §76, §102 steps 11–12)

- **Entry:** Project → Experiments → "Compare models."
- **Steps:** select 2+ models → pick identical dataset version + config (system enforces same test cases/evaluator/config — FR-BENCH-004) → **Run** → side-by-side table + weighted score.
- **States:** `⏳` running comparisons · `✓` table (accuracy/hallucination/latency/cost) + score + "Best overall" highlight · `⚠` config mismatch → explainer warning · `∅` no models → empty state linking to Models.
- `🔒` Viewer: read-only.

## F10 — Baseline & Regression (J13, §36–§37, §102 steps 13–15)

- **Entry:** Experiment detail → "Set as baseline" (confirm; label) → later, run a new experiment → "Compare to baseline."
- **Steps:** select baseline vs candidate → **Run regression** → result banner: `✓ Pass` | `⚠ Warning` | `🔴 Regression Detected` with per-metric deltas (accuracy ↓5%, hallucination ↑5%).
- **States:** `∅` no baseline → "No baseline set" CTA · `⚠` regression detected → dashboard banner + alert + optional CI callback · `↩` adjust thresholds via Quality Gate config, re-run.
- Dashboard reflects regression status chip (FR-DASH-004).

## F11 — CI/CD Trigger & Quality Gate (J14, §38–§40)

- **Entry:** GitHub Actions workflow (external) → CLI/API → user sees result in pipeline logs and in AIREX.
- **Steps:** CI calls `POST /evaluations/{id}/run` (API key) → polls → quality gate evaluated → exit 0 / non-zero (AC-CICD-003/004) → completion webhook.
- **UI counterpart:** Quality Gate config page (thresholds §39) with save + "last evaluated" summary; CI activity shown in Evaluations list (`triggered_by=ci` badge).
- **States:** `⏳` "Waiting for CI evaluation…" · `✓` gate pass · `⚠` gate fail with violated metrics (BUILD FAILED) · `🔒` configure = Admin/PO.

## F12 — Observability & Trace Inspection (J15, §41–§42)

- **Entry:** Project → Traces (or dashboard "view traces").
- **Steps:** time-range picker (15m/1h/24h/7d/30d/custom, §41) → trace list (status, model, latency, cost) → open trace → waterfall of steps (user_request → retriever → documents → prompt_builder → llm → evaluator → response) with per-step duration/input/output/error.
- **States:** `⏳` skeleton while loading · `∅` no traces in range → "No traffic in this window" + extend range CTA · `⚠` trace not found (retention) → explanatory empty state · `🔒` redacted content shown as `[REDACTED]` per privacy toggles (FR-OBS-007).

## F13 — Alerts Configuration & Feed (J16, §43–§44)

- **Entry:** Project → Alerts → "New rule."
- **Steps:** pick type → severity → threshold/operator → duration → cooldown → channel(s) (in-app/email/webhook) → enable → Save → rules list (enabled toggle).
- **States:** `∅` no rules → empty state with example rules ("P95 > 3s for 10 min" §44) · `✓` "Rule saved and active" · `⚠` invalid threshold → inline error · `🔴` firing alerts in feed with severity color + resolve/ack actions.
- `🔒` create/edit = Admin/PO; Viewer sees feed only.

## F14 — Reports & Export (J18, §79–§80)

- **Entry:** Project → Reports → "Generate report."
- **Steps:** pick scope (evaluation/experiment) + format (Markdown/PDF/JSON/CSV) → **Generate** (async) → status → download.
- **States:** `⏳` "Generating…" · `✓` "Ready" + download button (presigned) · `⚠` "Failed — retry" · `∅` no reports yet → empty state + CTA.
- **Export flow:** any results page → "Export" menu → same async pattern; artifact link emailed optionally (FR-NOTIFY).

## F15 — Research Experiment (J19, §102 step 18)

- **Entry:** /research → "New research project" → hypothesis → variables (baseline/treatment) → dataset → metrics → **Run**.
- **Steps:** run → statistics panel (mean/median/std/percentile/CI/effect size §48) → charts → conclusions → **Publish metadata** (§81).
- **States:** `⏳` stats computing · `✓` results + charts · `⚠` significance not claimed (sample too small) → explicit note (FR-RESEARCH-012) · `∅` no research yet → empty state + template ("Does hybrid retrieval improve RAG quality vs dense?" §47 example).
- **Reproducibility (J20):** "Export reproducibility metadata" button (§81) → JSON with dataset version/model/prompt/config/seed.

## F16 — Admin Management (J3, §10)

- **Entry:** Settings → Members/API keys/Webhooks; Audit Logs.
- **Steps:** invite (email+role) → member list → change role / remove (confirm; immediate access loss AC-SEC-004).
- **States:** `⏳` invite sending · `✓` "Invite sent" · `⚠` duplicate/invalid email · `🔒` only Admin sees management UI.
- Audit Logs: filterable table (action/resource/user/time/ip/result); `∅` empty → "No events yet."

## F17 — Permission / Forbidden States (AC-AUTH-006, AC-SEC)

- Viewer attempts write → UI hides the action; if a deep link is attempted, show **403 page** "You don't have permission to do this" + "Ask an admin" + back link (never a broken page).
- Cross-tenant deep link → **404** (anti-enumeration, AC-SEC-002) with "Not found or moved" + back to projects.

---

## Flow → PRD Traceability

| Flow | PRD / Journey |
|------|---------------|
| F1 | §9, §10, §102 steps 1–4, J1/J2 |
| F2 | §11, J4 |
| F3 | §12–§14, AC-MODEL-*, J5 |
| F4 | §15–§16, FR-DATASET-*, J6 |
| F5 | §26–§27, AC-TESTGEN-*, J7 |
| F6 | §56–§57, §102 step 7, J8 |
| F7 | §70–§71, J9 |
| F8 | §72–§75, J10 |
| F9 | §32, §76, J11 |
| F10 | §36–§37, J13 |
| F11 | §38–§40, AC-CICD-*, J14 |
| F12 | §41–§42, J15 |
| F13 | §43–§44, J16 |
| F14 | §79–§80, J18 |
| F15 | §47–§49, §81, J19/J20 |
| F16 | §10, §61, J3 |
| F17 | AC-AUTH-006, AC-SEC-001/002 |

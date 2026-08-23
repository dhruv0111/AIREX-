# Design System — AIREX

The visual and interaction design system. Stack: Tailwind CSS (PRD §67) + Recharts. Covers tokens, components, **the clarity system** (what is happening / completed / failed / next), states, accessibility (§86), and data visualization.

---

## 1. Design Tokens

### 1.1 Color (semantic, contrast-safe per §86)

| Token | Value | Use |
|-------|-------|-----|
| `bg-base` | #F8FAFC | page background |
| `bg-surface` | #FFFFFF | cards/surfaces |
| `bg-muted` | #F1F5F9 | muted panels |
| `text-primary` | #0F172A | headings |
| `text-secondary` | #475569 | body |
| `text-muted` | #94A3B8 | captions/placeholders |
| `border-default` | #E2E8F0 | hairlines |
| `accent` (brand) | #4F46E5 | primary actions, links, score accent |
| `success` | #16A34A | pass, completed, positive deltas |
| `warning` | #D97706 | warning, partial, WARNING status |
| `danger` | #DC2626 | fail, regression, critical alerts, destructive |
| `info` | #0284C7 | info, queued/running accents |
| `neutral` | #64748B | cancelled, skipped, unknown |

All text-on-color pairs meet WCAG AA (§86). Status colors never used as the *only* signal — always paired with text/icon (§86 + clarity).

### 1.2 Typography
| Token | Value |
|-------|-------|
| Family | Inter (system fallback) |
| Scale | 12/14/16/20/24/32 (caption/body/large/title/h1/display) |
| Monospace | ui-monospace (IDs, JSON, prompts, traces) |
| Numeric | tabular-nums for metrics (alignment) |

### 1.3 Spacing / Radius / Shadow / Z
- Spacing: 4px scale (4,8,12,16,24,32,48).
- Radius: `sm 6` `md 10` `lg 14` `full`.
- Shadow: `sm`, `md` (elevated cards, modals), `lg` (drawers).
- Z-index scale: `sticky 30 · header 40 · overlay 50 · modal 60 · toast 70 · tooltip 80`.
- Motion: 150–250 ms ease-out; respect `prefers-reduced-motion` (disable/limit).

---

## 2. The Clarity System (core requirement)

Every screen must answer 7 questions. Mapping to components:

| Question | Component |
|----------|-----------|
| **What is happening?** | Status banner / stepper / progress + contextual label ("Running — 80/100 tests") |
| **What completed?** | Success toast + state chip + persisted "Completed" on records |
| **What failed?** | Error banner (code + message + request id) + red state chip + failure list |
| **What should the user do next?** | Primary CTA always visible; empty/error states carry a next-action CTA |
| **Where is my data?** | Breadcrumb + object breadcrumb ("Project › Dataset › v2") + links from every reference |
| **Where are results?** | "Results" section on evaluation; report/export list with ready links |
| **How to recover?** | Retry button, "view error", cancel (with keep-results note), resend/regenerate, status page link |

### 2.1 Status vocabulary (consistent global chip set)

| Status | Color | Icon | Meaning + next action |
|--------|-------|------|-----------------------|
| `Draft` | neutral | file | not run — CTA: Run |
| `Queued` | info | clock | waiting — CTA: wait/cancel |
| `Running` | info | spinner | in progress — CTA: view progress/cancel |
| `Completed` | success | check | done — CTA: view results |
| `Failed` | danger | x | stopped — CTA: view error/retry |
| `Cancelled` | neutral | stop | stopped by user — CTA: re-run |
| `Pass` | success | check | met threshold |
| `Warning` | warning | triangle | partial — CTA: review |
| `Regression Detected` | danger | trending-down | broke baseline — CTA: view deltas |
| `Approved` / `Rejected` / `Pending` | success/danger/neutral | — | test approval (AC-TESTGEN-004) |
| `Archived` | neutral | archive | read-only |
| `Unknown` | neutral | question | evaluator indeterminate (AC-HALL-005) |

---

## 3. State Conventions

### 3.1 Loading (`⏳`)
- **Skeleton components** that mirror final layout (no layout shift); spinners only for inline actions.
- Buttons: spinner + disabled; forms: `aria-busy`.
- Async jobs: progress bar + live counts + "last updated Xs ago".
- Full-page: top-of-page slim progress bar (Next.js navigation).

### 3.2 Empty (`∅`)
Standard EmptyState component: **icon + title + description + primary CTA (+ optional secondary)**. Copy explains *why it's empty and what to do* (e.g., "No traces in the last 24h — extend the range or wait for traffic").
Types: `no-data`, `no-results (filter)`, `no-permission-action (see locked)`, `not-yet-configured`.

### 3.3 Error (`⚠`)
**ErrorBanner** at top of the affected region: severity icon + message (from error envelope: code/message/request_id) + actions (Retry / View details / Go to status).
- Inline field errors: under the field, red text + `aria-describedby`.
- Full-page fatal: ErrorPage with request id + retry + support link.
- Errors never expose stack traces (§63).

### 3.4 Success (`✓`)
- **Toast** (top-right, auto-dismiss): "Dataset v1 created", "Rule saved and active", "Report ready".
- Inline success states (form saved indicator), and persisted status chips on records.

### 3.5 Permission (`🔒`)
- **Hidden actions** for unauthorized roles (never render buttons the user can't use) — Viewer sees read-only view (AC-AUTH-006).
- **Locked affordance** for known-but-unpermitted actions (e.g., production credentials in dev env → "Request access", FR-ENV-003).
- **403 page** with "Ask an admin" path.
- Tooltips explain *why* when an action is disabled (e.g., "Requires Admin").

### 3.6 Billing (future, out of MVP — AMB-BILLING-001)
Reserved patterns: plan banner, usage meters, upgrade CTA, limit-reached notice with resume path, payment-failure alert. Documented, not implemented in V1.

---

## 4. Core Components

| Component | Notes |
|-----------|-------|
| **Button** | variants: primary / secondary / ghost / danger / link; sizes sm/md/lg; loading + disabled; 44px min touch target (mobile) |
| **IconButton** | for row actions; always has `aria-label` |
| **Input / Select / Textarea** | labeled (floating or top), required marks, error + hint text, password with show toggle |
| **Toggle** | enabled/disabled for rules and privacy toggles (§60) |
| **Table** | sticky header, sortable columns, row selection, numeric tabular alignment; mobile transforms to cards (see RESPONSIVE) |
| **Card** | surface container; optional header actions; used for metrics, objects |
| **MetricTile** | label + value + unit + delta (↑↓ with color) + sparkline; title/tooltip with definition |
| **Badge/Chip** | status vocabulary (§2.1); category chips for tests |
| **StatusBanner** | page-level state (running/failed/regression) with actions |
| **Toast** | success/info/warning/error; action links |
| **Modal** | confirmations (delete, cancel, set baseline) with explicit consequences; focus trap |
| **Drawer** | detail side panels (failure detail, member detail, trace event) |
| **Stepper** | evaluation status QUEUED→RUNNING→COMPLETED; onboarding progress |
| **Tabs / Accordion** | detail page sections; mobile fallback |
| **Skeleton** | loading placeholders |
| **EmptyState** | §3.2 |
| **CommandPalette** | Cmd/Ctrl+K global search |
| **Breadcrumb** | project context + object path |
| **FileDropzone** | dataset upload with format validation + progress |
| **DiffViewer** | expected vs actual answer highlight; version compare |
| **Waterfall** | trace step timeline (P20) |
| **FeedbackForm** | human review (PASS/FAIL/FALSE POSITIVE/comment) |
| **Tooltip/Help** | metric definitions, threshold explanations |

---

## 5. Data Visualization (Recharts)

| Chart | Used for |
|-------|----------|
| **ScoreRing/Gauge** | AI Reliability Score hero (0–100, delta) |
| **LineChart** | trends: accuracy/hallucination/latency/cost over time |
| **BarChart** | model comparison, category distribution |
| **RadarChart** | reliability score breakdown (§83 weights) |
| **PercentileBars** | P50/P95/P99 latency (§30) |
| **Sparkline** | inline metric trends in tiles |
| **Pie/Donut** | model distribution (§41), failure classification |
| **ScatterPlot** | research (baseline vs treatment, effect size) |

Rules: always labeled; units explicit; tooltips with exact values; no 3D; accessible `aria-label` summaries + data tables for screen readers (§86).

---

## 6. Accessibility (PRD §86) — token-level commitments

- Keyboard navigation: all interactive elements reachable/focusable; visible focus ring (`focus-visible`).
- Semantic HTML: `main/nav/header/h1..h3/table/form/label`.
- Contrast: WCAG AA (4.5:1 text, 3:1 UI).
- Screen readers: `aria-label` on icon buttons, `aria-live` on toasts/status updates, `aria-describedby` on errors, `role="status"` for async progress.
- Forms: labels + required indicators + error association.
- Reduced motion respected.

## 7. Copywriting / Tone

- Action-first, concrete, no jargon: "Run evaluation", not "Execute pipeline".
- Errors say *what happened + what to do*: "Model timed out (MODEL_TIMEOUT). Retry or increase the timeout in Models."
- Empty states teach the next step.
- AI-generated content (RCA/recommendations/score) labeled: "AI recommendation — review before applying" (FR-RCA-002, FR-RECO-003).

## 8. PRD Traceability (DESIGN)

| PRD | Element |
|-----|---------|
| §83 score transparency | ScoreRing + weight breakdown |
| §70–§71 results clarity | §2 clarity system + status vocabulary |
| §43–§44 alert severity | severity colors + feed |
| §60 privacy | redacted `[REDACTED]` render + toggle explainers |
| §86 accessibility | §6 |
| §72 human review | FeedbackForm + decisions stored |
| §46 recommendations reviewable | labeled AI recommendations + approve before apply |

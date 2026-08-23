# Frontend Architecture — AIREX Web App

**Stack (PRD §67):** Next.js, React, TypeScript, Tailwind CSS, Recharts — all free/open-source.
**Delivery:** Server-rendered Next.js app (App Router) served from the same deployment target as the API (or CDN). No paid frontend dependencies.

---

## 1. Goals & Constraints

| Goal | Constraint source |
|------|-------------------|
| Initial dashboard load < 3 s (§87) | SSR shell + code splitting + cached metrics |
| Pages per PRD §68 | Must render all listed routes |
| Accessibility per §86 | WCAG AA baseline, semantic HTML, focus states, keyboard nav |
| Real-time job/alert status | SSE/WebSocket for evaluation progress and alerts |
| Charts | Recharts (P50/P95/P99, trend lines, distributions, radar) |
| Human review & approval workflows | Interactive client components |

---

## 2. Routing Map (PRD §68)

| Route | Type | Data |
|-------|------|------|
| `/login`, `/register` | Public pages | Auth forms |
| `/dashboard` | Private, org-scoped | Reliability score, recent evaluations, alerts (§50) |
| `/projects` | Private list | Projects list |
| `/projects/:id` | Private | Project dashboard (§69) |
| `/projects/:id/models` | Private | Model config + provider management |
| `/projects/:id/datasets` | Private | Dataset list, upload, version compare (§16) |
| `/projects/:id/tests` | Private | Test cases, test generation preview/approve (§27) |
| `/projects/:id/evaluations` | Private | Evaluations list + details (§70) |
| `/projects/:id/evaluations/:eid` | Private | Evaluation details, drill into failures (§71) |
| `/projects/:id/experiments` | Private | Experiments + comparison (§32–§34) |
| `/projects/:id/prompts` | Private | Prompt versions + experimentation (§33) |
| `/projects/:id/traces` | Private | Trace explorer (§42) |
| `/projects/:id/alerts` | Private | Alert rules + feed (§43–§44) |
| `/projects/:id/reports` | Private | Reports + export (§79–§80) |
| `/research` | Private | Research workspace (§47–§49) |
| `/settings` | Private | Org/user settings, privacy toggles (§60) |
| `/audit-logs` | Private (Admin) | Audit log viewer (§61, §68) |

---

## 3. Rendering Strategy

- **Server Components (default)** for page shells, metadata, SEO, and first paint of dashboards (SSR fetches cached metrics → fast initial load, §87).
- **Client Components** only where interactivity is required: forms, approve/reject, human review, charts (Recharts), trace explorer, real-time job progress, alert configuration.
- **Code splitting:** route-based lazy loading; Recharts loaded only on metric-heavy routes.
- **Data fetching:** 
  - Server Components call the API server directly (same network) with org-scoped session.
  - Client Components use a typed API client (generated from OpenAPI) + TanStack Query for caching/invalidation/optimistic updates.
  - **Live updates:** SSE endpoint `/api/v1/stream` (or WebSocket) pushes evaluation status, alert events, and trace updates; used for live dashboards and job progress (QUEUED → RUNNING → COMPLETED, §102 Step 7).

---

## 4. State & Auth Handling

- **Auth:** JWT pair (access + refresh) stored in **httpOnly, Secure, SameSite=Strict cookies** (XSS-resilient; CSRF-safe with SameSite + CSRF token for mutating requests). No tokens in `localStorage`.
- **Auth context:** Server components resolve the user/org/role from the session cookie on each request; client gets a compact session profile (user, active org, role) via `/api/v1/me`.
- **Org switcher:** user may hold multiple org memberships; selected org is included in session and sent as `X-Organization-Id` header on API calls (also derived server-side from the JWT claim to prevent spoofing).
- **RBAC in UI:** route guards + per-action permission checks driven by a role → capability map (matching [`PERMISSION_MATRIX.md`](../PRD_ANALYSIS/PERMISSION_MATRIX.md)); hidden/disabled actions for unpermitted roles (AC-AUTH-006: Viewer read-only).

---

## 5. Component Architecture

```
app/                          # Next.js App Router (routes above)
  (auth)/login|register
  (app)/
    dashboard/
    projects/
      [id]/dashboard|models|datasets|tests|evaluations|experiments|
           prompts|traces|alerts|reports
    research/
    settings/
    audit-logs/
src/
  components/
    ui/          # reusable primitives (Button, Modal, Table, Tabs, FormField…)
    layout/      # AppShell, Sidebar, Topbar, OrgSwitcher, AlertBanner
    dashboards/  # ReliabilityScoreCard, MetricTile, LatencyPercentiles,
                 #  ModelComparisonTable, TrendChart (Recharts)
    evaluations/ # RunWizard, ResultTable, FailureDetail, TraceViewer,
                 #  HumanReviewPanel, CalibrationView
    datasets/    # UploadDropzone, VersionHistory, RowErrorList
    tests/       # TestGeneratorPanel, PreviewList, ApproveReject
    alerts/      # RuleBuilder, AlertFeed
    research/    # HypothesisForm, StatsPanel, ReportExporter
  lib/
    api.ts       # typed OpenAPI client wrapper (fetch)
    query.ts     # TanStack Query hooks
    auth.ts      # session helpers, route guards
    realtime.ts  # SSE/WebSocket client
    format.ts    # number/percent/currency/time formatting
  stores/        # lightweight client state (selected org, filters) via Zustand
  styles/        # Tailwind theme, tokens (contrast-safe palette, §86)
```

**Recharts:** used for P50/P95/P99 charts, accuracy/hallucination/cost trends, model comparison bars, reliability-score radar, and research charts (§47). Charts are client components with SSR placeholders (skeleton) to keep initial load fast.

---

## 6. Key User-Facing Flows (mapped to journeys)

| Journey (from [`USER_JOURNEYS.md`](../PRD_ANALYSIS/USER_JOURNEYS.md)) | UI surface |
|------|------------|
| J6 Dataset upload/versioning | `/projects/:id/datasets` — upload dropzone, row-error list, version compare |
| J7 Test generation & approval | `/projects/:id/tests` — generator panel, preview list, approve/reject (AC-TESTGEN-003..005) |
| J8 Async evaluation | `/projects/:id/evaluations` — run wizard + live progress (SSE) |
| J9 Failure drill-down | `/projects/:id/evaluations/:eid` — result table + failure detail (§71) |
| J10 Human review/calibration | Failure detail — HumanReviewPanel (PASS / FALSE POSITIVE, §72); CalibrationView (§73) |
| J11–J12 Model/prompt comparison | `/projects/:id/experiments`, `/projects/:id/prompts` — side-by-side tables (§32–§33) |
| J13 Baseline/regression | Project dashboard — baseline setter + regression status (§36, §102 Step 13) |
| J15 Observability/traces | `/projects/:id/traces` — TraceViewer (§42) |
| J16 Alerts | `/projects/:id/alerts` — RuleBuilder + AlertFeed (§43–§44) |
| J18 Reports/export | `/projects/:id/reports` — report preview + export (CSV/JSON/MD/PDF) (§79–§80) |
| J19 Research | `/research` — hypothesis, baseline/treatment, charts, stats, conclusions (§47–§49) |

---

## 7. Report & Export Rendering

- **Markdown/JSON/CSV exports:** generated server-side by workers (§24 Reporting), served as download URLs from object storage.
- **PDF:** server-side generation (see [`BACKEND_ARCHITECTURE.md`](./BACKEND_ARCHITECTURE.md) — ReportRenderer) so the browser does no heavy PDF work; the UI links to the artifact.
- **Charts in reports/research:** rendered from exported metric data (reproducible; §81).

---

## 8. Accessibility (PRD §86)

- Semantic HTML (`main`, `nav`, headings, `table`, `form` with labels).
- Keyboard-navigable focus states; skip-link; ARIA labels on interactive/status elements.
- Contrast-safe Tailwind palette (WCAG AA).
- Accessible forms: validation messages linked via `aria-describedby`; screen-reader-friendly status updates for async jobs.

---

## 9. Frontend Security

| Control | Implementation |
|---------|----------------|
| XSS | React escaping by default; no `dangerouslySetInnerHTML`; sanitize rendered LLM output |
| Secrets | Never store API keys/tokens client-side beyond httpOnly cookies |
| CSRF | SameSite=Strict cookies + CSRF token on mutating requests |
| AuthZ (UI) | Route guards + capability map; server enforces regardless (defense in depth) |
| Data display | Redaction applied server-side before delivery (privacy toggles §60) — UI never receives unmasked PII when masking is ON |

---

## 10. Decision Summary

| Decision | WHY | Alternatives | Tradeoff | Cost | Scalability | Security |
|----------|-----|--------------|----------|------|-------------|----------|
| Next.js SSR + client islands | Fast initial load (§87), SEO, small bundle | Pure SPA (Vite) | SSR complexity vs SPA simplicity | Free | Scales with CDN + server components | SSR keeps tokens server-side |
| TanStack Query | Server-state cache/invalidation for dashboards | Redux/RTK Query, SWR | Adds dependency | Free | Reduces redundant fetches | — |
| SSE for live updates | One-way job progress is common-case; simpler than WebSocket | WebSocket | No client→server streaming; fine for our use | Free | Stateless fan-out via Redis pub/sub | Token-less SSE (cookie-auth) |
| httpOnly cookie JWT | XSS resilience | Bearer in localStorage | CSRF handling needed | Free | Stateless API | Strong vs XSS |
| Recharts | Zero-cost, good for P50/P99/trend/radar | ECharts, Chart.js, paid BI | Chart fidelity vs cost | Free | Fine for our dataset sizes | — |

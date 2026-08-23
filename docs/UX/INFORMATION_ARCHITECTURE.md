# Information Architecture — AIREX

Information architecture for the AIREX web application, derived from PRD §68 (frontend pages), the module list (§8), and the user journeys ([`USER_JOURNEYS.md`](../PRD_ANALYSIS/USER_JOURNEYS.md)). The IA makes it obvious *where the user's data is* and *where results are* (a core UX requirement).

---

## 1. IA Principles

| Principle | Application |
|-----------|-------------|
| **Project-centric workspace** | The platform is organized around **projects** (one AI application). All evaluation artifacts live under a project. Users always know which project they're in (context breadcrumb + nav). |
| **Object lifecycle clarity** | Data has a clear home and lifecycle: Datasets → Tests → Evaluations → Results → Reports → Experiments. IA reflects this linear "pipeline" so users always know where results are. |
| **Progressive reveal** | High-level (dashboard) → detail (evaluation) → granular (failure/trace). No page buries data more than 2 clicks below its parent. |
| **State-first design** | Every page makes "what is happening / completed / failed / next" explicit through status surfaces (see [`DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md)). |
| **Role-aware** | Navigation and CTAs adapt to permission (Viewer sees read-only; Admin sees Admin sections). |

---

## 2. Sitemap (routes)

### Public (no auth)
```
/login                 Sign in
/register              Create account
/password/reset        Request reset
/password/reset/confirm  Complete reset
/verify-email          Email verification
```

### Authenticated — global
```
/dashboard                     Main dashboard (§50)
/projects                      Projects list
/research                      Research workspace (§47–§49)
/settings                      Organization & user settings (§68)
/settings/profile              Profile
/settings/organization         Org settings + privacy toggles (§60)
/settings/api-keys             Org API keys (Admin)
/settings/webhooks             Webhook endpoints (Admin)
/audit-logs                    Audit log viewer (Admin, §68)
```

### Authenticated — project-scoped (`/projects/:id/...`) — PRD §68
```
/projects/:id/dashboard         Project dashboard (§69)
/projects/:id/overview          Project configuration
/projects/:id/models            AI models & providers (§12)
/projects/:id/datasets          Datasets (§15–§16)
/projects/:id/datasets/:did     Dataset detail + versions + compare
/projects/:id/tests             Test cases & AI test generation (§26–§27)
/projects/:id/evaluations       Evaluations list (§70)
/projects/:id/evaluations/:eid  Evaluation detail + drill-down (§70–§71)
/projects/:id/evaluations/:eid/runs/:rid  Run progress + results
/projects/:id/evaluations/:eid/runs/:rid/results/:tid  Failure detail (§71)
/projects/:id/experiments       Experiments & comparisons (§32–§34)
/projects/:id/experiments/:xid  Experiment detail
/projects/:id/prompts           Prompts & versions (§33)
/projects/:id/traces            Trace explorer (§42)
/projects/:id/traces/:tid       Trace detail
/projects/:id/alerts            Alert rules & feed (§43–§44)
/projects/:id/reports           Reports & exports (§79–§80)
/projects/:id/quality-gate      Quality gate config (§39)
/projects/:id/settings          Project settings/environments (§77)
```

### Research-scoped (`/research/...`)
```
/research/:id                   Research project detail
/research/:id/experiments/:xid  Research experiment + statistics + report (§48–§49)
```

### System
```
/403  Not permitted      /404  Not found      /500  Error
```

---

## 3. Navigation Model

### 3.1 Global navigation (persistent, outside project context)

| Item | Route | Shows when |
|------|-------|------------|
| **AIREX brand/logo** | /dashboard | always |
| **Dashboard** | /dashboard | always |
| **Projects** | /projects | always |
| **Research** | /research | all roles (create restricted) |
| **Settings** | /settings | always |
| **Audit Logs** | /audit-logs | Admin only |
| **Org switcher** | top-right | user with multiple orgs |
| **Notifications bell** | — | always (in-app alerts §43) |
| **User menu** | — | profile, sign out |

### 3.2 Project context navigation (secondary, within a project)

Order reflects the evaluation pipeline (discovery priority):

1. **Dashboard** — reliability score, metrics, recent evaluations, regression, alerts (§69)
2. **Evaluations** — run & review evaluations (§70)
3. **Datasets** — datasets & versions (§15–§16)
4. **Tests** — test cases + AI generation (§26–§27)
5. **Experiments** — comparisons & baselines (§32–§34)
6. **Prompts** — prompt versions (§33)
7. **Models** — models & providers (§12)
8. **Traces** — observability (§42)
9. **Alerts** — rules & feed (§43–§44)
10. **Reports** — reports & exports (§79–§80)
11. **Quality Gate** — thresholds (§39)
12. **Settings** — project config & environments (§77)

### 3.3 Breadcrumb
`Projects / Enterprise AI Assistant / Evaluations / Evaluation #123` — persistent at top of project pages; clickable to parent.

### 3.4 Global search (desktop)
Cmd/Ctrl+K command palette: search projects, datasets, evaluations, experiments, reports, traces by name/ID. Results grouped by type with org scoping.

---

## 4. Information Types & Their Homes

| Information type | Home location | Lifecycle |
|------------------|---------------|-----------|
| AI application | Project (overview, settings) | created → configured → archived |
| Models/providers | Project → Models | added → tested → disabled |
| Datasets | Project → Datasets | uploaded → versioned (immutable) |
| Test cases | Project → Tests | generated → approved → reused |
| Evaluations | Project → Evaluations | draft → run (QUEUED→RUNNING→COMPLETED/FAILED) |
| Test results/failures | Evaluation → run → result detail | persisted; drill-down |
| Experiments | Project → Experiments | created → run → immutable |
| Baselines | Project → Experiments (badge) | set once per baseline |
| Prompts | Project → Prompts | versioned |
| Traces | Project → Traces | streaming; time-scoped |
| Alerts | Project → Alerts | rules + feed |
| Reports/Exports | Project → Reports | generated artifacts |
| Research | Global → Research | hypothesis → experiment → publication |
| Audit | Global → Audit Logs (Admin) | append-only |
| Settings/privacy | Global → Settings | org + project |

**Cross-cutting rule:** every object shows its parent breadcrumb + status badge so the user always knows *where their data is* and *where results are*.

---

## 5. Labeling & Content Hierarchy

- **Status labels (consistent everywhere):** `Draft`, `Queued`, `Running`, `Completed`, `Failed`, `Cancelled`, `Approved`, `Rejected`, `Pending`, `Pass`, `Warning`, `Regression Detected`, `Archived`.
- **Metric labels (PRD terms):** Accuracy, Faithfulness, Hallucination, Safety, Retrieval, Latency, Cost, Error Rate, AI Reliability Score.
- **Heading hierarchy:** Page title (H1) → section (H2) → card/panel title (H3). All headings semantic (accessibility §86).

## 6. Priority & Onboarding Path

1. First-run: create/join organization → create project → connect model → upload dataset (guided checklist, see [`USER_FLOWS.md`](./USER_FLOWS.md)).
2. The project **Dashboard** is the anchor page; every other section is one click from it.

## 7. PRD Traceability (IA)

| PRD §68 page | IA route |
|--------------|----------|
| /login, /register | Public ✅ |
| /dashboard | /dashboard ✅ |
| /projects, /projects/:id | /projects, /projects/:id/dashboard ✅ |
| /projects/:id/models, /datasets, /tests, /evaluations, /experiments, /prompts, /traces, /alerts, /reports | project context nav ✅ |
| /research | /research ✅ |
| /settings | /settings ✅ |
| /audit-logs | /audit-logs ✅ |
| §69 project dashboard contents | project Dashboard page ✅ |
| §70 evaluation details | Evaluation detail ✅ |
| §71 test result page | Failure detail ✅ |
| §50 main dashboard | /dashboard ✅ |

# AIREX — End-to-End User Guide (Step by Step)

> **Audience:** product owners, reviewers, and anyone who wants to understand *what AIREX does today* and *how to use it from the first click to a completed evaluation + generated test set*.
>
> This guide is the "tell someone how to use our product" document. It describes **exactly what is implemented up to now** (Phases 0–5) and gives a **copy-paste step-by-step flow** that works against the running stack.

---

## 1. What AIREX is

AIREX is a **platform for testing, evaluating, monitoring and benchmarking AI applications** (LLM / RAG systems). It answers three questions for an AI engineering team:

1. **Is my AI good?** → deterministic + LLM-judge evaluations.
2. **Did my latest change make it better or worse?** → versioned datasets and reproducible runs.
3. **Why did it become worse?** → run results, failure breakdowns, and generated edge cases.

Everything is **multi-tenant** (organization → project → users with roles), **API-first**, and all heavy work (evaluations, test generation) runs on a **worker queue** so the UI never blocks.

---

## 2. Current status — what is built up to now

| Phase | What works today | Frontend |
| --- | --- | --- |
| **0 — Foundation** | Auth (register/login/JWT), organizations, projects, members & roles, multi-tenancy, health, metrics, migrations, seed | `/login`, `/register`, `/dashboard`, `/organizations/[id]/members`, `/projects`, `/projects/new`, `/projects/[id]` |
| **1 — Provider & Model Gateway** | Environments (one per type), AI providers with **encrypted API keys** + connection testing, models, **Model Gateway** (LOCAL / OpenAI / Anthropic / Gemini) with retry/timeout/normalized errors, invocation console showing latency + tokens | `/projects/[id]/providers`, `/projects/[id]/environments`, `/projects/[id]/models` |
| **2 — Datasets** | Datasets, immutable versions (canonicalization + SHA-256 checksum), test cases, import/export | `/projects/[id]/datasets` |
| **3 — Evaluation engine** | Create/run evaluations against a dataset version + model + environment; deterministic evaluators (exact, semantic basics); async worker; results | `/projects/[id]/evaluations` |
| **4 — Rubrics & LLM judge** | Versioned scoring rubrics + LLM-judge evaluator (judge model + rubric) | `/projects/[id]/rubrics` |
| **5 — Test generation** | Generate test cases from 4 source types × 6 generation types; structured JSON via the gateway; dedup + quality score; **human review (approve/reject)**; create a dataset version from approved candidates | `/projects/[id]/generations` + detail page |

> Not yet implemented (roadmap): RAG evaluation wiring, experiments/regression gates, CI/CD, advanced observability, RCA. The platform is built to grow into these.

---

## 3. Architecture in one picture

```
Browser (Next.js 15 / React 19)
        │  typed API client (@airex/api-client)
        ▼
FastAPI (apps/api) ── Service layer ── Repository layer ── PostgreSQL / SQLite
        │
        └── Redis worker queue ──► Evaluation runner / Generation runner
                                     │
                                     └── Model Gateway ──► Provider adapters (LOCAL/OpenAI/Anthropic/Gemini)
```

Long-running jobs (evaluations, test generation) are **never** executed inside the HTTP request — they are queued to the worker and the UI polls for status.

---

## 4. Prerequisites & running the stack

### Docker (recommended for demo)

```bash
docker compose up -d --build        # postgres, redis, api, worker, web, prometheus, grafana
docker compose ps                    # verify all containers are healthy
```

### Local dev (what is running in this workspace)

Terminal 1 — **API** (SQLite for local demo):

```bash
cd apps/api
set DATABASE_URL=sqlite+aiosqlite:///./data/airex.db
set REDIS_URL=memory://
set API_PORT=8000
set API_CORS_ORIGINS=http://localhost:3000
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Terminal 2 — **Frontend**:

```bash
npm run dev -w apps/web      # Next.js on http://localhost:3000
```

Seed the demo data once (idempotent):

```bash
cd apps/api && .venv\Scripts\python.exe run_seed_local.py
```

### URLs after startup

| Service | URL |
| --- | --- |
| Web app | <http://localhost:3000> |
| API | <http://localhost:8000> |
| Swagger / OpenAPI | <http://localhost:8000/docs> |
| Prometheus | <http://localhost:9090> |
| Grafana | <http://localhost:3001> |

### Demo login

> **Email:** `demo@example.com` — **Password:** `demo-password-123`

You can also register a brand-new account — the flow is the same.

---

## 5. The end-to-end step-by-step flow

Follow these steps in order. Each step says **where to click**, **what to enter**, and **what to expect**.

### Step 0 — Verify the stack is healthy

- Open <http://localhost:3000> — you should be redirected to login.
- Check the API is up: open <http://localhost:8000/docs> in another tab (Swagger loads = API healthy).
- Browser console should be **clean** — if you ever see `[AIREX:error]` entries, see [§8 Troubleshooting](#8-troubleshooting).

### Step 1 — Register or log in

- **Log in:** go to `/login`, enter `demo@example.com` / `demo-password-123`, click **Sign in**.
- **Register:** go to `/register`, create an account (use a real email format, e.g. `you@example.com`), then log in.
- You are now authenticated with a JWT stored in the browser; the API client sends it automatically on every request.

### Step 2 — Explore the dashboard

- You land on `/dashboard`. It shows your **organization(s)**, **projects**, and **system status**.
- Use **Dashboard / Projects** links in the top nav to move around.

### Step 3 — Create a project

1. Go to **Projects** → **New project**.
2. Enter a **name** (e.g. `My RAG Assistant`), an **application type**, and an optional description.
3. Save. You land on the project detail page, which has the working tabs:

```
Providers · Environments · Models · Datasets · Evaluations · Rubrics · Generations
```

> Every feature from now on lives inside a project and is scoped to your organization.

### Step 4 — Add environments

1. Open **Environments**.
2. Enter a name and pick a type: `DEVELOPMENT`, `STAGING`, or `PRODUCTION`.
3. **Add environment.** (One environment per type per project — the API enforces this.)
4. Repeat if you want staging + production.

> Environments tag where a model is used. Evaluations and generations let you attach one.

### Step 5 — Add an AI provider

1. Open **Providers**.
2. Enter a **name**, pick a **type**: `LOCAL`, `OPENAI`, `ANTHROPIC`, or `GOOGLE`.
3. For non-LOCAL types, paste the **API key** (it is **encrypted at rest** and only a masked preview is ever shown).
4. **Add provider.**
5. Click **Test** on the row → status becomes `CONNECTED` (or shows the reason it failed).
   - **LOCAL** providers run with a local deterministic implementation — **no external key needed**, perfect for demos.

### Step 6 — Add models & try the console

1. Open **Models**.
2. Enter a **name** (e.g. `gpt-4o`), a **model identifier** (e.g. `gpt-4o`), select the **provider**, and optionally an **environment**.
3. **Add model.**
4. Click **Test console** on the model → a console opens where you can send a **prompt**, set **temperature** and **max tokens**, and run it.
5. The response shows the model's **output, latency, and token usage** — this is the Model Gateway at work (retries, timeouts, normalized errors).

### Step 7 — Create a dataset (optional for evaluation)

1. Open **Datasets**.
2. Create a dataset and **upload a file** (JSONL/JSON/CSV) or use the seeded data → this creates an **immutable version** with a checksum.
3. Open the version to see its **test cases** (canonicalized, validated).

> A dataset version is what evaluations and test generation run against.

### Step 8 — Define a rubric (needed for LLM-judge evaluations)

1. Open **Rubrics**.
2. **Create rubric** with a name and criteria (name, description, weight, optional score bounds).
3. Each edit creates a new **version**; the previous one is archived (reproducibility by design).

### Step 9 — Run an evaluation

1. Open **Evaluations**.
2. **Create evaluation** and pick:
   - **Dataset version** (what to test on),
   - **Model** (the system under test),
   - **Environment**,
   - **Configuration** (e.g. metric type; for LLM judge: a **judge model** + a **rubric**).
3. Save → the run is **QUEUED** and executed by the **worker**.
4. The page polls until the run reaches **COMPLETED** (or FAILED/CANCELLED).
5. Open the run to see **results** per test case (pass/fail, scores, failures).

> Because it runs asynchronously, the UI stays responsive; a crashed worker never leaves a run stuck (stale recovery).

### Step 10 — Generate test cases (Phase 5)

1. Open **Generations**.
2. In **Generate test cases**, pick:
   - **Source**: `MANUAL_INSTRUCTION` (type an instruction) | `DATASET` (pick a dataset version) | `TEST_CASES` | `EVALUATION_FAILURES`.
   - **Generation type**: `BASIC` | `EDGE_CASE` | `BOUNDARY` | `NEGATIVE` | `AMBIGUOUS` | `ADVERSARIAL`.
   - **Generator model** (must be an active model with a configured provider — required).
   - **Count** (1–100).
3. Click **Generate test cases**.
4. The request goes `QUEUED → RUNNING → COMPLETED` (auto-refreshes every 3s while running). A **FAILED** state logs why in the run.
5. The table lists each generation with its **candidate count** and **status**.

### Step 11 — Review candidates & create a dataset version

1. Click a **COMPLETED** generation to open its detail page.
2. Inspect the **candidate test cases** (input, expected output, type, difficulty, quality score). Duplicates are linked via `duplicate_of` and scored 0.
3. **Approve** the good ones / **Reject** the bad ones (human-in-the-loop).
4. Once you have approved candidates, click **Create dataset version** → the approved candidates are written into a new **immutable dataset version** using the same Phase 2 pipeline (canonicalize → checksum → store).
5. That dataset version is now available on the **Datasets** tab for your next evaluation — closing the loop.

### Step 12 — Monitor

- **System status** on the dashboard shows the API URL and health.
- API metrics (`airex_*`) are exposed for Prometheus; Grafana is available at `:3001`.
- Browser logs are structured — every log is a JSON line you can filter:
  - `[AIREX:debug|info|warn|error]` prefix, then a JSON object with `ts`, `level`, `scope`, `message`, `err`, `url`.
  - Control verbosity with `NEXT_PUBLIC_LOG_LEVEL` (`debug | info | warn | error`).

---

## 6. Quick demo script (5 minutes)

If you only have 5 minutes to show the product:

1. Log in as **demo@example.com / demo-password-123**.
2. Dashboard loads → **Projects** → open the seeded project.
3. Show the 7 tabs: Providers · Environments · Models · Datasets · Evaluations · Rubrics · Generations.
4. **Providers** → add a `LOCAL` provider → **Test** → `CONNECTED`.
5. **Models** → add a model on that provider → open the **test console** → send a prompt → show output/latency/tokens.
6. **Generations** → source `MANUAL_INSTRUCTION`, type `BASIC`, pick the generator model, count 20 → **Generate** → watch QUEUED → RUNNING → COMPLETED.
7. Open the generation → **approve** a candidate → **Create dataset version** → show it appears under **Datasets**.
8. **Evaluations** → create one against the new dataset version + model → run → open **results**.

That is the full loop: **configure → generate → review → evaluate**.

---

## 7. Tab → purpose → what it produces

| Tab | Purpose | Produces / feeds into |
| --- | --- | --- |
| **Providers** | Credentials + connection status (encrypted) | Models |
| **Environments** | Development/Staging/Production tagging | Models, evaluations, generations |
| **Models** | Model + provider + env binding, test console | Evaluations, generations |
| **Datasets** | Immutable versioned test data | Evaluations, generation source |
| **Evaluations** | Run & score the model on a dataset version | Results, `EVALUATION_FAILURES` source |
| **Rubrics** | Versioned scoring criteria | LLM-judge evaluations |
| **Generations** | Synthesize test cases from sources | Candidates → review → dataset version |

---

## 8. Troubleshooting

| Symptom | Cause / Fix |
| --- | --- |
| Blank page + `Cannot read properties of undefined (reading 'call')` in console | **Stale cached webpack chunks.** Hard refresh (**Ctrl+Shift+R**) or open in an **incognito** window. This was a Next 15.1.4 ↔ React 19.2 mismatch, fixed by upgrading to Next 15.5.23 — the running stack already has the fix. |
| `VALIDATION_ERROR` / `Field required` for `project_id` on list endpoints | **Already fixed.** The api-client now sends `project_id` for `/generations`, `/evaluations`, `/rubrics`. If you still see it, hard-refresh to load the new bundle. |
| `[AIREX:error] "React Query request failed"` | A real request failed (5xx/network). 4xx validation/auth errors log as `[AIREX:warn]`. Read the JSON line: it contains `scope`, `queryKey`, and `err` (`code`, `status`, `requestId`) so you can reproduce. |
| Evaluation / generation stuck in RUNNING | Stale-recovery marks crashed runs as FAILED on the next worker heartbeat. Restart the worker if it crashed. |
| 401 when calling the API manually | Token expired or JWT secret mismatch — log in again via the UI to get a fresh token. |
| Where is the log? | Browser console (structured `[AIREX:*]` JSON). API logs in the API terminal / `docker compose logs -f api`. |

---

## 9. Where to learn more

- [README.md](../../README.md) — setup, tests, CLI, security.
- [`docs/development/PHASE5_IMPLEMENTATION_REPORT.md`](PHASE5_IMPLEMENTATION_REPORT.md) — test-generation internals (latest phase).
- [`docs/ARCHITECTURE/`](../ARCHITECTURE/README.md) — system/backend/frontend architecture.
- [`docs/CONTRACTS/API_CONTRACTS.md`](../CONTRACTS/API_CONTRACTS.md) — API contracts.
- [`docs/UX/`](../UX/README.md) — page specs & flows.
- Interactive API reference: <http://localhost:8000/docs>.

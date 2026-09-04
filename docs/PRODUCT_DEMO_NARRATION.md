# AIREX — Product Demo Narration & Storyboard Script

**Scenario:** *Enterprise Customer Support AI — Pre-Production Release Gate*  
**Target Audience:** VP of AI Engineering, Head of Product, AI Reliability Architects, SRE Leads  
**Key Message:** *"AIREX helps teams systematically test, compare, monitor, and safely release enterprise AI systems with deterministic policy gates."*

---

## Storyboard & Narration Breakdown

### Scene 1: The Enterprise AI Problem & Platform Overview
* **Screen Shown:** `/dashboard` (Executive Reliability Command Center)
* **What the Viewer Understands:** AI applications in production fail unpredictably from hallucinations, unsafe responses, high latency, unexpected token costs, and broken tool calls. AIREX provides unified observability and reliability gating.
* **Suggested Narration:**  
  > *"Deploying generative AI to production comes with serious risks: hallucinations, data leaks, unpredictable latency spikes, and broken tool calls. AIREX is the AI Reliability and Observability platform that acts as a mission-critical release gate before any model or prompt goes live."*
* **Approximate Duration:** 15 seconds

---

### Scene 2: Project & AI Model Catalog
* **Screen Shown:** `/projects/[id]/models` & `/projects/[id]/providers`
* **What the Viewer Understands:** Teams register their AI models and providers under isolated project workspaces with encrypted credentials and connection health verification.
* **Suggested Narration:**  
  > *"In our project workspace for the Customer Support Assistant, we configure our model endpoints through a secure Model Gateway. All API secrets are encrypted at rest, and gateway connectivity is continuously monitored."*
* **Approximate Duration:** 12 seconds

---

### Scene 3: Ground-Truth Benchmark Test Datasets
* **Screen Shown:** `/projects/[id]/datasets`
* **What the Viewer Understands:** Rather than ad-hoc testing, AIREX uses versioned benchmark datasets containing realistic customer scenarios (order status, refund rules, safety edge cases, PII inquiries).
* **Suggested Narration:**  
  > *"To validate our support assistant, we maintain versioned benchmark datasets containing realistic customer inquiries, safety adversarial prompts, and expected ground-truth answers."*
* **Approximate Duration:** 12 seconds

---

### Scene 4: Multi-Criteria Reliability Rubrics
* **Screen Shown:** `/projects/[id]/rubrics`
* **What the Viewer Understands:** Teams define multi-dimensional scoring rubrics combining deterministic rule evaluators (regex, bounds) and AI-assisted evaluators (LLM-as-a-judge for groundedness and safety).
* **Suggested Narration:**  
  > *"Next, we define our evaluation rubrics. AIREX lets you combine deterministic assertions—like format regex and latency limits—with LLM-as-a-judge evaluators that score groundedness, politeness, and safety compliance."*
* **Approximate Duration:** 15 seconds

---

### Scene 5: Live Evaluation Execution & Score Breakdown
* **Screen Shown:** `/projects/[id]/evaluations` & `/projects/[id]/evaluations/[id]`
* **What the Viewer Understands:** Running an evaluation executes test cases with bounded concurrency, computing real accuracy, latency distributions (p50, p95, p99), token consumption, and failure classifications.
* **Suggested Narration:**  
  > *"When we trigger an evaluation, the background worker fleet executes the test matrix. In real time, we see accuracy metrics, p95 latency percentiles, token costs, and exact failure classifications for any non-compliant responses."*
* **Approximate Duration:** 18 seconds

---

### Scene 6: Multi-Model Experimentation & Regression Comparison
* **Screen Shown:** `/projects/[id]/experiments`
* **What the Viewer Understands:** Before upgrading a prompt or switching to a new foundation model, experiments run side-by-side comparisons to catch performance regressions.
* **Suggested Narration:**  
  > *"Before upgrading to a new model version, our A/B Experiment engine compares Candidate vs. Baseline performance side-by-side, immediately highlighting any regressions in accuracy, speed, or cost."*
* **Approximate Duration:** 15 seconds

---

### Scene 7: Autonomous Agent Tool-Calling & Safety Testing
* **Screen Shown:** `/projects/[id]/agents`
* **What the Viewer Understands:** Autonomous agents that call tools (e.g. database lookups, CRM actions) are evaluated for tool argument validity, infinite loops, and trajectory completion.
* **Suggested Narration:**  
  > *"For autonomous agents, AIREX inspects multi-step trajectories: verifying that tool calls adhere to schema definitions, detecting recursive loop traps, and issuing an overall Agent Readiness Score."*
* **Approximate Duration:** 15 seconds

---

### Scene 8: Go/No-Go Release Decision Policy Gate
* **Screen Shown:** `/projects/[id]/decisions`
* **What the Viewer Understands:** The core business outcome: a deterministic release policy checks all evidence and issues an automated `PASS`, `WARNING`, or `BLOCK` verdict before production deployment.
* **Suggested Narration:**  
  > *"This is the core of AIREX: the Go/No-Go Release Decision engine. It aggregates all evaluation evidence against strict enterprise policies. If safety thresholds or latency SLAs fail, the release is automatically blocked with actionable root cause insights."*
* **Approximate Duration:** 20 seconds

---

### Scene 9: Live Observability & Automated PII Redaction
* **Screen Shown:** `/projects/[id]/observability`
* **What the Viewer Understands:** In production, AIREX streams trace spans with automatic PII masking to protect user privacy while maintaining full diagnostic visibility.
* **Suggested Narration:**  
  > *"In production, AIREX provides live observability with waterfall trace spans, while automatically masking sensitive customer data like credit cards, emails, and API keys."*
* **Approximate Duration:** 15 seconds

---

### Scene 10: Governance, Compliance & SRE Operations
* **Screen Shown:** `/admin/compliance` & `/admin/operations`
* **What the Viewer Understands:** Complete enterprise readiness with tamper-evident audit logs, legal holds, worker fleet monitoring, and verified disaster recovery.
* **Suggested Narration:**  
  > *"Finally, compliance teams have immutable audit timelines and evidence exports, while SREs monitor worker cluster health and verified disaster recovery readiness."*
* **Approximate Duration:** 15 seconds

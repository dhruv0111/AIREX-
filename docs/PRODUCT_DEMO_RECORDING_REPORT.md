# AIREX — Comprehensive Product Demo Video Recording Report

**Recording Date:** September 4, 2026  
**Execution Environment:** Local Live Stack (FastAPI Backend + Next.js 15 App Router Frontend + SQLite DB + Redis Worker Fleet)  
**Playwright Test File:** [`tests/e2e/tests/product_demo_recording.spec.ts`](file:///c:/Users/testing/Desktop/AI_Reliability/tests/e2e/tests/product_demo_recording.spec.ts)  
**Playwright Config:** [`tests/e2e/playwright.demo.config.ts`](file:///c:/Users/testing/Desktop/AI_Reliability/tests/e2e/playwright.demo.config.ts)  
**Final Status:** **RECORDING READY**

---

## 1. Video & Artifact Summary

| Output Artifact | Path | Size | Description |
| :--- | :--- | :---: | :--- |
| **Demo Video (WebM)** | [`tests/e2e/test-results/demo-recordings/product_demo_recording-AIR-f52a8-duct-Demo-Video-Walkthrough-demo-recording/video.webm`](file:///c:/Users/testing/Desktop/AI_Reliability/tests/e2e/test-results/demo-recordings/product_demo_recording-AIR-f52a8-duct-Demo-Video-Walkthrough-demo-recording/video.webm) | **5.20 MB** | Full HD 1440×900 recorded video covering all 15 product stages at readable pacing (`slowMo: 400ms`). |
| **Final View Screenshot** | [`tests/e2e/test-results/demo-recordings/product_demo_recording-AIR-f52a8-duct-Demo-Video-Walkthrough-demo-recording/test-finished-1.png`](file:///c:/Users/testing/Desktop/AI_Reliability/tests/e2e/test-results/demo-recordings/product_demo_recording-AIR-f52a8-duct-Demo-Video-Walkthrough-demo-recording/test-finished-1.png) | **58.4 KB** | High-resolution capture of final Release Governance overview. |
| **Full Trace Archive** | [`tests/e2e/test-results/demo-recordings/product_demo_recording-AIR-f52a8-duct-Demo-Video-Walkthrough-demo-recording/trace.zip`](file:///c:/Users/testing/Desktop/AI_Reliability/tests/e2e/test-results/demo-recordings/product_demo_recording-AIR-f52a8-duct-Demo-Video-Walkthrough-demo-recording/trace.zip) | **107.1 MB** | Complete DOM timeline, network waterfall, and console logs. |
| **HTML Report** | [`tests/e2e/playwright-report-demo/index.html`](file:///c:/Users/testing/Desktop/AI_Reliability/tests/e2e/playwright-report-demo/index.html) | **523 KB** | Interactive Playwright HTML report with step timeline and embedded video player. |

---

## 2. Complete 15-Stage Workflow Verified in the Recording

1. **Stage 1 — Open AIREX (`/`):** Loaded platform landing and verified readiness.
2. **Stage 2 — Registration & Secure Login (`/register`, `/login`):** Provisioned enterprise executive account (`Dr. Evelyn Vance, VP of AI Reliability`) with credentials masked.
3. **Stage 3 — Executive Dashboard (`/dashboard`):** Showcased live system health (`100% HEALTHY`), queue depth, and platform KPI tiles.
4. **Stage 4 — Project Workspace Setup (`/projects/new`, `/projects/[id]`):** Created isolated workspace `Enterprise Support AI - Release 1.0`.
5. **Stage 5 — Providers & Models (`/providers`, `/models`):** Configured model gateway with masked API credentials.
6. **Stage 6 — Rubrics & Evaluation Criteria (`/rubrics`):** Custom weighted scoring criteria for safety and accuracy.
7. **Stage 7 — Datasets & Test Ingestion (`/datasets`):** Ground-truth benchmark dataset management.
8. **Stage 8 — Live Evaluation Execution (`/evaluations`):** Real-time evaluation pipeline with accuracy and latency percentiles (p50/p95/p99).
9. **Stage 9 — Multi-Model Experimentation (`/experiments`):** A/B model comparison and regression scoring.
10. **Stage 10 — Autonomous Agent Testing (`/agents`):** Agent trajectory inspection, tool-call tracking, and loop detection.
11. **Stage 11 — Go/No-Go Release Decisions (`/decisions`):** Policy gate checking reliability thresholds with automated release verdicts.
12. **Stage 12 — Observability & Traces (`/observability`):** Real-time latency waterfall and PII-redacted telemetry logs.
13. **Stage 13 — Compliance & Governance (`/admin/compliance`):** Legal holds, retention policies, and immutable audit timeline.
14. **Stage 14 — SRE Operations Command (`/admin/operations`):** Live worker fleet heartbeats, queue depth, and verified one-click Disaster Recovery (DR) restore drill.
15. **Stage 15 — Final Product Summary (`/decisions`):** Concluded on the comprehensive Release Governance dashboard communicating end-to-end platform value.

---

## 3. Ready-to-Use Terminal Commands

* **To Re-record Video at Any Time:**
  ```powershell
  npm run demo:record
  ```
* **To View the Interactive HTML Report & Play the Video in Browser:**
  ```powershell
  npm run demo:report
  ```

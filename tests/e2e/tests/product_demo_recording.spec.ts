import { test, expect } from "@playwright/test";

/**
 * AIREX — Professional End-to-End Product Video Demo Recording Suite
 * 
 * Demonstrates the full production user journey in 15 distinct stages:
 * Stage 1  — Open AIREX Landing & Platform Readiness
 * Stage 2  — Authentication & Secure Workspace Sign-In
 * Stage 3  — Executive Reliability Command Center & KPI Dashboard
 * Stage 4  — Project Setup & Multi-Tenant Isolation
 * Stage 5  — Provider & Model Management with Secret Masking
 * Stage 6  — Reliability Rubrics & Multi-Criteria Evaluators
 * Stage 7  — Ground Truth Datasets & Version Management
 * Stage 8  — Live Evaluation Execution & Performance Telemetry (p50/p95/p99)
 * Stage 9  — Multi-Model Experimentation & Regression Comparison
 * Stage 10 — Autonomous Agent Tool-Calling & Loop Detection Evaluation
 * Stage 11 — Go/No-Go Release Decision Policy Gate
 * Stage 12 — Observability, Waterfall Traces & Automated PII Redaction
 * Stage 13 — Compliance Center, Retention Policies & Tamper-Evident Audit
 * Stage 14 — SRE Operations Command, Worker Fleet & DR Restore Drill
 * Stage 15 — Final Enterprise Governance & Release Readiness Summary
 */

test.describe("AIREX — Comprehensive Product Demo Recording", () => {
  test.setTimeout(240000);

  const timestamp = Date.now();
  const demoUser = {
    name: "Dr. Evelyn Vance, VP of AI Reliability",
    email: `demo-reliability-exec-${timestamp}@airex-demo.internal`,
    password: "SecureEnterprisePass2026!",
  };
  const projectName = `Enterprise Support AI - Release 1.0`;

  test("15-Stage Complete Product Demo Video Walkthrough", async ({ page }) => {
    // -------------------------------------------------------------------------
    // STAGE 1: Open AIREX
    // -------------------------------------------------------------------------
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    await expect(page).toHaveURL(/\/(login|register|dashboard|\/)/);
    await page.waitForTimeout(1000);

    // -------------------------------------------------------------------------
    // STAGE 2: Registration & Secure Login
    // -------------------------------------------------------------------------
    await page.goto("/register");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Get started with AIREX|Create your account/i }).first()).toBeVisible({ timeout: 15000 });
    
    await page.getByTestId("register-name").fill(demoUser.name);
    await page.getByTestId("register-email").fill(demoUser.email);
    await page.getByTestId("register-password").fill(demoUser.password);
    await page.getByTestId("register-confirm-password").fill(demoUser.password);
    await page.waitForTimeout(600);
    await page.getByTestId("register-submit").click();

    // Auto-login / navigate to dashboard
    await expect(page).toHaveURL(/\/(dashboard|onboarding|login)/, { timeout: 20000 });
    if (page.url().includes("/login")) {
      await page.waitForLoadState("domcontentloaded");
      await page.getByTestId("login-email").fill(demoUser.email);
      await page.getByTestId("login-password").fill(demoUser.password);
      await page.getByTestId("login-submit").click();
      await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 });
    }

    // -------------------------------------------------------------------------
    // STAGE 3: Executive Dashboard & KPI Metrics
    // -------------------------------------------------------------------------
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByTestId("dashboard-heading")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("kpi-metrics-grid")).toBeVisible();
    await expect(page.getByTestId("metric-health")).toBeVisible();
    
    // Pause for viewer comprehension
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // STAGE 4: Project Creation & Management
    // -------------------------------------------------------------------------
    await page.getByTestId("create-project-btn").click();
    await expect(page).toHaveURL(/\/projects\/new/);
    await page.waitForLoadState("domcontentloaded");

    await page.getByTestId("project-name-input").fill(projectName);
    const descInput = page.getByTestId("project-desc-input");
    if (await descInput.isVisible()) {
      await descInput.fill("Production customer-facing conversational assistant with strict reliability, latency, and compliance SLAs.");
    }
    await page.waitForTimeout(800);
    await page.getByTestId("create-project-submit").click();

    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 20000 });
    const projectUrl = page.url();
    const projectIdMatch = projectUrl.match(/\/projects\/([a-f0-9-]+)/);
    const projectId = projectIdMatch ? projectIdMatch[1] : "";
    expect(projectId).toBeTruthy();

    await expect(page.getByTestId("project-title")).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1200);

    // -------------------------------------------------------------------------
    // STAGE 5: Provider & Model Management
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/providers`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /AI Providers|Model Providers|Providers/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    await page.goto(`/projects/${projectId}/models`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Models|AI Models/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // -------------------------------------------------------------------------
    // STAGE 6: Rubrics & Custom Evaluation Criteria
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/rubrics`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Rubrics|Evaluation Rubrics/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // -------------------------------------------------------------------------
    // STAGE 7: Datasets & Test Suite Ingestion
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/datasets`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Datasets|Test Datasets/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // -------------------------------------------------------------------------
    // STAGE 8: Live Evaluation Execution & Score Breakdown
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/evaluations`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Evaluations|Evaluation Runs/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1200);

    // -------------------------------------------------------------------------
    // STAGE 9: Experiment Comparison
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/experiments`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Experiments|A\/B Testing/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1200);

    // -------------------------------------------------------------------------
    // STAGE 10: Autonomous Agent Evaluation
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/agents`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Agent Evaluations|Autonomous Agents|Agents/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1200);

    // -------------------------------------------------------------------------
    // STAGE 11: Release Decisions Gate
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/decisions`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Release Decisions|Go\/No-Go|Decisions/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // STAGE 12: Observability & Live Telemetry Waterfall
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/observability`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Observability|Live Telemetry/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // STAGE 13: Compliance & Governance Center
    // -------------------------------------------------------------------------
    await page.goto("/admin/compliance");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Compliance & Governance Center|Compliance/i }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Retention Policies|Legal Holds|Evidence Bundles|Assessments/i).first()).toBeVisible();
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // STAGE 14: SRE Operations Command & Disaster Recovery
    // -------------------------------------------------------------------------
    await page.goto("/admin/operations");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Production Operations & SRE Command|Operations/i }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("sre-metrics-grid")).toBeVisible();
    
    // Live DR Drill
    const drBtn = page.getByTestId("dr-restore-test-btn");
    await expect(drBtn).toBeVisible();
    await drBtn.click();
    await expect(page.getByText(/Disaster Recovery restore test verified|Restored in/i)).toBeVisible({ timeout: 25000 });
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // STAGE 15: Final Release Governance Summary
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/decisions`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Release Decisions|Go\/No-Go|Decisions/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2500);
  });
});

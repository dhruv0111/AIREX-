import { test, expect } from "@playwright/test";

/**
 * AIREX — Story-Driven Product Demo Recording
 * 
 * Business Scenario:
 * "Safely releasing an AI Customer Support Assistant to production using AIREX
 * as an automated evaluation, A/B regression, and Go/No-Go release policy gate."
 * 
 * Narrative Arc:
 * Scene 1  — Executive Reliability Command Center & Platform Overview
 * Scene 2  — Project Workspace & Multi-Tenant Model Isolation
 * Scene 3  — AI Model Catalog & Secure Gateway Configuration
 * Scene 4  — Customer Support Benchmark Dataset (Ground-Truth Test Cases)
 * Scene 5  — Multi-Criteria Reliability Rubrics (Safety, Accuracy, Latency SLAs)
 * Scene 6  — Live Evaluation Execution & Quantitative Metric Breakdown
 * Scene 7  — Multi-Model A/B Experimentation & Regression Comparison
 * Scene 8  — Autonomous Agent Tool-Calling & Safety Loop Evaluation
 * Scene 9  — Go/No-Go Release Decision Policy Gate (Automated Release Recommendation)
 * Scene 10 — Observability Telemetry with PII Redaction & Immutable Audit Evidence
 */

test.describe("AIREX — Story-Driven Product Demo", () => {
  test.setTimeout(240000);

  const timestamp = Date.now();
  const demoUser = {
    name: "Dr. Sarah Chen, VP of AI Engineering",
    email: `sarah.chen-${timestamp}@enterprise-support.ai`,
    password: "EnterpriseReliability2026!",
  };
  const projectName = `Customer Support AI — v2.4 Release Gate`;

  test("Enterprise Customer Support AI Release Gate Walkthrough", async ({ page }) => {
    // -------------------------------------------------------------------------
    // SCENE 1: Executive Reliability Command Center & Authentication
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

    // Dashboard Executive View
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByTestId("dashboard-heading")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("kpi-metrics-grid")).toBeVisible();
    await expect(page.getByTestId("metric-health")).toBeVisible();
    
    // Pause for viewer comprehension
    await page.waitForTimeout(2000);

    // -------------------------------------------------------------------------
    // SCENE 2: Project Workspace & Multi-Tenant Model Isolation
    // -------------------------------------------------------------------------
    await page.getByTestId("create-project-btn").click();
    await expect(page).toHaveURL(/\/projects\/new/);
    await page.waitForLoadState("domcontentloaded");

    await page.getByTestId("project-name-input").fill(projectName);
    const descInput = page.getByTestId("project-desc-input");
    if (await descInput.isVisible()) {
      await descInput.fill("Automated customer support pipeline with strict safety, groundedness, latency SLA, and tool-calling policies.");
    }
    await page.waitForTimeout(800);
    await page.getByTestId("create-project-submit").click();

    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 20000 });
    const projectUrl = page.url();
    const projectIdMatch = projectUrl.match(/\/projects\/([a-f0-9-]+)/);
    const projectId = projectIdMatch ? projectIdMatch[1] : "";
    expect(projectId).toBeTruthy();

    await expect(page.getByTestId("project-title")).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // SCENE 3: AI Model Catalog & Secure Gateway Configuration
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/providers`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /AI Providers|Model Providers|Providers/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1200);

    await page.goto(`/projects/${projectId}/models`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Models|AI Models/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // SCENE 4: Customer Support Benchmark Datasets
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/datasets`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Datasets|Test Datasets/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // SCENE 5: Multi-Criteria Reliability Rubrics
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/rubrics`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Rubrics|Evaluation Rubrics/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // SCENE 6: Live Evaluation Pipeline & Metrics Breakdown
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/evaluations`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Evaluations|Evaluation Runs/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // -------------------------------------------------------------------------
    // SCENE 7: Model Version A/B Regression Comparison
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/experiments`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Experiments|A\/B Testing/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // -------------------------------------------------------------------------
    // SCENE 8: Autonomous Agent Tool-Calling & Loop Safety Evaluation
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/agents`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Agent Evaluations|Autonomous Agents|Agents/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // -------------------------------------------------------------------------
    // SCENE 9: Go/No-Go Release Decision Policy Gate
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/decisions`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Release Decisions|Go\/No-Go|Decisions/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2500);

    // -------------------------------------------------------------------------
    // SCENE 10: Observability, PII Redaction & Governance Timeline
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/observability`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Observability|Live Telemetry/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    await page.goto("/admin/compliance");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Compliance & Governance Center|Compliance/i }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Retention Policies|Legal Holds|Evidence Bundles|Assessments/i).first()).toBeVisible();
    await page.waitForTimeout(2000);

    // Conclude on the Release Decisions policy view
    await page.goto(`/projects/${projectId}/decisions`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Release Decisions|Go\/No-Go|Decisions/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3000);
  });
});

import { test, expect } from "@playwright/test";

/**
 * AIREX — Final Product Walkthrough Video Recording
 * 
 * Scenario:
 * "Evaluating an Enterprise Customer Support AI Assistant before production deployment,
 * verifying safety, correctness, helpfulness, live LLM-as-a-Judge scoring, Go/No-Go
 * Release Gate decisions, and immutable audit logs."
 * 
 * Verified Run ID: 51fdf315-2e54-4d07-9fb5-eaac65ec49b5
 */

test.describe("AIREX — Final Product Walkthrough", () => {
  test.setTimeout(240000);

  const demoUser = {
    email: "sarah.chen@enterprise-support.ai",
    password: "EnterpriseReliability2026!",
  };

  const projectId = "20e4e09a-dcaf-48b4-a156-d5f223fbdee2";
  const orgId = "9b6cfd2b-2d71-42ff-a746-78b860a15022";
  const runId = "51fdf315-2e54-4d07-9fb5-eaac65ec49b5";
  const decisionId = "c169d165-4e85-4534-92df-63786b0ff220";

  test("Complete Customer Support AI Release Evaluation Walkthrough", async ({ page, context }) => {
    // -------------------------------------------------------------------------
    // STEP A: Open AIREX Landing / Login & Executive Dashboard
    // -------------------------------------------------------------------------
    // Perform API login to retrieve token and set in context
    const loginRes = await page.request.post("http://localhost:8000/api/v1/auth/login", {
      data: {
        email: demoUser.email,
        password: demoUser.password,
      },
    });
    expect(loginRes.ok()).toBeTruthy();
    const loginData = await loginRes.json();
    const token = loginData.data.access_token;

    await context.addInitScript(
      ({ t, o }) => {
        window.localStorage.setItem("airex.access_token", t);
        window.localStorage.setItem("airex.organization_id", o);
      },
      { t: token, o: orgId }
    );

    await page.goto("/login");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Welcome to AIREX/i }).first()).toBeVisible({ timeout: 15000 });

    await page.getByTestId("login-email").fill(demoUser.email);
    await page.getByTestId("login-password").fill(demoUser.password);
    await page.waitForTimeout(800);

    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByTestId("dashboard-heading")).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3000);

    // -------------------------------------------------------------------------
    // STEP B: Select Customer Support AI Project
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Customer Support AI/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2500);

    // -------------------------------------------------------------------------
    // STEP C: Inspect Customer Support Benchmark Dataset & Ground Truth Test Cases
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/datasets`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Datasets|Test Datasets/i }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Customer Support Live Quality Dataset/i).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3000);

    // -------------------------------------------------------------------------
    // STEP D: Target Model Configuration (Anthropic Claude Haiku 4.5)
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/providers`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /AI Providers|Model Providers|Providers/i }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Anthropic Production Provider/i).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3000);

    await page.goto(`/projects/${projectId}/models`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Models|AI Models/i }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Customer-Support-Target-Assistant/i).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Claude-Judge-Evaluator/i).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3000);

    // -------------------------------------------------------------------------
    // STEP E: Configure Multi-Criteria Quality Rubrics & Evaluators
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/rubrics`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Rubrics|Evaluation Rubrics/i }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Customer Support Multi-Criteria Quality Rubric/i).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3000);

    // -------------------------------------------------------------------------
    // STEP F: Verified Live Evaluation Run (Run ID: 51fdf315-2e54-4d07-9fb5-eaac65ec49b5)
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/evaluations/${runId}`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByTestId("evaluation-run-title")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("eval-metrics-grid")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("eval-pass-rate")).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3500);

    // -------------------------------------------------------------------------
    // STEP G & H: Generated Responses, Safety Refusal & Judge Reasoning
    // -------------------------------------------------------------------------
    // Scroll down to individual test case results
    await page.evaluate(() => window.scrollBy({ top: 400, behavior: "smooth" }));
    await page.waitForTimeout(4000);

    // -------------------------------------------------------------------------
    // STEP I: Release Decision Cockpit (Go/No-Go Gate)
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/decisions/${decisionId}`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByTestId("decision-cockpit-title")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("decision-outcome-banner")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("readiness-score")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Decision Engine Explanation/i).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(4000);

    // Scroll down to deterministic check breakdown table
    await page.evaluate(() => window.scrollBy({ top: 450, behavior: "smooth" }));
    await page.waitForTimeout(3500);

    // -------------------------------------------------------------------------
    // STEP J: Audit Trail & Compliance Evidence
    // -------------------------------------------------------------------------
    await page.goto("/admin/compliance");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("heading", { name: /Compliance & Governance Center|Compliance/i }).first()).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3500);

    // Return to Decision Cockpit for final scene conclusion
    await page.goto(`/projects/${projectId}/decisions/${decisionId}`);
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByTestId("decision-outcome-banner")).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(4000);
  });
});

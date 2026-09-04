import { test, expect } from "@playwright/test";

/**
 * AIREX End-to-End Product Demo Test Suite
 * 
 * Executes an authentic, live product walkthrough across all core capabilities:
 * 1. Authentication & Workspace Landing
 * 2. Executive Dashboard & Metrics
 * 3. Project Creation & Setup
 * 4. Model Provider Registration & Connection Health Test
 * 5. Model Deployment & Live Prompt Test Console
 * 6. Dynamic Rubric Creation with Weighted Criteria
 * 7. Dataset Management & Version Upload
 * 8. Live Evaluation Execution & Score Breakdown
 * 9. A/B Experimentation & Regression Comparison
 * 10. Agent Tool Registry & Safety Manifest
 * 11. Go/No-Go Release Decision Governance Gate
 * 12. Observability Metrics & Trace Telemetry
 * 13. SRE Operations & Disaster Recovery Verification
 */

test.describe("AIREX Enterprise Platform Demo", () => {
  const timestamp = Date.now();
  const demoEmail = `demo-executive-${timestamp}@example.com`;
  const demoPassword = "DemoSecurePass2026!";
  const projectName = `Enterprise Support AI - ${timestamp.toString().slice(-4)}`;

  test("full product walkthrough from onboarding to governance & SRE operations", async ({
    page,
  }) => {
    // -------------------------------------------------------------------------
    // STEP 1: Registration & Onboarding
    // -------------------------------------------------------------------------
    await page.goto("/register");
    await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible({
      timeout: 15000,
    });

    await page.getByLabel("Full Name").fill("Dr. Sarah Chen, VP of AI Engineering");
    await page.getByLabel("Work Email").fill(demoEmail);
    await page.getByLabel("Password", { exact: true }).fill(demoPassword);
    await page.getByLabel("Confirm Password").fill(demoPassword);
    await page.getByRole("button", { name: "Create account" }).click();

    // -------------------------------------------------------------------------
    // STEP 2: Executive Dashboard
    // -------------------------------------------------------------------------
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 });
    await expect(
      page.getByRole("heading", { name: "AI Reliability Command Center" })
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Operational Status: All Systems Healthy")).toBeVisible();

    // Pause briefly for demo video viewer readability
    await page.waitForTimeout(1000);

    // -------------------------------------------------------------------------
    // STEP 3: Project Creation
    // -------------------------------------------------------------------------
    await page.goto("/projects/new");
    await expect(page.getByRole("heading", { name: "Create New Project" })).toBeVisible({
      timeout: 15000,
    });

    await page.getByLabel("Project Name").fill(projectName);
    await page
      .getByLabel("Description")
      .fill("Production customer-facing conversational assistant with strict reliability SLAs.");
    await page.getByRole("button", { name: "Create Project" }).click();

    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 20000 });
    const projectUrl = page.url();
    const projectId = projectUrl.split("/").pop()!;

    await expect(page.getByRole("heading", { name: projectName })).toBeVisible({
      timeout: 15000,
    });
    await page.waitForTimeout(800);

    // -------------------------------------------------------------------------
    // STEP 4: Provider Registration & Connection Health Test
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/providers`);
    await expect(
      page.getByRole("heading", { name: "Model Providers & Credentials" })
    ).toBeVisible({ timeout: 15000 });

    await page.getByLabel("Provider Name").fill("Production Local Gateway");
    await page.getByLabel("Provider Type").selectOption("LOCAL");
    await page.getByRole("button", { name: "Add Provider" }).click();

    await expect(
      page.getByRole("cell", { name: "Production Local Gateway", exact: true })
    ).toBeVisible({ timeout: 15000 });

    // Test connection health
    await page.getByRole("button", { name: "Test Connection", exact: true }).first().click();
    await expect(page.getByText("CONNECTED")).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(800);

    // -------------------------------------------------------------------------
    // STEP 5: Model Deployment & Live Test Console
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/models`);
    await expect(
      page.getByRole("heading", { name: "Models & Deployments" })
    ).toBeVisible({ timeout: 15000 });

    await page.getByLabel("Model Name").fill("Support-Assistant-v1");
    await page.getByLabel("Model Identifier").fill("support-assistant-v1");
    await page
      .getByLabel("Provider")
      .selectOption({ label: "Production Local Gateway (LOCAL)" });
    await page.getByRole("button", { name: "Register Model" }).click();

    await expect(
      page.getByRole("cell", { name: "Support-Assistant-v1", exact: true })
    ).toBeVisible({ timeout: 15000 });

    // Open Interactive Test Console
    await page.getByRole("button", { name: "Test Console" }).first().click();
    await expect(page.getByLabel("Prompt")).toBeVisible({ timeout: 10000 });
    await page
      .getByLabel("Prompt")
      .fill("How do I update my enterprise billing details in AIREX?");
    await page.getByRole("button", { name: "Run Model Inference" }).click();

    await expect(page.getByText("Inference Completed")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Latency")).toBeVisible();
    await page.waitForTimeout(1000);

    // -------------------------------------------------------------------------
    // STEP 6: Dynamic Rubric Creation with Weighted Criteria
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/rubrics`);
    await expect(
      page.getByRole("heading", { name: "Evaluation Rubrics & Criteria" })
    ).toBeVisible({ timeout: 15000 });

    await page.getByLabel("Rubric Name").fill("Enterprise Accuracy & Safety");
    await page
      .getByLabel("Description")
      .fill("Weighted rubric evaluating precision, safety constraints, and tonal compliance.");
    await page.getByRole("button", { name: "Create Rubric" }).click();

    await expect(
      page.getByRole("cell", { name: "Enterprise Accuracy & Safety", exact: true })
    ).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(800);

    // -------------------------------------------------------------------------
    // STEP 7: Dataset & Version Management
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/datasets`);
    await expect(
      page.getByRole("heading", { name: "Datasets & Ground Truth QA" })
    ).toBeVisible({ timeout: 15000 });

    await page.getByLabel("Dataset Name").fill("Customer Support Golden Set");
    await page
      .getByLabel("Description")
      .fill("Verified customer inquiries with expected answers for regression benchmarking.");
    await page.getByRole("button", { name: "Create Dataset" }).click();

    await expect(
      page.getByRole("cell", { name: "Customer Support Golden Set", exact: true })
    ).toBeVisible({ timeout: 15000 });

    // Open dataset details and add a test case
    await page.getByRole("link", { name: "View Dataset" }).first().click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/datasets/`), {
      timeout: 15000,
    });

    // Populate a test case
    await page.getByLabel("Input Prompt").fill("Can I reset my password via SSO?");
    await page
      .getByLabel("Expected Output")
      .fill("Yes, SSO password resets are managed directly through your organization Identity Provider.");
    await page.getByRole("button", { name: "Add Test Case" }).click();

    await expect(
      page.getByText("Can I reset my password via SSO?")
    ).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(800);

    // -------------------------------------------------------------------------
    // STEP 8: Evaluation Execution & Live Results
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/evaluations`);
    await expect(
      page.getByRole("heading", { name: "Evaluation Runs" })
    ).toBeVisible({ timeout: 15000 });

    await page.getByLabel("Evaluation Name").fill("Baseline Model Golden Benchmark");
    await page.getByLabel("Model").selectOption({ label: "Support-Assistant-v1" });
    await page.getByLabel("Dataset").selectOption({ label: "Customer Support Golden Set" });
    await page.getByRole("button", { name: "Launch Evaluation" }).click();

    // Check evaluation in list and navigate to details
    await expect(
      page.getByRole("cell", { name: "Baseline Model Golden Benchmark", exact: true })
    ).toBeVisible({ timeout: 15000 });

    await page.getByRole("link", { name: "View Results" }).first().click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/evaluations/`), {
      timeout: 20000,
    });
    await expect(page.getByText("Evaluation Results")).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // -------------------------------------------------------------------------
    // STEP 9: A/B Experiments & Regression Comparison
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/experiments`);
    await expect(
      page.getByRole("heading", { name: "A/B Experiments & Regression Analysis" })
    ).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(800);

    // -------------------------------------------------------------------------
    // STEP 10: Agents & Tool Manifest Registry
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/agents`);
    await expect(
      page.getByRole("heading", { name: "Agent Fleet & Tool Governance" })
    ).toBeVisible({ timeout: 15000 });

    await page.getByLabel("Agent Name").fill("Billing Inquiries Agent");
    await page.getByLabel("Role").fill("Specialized agent with secure stripe tool access.");
    await page.getByRole("button", { name: "Register Agent" }).click();

    await expect(
      page.getByRole("cell", { name: "Billing Inquiries Agent", exact: true })
    ).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(800);

    // -------------------------------------------------------------------------
    // STEP 11: Release Decision Cockpit (Go / No-Go Gate)
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/decisions`);
    await expect(
      page.getByRole("heading", { name: "Release Decisions & Gate Cockpit" })
    ).toBeVisible({ timeout: 15000 });

    await page.getByLabel("Release Target / Description").fill("Candidate Release v1.0.0 - Production Gate");
    await page.getByRole("button", { name: "Create Release Decision" }).click();

    await expect(
      page.getByRole("cell", { name: "Candidate Release v1.0.0 - Production Gate", exact: true })
    ).toBeVisible({ timeout: 15000 });

    // Open decision details and evaluate policy
    await page.getByRole("link", { name: "Inspect Decision" }).first().click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/decisions/`), {
      timeout: 15000,
    });

    await page.getByRole("button", { name: "Evaluate Release Policies" }).click();
    await expect(page.getByText(/Readiness Score/i)).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // -------------------------------------------------------------------------
    // STEP 12: Observability & Tracing Telemetry
    // -------------------------------------------------------------------------
    await page.goto(`/projects/${projectId}/observability`);
    await expect(
      page.getByRole("heading", { name: "Telemetry & Performance Observability" })
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Total Invocations")).toBeVisible();
    await expect(page.getByText("Average Latency")).toBeVisible();

    // View Trace Explorer
    await page.getByRole("link", { name: "View All Traces" }).click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/observability/traces`), {
      timeout: 15000,
    });
    await expect(page.getByRole("heading", { name: "Trace Telemetry & Request Explorer" })).toBeVisible();
    await page.waitForTimeout(800);

    // -------------------------------------------------------------------------
    // STEP 13: SRE Operations & Disaster Recovery Verification
    // -------------------------------------------------------------------------
    await page.goto("/admin/operations");
    await expect(
      page.getByRole("heading", { name: "SRE Reliability, SLOs & Fleet Operations" })
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Overall Availability")).toBeVisible();
    await expect(page.getByText("Active Workers")).toBeVisible();

    // Run DR Restore Validation (Dry Run)
    await page.getByRole("button", { name: "Execute Restore Test (Dry Run)" }).click();
    await expect(page.getByText("Disaster Recovery Dry Run Succeeded")).toBeVisible({
      timeout: 15000,
    });
    await page.waitForTimeout(1200);

    // -------------------------------------------------------------------------
    // STEP 14: Sign Out & Clean Exit
    // -------------------------------------------------------------------------
    await page.getByTestId("sign-out-btn").click();
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Sign in to AIREX" })).toBeVisible();
  });
});

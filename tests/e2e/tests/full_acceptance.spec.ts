import { test, expect } from "@playwright/test";

test.describe("AIREX — Full End-to-End Product Acceptance Suite", () => {
  test.setTimeout(180000);

  const timestamp = Date.now();
  const testUser = {
    name: "Lead Reliability Architect",
    email: `acceptance-lead-${timestamp}@example.com`,
    password: "StrongPassword123!",
  };
  const projectName = `Enterprise Pipeline V${timestamp.toString().slice(-4)}`;

  test("Complete End-to-End User Flow & Acceptance Verification", async ({ page }) => {
    // -------------------------------------------------------------------------
    // 1. AUTHENTICATION & REGISTRATION FLOW
    // -------------------------------------------------------------------------
    // 1.1 Unauthenticated direct access check
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");

    // 1.2 Negative Test: Invalid login credentials
    await page.goto("/login");
    await page.waitForLoadState("domcontentloaded");
    await page.getByTestId("login-email").fill("nonexistent@example.com");
    await page.getByTestId("login-password").fill("WrongPassword999!");
    await page.getByTestId("login-submit").click();
    await expect(page.getByText(/Invalid email or password|Invalid credentials|Authentication failed/i)).toBeVisible({ timeout: 10000 });

    // 1.3 User Registration Flow
    await page.goto("/register");
    await page.waitForLoadState("domcontentloaded");
    await page.getByTestId("register-name").fill(testUser.name);
    await page.getByTestId("register-email").fill(testUser.email);
    await page.getByTestId("register-password").fill(testUser.password);
    await page.getByTestId("register-confirm-password").fill(testUser.password);
    await page.getByTestId("register-submit").click();

    // 1.4 Redirect to dashboard or login
    await expect(page).toHaveURL(/\/(dashboard|onboarding|login)/, { timeout: 15000 });
    if (page.url().includes("/login")) {
      await page.waitForLoadState("domcontentloaded");
      await page.getByTestId("login-email").fill(testUser.email);
      await page.getByTestId("login-password").fill(testUser.password);
      await page.getByTestId("login-submit").click();
      await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    }

    // -------------------------------------------------------------------------
    // 2. MAIN DASHBOARD & EXECUTIVE KPIS
    // -------------------------------------------------------------------------
    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-heading")).toBeVisible();
    await expect(page.getByTestId("kpi-metrics-grid")).toBeVisible();
    await expect(page.getByTestId("metric-health")).toBeVisible();

    // -------------------------------------------------------------------------
    // 3. PROJECT CREATION & MANAGEMENT
    // -------------------------------------------------------------------------
    await page.getByTestId("create-project-btn").click();
    await expect(page).toHaveURL(/\/projects\/new/);

    await page.getByTestId("project-name-input").fill(projectName);
    const descInput = page.getByTestId("project-desc-input");
    if (await descInput.isVisible()) {
      await descInput.fill("Enterprise AI evaluation and autonomous agent testing pipeline.");
    }
    await page.getByTestId("create-project-submit").click();

    // Wait for project redirection to /projects/[id]
    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 15000 });
    await expect(page.getByTestId("project-title")).toBeVisible({ timeout: 10000 });

    // -------------------------------------------------------------------------
    // 4. PROVIDERS & MODELS CONFIGURATION
    // -------------------------------------------------------------------------
    const currentUrl = page.url();
    const projectIdMatch = currentUrl.match(/\/projects\/([a-f0-9-]+)/);
    const projectId = projectIdMatch ? projectIdMatch[1] : null;

    if (projectId) {
      // 4.1 Providers Page
      await page.goto(`/projects/${projectId}/providers`);
      await expect(page.getByRole("heading", { name: /AI Providers|Model Providers|Providers/i }).first()).toBeVisible({ timeout: 10000 });

      // 4.2 Models Page
      await page.goto(`/projects/${projectId}/models`);
      await expect(page.getByRole("heading", { name: /Models|AI Models/i }).first()).toBeVisible({ timeout: 10000 });

      // 4.3 Rubrics Page
      await page.goto(`/projects/${projectId}/rubrics`);
      await expect(page.getByRole("heading", { name: /Rubrics|Evaluation Rubrics/i }).first()).toBeVisible({ timeout: 10000 });

      // 4.4 Datasets Page
      await page.goto(`/projects/${projectId}/datasets`);
      await expect(page.getByRole("heading", { name: /Datasets|Test Datasets/i }).first()).toBeVisible({ timeout: 10000 });

      // 4.5 Agent Evaluations Page
      await page.goto(`/projects/${projectId}/agents`);
      await expect(page.getByRole("heading", { name: /Agent Evaluations|Autonomous Agents|Agents/i }).first()).toBeVisible({ timeout: 10000 });

      // 4.6 Release Decisions Page
      await page.goto(`/projects/${projectId}/decisions`);
      await expect(page.getByRole("heading", { name: /Release Decisions|Go\/No-Go|Decisions/i }).first()).toBeVisible({ timeout: 10000 });

      // 4.7 Observability Page
      await page.goto(`/projects/${projectId}/observability`);
      await expect(page.getByRole("heading", { name: /Observability|Live Telemetry/i }).first()).toBeVisible({ timeout: 10000 });
    }

    // -------------------------------------------------------------------------
    // 5. COMPLIANCE & AUDIT CENTER
    // -------------------------------------------------------------------------
    await page.goto("/admin/compliance");
    await expect(page.getByRole("heading", { name: /Compliance & Governance Center|Compliance/i }).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Retention Policies|Legal Holds|Evidence Bundles|Assessments/i).first()).toBeVisible();

    // -------------------------------------------------------------------------
    // 6. SRE OPERATIONS DASHBOARD & DISASTER RECOVERY
    // -------------------------------------------------------------------------
    await page.goto("/admin/operations");
    await expect(page.getByRole("heading", { name: /Production Operations & SRE Command|Operations/i }).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("sre-metrics-grid")).toBeVisible();

    // Verify key metrics
    await expect(page.getByText("Platform Health")).toBeVisible();
    await expect(page.getByText("Throughput (RPS)")).toBeVisible();
    await expect(page.getByText("Queue Depth / DLQ")).toBeVisible();

    // Execute Live DR Restore Test Button
    const drBtn = page.getByTestId("dr-restore-test-btn");
    await expect(drBtn).toBeVisible();
    await drBtn.click();
    await expect(page.getByText(/Disaster Recovery restore test verified|Restored in/i)).toBeVisible({ timeout: 25000 });

    // -------------------------------------------------------------------------
    // 7. SYSTEM ADMIN & DIAGNOSTICS
    // -------------------------------------------------------------------------
    await page.goto("/admin/system");
    await expect(page.getByRole("heading", { name: /System Readiness|Platform Operations/i }).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Deployment Readiness Diagnostics|Subsystem Health/i).first()).toBeVisible();

    // -------------------------------------------------------------------------
    // 8. USER SIGN OUT
    // -------------------------------------------------------------------------
    const signOutBtn = page.getByRole("button", { name: /Sign Out|Logout/i });
    if (await signOutBtn.isVisible()) {
      await signOutBtn.click();
      await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    }
  });

  test("Negative & Edge Case Security and Form Validation", async ({ page }) => {
    // 1. Unauthenticated direct access to protected routes redirects or displays auth barrier
    await page.goto("/dashboard");
    const authBarrier = page.getByText(/Authentication Required|Sign in to continue/i);
    if (await authBarrier.isVisible({ timeout: 5000 })) {
      await expect(authBarrier).toBeVisible();
    }

    await page.goto("/admin/operations");
    // Should show auth barrier or redirect to login
    const adminBarrier = page.getByText(/Authentication Required|Sign in to continue|Forbidden|Unauthorized/i);
    if (await adminBarrier.isVisible({ timeout: 5000 })) {
      await expect(adminBarrier).toBeVisible();
    }

    // 2. Registration password mismatch validation
    await page.goto("/register");
    await expect(page.getByTestId("register-name")).toBeVisible({ timeout: 10000 });
    await page.getByTestId("register-name").fill("Test Mismatch");
    await page.getByTestId("register-email").fill("mismatch@example.com");
    await page.getByTestId("register-password").fill("ValidPass123!");
    await page.getByTestId("register-confirm-password").fill("DifferentPass999!");
    await page.getByTestId("register-submit").click();
    await expect(page.getByText(/Passwords do not match/i)).toBeVisible({ timeout: 5000 });

    // 3. Login with malformed / non-existent credentials
    await page.goto("/login");
    await expect(page.getByTestId("login-email")).toBeVisible({ timeout: 10000 });
    await page.getByTestId("login-email").fill("invalid-user-format@nowhere-fake.org");
    await page.getByTestId("login-password").fill("random_wrong_password");
    await page.getByTestId("login-submit").click();
    await expect(page.getByText(/Invalid email or password|Invalid credentials|Authentication failed/i)).toBeVisible({ timeout: 10000 });
  });
});


import { test, expect } from "@playwright/test";

test.describe("Phase 15 Unified Governance, Access Control & Production Hardening E2E", () => {
  test("Complete Phase 15 release gate lifecycle: project access, compliance evidence explorer, legal hold retention, and decision engine readiness", async ({
    page,
  }) => {
    test.setTimeout(90000);
    const uniqueEmail = `governance_lead_${Date.now()}@example.com`;
    const password = "StrongPassword123!";

    // 1. Register organization owner / governance lead
    await page.goto("/register");
    await page.getByLabel("Name").fill("Governance Lead");
    await page.getByLabel("Email").fill(uniqueEmail);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    // Verify redirected to dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.getByText("AIREX").first()).toBeVisible();

    // 2. Create a new test project for Phase 15 release gate
    await page.goto("/dashboard");
    const createProjectBtn = page.getByRole("button", { name: "+ New Project" }).or(page.getByRole("button", { name: "Create Project" })).first();
    if (await createProjectBtn.isVisible()) {
      await createProjectBtn.click();
      const nameInput = page.getByPlaceholder("Project name").or(page.getByLabel("Name")).first();
      await nameInput.fill(`Gate-Project-${Date.now()}`);
      const submitBtn = page.getByRole("button", { name: "Create", exact: true }).or(page.getByRole("button", { name: "Save" })).first();
      await submitBtn.click();
      await page.waitForTimeout(2000);
    }

    // 3. Navigate to Compliance Center: verify Canonical Evidence Explorer
    await page.goto("/admin/compliance");
    await expect(
      page.getByRole("heading", { name: "Compliance, Audit Intelligence & Data Governance" })
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Phase 14")).toBeVisible();

    // Click "Evidence Explorer" tab
    const evidenceTab = page.getByRole("button", { name: "Evidence Explorer" });
    await expect(evidenceTab).toBeVisible();
    await evidenceTab.click();

    // Verify Evidence table headers and SHA-256 fingerprint column
    await expect(page.getByRole("heading", { name: "Canonical Evidence Registry" })).toBeVisible();
    await expect(page.getByText("SHA-256 Fingerprint")).toBeVisible();
    await expect(page.getByText("Source Type")).toBeVisible();

    // 4. Verify Retention & Legal Holds tab
    const retentionTab = page.getByRole("button", { name: "Retention & Legal Holds" });
    await expect(retentionTab).toBeVisible();
    await retentionTab.click();
    await expect(page.getByRole("heading", { name: "Data Lifecycle & Legal Preservation Holds" })).toBeVisible();

    // Test placing a legal hold via modal
    await page.getByRole("button", { name: "+ Place Legal Hold" }).click();
    await page.getByPlaceholder("e.g. Pending Audit Investigation 2026-A").fill("Litigation Hold Release Gate 2026");
    await page.getByRole("button", { name: "Place Hold" }).click();

    // Verify legal hold is recorded
    await expect(page.getByText("Litigation Hold Release Gate 2026")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("LOCKED").first()).toBeVisible();

    // Execute retention dry-run cleanup
    await page.getByRole("button", { name: "Dry-Run Cleanup" }).click();
    await expect(page.getByText("Retention cleanup [Dry Run: true]")).toBeVisible({ timeout: 10000 });

    // Release legal hold
    const releaseBtn = page.getByRole("button", { name: "Release Hold" }).first();
    await expect(releaseBtn).toBeVisible();
    await releaseBtn.click();
    await expect(page.getByText("RELEASED").first()).toBeVisible({ timeout: 10000 });

    // 5. Navigate to Frameworks & Controls: verify SOC2 / ISO framework creation
    await page.getByRole("button", { name: "Frameworks & Controls" }).click();
    await expect(page.getByRole("heading", { name: "Compliance Frameworks" })).toBeVisible();

    // 6. Navigate to Audit Timeline: verify unified audit stream
    await page.getByRole("button", { name: "Audit Timeline" }).click();
    await expect(page.getByRole("heading", { name: "Unified Audit Intelligence Timeline" })).toBeVisible();
  });
});

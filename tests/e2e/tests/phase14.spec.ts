import { test, expect } from "@playwright/test";

test.describe("Phase 14 Compliance, Audit Intelligence & Data Governance E2E", () => {
  test("Complete compliance lifecycle: framework, controls, assessment run, approval, retention, legal holds, and audit timeline", async ({ page }) => {
    test.setTimeout(60000);
    const uniqueEmail = `compliance_officer_${Date.now()}@example.com`;
    const password = "StrongPassword123!";

    // 1. Register compliance officer
    await page.goto("/register");
    await page.getByLabel("Name").fill("Compliance Officer");
    await page.getByLabel("Email").fill(uniqueEmail);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    // Verify redirected to dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.getByText("AIREX").first()).toBeVisible();

    // 2. Navigate to Compliance Center console
    await page.goto("/admin/compliance");
    await expect(
      page.getByRole("heading", { name: "Compliance, Audit Intelligence & Data Governance" })
    ).toBeVisible();
    await expect(page.getByText("Phase 14")).toBeVisible();

    // 3. Tab: Frameworks & Controls
    await page.getByRole("button", { name: "Frameworks & Controls" }).click();
    await expect(page.getByRole("heading", { name: "Compliance Frameworks" })).toBeVisible();

    await page.getByRole("button", { name: "+ Add Framework" }).click();
    await expect(page.getByText("Create Compliance Framework")).toBeVisible();
    await page.getByPlaceholder("e.g. SOC2, ISO_27001, INTERNAL_POLICY").fill("SOC2_READINESS");
    await page.getByPlaceholder("Framework purpose and scope").fill("SOC 2 Type II Security & Governance");
    await page.getByRole("button", { name: "Create Framework" }).click();

    await expect(page.getByText("SOC2_READINESS", { exact: true }).first()).toBeVisible();

    // Select framework to add control
    await page.getByText("SOC2_READINESS", { exact: true }).first().click();
    await page.getByRole("button", { name: "+ Add Control" }).click();
    await page.getByPlaceholder("e.g. IAM-01, ENC-02, REL-03").fill("CC-01");
    await page.getByPlaceholder("Control requirement title").fill("Access Control Least Privilege");
    await page.getByRole("button", { name: "Save Control" }).click();

    await expect(page.getByText("CC-01")).toBeVisible();
    await expect(page.getByText("Access Control Least Privilege")).toBeVisible();

    // Activate and lock framework
    const activateBtn = page.getByRole("button", { name: "Activate & Lock" }).first();
    await expect(activateBtn).toBeVisible();
    await activateBtn.click();
    await expect(page.getByText("v1 ACTIVE")).toBeVisible();

    // 4. Tab: Assessments
    await page.getByRole("button", { name: "Assessments" }).click();
    await expect(page.getByRole("heading", { name: "Compliance Assessments" })).toBeVisible();

    await page.getByRole("button", { name: "+ New Assessment" }).click();
    await page.getByPlaceholder("e.g. Q3 2026 Production Security Assessment").fill("Q3 2026 SOC 2 Audit");
    await page.getByRole("button", { name: "Create Assessment" }).click();

    await expect(page.getByText("Q3 2026 SOC 2 Audit")).toBeVisible();

    // Run evaluation
    const runBtn = page.getByRole("button", { name: "Run Evaluation" }).first();
    await expect(runBtn).toBeVisible();
    await runBtn.click();

    // Approve assessment
    const approveBtn = page.getByRole("button", { name: "Approve" }).first();
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();
    await expect(page.getByText("APPROVED").first()).toBeVisible();

    // 5. Tab: Retention & Legal Holds
    await page.getByRole("button", { name: "Retention & Legal Holds" }).click();
    await expect(page.getByRole("heading", { name: "Data Lifecycle & Legal Preservation Holds" })).toBeVisible();

    await page.getByRole("button", { name: "+ Place Legal Hold" }).click();
    await page.getByPlaceholder("e.g. Pending Audit Investigation 2026-A").fill("Litigation Preservation 2026-A");
    await page.getByRole("button", { name: "Place Hold" }).click();

    await expect(page.getByText("Litigation Preservation 2026-A")).toBeVisible();
    await expect(page.getByText("LOCKED").first()).toBeVisible();

    // Dry-run cleanup
    await page.getByRole("button", { name: "Dry-Run Cleanup" }).click();
    await expect(page.getByText("Retention cleanup [Dry Run: true]")).toBeVisible();

    // Release legal hold
    const releaseBtn = page.getByRole("button", { name: "Release Hold" }).first();
    await expect(releaseBtn).toBeVisible();
    await releaseBtn.click();
    await expect(page.getByText("RELEASED").first()).toBeVisible();

    // 6. Tab: Audit Timeline
    await page.getByRole("button", { name: "Audit Timeline" }).click();
    await expect(page.getByRole("heading", { name: "Unified Audit Intelligence Timeline" })).toBeVisible();
  });
});

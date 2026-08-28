import { test, expect, Page } from "@playwright/test";

const EMAIL = `e2e-phase7-${Date.now()}@example.com`;
const PASSWORD = "StrongPassword123!";
const PROJECT_NAME = `E2E Phase7 ${Date.now()}`;

async function registerAndCreateProject(page: Page): Promise<string> {
  await page.goto("/register");
  await page.getByLabel("Name").fill("Phase7 User");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Confirm Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });

  await page.goto("/projects/new");
  await page.getByLabel("Name").fill(PROJECT_NAME);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 15000 });
  const url = page.url();
  return url.split("/").pop()!;
}

test.describe("Phase 7 CI/CD & Service Token E2E Journey", () => {
  test("Create, Rotate, Revoke Service Tokens and check CI history layout", async ({ page }) => {
    const projectId = await registerAndCreateProject(page);

    // 1. Navigate to CI Settings page
    await page.goto(`/projects/${projectId}/settings/ci`);
    await expect(page.getByText("CI/CD Integration Settings")).toBeVisible();

    // 2. Create Service Token
    await page.getByLabel("Token Name").fill("GitHub actions deploy gate");
    await page.getByRole("button", { name: "Generate Token" }).click();

    // 3. Verify raw token is shown in alert
    await expect(page.getByText("New API Token Generated")).toBeVisible();
    await expect(page.getByText("Please copy your new API token now")).toBeVisible();
    
    // Dismiss raw token alert
    await page.getByRole("button", { name: "Dismiss" }).click();
    await expect(page.getByText("New API Token Generated")).not.toBeVisible();

    // 4. Verify token table contains the new token prefix row
    await expect(page.getByText("GitHub actions deploy gate")).toBeVisible();
    await expect(page.getByText("airex_ci_")).toBeVisible();

    // 5. Rotate Token
    await page.getByRole("button", { name: "Rotate" }).first().click();
    await expect(page.getByText("New API Token Generated")).toBeVisible();
    await page.getByRole("button", { name: "Dismiss" }).click();

    // 6. Revoke Token
    await page.getByRole("button", { name: "Revoke" }).first().click();
    await expect(page.getByText("GitHub actions deploy gate")).not.toBeVisible();

    // 7. Check CI History logs layout
    await page.goto(`/projects/${projectId}/ci-runs`);
    await expect(page.getByText("CI Run History & Provenance")).toBeVisible();
    await expect(page.getByText("Total Pipeline Runs")).toBeVisible();
    await expect(page.getByText("No CI runs executed yet")).toBeVisible();
  });
});

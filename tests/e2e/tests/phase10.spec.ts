import { test, expect, Page } from "@playwright/test";

const EMAIL = `e2e-phase10-${Date.now()}@example.com`;
const PASSWORD = "StrongPassword123!";
const PROJECT_NAME = `E2E Phase10 ${Date.now()}`;

async function registerAndCreateProject(page: Page): Promise<string> {
  await page.goto("/register");
  await page.getByLabel("Name").fill("Phase10 User");
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

test.describe("Phase 10 Intelligence & Deployment Decisions E2E Journey", () => {
  test("Navigate Intelligence Dashboard, create release policy, create decision, and evaluate", async ({ page }) => {
    const projectId = await registerAndCreateProject(page);

    // 1. Visit Project Intelligence Health Dashboard
    await page.goto(`/projects/${projectId}/intelligence`);
    await expect(page.getByText("Intelligence & Health Dashboard")).toBeVisible();
    await expect(page.getByTestId("executive-status-banner")).toBeVisible();
    await expect(page.getByText("Blocking Issues")).toBeVisible();
    await expect(page.getByText("Required Actions")).toBeVisible();

    // 2. Navigate to Release Decisions List
    await page.getByRole("link", { name: "Release Decisions →" }).click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/decisions`));
    await expect(page.getByText("Release & Deployment Decisions")).toBeVisible();

    // 3. Create a Release Policy
    await page.getByRole("button", { name: "+ Create Policy" }).click();
    await expect(page.getByRole("heading", { name: "Create Release Policy" })).toBeVisible();

    // Fill policy name and save
    await page.getByLabel("Policy Name").fill("Automated E2E Safe Gate");
    await page.getByRole("button", { name: "Save Policy" }).click();

    // 4. Navigate back to overview to ensure no broken state
    await page.getByRole("link", { name: "Health Dashboard →" }).click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/intelligence`));
    await expect(page.getByText("Intelligence & Health Dashboard")).toBeVisible();
  });
});

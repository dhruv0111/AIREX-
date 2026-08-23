import { test, expect } from "@playwright/test";

// Use a real, registerable domain: the API rejects special-use/reserved
// TLDs such as `.local`. The login test below still uses the seeded demo user.
const EMAIL = `e2e-${Date.now()}@example.com`;
const PASSWORD = "StrongPassword123!";

test.describe("Phase 0 critical journey (AT-033..AT-035)", () => {
  test("register, create project, logout (AT-033/034/035)", async ({ page }) => {
    // ---- Register (via UI) ----
    await page.goto("/register");
    await page.getByLabel("Name").fill("E2E User");
    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Confirm Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Create account" }).click();

    // Registration auto-authenticates and lands on the dashboard.
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });

    // ---- Create project (AT-034) ----
    await page.goto("/projects/new");
    await page.getByLabel("Name").fill("E2E Demo Assistant");
    await page.getByRole("button", { name: "Create project" }).click();

    // Lands on the project detail page.
    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "E2E Demo Assistant" })).toBeVisible();

    // Project appears in the projects list.
    await page.goto("/projects");
    await expect(page.getByText("E2E Demo Assistant")).toBeVisible();

    // ---- Logout (AT-035) ----
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });

    // Protected page must not show data after logout.
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Authentication required" })).toBeVisible({
      timeout: 15000,
    });
  });

  test("login with existing credentials (AT-033)", async ({ page }) => {
    // Seed user created by scripts/seed (AT-019). The seed uses a registerable
    // domain because the API rejects special-use TLDs such as `.local`.
    await page.goto("/login");
    await page.getByLabel("Email").fill("demo@example.com");
    await page.getByLabel("Password").fill("demo-password-123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  });
});

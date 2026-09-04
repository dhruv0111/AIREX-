import { test, expect } from "@playwright/test";

test.describe("Phase 12 Production Deployment, Enterprise Security & Platform Readiness E2E", () => {
  test("Complete journey: System readiness diagnostics, worker fleet, session management, and configuration fingerprint", async ({ page }) => {
    test.setTimeout(60000);
    const uniqueEmail = `admin_${Date.now()}@example.com`;
    const password = "StrongPassword123!";

    // 1. Register authenticated administrator
    await page.goto("/register");
    await page.getByLabel("Name").fill("Platform Admin");
    await page.getByLabel("Email").fill(uniqueEmail);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    // Verify redirected to dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.getByText("AIREX").first()).toBeVisible();

    // 2. Navigate to System Admin
    await page.goto("/admin/system");
    await expect(page.getByRole("heading", { name: "System Readiness & Platform Operations" })).toBeVisible();

    // 3. Verify Overall System Status Badge
    await expect(page.getByText(/System Status: (HEALTHY|DEGRADED)/i)).toBeVisible();

    // 4. Verify Deployment Readiness Diagnostics Table
    await expect(page.getByRole("heading", { name: "Deployment Readiness Diagnostics" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "database", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "database_migrations", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "task_queue", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "encryption_key", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "storage", exact: true })).toBeVisible();

    // 5. Verify Background Worker Fleet Card
    await expect(page.getByRole("heading", { name: "Background Worker Fleet" })).toBeVisible();

    // 6. Verify Authenticated User Sessions Table
    await expect(page.getByRole("heading", { name: "Authenticated User Sessions" })).toBeVisible();
    await expect(page.getByText("ACTIVE").first()).toBeVisible();

    // 7. Verify Schema Migration & Configuration Cards
    await expect(page.getByText("Database Schema Migration Status")).toBeVisible();
    await expect(page.getByText("Active Configuration Fingerprint")).toBeVisible();
    await expect(page.getByText(/001[34]_phase1[23]_[a-z_]+/i).first()).toBeVisible();

    // 8. Test Refresh Status button
    const refreshBtn = page.getByRole("button", { name: "Refresh Status" });
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();
    await expect(page.getByText("Deployment Readiness Diagnostics")).toBeVisible();
  });
});

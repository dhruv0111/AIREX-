import { test, expect } from "@playwright/test";

test.describe("Phase 16 Production Operations, SRE & Disaster Recovery E2E", () => {
  test("Complete Phase 16 SRE operations dashboard and DR restore test execution", async ({ page }) => {
    test.setTimeout(90000);
    const timestamp = Date.now();
    const email = `sre-operator-${timestamp}@example.com`;
    const password = "StrongPassword123!";

    // 1. Register new user
    await page.goto("/register");
    await page.getByLabel("Name").fill("SRE Lead Operator");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    // 2. Wait for redirect to dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });

    // 3. Navigate to Operations (SRE) Dashboard
    await page.waitForURL("**/dashboard");
    await page.getByRole("link", { name: "Operations (SRE)" }).click();
    await page.waitForURL("**/admin/operations");

    // 4. Verify Dashboard Header and Badges
    await expect(page.getByRole("heading", { name: "Production Operations & SRE" })).toBeVisible();
    await expect(page.getByText("Phase 16")).toBeVisible();

    // 5. Verify Core Metric Cards
    await expect(page.getByText("Platform Health")).toBeVisible();
    await expect(page.getByText("Throughput (RPS)")).toBeVisible();
    await expect(page.getByText("Latency (p95)")).toBeVisible();
    await expect(page.getByText("Queue Depth / DLQ")).toBeVisible();
    await expect(page.getByText("DB Pool Utilization")).toBeVisible();

    // 6. Verify Detailed Sections
    await expect(page.getByRole("heading", { name: "Live Traffic & Latency Percentiles" })).toBeVisible();
    await expect(page.getByText("p50 Median")).toBeVisible();
    await expect(page.getByText("p95 Percentile")).toBeVisible();
    await expect(page.getByText("p99 Percentile")).toBeVisible();

    await expect(page.getByRole("heading", { name: "Worker Fleet & Dead-Letter Queue" })).toBeVisible();
    await expect(page.getByText("Dead-Letter Queue (Poison Tasks):")).toBeVisible();

    await expect(page.getByRole("heading", { name: "Disaster Recovery (DR) & Business Continuity" })).toBeVisible();
    await expect(page.getByText("RPO (Recovery Point Objective)")).toBeVisible();
    await expect(page.getByText("RTO (Recovery Time Objective)")).toBeVisible();

    // 7. Execute Live Disaster Recovery Restore Test
    const restoreBtn = page.getByRole("button", { name: "Execute DR Restore Test" });
    await expect(restoreBtn).toBeVisible();
    await restoreBtn.click();

    // Verify success banner appears with measured restore time
    await expect(page.getByText(/Disaster Recovery restore test verified! Restored in/i)).toBeVisible({ timeout: 15000 });

    // 8. Test Refresh Telemetry action
    await page.getByRole("button", { name: "Refresh Telemetry" }).click();
    await expect(page.getByRole("heading", { name: "Production Operations & SRE" })).toBeVisible();
  });
});

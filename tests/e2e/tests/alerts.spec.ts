import { test, expect, Page } from "@playwright/test";

const EMAIL = `e2e-alerts-${Date.now()}@example.com`;
const PASSWORD = "StrongPassword123!";
const PROJECT_NAME = `E2E Alerts ${Date.now()}`;
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";

// The alert engine runs on the worker's periodic scheduler (~60s cadence), so
// this test intentionally waits for real alert production (no fake alerts).
test.setTimeout(240_000);

async function registerAndCreateProject(page: Page): Promise<string> {
  const uniqueEmail = `e2e-alerts-${Date.now()}-${Math.random().toString(36).substring(2, 7)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Name").fill("Alerts User");
  await page.getByLabel("Email").fill(uniqueEmail);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Confirm Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });

  await page.goto("/projects/new");
  await page.getByLabel("Name").fill(PROJECT_NAME);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 15000 });
  return page.url().split("/").pop()!;
}

async function ingestTraces(
  page: Page,
  projectId: string,
  statuses: string[],
  prefix: string,
) {
  const token = await page.evaluate(() => localStorage.getItem("airex.access_token"));
  const now = new Date().toISOString();
  const traces = statuses.map((status, i) => ({
    trace_id: `${prefix}_${i}_${Date.now()}`,
    environment: "production",
    service_name: "e2e-api",
    operation_name: "chat",
    start_time: now,
    end_time: now,
    status,
  }));
  const resp = await page.request.post(`${API_URL}/api/v1/observability/ingest`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Project-Id": projectId,
    },
    data: { traces, spans: [] },
  });
  expect(resp.status(), await resp.text()).toBe(202);
}

test.describe("Phase 8 Alerting E2E Journey", () => {
  test("Create rule, trigger alert, acknowledge, resolve", async ({ page }) => {
    page.on("console", (msg) => console.log("BROWSER CONSOLE:", msg.text()));
    page.on("pageerror", (err) => console.log("BROWSER PAGE ERROR:", err.message));
    
    const projectId = await registerAndCreateProject(page);

    // 1. Create an alert rule via the UI (error_rate > 0.1)
    await page.goto(`/projects/${projectId}/alerts/rules`);
    await page.getByLabel("Rule name").fill("E2E High Error Rate");
    await page.getByLabel("Metric").selectOption("error_rate");
    await page.getByLabel("Threshold").fill("0.1");
    await page.getByRole("button", { name: "Create rule" }).click();
    await expect(page.getByText("E2E High Error Rate")).toBeVisible();
    await expect(page.getByText("ENABLED")).toBeVisible();

    // 2. Ingest data crossing the threshold (3 errors + 1 success = 75% error)
    await ingestTraces(page, projectId, ["ERROR", "ERROR", "ERROR", "SUCCESS"], "alert_fail");

    // 3. Wait for the alert engine to trigger a real alert (worker cadence)
    await page.goto(`/projects/${projectId}/alerts`);
    await expect(page.getByText("Active", { exact: false }).first()).toBeVisible({ timeout: 15000 });
    await expect
      .poll(
        async () => {
          await page.reload();
          await expect(page.getByText("Loading alerts…")).not.toBeVisible({ timeout: 15000 });
          return page.getByText("TRIGGERED", { exact: true }).count();
        },
        { timeout: 180_000, intervals: [15_000] },
      )
      .toBeGreaterThan(0);

    // 4. Acknowledge the alert
    await page.getByRole("button", { name: "Acknowledge" }).first().click();
    await expect
      .poll(
        async () => {
          await page.reload();
          await expect(page.getByText("Loading alerts…")).not.toBeVisible({ timeout: 15000 });
          return page.getByText("ACKNOWLEDGED", { exact: true }).count();
        },
        { timeout: 45_000, intervals: [5_000] },
      )
      .toBeGreaterThan(0);

    // 5. Resolve the condition by diluting the error rate below 10%
    await ingestTraces(page, projectId, Array(40).fill("SUCCESS"), "alert_ok");

    // 6. Wait for the alert engine to resolve the incident
    await expect
      .poll(
        async () => {
          await page.reload();
          await expect(page.getByText("Loading alerts…")).not.toBeVisible({ timeout: 15000 });
          await page.getByRole("button", { name: /History/ }).click();
          return page.getByText("RESOLVED", { exact: true }).count();
        },
        { timeout: 210_000, intervals: [15_000] },
      )
      .toBeGreaterThan(0);
  });
});

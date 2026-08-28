import { test, expect, Page } from "@playwright/test";

// Use a real, registerable domain: the API's email validation rejects
// special-use/reserved TLDs such as `.local` (email-validator default).
const EMAIL = `e2e-phase1-${Date.now()}@example.com`;
const PASSWORD = "StrongPassword123!";
const PROJECT_NAME = `E2E Phase1 ${Date.now()}`;

async function registerAndCreateProject(page: Page): Promise<void> {
  const uniqueEmail = `e2e-phase1-${Date.now()}-${Math.random().toString(36).substring(2, 7)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Name").fill("Phase1 User");
  await page.getByLabel("Email").fill(uniqueEmail);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Confirm Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });

  await page.goto("/projects/new");
  await page.getByLabel("Name").fill(PROJECT_NAME);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 15000 });
  await expect(page.getByRole("heading", { name: PROJECT_NAME })).toBeVisible();
}

test.describe("Phase 1 provider/model journey (AT-P1-UI-001..013)", () => {
  test("create environment, provider, model, invoke (AT-P1-UI)", async ({ page }) => {
    await registerAndCreateProject(page);
    const url = page.url();
    const projectId = url.split("/").pop()!;

    // ---- Environment (AT-P1-UI: environments page) ----
    await page.goto(`/projects/${projectId}/environments`);
    await page.getByLabel("Environment name").fill("Production");
    // Explicitly choose the PRODUCTION type (the UI defaults to DEVELOPMENT).
    await page.getByLabel("Environment type").selectOption("PRODUCTION");
    await page.getByRole("button", { name: "Add environment" }).click();
    // Target the created table row cells (getByText would also match the hidden
    // <option>PRODUCTION</option> in the type dropdown → strict-mode violation).
    await expect(page.getByRole("cell", { name: "Production", exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("cell", { name: "PRODUCTION", exact: true })).toBeVisible();

    // ---- Provider (AT-P1-UI: providers page) ----
    await page.goto(`/projects/${projectId}/providers`);
    await page.getByLabel("Provider name").fill("Local E2E");
    // Provider type defaults to LOCAL, which needs no API key.
    await page.getByRole("button", { name: "Add provider" }).click();
    await expect(page.getByRole("cell", { name: "Local E2E", exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("cell", { name: "LOCAL", exact: true })).toBeVisible();

    // Connection test must report CONNECTED.
    await page.getByRole("button", { name: "Test", exact: true }).first().click();
    await expect(page.getByText("CONNECTED")).toBeVisible({ timeout: 10000 });

    // ---- Model (AT-P1-UI: models page + test console) ----
    await page.goto(`/projects/${projectId}/models`);
    await page.getByLabel("Model name").fill("Local Model");
    await page.getByLabel("Model identifier").fill("local-e2e-model");
    // Provider dropdown has a placeholder option; select the provider by label.
    await page.getByLabel("Provider").selectOption({ label: "Local E2E (LOCAL)" });
    await page.getByLabel("Environment").selectOption({ label: "Production (PRODUCTION)" });
    await page.getByRole("button", { name: "Add model" }).click();
    await expect(page.getByRole("cell", { name: "Local Model", exact: true })).toBeVisible({ timeout: 10000 });

    // Open the test console and invoke.
    await page.getByRole("button", { name: "Invoke" }).first().click();
    await page.getByLabel("Prompt").fill("What is 2 + 2?");
    await page.getByRole("button", { name: "Invoke" }).click();

    // The local adapter returns a deterministic response; latency + tokens render.
    await expect(page.getByText("Latency")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/in \//)).toBeVisible({ timeout: 15000 });
  });

  test("provider test console latency + tokens shown after invoke (AT-P1-UI-013)", async ({ page }) => {
    await registerAndCreateProject(page);
    const url = page.url();
    const projectId = url.split("/").pop()!;

    // Fast path through the API to set up resources so the UI test focuses on
    // the console output rendering.
    const token = await page.evaluate(() => localStorage.getItem("airex.access_token"));
    const orgId = await page.evaluate(() => localStorage.getItem("airex.organization_id"));
    const apiBase = process.env.E2E_API_URL ?? "http://localhost:8000";
    const headers = {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Organization-Id": orgId ?? "",
    };

    const provider = await page.request.post(`${apiBase}/api/v1/providers`, {
      headers,
      data: { provider_type: "LOCAL", name: "Local E2E 2", configuration: { latency_ms: 3 } },
    });
    expect(provider.ok()).toBeTruthy();
    const providerId = (await provider.json()).data.id;

    await page.request.post(`${apiBase}/api/v1/projects/${projectId}/models`, {
      headers,
      data: {
        name: "Local Model 2",
        model_identifier: "local-e2e-2",
        provider_id: providerId,
        configuration: { retry_policy: { max_retries: 0 } },
      },
    });

    await page.goto(`/projects/${projectId}/models`);
    await expect(page.getByText("Local Model 2")).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: "Invoke" }).first().click();
    await page.getByLabel("Prompt").fill("Hello!");
    await page.getByRole("button", { name: "Invoke" }).click();

    await expect(page.getByText("Latency")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Finish reason")).toBeVisible({ timeout: 15000 });
    const msText = await page.locator("text=/ms/").first().textContent();
    expect(msText).toContain("ms");
  });
});

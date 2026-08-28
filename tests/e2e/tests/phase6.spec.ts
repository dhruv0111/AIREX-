import { test, expect, Page } from "@playwright/test";

const EMAIL = `e2e-phase6-${Date.now()}@example.com`;
const PASSWORD = "StrongPassword123!";
const PROJECT_NAME = `E2E Phase6 ${Date.now()}`;
const BASE_IDENT = "baseline-model";
const CAND_IDENT = "candidate-model";

async function registerAndCreateProject(page: Page): Promise<string> {
  await page.goto("/register");
  await page.getByLabel("Name").fill("Phase6 User");
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

test.describe("Phase 6 Experimentation E2E Journey", () => {
  test("Complete Experiment wizard and execution journey (AT-P6-UI)", async ({ page }) => {
    const projectId = await registerAndCreateProject(page);

    // Fast-path provisioning of models and datasets
    const token = await page.evaluate(() => localStorage.getItem("airex.access_token"));
    const orgId = await page.evaluate(() => localStorage.getItem("airex.organization_id"));
    const apiBase = process.env.E2E_API_URL ?? "http://localhost:8000";
    const headers = {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Organization-Id": orgId ?? "",
    };

    // 1. Create provider
    const provider = await page.request.post(`${apiBase}/api/v1/providers`, {
      headers,
      data: { provider_type: "LOCAL", name: "Local E2E P6" },
    });
    expect(provider.ok()).toBeTruthy();
    const providerId = (await provider.json()).data.id;

    // 2. Create baseline model
    const baselineModel = await page.request.post(`${apiBase}/api/v1/projects/${projectId}/models`, {
      headers,
      data: {
        name: "Baseline Model",
        model_identifier: BASE_IDENT,
        provider_id: providerId,
        configuration: {},
      },
    });
    expect(baselineModel.ok()).toBeTruthy();

    // 3. Create candidate model
    const candidateModel = await page.request.post(`${apiBase}/api/v1/projects/${projectId}/models`, {
      headers,
      data: {
        name: "Candidate Model",
        model_identifier: CAND_IDENT,
        provider_id: providerId,
        configuration: {},
      },
    });
    expect(candidateModel.ok()).toBeTruthy();

    // 4. Create dataset
    const dataset = await page.request.post(`${apiBase}/api/v1/projects/${projectId}/datasets`, {
      headers,
      data: { name: "E2E Dataset" },
    });
    expect(dataset.ok()).toBeTruthy();
    const datasetId = (await dataset.json()).data.id;

    // 5. Create dataset version (with 6 test cases to satisfy Welch's minimum size of 5)
    const boundary = "------PlaywrightBoundary";
    let fileContent = "";
    for (let i = 0; i < 6; i++) {
      fileContent += `{"input": "What is 2+2? idx ${i}", "expected_output": "[local:${CAND_IDENT}] What is 2+2? idx ${i}"}\n`;
    }
    const datasetVersion = await page.request.post(`${apiBase}/api/v1/datasets/${datasetId}/versions`, {
      headers: {
        ...headers,
        "Content-Type": `multipart/form-data; boundary=${boundary}`,
      },
      data: `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="cases.jsonl"\r\nContent-Type: application/octet-stream\r\n\r\n${fileContent}\r\n--${boundary}\r\nContent-Disposition: form-data; name="format"\r\n\r\njsonl\r\n--${boundary}--\r\n`,
    });
    expect(datasetVersion.ok()).toBeTruthy();

    // ---- Run through UI Wizard ----
    await page.goto(`/projects/${projectId}/experiments/new`);

    // Step 1: Details
    await page.getByLabel("Name").fill("Wizard Experiment");
    await page.getByLabel("Description").fill("E2E test of the creation wizard");
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 2: Dataset
    await page.locator("#dataset-select").selectOption({ label: "E2E Dataset" });
    await page.locator("#dataset-version-select").selectOption({ index: 1 });
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 3: Baseline
    await page.locator("#baseline-model-select").selectOption({ label: "Baseline Model (baseline-model)" });
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 4: Candidate
    await page.locator("#candidate-model-select").selectOption({ label: "Candidate Model (candidate-model)" });
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 5: Quality Gates Setup
    await page.getByRole("button", { name: "Add Gate rule" }).click();
    await expect(page.getByText("exact_match (CANDIDATE_VALUE) GTE 0.9")).toBeVisible();
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 6: Review & Submit
    await page.getByRole("button", { name: "Create Experiment" }).click();

    // Should redirect to details page
    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+\/experiments\/[a-f0-9-]+/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Wizard Experiment" })).toBeVisible();

    // Trigger execution
    await page.getByRole("button", { name: "Run Experiment" }).click();

    // Check polling triggers completion and stats load
    await expect(page.getByText("COMPLETED")).toBeVisible({ timeout: 20000 });
    await expect(page.getByText("exact_match").first()).toBeVisible({ timeout: 10000 });
  });
});

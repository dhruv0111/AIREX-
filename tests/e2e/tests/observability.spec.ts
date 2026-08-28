import { test, expect, Page } from "@playwright/test";

const EMAIL = `e2e-obs-${Date.now()}@example.com`;
const PASSWORD = "StrongPassword123!";
const PROJECT_NAME = `E2E Observability ${Date.now()}`;
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const TRACE_ID = `e2e_trace_${Date.now()}`;
const SPAN_ID = `e2e_span_${Date.now()}`.slice(0, 16);

async function registerAndCreateProject(page: Page): Promise<string> {
  await page.goto("/register");
  await page.getByLabel("Name").fill("Obs User");
  await page.getByLabel("Email").fill(EMAIL);
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

async function ingestTrace(page: Page, projectId: string, traceId: string, spanId: string) {
  const token = await page.evaluate(() => localStorage.getItem("airex.access_token"));
  const now = new Date().toISOString();
  const end = new Date(Date.now() + 800).toISOString();
  const resp = await page.request.post(`${API_URL}/api/v1/observability/ingest`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Project-Id": projectId,
    },
    data: {
      traces: [
        {
          trace_id: traceId,
          environment: "production",
          service_name: "e2e-api",
          operation_name: "chat-completion",
          start_time: now,
          end_time: end,
          status: "SUCCESS",
          duration_ms: 800,
        },
      ],
      spans: [
        {
          trace_id: traceId,
          span_id: spanId,
          parent_span_id: null,
          name: "model-call",
          span_type: "LLM",
          provider: "openai",
          model: "gpt-4o",
          input_tokens: 1000,
          output_tokens: 500,
          total_tokens: 1500,
          start_time: now,
          end_time: end,
          status: "SUCCESS",
          duration_ms: 800,
        },
      ],
    },
  });
  expect(resp.status(), await resp.text()).toBe(202);
}

test.describe("Phase 8 Observability E2E Journey", () => {
  test("Dashboard, trace explorer, and trace detail reflect ingested data", async ({ page }) => {
    const projectId = await registerAndCreateProject(page);

    // 1. Empty state before any data
    await page.goto(`/projects/${projectId}/observability`);
    await expect(page.getByText("No observability data yet", { exact: false })).toBeVisible();

    // 2. Ingest a deterministic trace via the ingestion API
    await ingestTrace(page, projectId, TRACE_ID, SPAN_ID);

    // 3. Dashboard reflects the ingested request
    await page.goto(`/projects/${projectId}/observability`);
    await expect(page.getByText("1", { exact: true }).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Success Rate")).toBeVisible();
    await expect(page.getByText("gpt-4o", { exact: false }).first()).toBeVisible({ timeout: 15000 });

    // 4. Trace explorer lists the trace
    await page.goto(`/projects/${projectId}/observability/traces`);
    await expect(page.getByText(TRACE_ID)).toBeVisible({ timeout: 15000 });

    // 5. Open trace detail, verify span hierarchy + cost
    await page.goto(`/projects/${projectId}/observability/traces/${TRACE_ID}`);
    await expect(page.getByText("LLM", { exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("model-call")).toBeVisible();
    await expect(page.getByText("Tokens", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Cost", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("1500", { exact: true }).first()).toBeVisible();
  });
});

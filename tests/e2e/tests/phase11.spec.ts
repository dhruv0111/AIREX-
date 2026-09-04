import { test, expect, Page } from "@playwright/test";

const EMAIL = `e2e-phase11-${Date.now()}@example.com`;
const PASSWORD = "StrongPassword123!";
const PROJECT_NAME = `E2E Phase11 ${Date.now()}`;

async function registerAndCreateProject(page: Page): Promise<string> {
  await page.goto("/register");
  await page.getByLabel("Name").fill("Phase11 Release User");
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

test.describe("Phase 11 AI Agent Evaluation & Trajectory Testing Full User Journey", () => {
  test("Complete journey: Register tool, create agent, standard run, loop detection, safety blocking, and trajectory explorer", async ({ page }) => {
    test.setTimeout(60000);
    const projectId = await registerAndCreateProject(page);

    // 1. Visit Agents & Tools Registry
    await page.goto(`/projects/${projectId}/agents`);
    await expect(page.getByText("AI Agents & Tool Registry")).toBeVisible();
    await expect(page.getByText("No agents configured yet")).toBeVisible();

    // 2. Register a Tool Definition
    await page.getByRole("button", { name: "+ Register Tool" }).click();
    await expect(page.getByRole("heading", { name: "Register Tool Definition" })).toBeVisible();
    await page.getByPlaceholder("e.g., search_database").fill("market_data_api");
    await page.getByRole("button", { name: "Register Tool", exact: true }).click();
    await expect(page.getByText("market_data_api")).toBeVisible();

    // 3. Create Agent Definition
    await page.getByRole("button", { name: "+ Create Agent" }).click();
    await expect(page.getByRole("heading", { name: "Create AI Agent Definition" })).toBeVisible();
    await page.getByPlaceholder("e.g., Research Analyst Agent").fill("E2E Market Analyst");
    await page.getByRole("button", { name: "Create Agent", exact: true }).click();
    await expect(page.getByText("E2E Market Analyst")).toBeVisible();

    // 4. Navigate to Agent Runs
    await page.getByRole("link", { name: "View Agent Runs" }).click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/agent-runs`));
    await expect(page.getByText("Agent Trajectory Runs")).toBeVisible();

    // 5. Trigger Standard Nominal Run
    await page.getByRole("button", { name: "+ Trigger Agent Run" }).click();
    await expect(page.getByRole("heading", { name: "Trigger Agent Task Trajectory" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Start Trajectory Run" })).toBeEnabled({ timeout: 10000 });
    await page.getByRole("button", { name: "Start Trajectory Run" }).click();

    // Verify redirect to Trajectory Explorer
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/agent-runs/[a-f0-9-]+`), { timeout: 15000 });
    await expect(page.getByText("Trajectory Explorer")).toBeVisible();
    await expect(page.getByText("Agent Reliability Score")).toBeVisible();
    await expect(page.getByText("Interactive Execution Trajectory")).toBeVisible();
    await expect(page.getByText("Deterministic Trajectory Evaluation Checks")).toBeVisible();

    // 6. Test Step Expansion in Trajectory Explorer
    const stepCards = page.locator("button:has-text('View Input Arguments')");
    if (await stepCards.count() > 0) {
      await stepCards.first().click();
      await expect(page.getByText("Input Arguments")).toBeVisible();
    }

    // 7. Trigger Run with Simulated Loop
    await page.goto(`/projects/${projectId}/agent-runs`);
    await page.getByRole("button", { name: "+ Trigger Agent Run" }).click();
    await expect(page.getByRole("heading", { name: "Trigger Agent Task Trajectory" })).toBeVisible();
    await page.getByTestId("sim-scenario-select").selectOption("loop");
    await expect(page.getByRole("button", { name: "Start Trajectory Run" })).toBeEnabled({ timeout: 10000 });
    await page.getByRole("button", { name: "Start Trajectory Run" }).click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/agent-runs/[a-f0-9-]+`), { timeout: 15000 });
    await expect(page.getByText(/Loop Detected|Loop Warning/i).first()).toBeVisible();

    // 8. Trigger Run with Forbidden Tool (Safety Blocking Invariant)
    await page.goto(`/projects/${projectId}/agent-runs`);
    await page.getByRole("button", { name: "+ Trigger Agent Run" }).click();
    await expect(page.getByRole("heading", { name: "Trigger Agent Task Trajectory" })).toBeVisible();
    await page.getByTestId("sim-scenario-select").selectOption("forbidden");
    await expect(page.getByRole("button", { name: "Start Trajectory Run" })).toBeEnabled({ timeout: 10000 });
    await page.getByRole("button", { name: "Start Trajectory Run" }).click();
    await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/agent-runs/[a-f0-9-]+`), { timeout: 15000 });
    await expect(page.getByText(/BLOCKED|Critical Safety Violation/i).first()).toBeVisible();
  });
});

import { test, expect } from "@playwright/test";

test.describe("Phase 13 Enterprise Identity, Collaboration & Governance E2E", () => {
  test("Complete enterprise lifecycle: SSO, verified domains, teams, governance policies, approvals, and access reviews", async ({ page }) => {
    test.setTimeout(60000);
    const uniqueEmail = `enterprise_admin_${Date.now()}@example.com`;
    const password = "StrongPassword123!";

    // 1. Register administrator
    await page.goto("/register");
    await page.getByLabel("Name").fill("Enterprise Administrator");
    await page.getByLabel("Email").fill(uniqueEmail);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    // Verify redirected to dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.getByText("AIREX").first()).toBeVisible();

    // 2. Navigate to Enterprise Admin console
    await page.goto("/admin/enterprise");
    await expect(page.getByRole("heading", { name: "Enterprise Identity, Collaboration & Governance" })).toBeVisible();

    // 3. Tab 1: Identity Providers (SSO)
    await expect(page.getByRole("heading", { name: "Enterprise Identity Providers" })).toBeVisible();
    await page.getByRole("button", { name: "+ Add Identity Provider" }).click();
    await expect(page.getByText("Add Enterprise Identity Provider")).toBeVisible();
    await page.getByPlaceholder("e.g. Okta Corporate, Google Workspace").fill("Okta Workforce SSO");
    await page.getByPlaceholder("client_12345").fill("okta_client_101");
    await page.getByPlaceholder("••••••••••••").fill("my-secure-client-secret-9988");
    await page.getByRole("button", { name: "Save Provider" }).click();

    // Verify IdP created with masked secret
    await expect(page.getByText("Okta Workforce SSO")).toBeVisible();
    await expect(page.getByText("my-****9988")).toBeVisible();

    // 4. Tab 2: Verified Domains
    await page.getByRole("button", { name: "Verified Domains" }).click();
    await expect(page.getByRole("heading", { name: "Organization Domains" })).toBeVisible();
    await page.getByRole("button", { name: "+ Register Domain" }).click();
    await page.getByPlaceholder("e.g. acme-corp.com").fill("acme-enterprise.ai");
    await page.getByRole("button", { name: "Register Domain", exact: true }).click();

    await expect(page.getByText("acme-enterprise.ai")).toBeVisible();
    await expect(page.getByText("PENDING").first()).toBeVisible();

    // Verify domain
    const verifyBtn = page.getByRole("button", { name: "Verify Now" }).first();
    await expect(verifyBtn).toBeVisible();
    await verifyBtn.click();
    await expect(page.getByText("VERIFIED").first()).toBeVisible();

    // 5. Tab 3: Teams & Project Access
    await page.getByRole("button", { name: "Teams & Project Access" }).click();
    await expect(page.getByRole("heading", { name: "Teams & Collaborative Workspaces" })).toBeVisible();
    await page.getByRole("button", { name: "+ Create Team" }).click();
    await page.getByPlaceholder("e.g. Safety Red Team, Core LLM Engineers").fill("Core Safety Engineering");
    await page.getByPlaceholder("Team responsibilities and scope").fill("Safety benchmarks and red-teaming");
    await page.getByRole("button", { name: "Create Team", exact: true }).click();

    await expect(page.getByText("Core Safety Engineering")).toBeVisible();
    await expect(page.getByText("core-safety-engineering")).toBeVisible();

    // 6. Tab 4: Governance Policies
    await page.getByRole("button", { name: "Governance Policies" }).click();
    await expect(page.getByRole("heading", { name: "Organization Governance Policies" })).toBeVisible();
    await page.getByRole("button", { name: "+ Create Policy" }).click();
    await page.getByPlaceholder("e.g. Enterprise Production Guardrails").fill("Production Deployment Guardrail Policy");
    await page.getByPlaceholder("Details about enforcement rules").fill("Requires release decision readiness >= 80%");
    await page.getByRole("button", { name: "Create Policy", exact: true }).click();

    await expect(page.getByText("Production Deployment Guardrail Policy")).toBeVisible();
    const activateBtn = page.getByRole("button", { name: "Activate" }).first();
    await expect(activateBtn).toBeVisible();
    await activateBtn.click();
    await expect(page.getByText("ACTIVE").first()).toBeVisible();

    // 7. Tab 5: Approval Workflows
    await page.getByRole("button", { name: "Approval Workflows" }).click();
    await expect(page.getByRole("heading", { name: "Approval Workflows" })).toBeVisible();
    await page.getByRole("button", { name: "+ Request Approval" }).click();
    await page.getByPlaceholder("e.g. Production Deployment Approval for GPT-4o v2").fill("Deploy Customer Care Assistant v2");
    await page.getByPlaceholder("UUID or identifier").fill("rel_dec_prod_001");
    await page.getByRole("button", { name: "Submit Request", exact: true }).click();

    await expect(page.getByText("Deploy Customer Care Assistant v2")).toBeVisible();
    await expect(page.getByText("PENDING").first()).toBeVisible();

    // 8. Tab 6: Access Reviews
    await page.getByRole("button", { name: "Access Reviews" }).click();
    await expect(page.getByRole("heading", { name: "Access Review Campaigns" })).toBeVisible();
    await page.getByRole("button", { name: "+ Start Access Review" }).click();
    await page.getByPlaceholder("e.g. Q3 2026 Privilege & Token Audit").fill("Q3 Enterprise Access Review");
    await page.getByRole("button", { name: "Launch Campaign", exact: true }).click();

    await expect(page.getByText("Q3 Enterprise Access Review")).toBeVisible();
    await expect(page.getByText(/Review Items/i)).toBeVisible();
  });
});

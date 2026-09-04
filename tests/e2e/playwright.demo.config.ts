import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: ["**/final_product_walkthrough.spec.ts"],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 240000,
  reporter: [["list"], ["html", { outputFolder: "playwright-report-demo", open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    viewport: { width: 1440, height: 900 },
    video: {
      mode: "on",
      size: { width: 1440, height: 900 },
    },
    trace: "on",
    screenshot: "on",
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  outputDir: "test-results/demo-recordings",
  projects: [
    {
      name: "demo-recording",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 1,
        launchOptions: {
          slowMo: 400, // Smooth pacing for professional demo video readability
        },
      },
    },
  ],
});

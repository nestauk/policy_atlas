import { defineConfig, devices } from "@playwright/test";

/**
 * Isolated configuration for the built-frontend/real-API smoke. The shell
 * runner owns both servers because it must inject a freshly minted dev token
 * and a real API base URL at build time; this config only drives that site.
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "fe-api-smoke.spec.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: process.env.FE_API_SMOKE_FRONTEND_URL ?? "http://127.0.0.1:4174",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});

import { defineConfig, devices } from "@playwright/test";

/**
 * One-off configuration for the task-027 acceptance live check (G.1): the
 * dev SPA on :5173 (VITE_DEV_TOKEN-authenticated) against the REAL backend
 * and the real chain at rapid effort. Deliberately excluded from CI and from
 * the mock config — the spec restarts the API process mid-flight, spends
 * provider credits, and takes tens of minutes. Run explicitly with:
 *   pnpm playwright test --config playwright.live-027.config.ts
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: process.env.LIVE_PART === "b" ? "live-027b.spec.ts" : "live-027.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  timeout: 45 * 60 * 1000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});

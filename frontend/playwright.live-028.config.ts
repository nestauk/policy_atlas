import { defineConfig, devices } from "@playwright/test";

/**
 * One-off configuration for the task-028 acceptance live check (G.2): the
 * dev SPA on :5173 (VITE_DEV_TOKEN-authenticated) against the REAL backend
 * and the real planner/chain. Deliberately excluded from CI and the mock
 * config — the spec restarts the API mid-planning, spends provider credits,
 * and takes tens of minutes. Run explicitly with:
 *   LIVE_TOKEN=… pnpm playwright test --config playwright.live-028.config.ts
 * LIVE_LEG=a or b runs one leg alone.
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "live-028.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  timeout: 60 * 60 * 1000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    // A pause card can be answered between locating a button and clicking
    // it (SSE resolves mid-action) — never let a click wait forever.
    actionTimeout: 15_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});

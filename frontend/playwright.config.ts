import { defineConfig, devices } from "@playwright/test";

/**
 * Mock-mode journey config (task 025 I.1). The dev server is started with
 * `VITE_MOCK=1` so every `/api/v1/*` call is served by `src/mock/api.ts` —
 * no backend, no Postgres, no auth infrastructure required. Vite's own
 * default port (5173) is used as-is; chromium only (owner scope for this
 * slice's acceptance pass).
 */
const PORT = 5173;

export default defineConfig({
  testDir: "./e2e",
  // The real-API smoke owns its own built-site/server lifecycle in
  // scripts/fe_api_smoke.sh. It must never be picked up by this mock-only
  // suite, whose web server intercepts every API call.
  testIgnore: "**/fe-api-smoke.spec.ts",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  webServer: {
    command: "pnpm dev",
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { VITE_MOCK: "1" },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});

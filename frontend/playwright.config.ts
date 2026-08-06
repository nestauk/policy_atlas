import { defineConfig, devices } from "@playwright/test";

/**
 * Mock-mode journey config (task 025 I.1). The dev server is started with
 * `VITE_MOCK=1` so every `/api/v1/*` call is served by `src/mock/api.ts` —
 * no backend, no Postgres, no auth infrastructure required. Chromium only
 * (owner scope for this slice's acceptance pass).
 *
 * Own port, never 5173: with `reuseExistingServer` a developer's running
 * `make dev` server would silently absorb this suite into the REAL app
 * (the mock-fetch-blindness trap, docs/knowledge) — mock asserts then fail
 * against real projects, or worse, pass against them.
 */
const PORT = 5199;

export default defineConfig({
  testDir: "./e2e",
  // The real-API smoke owns its own built-site/server lifecycle in
  // scripts/fe_api_smoke.sh. It must never be picked up by this mock-only
  // suite, whose web server intercepts every API call.
  // live-027 is the task-027 acceptance drive: real backend, real chain,
  // restarts the API process — never part of this suite or CI.
  testIgnore: ["**/fe-api-smoke.spec.ts", "**/live-027*.spec.ts", "**/live-028.spec.ts"],
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  webServer: {
    command: `pnpm dev --port ${PORT} --strictPort`,
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

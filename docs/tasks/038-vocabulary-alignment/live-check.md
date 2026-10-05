# Local live check — task 038 (contract § Acceptance, pre-merge half)

Run 2026-09-05 against `make dev` (API :8000, Vite :5173 with the dev token) plus a second token-less Vite on :5174 for the signed-out leg, on the dev database migrated to `c1a7f4e9b0d2` (52 real Tasks). The Chrome extension was not connected, so the browser part ran as the Playwright spec below (real browser, real API, real rows). Results: **4 passed**.

## Commands

```bash
make dev                                   # API :8000 + Vite :5173 (dev token)
cd frontend && pnpm dev --port 5174 --strictPort   # signed-out frontend, same API
cd backend && uv run python -m policy_atlas.api.dev_issuer mint --dir .dev-issuer --sub dev-user --client-id policy-atlas-dev --ttl 3600 | tail -1   # token for curl
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/tasks?page_size=3"      # 20 tasks, project_ids
curl -H "Authorization: Bearer $TOKEN"  http://localhost:8000/api/v1/projects               # 1 project, task_count 3
curl -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/portfolios   # 404
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"is_public\": true}" http://localhost:8000/api/v1/tasks/$TASK_ID   # then signed-out GET -> 200; old /api/v1/projects/$TASK_ID -> 401
cd frontend && TASK_ID=fdfe3811-cea5-4d8e-91c3-e6435fdb3a56 PROJECT_ID=97a96376-92d9-48ae-a19e-78efb23e3f58 npx playwright test --config live-038.config.ts   # 4 passed (3.7s)
make fe-api-smoke                          # see verification.md
```

## The spec (`live-038.spec.ts`; config = testDir + baseURL http://localhost:5173, no webServer)

```ts
// Task 038 local live check (contract § Acceptance, pre-merge half): one real
// Task through Agent → Result → Sources → Share → History, its Project, and one
// signed-out public Task URL — against `make dev` (Vite :5173 with the dev
// token baked in, API :8000, the migrated dev database). Run:
//   cd frontend && TASK_ID=… PROJECT_ID=… npx playwright test \
//     --config /path/to/live-038.config.ts
import { expect, test } from "@playwright/test";

const TASK_ID = process.env.TASK_ID!;
const PROJECT_ID = process.env.PROJECT_ID!;
const TABS = ["Agent", "Result", "Sources", "Share", "History"] as const;

test("one Task through its five tabs, under the new words", async ({ page }) => {
  await page.goto(`/tasks/${TASK_ID}`);
  const nav = page.getByRole("navigation", { name: /task/i }).first();
  for (const label of TABS) {
    await expect(nav.getByRole("link", { name: label, exact: true })).toBeVisible();
  }
  // Old labels are gone.
  await expect(nav.getByRole("link", { name: "Plan", exact: true })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Results", exact: true })).toHaveCount(0);
  // Agent tab = index route (no /agent segment); the Agent overlay is present.
  await expect(page).toHaveURL(new RegExp(`/tasks/${TASK_ID}$`));
  await expect(page.getByRole("button", { name: /Open the Agent|Agent/ }).first()).toBeVisible();

  await nav.getByRole("link", { name: "Result", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/tasks/${TASK_ID}/result$`));
  await expect(page.getByRole("navigation", { name: "Contents" })).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveTitle(/Report/);

  await nav.getByRole("link", { name: "Sources", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/tasks/${TASK_ID}/sources`));

  await nav.getByRole("link", { name: "Share", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/tasks/${TASK_ID}/share$`));
  await expect(page.getByRole("region", { name: "Public link" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy link" })).toBeVisible();
  await expect(page.getByText(/this Task's result and sources/)).toBeVisible();

  await nav.getByRole("link", { name: "History", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/tasks/${TASK_ID}/history$`));
  // Pre-migration event rows read under the new words (V3 copy row, both event generations).
  await expect(page.getByText("Opened an evidence-search run.").first()).toBeVisible();
  await expect(page.getByText("Approved the plan.").first()).toBeVisible();
});

test("its Project lists it", async ({ page }) => {
  await page.goto(`/projects/${PROJECT_ID}`);
  await expect(page).toHaveURL(new RegExp(`/projects/${PROJECT_ID}$`));
  await expect(page.getByRole("link", { name: /Childhood Obesity/ }).first()).toBeVisible();
});

test("old URLs do not resolve (F3: no redirects)", async ({ page }) => {
  await page.goto(`/projects/${TASK_ID}/results`);
  await expect(page.getByRole("heading", { name: /unavailable|not found/i })).toBeVisible();
});

test("a signed-out visitor opens the public Task URL", async ({ browser }) => {
  // A second Vite dev server on :5174 runs WITHOUT the dev token, so the app is
  // signed out and serves the public router against the same API (:8000).
  const context = await browser.newContext({ baseURL: process.env.PUBLIC_BASE ?? "http://localhost:5174" });
  const page = await context.newPage();
  await page.goto(`/tasks/${TASK_ID}/result`);
  await expect(page.getByRole("navigation", { name: "Contents" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("link", { name: "Result", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Sources", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Share", exact: true })).toHaveCount(0);
  await context.close();
});
```

## Read models on the pre-migration Task (curl, new paths)

- `/api/v1/tasks/{id}/decisions`: 36 rows — kinds `plan.approved`, `run.opened`, `run.parked`, `run.finished`, `component.completed`, `search.executed`, `steering.decision`; `decided_by` `user`/`None` (this Task had no orchestrator-decided check-in).
- `/api/v1/tasks/{id}/conversations`: 2 rows — `kind` `planning`, `chat`.
- History tab renders the pre-migration `run.opened` event as "Opened an evidence-search run." (V3 copy row) and `plan.approved` as "Approved the plan.".
- The public flag was reset to `false` afterwards.

## Not covered locally (staging half, post-merge — contract P11)

One real Cognito sign-in round trip from a Task deep link (V11 is covered by the three `App.test.tsx` tests locally; the local dev issuer injects the token, so there is no redirect to round-trip), `rows assign --task` dry run against staging, `make fe-api-smoke` against staging.

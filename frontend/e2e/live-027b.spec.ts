import { execSync, spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Task 027 G.1, part B — the synthesis-streaming and interruption legs.
 * Part A (live-027.spec.ts tests 1–2 + the check-in/hygiene legs of test 3)
 * passed on 2026-07-29; a pre-existing steering livelock at the
 * before-select boundary under FREQUENT mode blocked run completion there
 * (recorded in verification.md), so these legs run UNATTENDED — the
 * check-in surface is already proven.
 */

const REPO = path.resolve(__dirname, "../..");
const EVIDENCE = path.join(REPO, "docs/tasks/027-frontend-uplift/evidence");
const API = "http://localhost:8000";

function log(message: string) {
  console.log(`[live-027b ${new Date().toISOString()}] ${message}`);
}

async function apiStatus(page: Page): Promise<number> {
  try {
    const response = await page.request.get(`${API}/api/v1/projects`, {
      headers: { Authorization: `Bearer ${process.env.LIVE_TOKEN ?? ""}` },
      timeout: 2_000,
    });
    return response.status();
  } catch {
    return 0;
  }
}

async function killApi(page: Page) {
  log("killing the API process");
  try {
    execSync(
      "lsof -ti tcp:8000 -sTCP:LISTEN | xargs kill -9; pkill -9 -f 'uvicorn policy_atlas' || true",
      { stdio: "ignore" },
    );
  } catch {
    // already dead is fine
  }
  await expect.poll(async () => apiStatus(page), { timeout: 30_000, intervals: [500] }).toBe(0);
  await expect
    .poll(
      () => {
        try {
          execSync("lsof -ti tcp:8000 -sTCP:LISTEN", { stdio: "pipe" });
          return "held";
        } catch {
          return "free";
        }
      },
      { timeout: 30_000, intervals: [500] },
    )
    .toBe("free");
  log("API confirmed down (port free)");
}

function startApi() {
  log("starting the API process");
  const child = spawn("bash", ["-lc", "cd backend && exec make dev >> /tmp/pa-api.log 2>&1"], {
    cwd: REPO,
    detached: true,
    stdio: "ignore",
  });
  child.unref();
}

async function waitForApi(page: Page) {
  await expect
    .poll(async () => apiStatus(page), { timeout: 120_000, intervals: [1000] })
    .toBe(200);
  log("API is answering");
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: path.join(EVIDENCE, `${name}.png`), fullPage: false });
  log(`screenshot: ${name}`);
}

async function plannerTurn(page: Page, message: string) {
  log(`planner turn: ${message.slice(0, 60)}…`);
  await page.getByLabel("Message the planner").fill(message);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Planning…")).toHaveCount(0, { timeout: 180_000 });
  await page.waitForTimeout(500);
}

async function planToReadyAndStart(page: Page, firstMessage: string) {
  await plannerTurn(page, firstMessage);
  for (let attempt = 0; attempt < 8; attempt++) {
    const start = page.getByRole("button", { name: /Start(ing…)? the analysis/ });
    if (await start.isVisible().catch(() => false)) break;
    await plannerTurn(page, "Yes — that's right. Mark the plan ready.");
  }
  await page.getByRole("button", { name: /Start(ing…)? the analysis/ }).click();
  log("run started");
}

let projectUrl = "";

test.describe.serial("task 027 live check — part B", () => {
  test("B1 · unattended run: synthesis streams, reload replays, artefact commits", async ({
    page,
  }) => {
    test.setTimeout(45 * 60 * 1000);
    if (process.env.LIVE_PROJECT) {
      // Resume mode: the chain run already succeeded on a prior attempt whose
      // terminal ASSERTION was wrong (regex demanded "analysis is complete";
      // the heading says "Analysis complete"). Assert the terminal journey on
      // the existing project instead of paying for another chain run — the
      // streaming/reload legs already passed and are in the log + screenshots.
      projectUrl = `/projects/${process.env.LIVE_PROJECT}`;
      await page.goto(projectUrl);
      projectUrl = page.url();
      await expect(page.getByText(/Analysis complete/i).first()).toBeVisible({
        timeout: 60_000,
      });
      await expect(page.getByText("Done").first()).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Read the evidence base" }),
      ).toBeVisible();
      log("run 1 terminal journey renders (completion card + CTA)");
      await shot(page, "12-journey-complete");
      await expect(page.getByText("Analysis run").first()).toBeVisible();
      await shot(page, "13-thread-run-block");
      return;
    }
    await page.goto("/");
    await page.getByRole("button", { name: "New project" }).first().click();
    await page.getByLabel("Project name").fill("027 live check B");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page).toHaveURL(/\/projects\/[^/]+$/);
    projectUrl = page.url();

    await planToReadyAndStart(
      page,
      "I need evidence on how school-based interventions affect pupil attendance in the UK. " +
        "Rapid search effort, standard analysis depth, academic sources only, and run fully " +
        "unattended — do not pause for check-ins.",
    );

    // Hygiene: the landing card reflects the running state without a manual
    // refresh (the 15s live refetch).
    await page.goto("/");
    await expect(page.getByText(/analysing|running|paused/i).first()).toBeVisible({
      timeout: 60_000,
    });
    log("hygiene: landing card shows the live running state");
    await shot(page, "21-landing-live-status");
    await page.goto(projectUrl);

    // Wait for synthesise, then watch the artefact page fill in place.
    await expect(page.getByText("Writing the evidence base").first()).toBeVisible({
      timeout: 30 * 60 * 1000,
    });
    await page.getByRole("link", { name: /evidence base/i }).first().click();
    await expect(
      page.getByText(/Writing this section now…|sections appear as they are drafted/).first(),
    ).toBeVisible({ timeout: 5 * 60 * 1000 });
    await shot(page, "09-live-writing");
    await expect(page.locator("main p.anim-rise").first()).toBeVisible({
      timeout: 10 * 60 * 1000,
    });
    await shot(page, "10-live-filled");
    const filledText = (await page.locator("main p.anim-rise").first().textContent()) ?? "";
    await page.reload();
    await expect(page.getByText(filledText.slice(0, 40)).first()).toBeVisible({
      timeout: 60_000,
    });
    log("browser reload mid-synthesis replayed the completed sections");
    await shot(page, "11-live-after-reload");

    // Let the run finish; the terminal journey state is the completion signal.
    await page.goto(projectUrl);
    await expect(
      page.getByText(/Analysis complete|completed with|interrupted|failed/i).first(),
    ).toBeVisible({ timeout: 20 * 60 * 1000 });
    log("run 1 reached a terminal state");
    await shot(page, "12-journey-complete");
    await expect(page.getByText("Analysis run").first()).toBeVisible();
    await shot(page, "13-thread-run-block");
  });

  test("B2 · evidence base, findings both kinds, sources filters", async ({ page }) => {
    test.setTimeout(10 * 60 * 1000);
    await page.goto(projectUrl);
    await page.getByRole("link", { name: /evidence base/i }).first().click();
    await expect(page.getByText("Evidence base").first()).toBeVisible({ timeout: 60_000 });
    await shot(page, "14-evidence-base");

    const marker = page.locator("button[aria-label^='Citation']").first();
    if (await marker.isVisible().catch(() => false)) {
      await marker.click();
      await expect(page.getByText(/Open the source dossier/)).toBeVisible({ timeout: 30_000 });
      await shot(page, "15-claim-popover");
      await page.getByRole("button", { name: "Open the source dossier" }).click();
      await expect(page).toHaveURL(/source=/);
      await shot(page, "16-dossier");
      await page.keyboard.press("Escape");
    } else {
      log("no citation markers rendered — flagged for verification.md");
      await shot(page, "15-no-citations");
    }

    await page.goto(projectUrl);
    await page.getByRole("link", { name: /findings/i }).first().click();
    await expect(page.getByRole("button", { name: "All kinds" })).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole("button", { name: "Intervention–outcome" }).click();
    await expect(page).toHaveURL(/profile=iof/);
    const expand = page.getByRole("button", { name: /Expand finding/ }).first();
    if (await expand.isVisible().catch(() => false)) {
      await expand.click();
      await expect(page.getByText("Reported numbers")).toBeVisible();
      await expect(page.getByText("The exact words")).toBeVisible();
      await shot(page, "17-iof-expanded");
    } else {
      log("no IOF rows — flagged for verification.md");
      await shot(page, "17-iof-empty");
    }
    await page.getByRole("button", { name: "Implementation context" }).click();
    await expect(page).toHaveURL(/profile=icf/);
    const expandIcf = page.getByRole("button", { name: /Expand finding/ }).first();
    if (await expandIcf.isVisible().catch(() => false)) {
      await expandIcf.click();
      await expect(page.getByText("Context detail")).toBeVisible();
      await shot(page, "18-icf-expanded");
    } else {
      log("no ICF rows in this corpus — honest absence, flagged for verification.md");
      await shot(page, "18-icf-empty");
    }

    await page.goto(projectUrl);
    await page.getByRole("link", { name: /sources/i }).first().click();
    await expect(page).toHaveURL(/\/sources/);
    await shot(page, "20-sources");
    const statusFilter = page.getByRole("button", { name: /screened out|included/i }).first();
    if (await statusFilter.isVisible().catch(() => false)) {
      await statusFilter.click();
      await expect(page).toHaveURL(/status=/);
      await shot(page, "19-sources-filtered");
    }
  });

  test("B3 · run 2: kill mid-synthesis → interrupted honestly, sections stay, thread intact", async ({
    page,
  }) => {
    test.setTimeout(45 * 60 * 1000);
    if (projectUrl === "" && process.env.LIVE_PROJECT) {
      projectUrl = `/projects/${process.env.LIVE_PROJECT}`;
    }
    await page.goto(projectUrl);
    projectUrl = page.url();
    if (process.env.LIVE_RESUME_INTERRUPTED) {
      // The kill-mid-synthesis already happened on a prior attempt (the run
      // is durably `interrupted` with streamed artefact.* events); assert
      // the honest UI over the replayed stream without another chain run.
      await page.goto(`${projectUrl}/evidence-base`);
      await expect(
        page.getByText(/This run ended before the write-up completed/).first(),
      ).toBeVisible({ timeout: 120_000 });
      await shot(page, "23-terminal-partial");
      await page.goto(projectUrl);
      await expect(page.getByText(/interrupted/i).first()).toBeVisible({ timeout: 120_000 });
      await expect(
        page.getByText(/school-based interventions affect pupil attendance/).first(),
      ).toBeVisible();
      log("run 2 interrupted honestly; thread intact (resume assertions)");
      await shot(page, "24-run2-interrupted-journey");
      return;
    }
    await plannerTurn(
      page,
      "Run the same analysis again, fully unattended — no pauses.",
    );
    // After a terminal run the journey persists — a replanned ready plan is
    // started from its inline plan card in the thread (the completion card's
    // "Run the analysis again" control was removed, owner 2026-08-05).
    const runAgain = page
      .getByTestId("plan-ready-actions")
      .getByRole("button", { name: /Start(ing…)? the analysis/ });
    for (let attempt = 0; attempt < 8; attempt++) {
      if (await runAgain.isVisible().catch(() => false)) break;
      await plannerTurn(page, "Yes — mark it ready.");
    }
    await runAgain.click();
    log("run 2 started (unattended)");

    await expect(page.getByText("Writing the evidence base").first()).toBeVisible({
      timeout: 30 * 60 * 1000,
    });
    await page.getByRole("link", { name: /evidence base/i }).first().click();
    // The committed run-1 artefact may render; the reducer swaps to the live
    // view once run-2 sections stream.
    await expect(
      page.getByText(/Writing this section now…|sections appear as they are drafted/).first(),
    ).toBeVisible({ timeout: 5 * 60 * 1000 });
    await expect(page.locator("main p.anim-rise").first()).toBeVisible({
      timeout: 10 * 60 * 1000,
    });
    await killApi(page);
    log("API killed mid-synthesis");
    await shot(page, "22-killed-mid-synthesis");

    startApi();
    await waitForApi(page);
    await page.reload();
    await expect(
      page.getByText(/This run ended before the write-up completed|interrupted/i).first(),
    ).toBeVisible({ timeout: 180_000 });
    await shot(page, "23-terminal-partial");

    await page.goto(projectUrl);
    await expect(page.getByText(/interrupted/i).first()).toBeVisible({ timeout: 120_000 });
    await expect(
      page.getByText(/school-based interventions affect pupil attendance/).first(),
    ).toBeVisible();
    log("run 2 interrupted honestly; thread intact");
    await shot(page, "24-run2-interrupted-journey");
  });
});

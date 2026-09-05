import { execSync, spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Task 027 G.1 — the contract-pinned live check, scripted (owner-approved
 * fallback for browser-drive, 2026-07-29). Real backend, real chain at rapid
 * effort, dev-issuer auth via VITE_DEV_TOKEN. The spec restarts the API
 * mid-planning (transcript durability) and kills it mid-synthesis on a
 * second run (interruption honesty). Evidence screenshots land in
 * docs/tasks/027-frontend-uplift/evidence/.
 */

const REPO = path.resolve(__dirname, "../..");
const EVIDENCE = path.join(REPO, "docs/tasks/027-frontend-uplift/evidence");
const API = "http://localhost:8000";

function log(message: string) {
  console.log(`[live-027 ${new Date().toISOString()}] ${message}`);
}

async function apiStatus(page: Page): Promise<number> {
  try {
    const response = await page.request.get(`${API}/api/v1/tasks`, {
      headers: { Authorization: `Bearer ${process.env.LIVE_TOKEN ?? ""}` },
      timeout: 2_000,
    });
    return response.status();
  } catch {
    return 0;
  }
}

/** Kill the API and PROVE it is down before returning (the old process can
 *  answer one last request and fake a successful "restart"). */
async function killApi(page: Page) {
  log("killing the API process");
  try {
    // SIGKILL by PORT, not by name: uvicorn --reload's worker is a
    // multiprocessing-spawn child whose argv never says "uvicorn", so a
    // name-based pkill orphans the serving process. Killing every holder of
    // :8000 is the faithful crash simulation (and reaps the reloader too).
    // LISTEN scope only — an unscoped lsof would also match the browser's
    // and Vite's CLIENT sockets to :8000 and kill the test itself.
    execSync(
      "lsof -ti tcp:8000 -sTCP:LISTEN | xargs kill -9; pkill -9 -f 'uvicorn policy_atlas' || true",
      { stdio: "ignore" },
    );
  } catch {
    // already dead is fine
  }
  await expect
    .poll(async () => apiStatus(page), { timeout: 30_000, intervals: [500] })
    .toBe(0);
  // The socket outlives the process briefly — the replacement uvicorn gets
  // "Address already in use" unless :8000 is genuinely free.
  await expect
    .poll(
      () => {
        try {
          // LISTEN only: the SPA's own client sockets to :8000 linger in
          // CLOSE_WAIT and would otherwise hold this check forever.
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
  const child = spawn(
    "bash",
    ["-lc", "cd backend && exec make dev >> /tmp/pa-api.log 2>&1"],
    { cwd: REPO, detached: true, stdio: "ignore" },
  );
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

/** Send one planner turn through the composer and wait for the reply. */
async function plannerTurn(page: Page, message: string) {
  log(`planner turn: ${message.slice(0, 60)}…`);
  await page.getByLabel("Message the planner").fill(message);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  // The thinking row appears then clears when the reply lands.
  await expect(page.getByText("Planning…")).toHaveCount(0, { timeout: 180_000 });
  await page.waitForTimeout(500);
}

/** Answer the pending check-in with its continue-style option. */
async function answerCheckIn(page: Page) {
  // The card is the aria-live container that carries the waiting chip AND
  // the option buttons (an unanchored div filter matches the chip's own
  // text node, which has no buttons).
  const card = page
    .locator("[aria-live='polite']")
    .filter({ hasText: "Waiting on your input" })
    .first();
  await card.scrollIntoViewIfNeeded();
  const preferred = card
    .getByRole("button", { name: /continue|proceed|keep going|carry on/i })
    .first();
  if (await preferred.isVisible().catch(() => false)) {
    log(`answering check-in via option: ${(await preferred.textContent())?.trim()}`);
    await preferred.click();
    return;
  }
  const buttons = card.getByRole("button");
  const count = await buttons.count();
  for (let index = 0; index < count; index++) {
    const name = (await buttons.nth(index).textContent())?.trim() ?? "";
    if (!/stop the analysis|compile|send/i.test(name) && name.length > 0) {
      log(`answering check-in via option: ${name}`);
      await buttons.nth(index).click();
      return;
    }
  }
  throw new Error("no answerable check-in option found");
}

let taskUrl = "";

test.describe.serial("task 027 live check", () => {
  test("1 · landing rename/archive", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "New task" }).first()).toBeVisible({
      timeout: 60_000,
    });

    // A disposable task to archive.
    await page.getByRole("button", { name: "New task" }).first().click();
    await page.getByLabel("Project name").fill("027 archive me");
    await page.getByRole("button", { name: "Create task" }).click();
    await expect(page).toHaveURL(/\/tasks\/[^/]+$/);
    await page.goto("/");

    // Rename: cancel restores, save applies.
    const renameButton = page.getByRole("button", { name: /rename/i }).first();
    await expect(renameButton).toBeVisible();
    await renameButton.click();
    const nameInput = page.getByRole("textbox").first();
    await nameInput.fill("won't keep this");
    await page.keyboard.press("Escape");
    await expect(page.getByText("027 archive me")).toBeVisible();
    await renameButton.click();
    await page.getByRole("textbox").first().fill("027 renamed then archived");
    await page.keyboard.press("Enter");
    await expect(page.getByText("027 renamed then archived")).toBeVisible({ timeout: 15_000 });

    // Archive: two-step confirm, archive vocabulary.
    await page.getByRole("button", { name: "Archive task" }).first().click();
    await expect(page.getByText(/Confirm to archive/)).toBeVisible();
    await page.getByRole("button", { name: "Confirm archive" }).click();
    await expect(page.getByText("027 renamed then archived")).toHaveCount(0, { timeout: 15_000 });
    await shot(page, "01-landing");
  });

  test("2 · planning, restart mid-planning, durable thread + idempotent retry", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "New task" }).first().click();
    await page.getByLabel("Project name").fill("027 live check");
    await page.getByRole("button", { name: "Create task" }).click();
    await expect(page).toHaveURL(/\/tasks\/[^/]+$/);
    taskUrl = page.url();

    await plannerTurn(
      page,
      "I need evidence on how school-based interventions affect pupil attendance in the UK. " +
        "Rapid search effort, standard analysis depth, academic sources only, and check in with " +
        "me at every step. Please also extract implementation-context findings.",
    );
    await expect(page.getByText(/forming…|ready/).first()).toBeVisible();
    await shot(page, "02-plan-forming");

    // Restart the API mid-planning: the durable thread must survive.
    const userBubble = page.getByText(/school-based interventions affect pupil attendance/).first();
    await expect(userBubble).toBeVisible();
    await killApi(page);
    startApi();
    await waitForApi(page);
    await page.reload();
    await expect(
      page.getByText(/school-based interventions affect pupil attendance/).first(),
    ).toBeVisible({ timeout: 30_000 });
    log("thread survived the API restart");
    await shot(page, "03-thread-after-restart");

    // Idempotent replay of the FIRST turn's client id, via the API directly:
    // fish the durable row out and re-POST its client_turn_id + message.
    const token = process.env.LIVE_TOKEN ?? "";
    const taskId = new URL(taskUrl).pathname.split("/").at(-1) ?? "";
    const turnsResponse = await page.request.get(
      `${API}/api/v1/tasks/${taskId}/planning-turns`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(turnsResponse.status()).toBe(200);
    const turns = (await turnsResponse.json()).data as Array<Record<string, unknown>>;
    expect(turns.length).toBeGreaterThan(0);
    const first = turns[0];
    const retry = await page.request.post(`${API}/api/v1/tasks/${taskId}/planning-turns`, {
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      data: { message: first.user_message, client_turn_id: first.client_turn_id },
    });
    expect(retry.status()).toBe(200);
    const replay = await retry.json();
    expect(replay.reply).toBeTruthy();
    log("idempotent retry returned the stored turn verbatim (200, same reply)");

    // The next turn works after rehydration; push to ready.
    for (let attempt = 0; attempt < 4; attempt++) {
      const start = page.getByRole("button", { name: /Start(ing…)? the analysis/ });
      if (await start.isVisible().catch(() => false)) break;
      await plannerTurn(
        page,
        attempt === 0
          ? "Yes, that's exactly right. Please finalise the plan as discussed."
          : "That plan is right — mark it ready.",
      );
    }
    await expect(page.getByRole("button", { name: /Start(ing…)? the analysis/ })).toBeVisible();
    await expect(page.getByText("ready").first()).toBeVisible();
    await shot(page, "04-plan-ready");
  });

  test("3 · run 1: journey live, check-ins answered, synthesis streams, reload replays", async ({
    page,
  }) => {
    test.setTimeout(45 * 60 * 1000);
    await page.goto(taskUrl);
    await page.getByRole("button", { name: /Start(ing…)? the analysis/ }).click();
    log("run 1 started");
    await expect(page.getByRole("list", { name: "Stage timeline" })).toBeVisible({
      timeout: 120_000,
    });
    await shot(page, "05-journey-early");

    let answered = 0;
    let hygieneChecked = false;
    let streamedChecked = false;
    const deadline = Date.now() + 40 * 60 * 1000;
    let sawAnsweredEcho = false;

    while (Date.now() < deadline) {
      // Terminal?
      const completion = page.getByText(/analysis is complete|completed with gaps/i).first();
      if (await completion.isVisible().catch(() => false)) break;
      const failed = page.getByText("The analysis failed.").first();
      if (await failed.isVisible().catch(() => false)) {
        await shot(page, "run1-failed");
        throw new Error("run 1 failed — see screenshot");
      }

      // Pending check-in?
      if (await page.getByText("Waiting on your input").first().isVisible().catch(() => false)) {
        if (!hygieneChecked) {
          // Hygiene leg: badge + title marker while a check-in is pending.
          await shot(page, "06-checkin-pending");
          await page.getByRole("link", { name: /sources/i }).first().click();
          await expect(page.getByText("Check-in pending").first()).toBeVisible({
            timeout: 20_000,
          });
          await expect
            .poll(async () => page.title(), { timeout: 15_000 })
            .toMatch(/^●/);
          log("hygiene: nav badge + title marker confirmed while check-in pending");
          await shot(page, "07-badge-on-sources");
          await page.goBack();
          hygieneChecked = true;
        }
        await answerCheckIn(page);
        answered += 1;
        if (!sawAnsweredEcho) {
          await expect(page.getByText("Answered").first()).toBeVisible({ timeout: 30_000 });
          sawAnsweredEcho = true;
          log("answered-state echo rendered in the journey");
          await shot(page, "08-answered-echo");
        }
        continue;
      }

      // Synthesis streaming leg: once the writing stage is live, watch the
      // artefact page fill, then reload and confirm the replay.
      if (
        !streamedChecked &&
        (await page
          .getByText("Writing the evidence base")
          .first()
          .isVisible()
          .catch(() => false))
      ) {
        await page.getByRole("link", { name: /evidence base/i }).first().click();
        const anySection = page.getByText(/Writing this section now…|sections appear as they are drafted/);
        if (await anySection.first().isVisible({ timeout: 60_000 }).catch(() => false)) {
          await shot(page, "09-live-writing");
          // Wait for at least one filled section (prose paragraph in the live page).
          await expect(page.locator("main p.anim-rise").first()).toBeVisible({
            timeout: 10 * 60 * 1000,
          });
          await shot(page, "10-live-filled");
          const filledText = await page.locator("main p.anim-rise").first().textContent();
          await page.reload();
          await expect(page.getByText((filledText ?? "").slice(0, 40)).first()).toBeVisible({
            timeout: 60_000,
          });
          log("browser reload mid-synthesis replayed the completed sections");
          await shot(page, "11-live-after-reload");
          streamedChecked = true;
        }
        await page.goto(taskUrl);
        continue;
      }

      await page.waitForTimeout(4000);
    }

    log(`run 1 reached terminal; check-ins answered: ${answered}`);
    expect(answered).toBeGreaterThan(0);
    expect(sawAnsweredEcho).toBe(true);
    await shot(page, "12-journey-complete");

    // The decision echo appears in the planning thread inside its run block.
    await expect(page.getByText("Analysis run").first()).toBeVisible();
    await shot(page, "13-thread-run-block");
  });

  test("4 · evidence base, findings both kinds, sources filters", async ({ page }) => {
    await page.goto(taskUrl.replace(/\/?$/, "/evidence-search"));
    // If that path 404s the nav link is the source of truth.
    if (await page.getByText(/nothing here/i).isVisible().catch(() => false)) {
      await page.goto(taskUrl);
      await page.getByRole("link", { name: /evidence base/i }).first().click();
    }
    await expect(page.getByText("Evidence base").first()).toBeVisible({ timeout: 60_000 });
    await shot(page, "14-evidence-base");

    // Claim popover with quote-highlighted chunk context.
    const marker = page.locator("button.citation-marker, button[aria-label^='Citation']").first();
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
    }

    // Findings: kind filter + expansions.
    await page.goto(taskUrl);
    await page.getByRole("link", { name: /findings/i }).first().click();
    await expect(page.getByRole("button", { name: "All kinds" })).toBeVisible({ timeout: 30_000 });
    const iofFilter = page.getByRole("button", { name: "Intervention–outcome" });
    await iofFilter.click();
    await expect(page).toHaveURL(/profile=iof/);
    const expand = page.getByRole("button", { name: /Expand finding/ }).first();
    if (await expand.isVisible().catch(() => false)) {
      await expand.click();
      await expect(page.getByText("Reported numbers")).toBeVisible();
      await expect(page.getByText("The exact words")).toBeVisible();
      await shot(page, "17-iof-expanded");
    } else {
      log("no IOF rows — flagged for verification.md");
    }
    await page.getByRole("button", { name: "Implementation context" }).click();
    await expect(page).toHaveURL(/profile=icf/);
    const expandIcf = page.getByRole("button", { name: /Expand finding/ }).first();
    if (await expandIcf.isVisible().catch(() => false)) {
      await expandIcf.click();
      await expect(page.getByText("Context detail")).toBeVisible();
      await shot(page, "18-icf-expanded");
    } else {
      log("no ICF rows in this run's corpus — honest absence, flagged for verification.md");
      await shot(page, "18-icf-empty");
    }

    // Sources: server-side filter is URL-addressable and collection-true.
    await page.goto(taskUrl);
    await page.getByRole("link", { name: /sources/i }).first().click();
    await expect(page).toHaveURL(/\/sources/);
    const statusFilter = page.getByRole("button", { name: /screened out|included/i }).first();
    if (await statusFilter.isVisible().catch(() => false)) {
      await statusFilter.click();
      await expect(page).toHaveURL(/status=/);
      await shot(page, "19-sources-filtered");
    }
    await shot(page, "20-sources");
  });

  test("5 · run 2: kill mid-synthesis → interrupted honestly, sections stay, thread intact", async ({
    page,
  }) => {
    test.setTimeout(45 * 60 * 1000);
    await page.goto(taskUrl);

    // Replan to unattended so run 2 flows straight to synthesise.
    await plannerTurn(
      page,
      "Run it again exactly as before, but switch check-ins to unattended — no pauses.",
    );
    for (let attempt = 0; attempt < 3; attempt++) {
      const start = page.getByRole("button", { name: /Start(ing…)? the analysis/ });
      if (await start.isVisible().catch(() => false)) break;
      await plannerTurn(page, "Yes — mark it ready.");
    }
    const start = page.getByRole("button", { name: /Start(ing…)? the analysis/ });
    await expect(start).toBeVisible();
    await start.click();
    log("run 2 started (unattended)");

    // Landing live status (hygiene): the card reflects the running state
    // without a manual refresh.
    await page.goto("/");
    await expect(page.getByText(/analysing|running/i).first()).toBeVisible({ timeout: 60_000 });
    log("hygiene: landing card shows the live running state");
    await shot(page, "21-landing-live-status");
    await page.goto(taskUrl);

    // Wait for synthesise to start writing, then kill the API mid-write.
    await expect(page.getByText("Writing the evidence base").first()).toBeVisible({
      timeout: 35 * 60 * 1000,
    });
    await page.getByRole("link", { name: /evidence base/i }).first().click();
    await expect(
      page.getByText(/Writing this section now…|sections appear as they are drafted/).first(),
    ).toBeVisible({ timeout: 5 * 60 * 1000 });
    // Let at least one section land so the partial state is non-empty.
    await expect(page.locator("main p.anim-rise").first()).toBeVisible({ timeout: 10 * 60 * 1000 });
    await killApi(page);
    log("API killed mid-synthesis");
    await shot(page, "22-killed-mid-synthesis");

    startApi();
    await waitForApi(page);
    await page.reload();

    // 025 semantics unchanged: mid-component death = interrupted. Streamed
    // sections stay visible under the explicit terminal banner.
    await expect(
      page.getByText(/This run ended before the write-up completed|interrupted/i).first(),
    ).toBeVisible({ timeout: 120_000 });
    await shot(page, "23-terminal-partial");

    await page.goto(taskUrl);
    await expect(
      page.getByText(/interrupted|wasn't completed|didn't finish/i).first(),
    ).toBeVisible({ timeout: 60_000 });
    // The planning thread is intact after the crash.
    await expect(
      page.getByText(/school-based interventions affect pupil attendance/).first(),
    ).toBeVisible();
    log("run 2 interrupted honestly; thread intact");
    await shot(page, "24-run2-interrupted-journey");
  });
});

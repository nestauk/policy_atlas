import { execSync, spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Task 028 G.2 — the contract-pinned live check, scripted (the 027
 * owner-approved fallback for browser-drive). Real backend, real planner,
 * real chain; dev-issuer auth via VITE_DEV_TOKEN; evidence screenshots land
 * in docs/tasks/028-ux-refinement/evidence/.
 *
 * Leg A — Quick look, UNATTENDED: sequential three-part planning, chip edit,
 * inline ready plan card (details open, honest band), zero pauses end to
 * end, short report with key-findings bullets + working claim popovers,
 * collapsed sections showing verified summaries, contents sidebar, sortable
 * sources with URL state.
 *
 * Leg B — Standard review, FREQUENT (requested in words; the CONTRACT's
 * standard-preset pin — the plan's "quick look" wording composes no select,
 * so P2/P3 could never fire there): compound opening fast-path,
 * restart-mid-planning rehydration, P1 search-review bundle, P2 theme
 * rename, P3 free-text steer through compile→confirm, P4 displayed-list +
 * inline section edit, pause salience on every tab.
 */

const REPO = path.resolve(__dirname, "../..");
const EVIDENCE = path.join(REPO, "docs/tasks/028-ux-refinement/evidence");
const API = "http://localhost:8000";
const LEG = process.env.LIVE_LEG ?? "";

function log(message: string) {
  console.log(`[live-028 ${new Date().toISOString()}] ${message}`);
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
  await expect
    .poll(async () => apiStatus(page), { timeout: 30_000, intervals: [500] })
    .toBe(0);
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

/** Click through SSE-driven re-renders: the check-in card re-mounts when
 *  stream frames land, detaching elements mid-action — retry a fresh locate
 *  a few times before giving up. */
async function clickThroughRerenders(locate: () => ReturnType<Page["locator"]>, tries = 4) {
  for (let attempt = 0; attempt < tries; attempt++) {
    const ok = await locate()
      .click({ timeout: 8_000 })
      .then(() => true)
      .catch(() => false);
    if (ok) return true;
  }
  return false;
}

/** Send one planner turn through the composer and wait for the reply. */
async function plannerTurn(page: Page, message: string) {
  log(`planner turn: ${message.slice(0, 70)}…`);
  await page.getByLabel("Message the planner").fill(message);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Planning…")).toHaveCount(0, { timeout: 300_000 });
  await page.waitForTimeout(500);
}

/** Click an option on the LATEST part card. The planner authors labels, so
 *  the stable handle is the prompt-pinned option id (data-option-id) or the
 *  card's one primary (data-part-option="primary"). Options send a canned
 *  confirm turn, so wait out the following planner call too. */
async function partOption(page: Page, selector: { id?: string; primary?: boolean }) {
  const card = page.getByTestId("part-card").last();
  const button = selector.id !== undefined
    ? card.locator(`[data-option-id="${selector.id}"]`)
    : card.locator('[data-part-option="primary"]');
  await expect(button).toBeVisible({ timeout: 30_000 });
  log(`part option: ${(await button.textContent())?.slice(0, 60)}`);
  await button.click();
  await expect(page.getByText("Planning…")).toHaveCount(0, { timeout: 300_000 });
  await page.waitForTimeout(500);
}

/** Drive the sequential part flow until the inline ready plan card shows.
 *  Free text beats buttons, so any part the planner skips is fine — we press
 *  whatever live card is showing, preferring its primary. */
async function driveToReady(page: Page, thoroughness: string, maxSteps = 8) {
  for (let step = 0; step < maxSteps; step++) {
    if (await page.getByTestId("plan-card").isVisible().catch(() => false)) return;
    const card = page.getByTestId("part-card").last();
    const preset = card.locator(`[data-option-id="${thoroughness}"]`);
    if (await preset.isVisible().catch(() => false)) {
      await partOption(page, { id: thoroughness });
      continue;
    }
    const primary = card.locator('[data-part-option="primary"]');
    if (await primary.isVisible().catch(() => false)) {
      await partOption(page, { primary: true });
      continue;
    }
    // No live card button — nudge in free text.
    await plannerTurn(page, "That's right — carry on.");
  }
  await expect(page.getByTestId("plan-card")).toBeVisible({ timeout: 30_000 });
}

async function newProject(page: Page, name: string): Promise<string> {
  await page.goto("/");
  await page.getByRole("button", { name: "New project" }).first().click();
  await page.getByLabel("Project name").fill(name);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\/[^/]+$/);
  return page.url();
}

test.describe.serial("task 028 live check", () => {
  test.skip(LEG === "b", "running leg B only");

  test("leg A · Quick look, unattended, end to end", async ({ page }) => {
    test.setTimeout(45 * 60 * 1000);
    const projectUrl = await newProject(page, "028 live leg A");

    // Pre-run the workspace is a centred single-column chat: no rail toggle.
    await expect(page.getByRole("button", { name: /collapse the planning rail/i })).toHaveCount(0);
    await expect(page.getByText(/question, scope, thoroughness/)).toBeVisible();
    await shot(page, "a-01-centred-empty");

    // Slow path: a bare opening so the parts propose one at a time.
    await plannerTurn(
      page,
      "ensuring that our most disadvantaged children have access to high quality early childhood education and care",
    );
    await expect(page.getByText(/Plan · .*question/i).first()).toBeVisible({ timeout: 30_000 });
    await shot(page, "a-02-question-part");
    await partOption(page, { primary: true });

    // Scope card: stage a chip edit if an editable chip is live, else add one.
    const scopeCard = page.getByText(/Plan · .*scope/i).first();
    if (await scopeCard.isVisible({ timeout: 60_000 }).catch(() => false)) {
      await shot(page, "a-03-scope-part");
      const editChip = page.getByRole("button", { name: /^Edit / }).last();
      if (await editChip.isVisible().catch(() => false)) {
        await editChip.click();
        const dateFrom = page.locator("input[type=date]").first();
        if (await dateFrom.isVisible().catch(() => false)) {
          await dateFrom.fill("2016-01-01");
          log("chip edit: native date range editor used");
        } else {
          await page.getByLabel(/New value for/).fill("UK and comparator countries");
        }
        await page.getByRole("button", { name: "Stage" }).click();
        await shot(page, "a-04-chip-staged");
        await page.getByRole("button", { name: "Apply changes" }).click();
        await expect(page.getByText("Planning…")).toHaveCount(0, { timeout: 300_000 });
        log("staged chip edits applied as one batched planning turn");
      }
      await partOption(page, { primary: true });
    }

    // Thoroughness: Quick look (outcome-first preset with its honest band).
    await expect(page.getByText(/Plan · .*thoroughness/i).first()).toBeVisible({
      timeout: 120_000,
    });
    await expect(page.getByText(/short cited overview/i).first()).toBeVisible();
    await shot(page, "a-05-thoroughness-part");
    await partOption(page, { id: "quick_look" });

    // The inline ready plan card: details open, honest band, no-pause copy.
    await driveToReady(page, "quick_look");
    const planCard = page.getByTestId("plan-card");
    await expect(planCard.getByText("ready", { exact: true })).toBeVisible();
    await expect(planCard.getByText(/~5-10 min|~10-15 min/)).toBeVisible();
    await expect(planCard.getByText(/runs without pausing/)).toBeVisible();
    await shot(page, "a-06-ready-card");

    // Start from the card — the ONLY start surface.
    await planCard.getByRole("button", { name: /Start(ing…)? the analysis/ }).click();
    log("leg A run started");
    // Run stage: the two-pane layout returns (rail collapse control exists).
    await expect(page.getByRole("button", { name: /collapse the planning rail/i })).toBeVisible({
      timeout: 60_000,
    });
    await shot(page, "a-07-run-5050");

    // Unattended: poll to terminal asserting no pause ever renders.
    const deadline = Date.now() + 30 * 60 * 1000;
    let sawTerminal = false;
    while (Date.now() < deadline) {
      expect(
        await page.getByText("Waiting on your input").count(),
        "unattended run must never pause",
      ).toBe(0);
      const completion = page.getByText(/analysis complete|completed with gaps/i).first();
      if (await completion.isVisible().catch(() => false)) {
        sawTerminal = true;
        break;
      }
      const failed = page.getByText("The analysis failed.").first();
      if (await failed.isVisible().catch(() => false)) {
        await shot(page, "a-run-failed");
        throw new Error("leg A run failed — see screenshot");
      }
      await page.waitForTimeout(4000);
    }
    expect(sawTerminal, "run must reach terminal within 30 min").toBe(true);
    log("leg A reached terminal with zero pauses");
    await shot(page, "a-08-complete");

    // The artefact: short report, bullets, summaries, sidebar, disclosure.
    await page.getByRole("link", { name: /evidence base/i }).first().click();
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible({
      timeout: 60_000,
    });
    await shot(page, "a-09-artefact-top");

    // Key findings renders in full as bullets with working claim popovers.
    const bullets = page.getByRole("listitem").filter({ has: page.locator("button") });
    const bulletCount = await page.locator("main ul li").count();
    log(`key-findings bullet rows visible: ${bulletCount}`);
    expect(bulletCount).toBeGreaterThanOrEqual(3);
    const claimSpan = bullets.locator("button").first();
    if (await claimSpan.isVisible().catch(() => false)) {
      await claimSpan.click();
      await expect(page.getByText(/Tier|cited|quote/i).first()).toBeVisible({ timeout: 15_000 });
      log("claim popover opened from a key-findings bullet");
      await shot(page, "a-10-claim-popover");
      await page.keyboard.press("Escape");
    }

    // Collapsed ordinary sections show their one-line summaries; expanding
    // reveals prose. Contents sidebar present at desktop width.
    const collapsed = page.getByRole("button", { expanded: false }).first();
    await expect(collapsed).toBeVisible();
    await collapsed.click();
    await expect(page.getByRole("button", { expanded: true }).first()).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Contents" })).toBeVisible();
    await shot(page, "a-11-sections-sidebar");

    // Ordinary-section budget: quick look = 3 ordinary + structural.
    const projectId = new URL(projectUrl).pathname.split("/").at(-1) ?? "";
    const token = process.env.LIVE_TOKEN ?? "";
    const artefact = await page.request.get(`${API}/api/v1/projects/${projectId}/artefact`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(artefact.status()).toBe(200);
    const body = await artefact.json();
    const roles = (body.sections as Array<{ role: string; summary_status?: string | null }>).map(
      (section) => section.role,
    );
    const ordinary = roles.filter((role) => role === "standard").length;
    log(`section roles: ${roles.join(", ")} (ordinary=${ordinary})`);
    expect(ordinary).toBeLessThanOrEqual(3);
    const verified = (body.sections as Array<{ summary_status?: string | null }>).filter(
      (section) => section.summary_status === "verified",
    ).length;
    log(`verified block summaries: ${verified}; artefact summary status: ${body.summary_status}`);
    expect(verified).toBeGreaterThan(0);

    // Sources: sortable headers, URL state, server-side collection truth.
    await page.getByRole("link", { name: /sources/i }).first().click();
    await page.getByRole("button", { name: /sort by year/i }).click();
    await expect(page).toHaveURL(/sort=year/);
    await page.getByRole("button", { name: /sort by year/i }).click();
    await expect(page).toHaveURL(/order=asc/);
    await shot(page, "a-12-sources-sorted");
    log("leg A complete");
  });
});

test.describe.serial("task 028 live check — leg B", () => {
  test.skip(LEG === "a", "running leg A only");

  test("leg B · Standard review, frequent (requested in words)", async ({ page }) => {
    test.setTimeout(60 * 60 * 1000);
    const projectUrl = await newProject(page, "028 live leg B");
    const projectId = new URL(projectUrl).pathname.split("/").at(-1) ?? "";

    // Compound opening (fast path): several parts answered in one message,
    // check-ins REQUESTED IN WORDS (standard preset per the contract pin).
    await plannerTurn(
      page,
      "I need evidence on how school-based interventions affect pupil attendance in the UK. " +
        "A standard review is right. Review the key stages with me — check in at every step.",
    );
    await shot(page, "b-01-compound-opening");

    // Restart the API mid-planning: thread AND part states must rehydrate.
    await killApi(page);
    startApi();
    await waitForApi(page);
    await page.reload();
    await expect(
      page.getByText(/school-based interventions affect pupil attendance/).first(),
    ).toBeVisible({ timeout: 30_000 });
    log("thread survived the API restart");
    await shot(page, "b-02-thread-after-restart");

    await driveToReady(page, "standard_review");
    const planCard = page.getByTestId("plan-card");
    await expect(planCard.getByText("ready", { exact: true })).toBeVisible();
    await shot(page, "b-03-ready-card");
    await planCard.getByRole("button", { name: /Start(ing…)? the analysis/ }).click();
    log("leg B run started");

    const deadline = Date.now() + 45 * 60 * 1000;
    let salienceChecked = false;
    let renamed = false;
    let freeTextSteered = false;
    let sectionEdited = false;
    let answered = 0;
    const token = process.env.LIVE_TOKEN ?? "";
    let lastAnsweredId = "";

    /** The API is the truth for WHICH pause is live — DOM sniffing races the
     *  resolve/re-pause cycle (a steer typed into a just-resolved card 409s
     *  invisibly). Returns null when nothing is pending. */
    const pendingCheckIn = async (): Promise<Record<string, unknown> | null> => {
      const response = await page.request
        .get(`${API}/api/v1/projects/${projectId}/check-ins?status=pending`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: 5_000,
        })
        .catch(() => null);
      if (response === null || response.status() !== 200) return null;
      const rows = ((await response.json()).data ?? []) as Array<Record<string, unknown>>;
      return rows[0] ?? null;
    };

    while (Date.now() < deadline) {
      const completion = page.getByText(/analysis complete|completed with gaps/i).first();
      if (await completion.isVisible().catch(() => false)) break;
      const failed = page.getByText("The analysis failed.").first();
      if (await failed.isVisible().catch(() => false)) {
        await shot(page, "b-run-failed");
        throw new Error("leg B run failed — see screenshot");
      }

      const pending = await pendingCheckIn();
      if (pending === null || pending.check_in_id === lastAnsweredId) {
        await page.waitForTimeout(4000);
        continue;
      }
      const checkInId = pending.check_in_id as string;
      const bundle = (pending.bundle ?? {}) as Record<string, unknown>;
      const keys = new Set(Object.keys(bundle));

      // Wait for THIS pause's card to render before interacting.
      const card = page
        .locator("[aria-live='polite']")
        .filter({ hasText: "Waiting on your input" })
        .first();
      if (!(await card.isVisible().catch(() => false))) {
        await page.waitForTimeout(2000);
        continue;
      }
      await card.scrollIntoViewIfNeeded();

      if (!salienceChecked) {
        await expect(page.getByText("Paused — waiting on you").first()).toBeVisible({
          timeout: 20_000,
        });
        await expect(page.getByText(/Paused at a check-in/).first()).toBeVisible();
        await shot(page, "b-04-pause-salience-workspace");
        await page.getByRole("link", { name: "Sources", exact: true }).first().click();
        await expect(
          page.getByText(/analysis is paused — a check-in is waiting on you/i).first(),
        ).toBeVisible({ timeout: 20_000 });
        await shot(page, "b-05-crosstab-banner-sources");
        await page.goBack();
        salienceChecked = true;
        log("pause salience confirmed: heading, banner, cross-tab banner");
        continue;
      }

      if (keys.has("backends")) {
        // P1 search review.
        await expect(card.getByText("What the search collected")).toBeVisible({ timeout: 15_000 });
        await shot(page, "b-06-p1-bundle");
        log("P1 search-review bundle rendered (counts + sample titles)");
        if (await clickThroughRerenders(() => card.getByRole("button", { name: /looks right — assess these/i }))) {
          answered += 1;
          lastAnsweredId = checkInId;
        }
        continue;
      }

      if (keys.has("themes") && !renamed) {
        // P2: stage one rename, then answer — renames ride the single response.
        await expect(card.getByRole("button", { name: /^Rename / }).first()).toBeVisible({
          timeout: 15_000,
        });
        await card.getByRole("button", { name: /^Rename / }).first().click();
        const renameInput = card.getByLabel(/New name for/);
        await renameInput.fill("Renamed live theme");
        await card.getByRole("button", { name: "Rename", exact: true }).click();
        await expect(card.getByText(/renamed — applies with your answer/)).toBeVisible();
        await shot(page, "b-07-p2-rename-staged");
        renamed = true;
        if (
          await clickThroughRerenders(() =>
            card.getByRole("button", { name: /looks right — go on to choose the reading list/i }),
          )
        ) {
          answered += 1;
          lastAnsweredId = checkInId;
          log("P2 theme renamed inline; rename rode the single answer");
        }
        continue;
      }

      if (keys.has("shortlist") && !freeTextSteered) {
        // P3: steer in free text through compile→confirm.
        await expect(card.getByText(/The reading list/i)).toBeVisible({ timeout: 15_000 });
        await shot(page, "b-08-p3-shortlist");
        const steerInput = page.getByLabel(/steer in your own words/i);
        await steerInput.fill("Read 18 documents in full, keeping every theme represented.");
        await steerInput.press("Enter");
        await expect(page.getByText(/Here's what that would change/)).toBeVisible({
          timeout: 120_000,
        });
        await shot(page, "b-09-freetext-compiled");
        expect(
          await clickThroughRerenders(() => page.getByRole("button", { name: "Apply these changes" })),
        ).toBe(true);
        freeTextSteered = true;
        answered += 1;
        lastAnsweredId = checkInId;
        log("free-text steer compiled and applied through the confirm ladder");
        continue;
      }

      if (keys.has("proposal") || keys.has("proposed_sections")) {
        if (!sectionEdited) {
          // P4: one inline section edit, submit the edited displayed list.
          await expect(card.getByText(/Proposed sections/i)).toBeVisible({ timeout: 15_000 });
          await shot(page, "b-10-p4-sections");
          expect(
            await clickThroughRerenders(() => card.getByRole("button", { name: /^Edit section / }).first()),
          ).toBe(true);
          const titleInput = card.getByLabel("Section title");
          await titleInput.fill("What the evidence shows — edited live");
          expect(
            await clickThroughRerenders(() => card.getByRole("button", { name: "Keep edit" })),
          ).toBe(true);
          expect(
            await clickThroughRerenders(() =>
              card.getByRole("button", { name: "Write the report with the edited sections" }),
            ),
          ).toBe(true);
          sectionEdited = true;
          answered += 1;
          lastAnsweredId = checkInId;
          log("P4 inline section edit submitted the full displayed list");
          await shot(page, "b-11-p4-edited-submitted");
          continue;
        }
      }

      // Anything else (generic frequent boundary, or a re-visited point):
      // proceed via the card's continue-style option.
      const primary = card
        .getByRole("button", { name: /continue|proceed|keep|looks right|write the report/i })
        .first();
      const name = (await primary.textContent().catch(() => null))?.trim()?.slice(0, 50);
      if (await clickThroughRerenders(() => primary)) {
        log(`generic pause answered: ${name}`);
        answered += 1;
        lastAnsweredId = checkInId;
      }
      continue;
    }

    log(`leg B terminal; pauses answered: ${answered}`);
    expect(answered).toBeGreaterThanOrEqual(3);
    expect(salienceChecked).toBe(true);
    await shot(page, "b-12-complete");

    // The edited section title made it into the written artefact.
    if (sectionEdited) {
      const artefact = await page.request.get(`${API}/api/v1/projects/${projectId}/artefact`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(artefact.status()).toBe(200);
      const body = await artefact.json();
      const titles = (body.sections as Array<{ title: string }>).map((section) => section.title);
      log(`artefact sections: ${titles.join(" | ")}`);
      expect(titles.some((title) => title.includes("edited live"))).toBe(true);
    }

    // Legacy fallback: any pre-028 artefact in this dev DB renders on the
    // first-sentence fallback with its marker (no verified summaries).
    const projects = await page.request.get(`${API}/api/v1/projects?page_size=50`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const rows = ((await projects.json()).data ?? []) as Array<Record<string, unknown>>;
    for (const row of rows) {
      if (row.project_id === projectId) continue;
      const artefact = await page.request.get(
        `${API}/api/v1/projects/${row.project_id}/artefact`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (artefact.status() !== 200) continue;
      const sections = (await artefact.json()).sections as Array<{
        summary_status?: string | null;
      }>;
      if (sections.some((section) => section.summary_status === "verified")) continue;
      await page.goto(`/projects/${row.project_id}/evidence-base`);
      const marker = page.getByText(/no checked summary/).first();
      if (await marker.isVisible({ timeout: 15_000 }).catch(() => false)) {
        log(`legacy artefact ${row.project_id} renders the fallback with its marker`);
        await shot(page, "b-13-legacy-fallback");
      } else {
        log(`legacy artefact ${row.project_id} had no collapsed ordinary section to show a fallback`);
      }
      break;
    }
    log("leg B complete");
  });
});

import { expect, test, type Page } from "@playwright/test";

import { MOCK_TASK_ID, mockProject, mockTask } from "../src/mock/fixtures";

/** New task → Options scoping → the question → Prepare plan, landing on the
 *  Agent tab. */
async function openScopingTask(page: Page) {
  await page.goto("/new");
  await page.getByRole("button", { name: "Options scoping" }).click();
  await page
    .getByLabel("Your question")
    .fill("How can we reduce the number of young people not in education, employment or training?");
  await page.getByRole("button", { name: "Prepare plan" }).click();
  await expect(page.getByRole("region", { name: "Task Agent conversation" })).toBeVisible();
}

/** A new scoping task with its baseline walk started from the plan. */
async function startScopingWalk(page: Page) {
  await openScopingTask(page);
  // The plan card starts the baseline (task 058, annex block H).
  await page.getByRole("button", { name: "Confirm and build the baseline" }).click();
  await expect(page.getByRole("button", { name: "Confirm and build the baseline" })).toHaveCount(0);
}

/**
 * Options scoping's New task journey (task 044, phase 3.4): pick the
 * capability, ask the question, start from an existing Evidence search in
 * the same project, and land on the Agent tab with a scoping plan document
 * that shows the link. Runs against the mock server (`VITE_MOCK=1`), whose
 * single-task world offers its one Evidence search task (`mockTask`) as the
 * "Starts from" candidate — the same task the mock's `POST /tasks` handler
 * then overwrites to become the new scoping task, capturing the source
 * task's name for the link fixture (`src/mock/api.ts`).
 */
test.describe("mock options-scoping journey", () => {
  test("New task → Options scoping → question · Starts from → Prepare plan → the plan document", async ({
    page,
  }) => {
    await page.goto("/new");
    await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();

    await page.getByRole("button", { name: "Options scoping" }).click();
    await expect(
      page.getByRole("heading", { name: "What are you trying to change?" }),
    ).toBeVisible();

    await page
      .getByLabel("Your question")
      .fill("How can we reduce the number of young people not in education, employment or training?");

    // Starts from is disabled until a project is chosen.
    await expect(
      page.getByText("Choose a project to start from its Evidence searches"),
    ).toBeVisible();

    await page.getByLabel(/Add to a project/).click();
    await page.getByRole("option", { name: mockProject.name }).click();

    const startsFrom = page.getByRole("group", { name: "Starts from" });
    await expect(startsFrom).toBeVisible();
    await page.getByLabel(mockTask.name).check();

    await page.getByRole("button", { name: "Prepare plan" }).click();

    // Lands on the Agent tab; the plan is ready immediately (mock: a
    // pre-scripted ready scoping draft — `mockScopingPlanReady`).
    await expect(page.getByRole("region", { name: "Task Agent conversation" })).toBeVisible();
    await page.getByRole("button", { name: "Review the plan" }).click();

    const plan = page.getByRole("dialog", { name: "Scoping plan" });
    await expect(plan).toBeVisible();
    await expect(plan.getByRole("heading", { name: "Starts from" })).toBeVisible();
    await expect(plan.getByText(`Evidence search: ${mockTask.name} · linked`)).toBeVisible();
    await expect(plan.getByRole("heading", { name: "Question and intended change" })).toBeVisible();
    await expect(plan.getByRole("heading", { name: "Settings" })).toBeVisible();
    await expect(plan.getByRole("heading", { name: "Constraints and preferences" })).toBeVisible();
  });

  /**
   * Phase 4.3: Result is the baseline. The mock serves `mockBaselineArtefact`
   * for a scoping task, and the Result tab opens on it even though the mock's
   * new task has no run yet — A17's unlock is the baseline's existence, not
   * the walk's ending.
   */
  test("the scoping task's Result shows the baseline, headed Baseline", async ({ page }) => {
    await openScopingTask(page);

    await page.getByRole("link", { name: "Result" }).first().click();

    await expect(
      page.getByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).toBeVisible();
    await expect(page.getByText("Baseline", { exact: true })).toBeVisible();
    await expect(page.getByText("scoping pass")).toHaveCount(0);
    await expect(page.getByText(/the situation these options would change/)).toHaveCount(0);
    // A baseline has no Key findings and no Executive summary / Full report
    // parts framing it.
    await expect(page.getByRole("heading", { name: "Executive summary" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Sources", exact: true }).first()).toBeVisible();
  });
});

/**
 * Phase 5.5: the Task Agent thread at the baseline gate. The mock's scoping
 * walk parks after the baseline (`mockBaselineGateCheckIn`), so the gate card
 * lands IN the thread, the composer stays open, a question comes back as a
 * cited answer, and "Change the plan" reopens the plan document's two start
 * actions.
 */
test.describe("mock options-scoping baseline gate", () => {
  test("the gate card sits in the thread and the composer takes a question about the baseline", async ({
    page,
  }) => {
    await startScopingWalk(page);

    const thread = page.getByRole("region", { name: "Task Agent conversation" });
    await expect(
      thread.getByRole("heading", { name: "Does the plan still look right now you have the baseline?" }),
    ).toBeVisible();
    // Round 12 (owner): the gate card shows no key assumption.
    await expect(thread.getByText("Careers advice reaches the young people already in school")).toHaveCount(0);
    await expect(thread.getByRole("radio", { name: /^Confirm plan and build longlist/ })).toBeVisible();
    await expect(thread.getByRole("radio", { name: /^Change the plan/ })).toBeVisible();

    // The composer is open at the gate, not fenced.
    const composer = page.getByLabel("Message the Task Agent");
    await expect(composer).toBeEnabled();
    await expect(composer).toHaveAttribute("placeholder", "Question the baseline…");

    await composer.fill("Does the baseline cover young people who have already left school?");
    await page.getByRole("button", { name: "Send" }).click();

    // The turn comes back as a cited answer, rendered by the chat's own
    // citation renderer.
    await expect(thread.getByText("References (1)")).toBeVisible();
  });

  test("Change the plan records a decision and reopens both start actions", async ({ page }) => {
    await startScopingWalk(page);

    const thread = page.getByRole("region", { name: "Task Agent conversation" });
    await thread.getByRole("radio", { name: /^Change the plan/ }).click();

    // The decision is said once, in the settled part card's language (round 10).
    await expect(thread.getByTestId("settled-gate")).toContainText("Change the plan");
    await expect(thread.getByText("recorded")).toHaveCount(0);

    await page.getByRole("button", { name: "Review the plan" }).click();
    const plan = page.getByRole("dialog", { name: "Scoping plan" });
    await expect(plan.getByRole("button", { name: "Rebuild baseline" })).toBeVisible();
    await expect(plan.getByRole("button", { name: "Confirm plan and build longlist" })).toBeVisible();
  });
});

/**
 * Task 045 (6.3): after the gate's Confirm the mock opens the longlist walk
 * (six stages, then `has_longlist`). The plan document walks its longlist
 * states — "Building the longlist", "Longlist built · N options", and after a
 * plan edit "built from plan version N" with Rebuild longlist — and the
 * Result opens on the longlist behind the Baseline · Longlist · Report switch.
 */
test.describe("mock options-scoping longlist states (task 045)", () => {
  async function buildLonglist(page: Page) {
    await startScopingWalk(page);
    const thread = page.getByRole("region", { name: "Task Agent conversation" });
    await thread.getByRole("radio", { name: /^Confirm plan and build longlist/ }).click();
  }

  /** The live run's trace in the thread (task 058; owner 2026-11-05). */
  function runTrace(page: Page) {
    return page.getByRole("region", { name: "Task Agent conversation" }).getByRole("region", { name: "Analysis run" });
  }

  /** Show the trace's step list: open already while the run is live or
   *  paused (owner, round 6); once it has ended, opened from the header's
   *  chevron. */
  async function openSteps(page: Page) {
    const header = runTrace(page).getByTestId("trace-header");
    await expect(header).toBeVisible({ timeout: 15_000 });
    const fold = header.getByRole("button");
    if ((await fold.count()) > 0 && (await fold.getAttribute("aria-expanded")) !== "true") await fold.click();
    await expect(page.getByRole("list", { name: "Run steps" })).toBeVisible();
  }

  /** The plan opens from "See plan" at the foot of the trace's open step
   *  list (owner, polish round 2). */
  async function openPlan(page: Page) {
    await openSteps(page);
    await page.getByRole("button", { name: "See plan" }).click();
  }

  test("the plan document says the longlist is building, then built, and the Result opens on it", async ({
    page,
  }) => {
    await buildLonglist(page);

    await openPlan(page);
    const plan = page.getByRole("dialog", { name: "Scoping plan" });
    await expect(plan.getByText("Building the longlist")).toBeVisible();
    await expect(plan.getByText(/^Longlist built · \d+ options$/)).toBeVisible({ timeout: 10_000 });
    await expect(plan.getByRole("button", { name: "Rebuild baseline" })).toHaveCount(0);
    await plan.getByRole("button", { name: "Close the scoping plan" }).click();

    await page.getByRole("link", { name: "Result" }).first().click();
    const views = page.getByRole("tablist", { name: "Result view" });
    await expect(views.getByRole("tab", { name: "Longlist" })).toHaveAttribute("aria-selected", "true");
    await expect(views.getByRole("tab", { name: /Report/ })).toBeDisabled();
    await views.getByRole("tab", { name: "Baseline" }).click();
    await expect(
      page.getByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).toBeVisible();
  });

  test("the longlist walk's rows show in the run trace, with the server's counts", async ({ page }) => {
    await buildLonglist(page);
    await openSteps(page);
    const card = page.getByRole("list", { name: "Run steps" });
    await expect(card.getByRole("listitem").filter({ hasText: /^Suggesting options/ })).toContainText(
      "12 suggested",
      { timeout: 15_000 },
    );
    await expect(card.getByRole("listitem").filter({ hasText: /^Searching for each option/ })).toContainText(
      "12 searches",
      { timeout: 15_000 },
    );
  });

  test("an option search (a child walk) gets no block of its own in the thread", async ({ page }) => {
    await buildLonglist(page);
    const thread = page.getByRole("region", { name: "Task Agent conversation" });
    // The walk has finished, so /runs now lists the child beside its parent.
    await openPlan(page);
    const plan = page.getByRole("dialog", { name: "Scoping plan" });
    await expect(plan.getByText(/^Longlist built · \d+ options$/)).toBeVisible({ timeout: 10_000 });
    await plan.getByRole("button", { name: "Close the scoping plan" }).click();
    await expect(thread.getByText(/^Option search|^The option's search is done/)).toHaveCount(0);
    // The baseline's folded line and the longlist walk's trace (the stream's
    // live run) only: the child adds nothing. Each carries one status mark.
    await expect(thread.getByRole("region", { name: "Analysis run" })).toHaveCount(1);
    await expect(thread.locator("[data-tone]")).toHaveCount(2);
  });

  test("a plan edit after the longlist offers Rebuild longlist, which starts the walk again", async ({
    page,
  }) => {
    await buildLonglist(page);
    await openPlan(page);
    const plan = page.getByRole("dialog", { name: "Scoping plan" });
    await expect(plan.getByText(/^Longlist built · \d+ options$/)).toBeVisible({ timeout: 10_000 });

    await plan.getByRole("button", { name: "Remove" }).click();
    await expect(
      plan.getByText("Longlist built from plan version 1 · the plan has changed"),
    ).toBeVisible();
    await plan.getByRole("button", { name: "Rebuild longlist" }).click();
    await expect(plan.getByText("Building the longlist")).toBeVisible();
  });
});

// --- Task 058 (N26): the product gate and the longlist during the build ------
//
// The mock plays the longlist build in about ten seconds, so a state can be on
// screen for less than one polling interval. `watchPage` keeps every distinct
// line the page has shown, in order, and `seen` asserts on that record.

async function watchPage(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const seenLines = new Set<string>();
    const order: string[] = [];
    (window as unknown as { __seenLines: string[] }).__seenLines = order;
    let queued = false;
    const scan = () => {
      queued = false;
      for (const raw of document.body.innerText.split("\n")) {
        const line = raw.trim();
        if (line !== "" && !seenLines.has(line)) {
          seenLines.add(line);
          order.push(line);
        }
      }
    };
    new MutationObserver(() => {
      if (!queued) {
        queued = true;
        requestAnimationFrame(scan);
      }
    }).observe(document, { subtree: true, childList: true, characterData: true });
  });
}

async function seenLines(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as unknown as { __seenLines?: string[] }).__seenLines ?? []);
}

async function seen(page: Page, wanted: string | RegExp, timeout = 30_000): Promise<void> {
  const matches = (line: string) => (typeof wanted === "string" ? line === wanted : wanted.test(line));
  await expect
    .poll(async () => (await seenLines(page)).some(matches), {
      timeout,
      message: `the page never showed ${String(wanted)}`,
    })
    .toBe(true);
}

/** The options read, called the way the app calls it (through the mock). */
async function optionRowCount(page: Page): Promise<number> {
  return page.evaluate(async (taskId) => {
    const response = await fetch(`/api/v1/tasks/${taskId}/options`);
    const body = (await response.json()) as { options: unknown[] };
    return body.options.length;
  }, MOCK_TASK_ID);
}

function taskNav(page: Page) {
  return page.getByRole("navigation", { name: "Task" });
}

test.describe("task 058 options scoping: the gate and the longlist build", () => {
  test("the product gate: baseline, pause, no option rows, then suggestions", async ({ page }) => {
    await watchPage(page);
    await startScopingWalk(page);

    // The baseline runs and the walk parks on the gate, which is answerable.
    await seen(page, "Does the plan still look right now you have the baseline?");
    const thread = page.getByRole("region", { name: "Task Agent conversation" });
    await expect(thread.getByRole("radio", { name: /^Confirm plan and build longlist/ })).toBeVisible();

    // No option rows exist before the answer: the read is empty and the
    // Result tab shows the baseline, not a longlist.
    expect(await optionRowCount(page)).toBe(0);
    await taskNav(page).getByRole("link", { name: /^Result/ }).click();
    await expect(page.getByRole("heading", { name: "Do nothing: current policy and trajectory" })).toBeVisible();
    await expect(page.getByText("Youth guarantee with a job or training offer")).toHaveCount(0);
    await taskNav(page).getByRole("link", { name: /^Agent/ }).click();

    // The answer continues the walk: suggestions first, then rows.
    await thread.getByRole("radio", { name: /^Confirm plan and build longlist/ }).click();
    // The run trace's header names the step in progress (task 058).
    await seen(page, /^Suggesting options/);
    await expect.poll(() => optionRowCount(page), { timeout: 30_000 }).toBeGreaterThanOrEqual(12);
  });

  test("the run trace counts the option searches", async ({ page }) => {
    await watchPage(page);
    await startScopingWalk(page);
    await page
      .getByRole("region", { name: "Task Agent conversation" })
      .getByRole("radio", { name: /^Confirm plan and build longlist/ })
      .click();
    await seen(page, /^Searching for each option · \d+ of 12 searches done · [\d,]+ sources/);
    // The step in progress links to the longlist being built (round 10, D4).
    await seen(page, /Longlist →$/);
  });

  test("the longlist while it builds: rows search, fold, fill, group, and the status bar announces it", async ({
    page,
  }) => {
    await watchPage(page);
    await startScopingWalk(page);
    const thread = page.getByRole("region", { name: "Task Agent conversation" });
    await expect(thread.getByRole("radio", { name: /^Confirm plan and build longlist/ })).toBeVisible();
    await thread.getByRole("radio", { name: /^Confirm plan and build longlist/ }).click();
    await taskNav(page).getByRole("link", { name: /^Result/ }).click();

    // The run status bar walks the build, with the server's words after the
    // label; the page itself carries no stage line (round 10, D3).
    await seen(page, /^Searching for each option · \d+ of 12 searches done · [\d,]+ sources$/);
    await seen(page, /^Reading the abstracts · [\d,]+ of [\d,]+ abstracts read$/);
    await seen(page, /^Clustering into options/);
    await seen(page, /^Estimating what each option would take/);
    await seen(page, /^Applying your constraints/);
    await seen(page, /^Grouping into themes/);
    await seen(page, /^Shortlisting/);

    // Rows: queued and searching while the fan-out runs, then a found count.
    await seen(page, "Queued");
    await seen(page, "Searching");
    await seen(page, /^Searched · \d+ found$/);
    // Clustering names its options as rows, assigning their sources (round
    // 11); a folded suggestion leaves the list for its option card.
    await seen(page, "Assigning sources");
    await seen(page, "Benefit run-ons when a young person starts work");
    // The heading is a flex line (round 12): the name, the count and the Show
    // word are separate boxes, so innerText records them as separate lines.
    await seen(page, /^Excluded$/i);
    await seen(page, "2 options");

    // The list carries no qualifier word; the shortlist wave marks its rows
    // in words, and the finished list then gains its controls in place.
    const lines = await seenLines(page);
    expect(lines.filter((line) => /provisional/i.test(line))).toEqual([]);
    await expect(page.getByRole("heading", { level: 1, name: "Longlist" })).toBeVisible();
    await seen(page, "Shortlisted");
    await expect(page.getByRole("group", { name: "Group by" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { level: 1, name: "Longlist" })).toBeVisible();
  });

  test("the trace folds to The longlist is ready once the build ends, and nothing else shows the run", async ({
    page,
  }) => {
    await startScopingWalk(page);
    const thread = page.getByRole("region", { name: "Task Agent conversation" });
    await expect(thread.getByRole("radio", { name: /^Confirm plan and build longlist/ })).toBeVisible();
    await thread.getByRole("radio", { name: /^Confirm plan and build longlist/ }).click();
    const trace = thread.getByRole("region", { name: "Analysis run" });
    await expect(trace.getByTestId("trace-header")).toContainText("The longlist is ready", { timeout: 40_000 });
    await expect(trace.getByRole("link", { name: "Read it →" })).toHaveAttribute("href", /\/result\?view=longlist$/);
    await taskNav(page).getByRole("link", { name: /^Sources/ }).click();
    await expect(page.getByText(/The longlist is ready/)).toHaveCount(0);
  });
});

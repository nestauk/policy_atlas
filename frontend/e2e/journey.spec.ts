import { expect, test, type Page } from "@playwright/test";

import {
  MOCK_CHAT_CLAIM_TEXT,
  MOCK_TASK_ID,
  mockCheckIn,
  mockEvidence,
  mockTask,
} from "../src/mock/fixtures";

/**
 * End-to-end mock journey (task 025 I.1; rewritten 027 F.2 for the uplifted
 * demo surfaces; rewritten again for 032's task-lifecycle IA — Plan · Results
 * · Sources · Share · History replacing the old flat nav). Runs against the
 * dev server in `VITE_MOCK=1` mode (see `playwright.config.ts`), so every
 * step drives the scripted fixture task + SSE narrative in `src/mock/`.
 * The mock task starts with no run — the journey begins at the plan pane
 * and starts the analysis itself, matching the "resumed session" fixture (a
 * durable task_agent transcript already formed a ready plan; see
 * `src/mock/fixtures.ts`). Selectors favour roles/labels/text over CSS — the
 * same accessible surface a screen-reader or keyboard user would rely on.
 */

const SUGGESTED_OPTION_LABEL = (mockCheckIn.options ?? []).find(
  (option) => option.suggested,
)?.label;
if (!SUGGESTED_OPTION_LABEL) throw new Error("fixture check-in has no suggested option");

/** The check-in's question as the mock's render carries it. */
const CHECK_IN_QUESTION = "Does this look right before I assess the sources?";

const CITED_SOURCE_TITLE = "Universal breakfast clubs and diet quality";
const CITATION_QUOTE = "Breakfast participation increased when provision was universal.";

/** The task-stage bar (Plan · Results · Sources · Share · History).
 *  The global App nav sits above it; Sources has its own subnav below. */
function lifecycleNav(page: Page) {
  return page.getByRole("navigation", { name: "Task" });
}

/** The run trace in the Task Agent thread (task 058; owner 2026-11-05). */
function runTrace(page: Page) {
  return page.getByRole("region", { name: "Analysis run" });
}

/** The trace's header line (owner round 6): live or paused a line over the
 *  open step list; ended, a button whose chevron opens the list. */
function traceHeader(page: Page) {
  return runTrace(page).getByTestId("trace-header");
}

/** The ended trace's fold: the header's button. */
function traceFold(page: Page) {
  return traceHeader(page).getByRole("button");
}

/** Show the trace's step list: open already while the run is live or
 *  paused; once it has ended, opened from the header's chevron. */
async function openSteps(page: Page): Promise<void> {
  if ((await traceFold(page).count()) > 0 && (await traceFold(page).getAttribute("aria-expanded")) !== "true") {
    await traceFold(page).click();
  }
  await expect(page.getByRole("list", { name: "Run steps" })).toBeVisible();
}

/** The ended trace's one destination: "Report ready · 14 min · Read it →". */
function runCompletionLink(page: Page) {
  return runTrace(page).getByRole("link", { name: "Read it →" });
}

/** (a) Tasks list renders the mock task's row, then (b) navigating into it
 *  opens the workspace (Plan). */
async function openWorkspaceFromLanding(page: Page): Promise<void> {
  await page.goto("/");
  const link = page.getByRole("link", { name: mockTask.name });
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}`));
}

/** Drive a run from a fresh workspace through to "succeeded": start the
 *  analysis, wait for the check-in, answer it with the suggested option, and
 *  wait for the folded trace's "Read it →" link — the same
 *  drive several tests below need before they can reach a stage the
 *  lifecycle only opens once a run has finished. */
async function driveRunToSuccess(page: Page): Promise<void> {
  await openWorkspaceFromLanding(page);
  await page.getByRole("button", { name: "Start the search" }).click();
  await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });
  await page.getByRole("radio", { name: new RegExp(`^${SUGGESTED_OPTION_LABEL}`) }).click();
  await expect(page.getByText(CHECK_IN_QUESTION)).toHaveCount(0);
  await expect(runCompletionLink(page)).toBeVisible({ timeout: 15_000 });
}

test.describe("mock task-lifecycle journey", () => {
  test("plan through run, results, sources and history", async ({ page }) => {
    // (a) Tasks list: the mock task's row, no per-row rename/archive (task
    // 032 moved that into the header's "Task settings" popover, reachable
    // only once inside a task).
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Tasks" })).toBeVisible();
    await expect(page.getByRole("link", { name: mockTask.name })).toBeVisible();

    // (b) Into the workspace (the Agent tab): two columns — the Task's
    // conversations in a sidebar, the selected one in the main view (038
    // V8, owner ruling 2026-09-05). No overlay launcher on this tab.
    await page.getByRole("link", { name: mockTask.name }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}`));
    const chats = page.getByRole("complementary", { name: "Chats" });
    await expect(chats).toBeVisible();
    await expect(page.getByRole("button", { name: "Open the Agent" })).toHaveCount(0);
    // The sidebar starts as a rail (shut by default); open it. The Task Agent
    // is the first row after the sidebar's own two actions (Hide chats, New
    // chat), and it is what the main view shows.
    await chats.getByRole("button", { name: "Show chats" }).click();
    await expect(chats.getByRole("button").nth(2)).toHaveAccessibleName("Task Agent");
    await expect(page.getByRole("region", { name: "Task Agent conversation" })).toHaveCount(1);

    // (c) Rename/archive now lives in the header's "Task settings"
    // popover: inline rename (cancel restores the original, then a real
    // save) and the two-step archive confirm (exercised, then cancelled —
    // the task carries on into the rest of the journey below).
    const settings = page.getByRole("button", { name: "Task settings" });
    await settings.click();

    await page.getByRole("button", { name: "Rename" }).click();
    await page.getByLabel("Task name").fill("A name that gets cancelled");
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByLabel("Task name")).toHaveCount(0);
    await expect(page.getByText(mockTask.name)).toBeVisible();

    const renamedName = "Healthier childhoods in Tower Hamlets (2026 pass)";
    await page.getByRole("button", { name: "Rename" }).click();
    await page.getByLabel("Task name").fill(renamedName);
    await page.getByRole("button", { name: "Save name" }).click();
    await expect(page.getByText(renamedName)).toBeVisible();

    await page.getByRole("button", { name: "Archive" }).click();
    await expect(page.getByRole("button", { name: "Confirm archive" })).toBeVisible();
    await expect(page.getByText("Archiving removes this task")).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("button", { name: "Archive" })).toBeVisible();
    await settings.click(); // close the popover

    // No result yet, so there is nothing to ask about: New chat is offered
    // but disabled, with the reason (038 V8, owner 2026-09-05). The chat
    // round-trip itself runs after the run, in the chat test below.
    await expect(chats.getByRole("button", { name: "New chat" })).toBeDisabled();
    await expect(chats.getByRole("button", { name: "New chat" })).toHaveAttribute("title", /available once the task has a result/);

    // (d) The lifecycle bar shows all five stages from the first moment —
    // with no run yet, Plan and Share are open; Results/Sources/History
    // render but are locked (a `<span aria-disabled>`, not a link).
    const nav = lifecycleNav(page);
    await expect(nav.getByRole("link", { name: "Agent", exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Share", exact: true })).toBeVisible();
    for (const label of ["Result", "Sources", "History"]) {
      await expect(nav.getByRole("link", { name: label, exact: true })).toHaveCount(0);
      await expect(nav.getByText(label)).toBeVisible();
    }

    // (e) Pre-run, the workspace is a centred single-column chat (028 strand
    // 3): no task_agent rail, no two-pane split — the conversation itself is
    // the surface. The durable seed transcript renders as structured part
    // cards rather than plain reply bubbles: turn 1's question part is
    // settled by turn 2's canned marker message — the raw marker text never
    // leaks as a visible bubble, and the settled block carries no tick
    // (owner, 2026-11-05) — and turn 2's scope part, answered by turn 3, has
    // settled to its chips (owner, polish round 2: no open card once a later
    // turn exists).
    const settledQuestion = page.getByTestId("part-settled").filter({ hasText: /^Question/ }).first();
    await expect(settledQuestion).toBeVisible();
    await expect(settledQuestion).not.toContainText("✓");
    await expect(page.getByText("[confirm part=question option=confirm]")).toHaveCount(0);
    await expect(page.getByTestId("part-settled").filter({ hasText: /^Scope/ })).toContainText(/UK primary|Since 2016/);
    await expect(page.getByRole("radio", { name: /^Looks right/ })).toHaveCount(0);

    // (f) The ready plan is two actions at the foot of the thread — review
    // in the side panel, or start. Locked-vocabulary labels live in the panel,
    // not in an expandable card in the chat.
    await expect(page.getByRole("button", { name: "Review the plan" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Start the search" })).toBeVisible();

    // (g) Start the analysis — the workspace stays a single-column chat.
    // Progress is the run trace in the thread (not a right-hand analysing
    // pane). The mock races through every pre-synthesise stage with no
    // artificial delay, straight to the paused check-in (see step (h)), so
    // the trace's paused header and its step list are the robust checks.
    await page.getByRole("button", { name: "Start the search" }).click();
    const runCard = runTrace(page);
    await expect(runCard).toBeVisible({ timeout: 15_000 });
    // Live, the steps are the trace's body and stay open (owner, round 6):
    // the header is a line, not a control.
    await expect(page.getByRole("list", { name: "Run steps" })).toBeVisible();
    await expect(traceFold(page)).toHaveCount(0);
    const timeline = page.getByRole("list", { name: "Run steps" });
    await expect(timeline.getByText("Searching and screening").first()).toBeVisible({ timeout: 15_000 });
    await expect(timeline.getByRole("listitem").filter({ hasText: /^Writing/ })).toBeVisible({ timeout: 15_000 });
    // No stage signposts under the trace (owner, polish round 2): its own
    // row links point at the outputs.
    await expect(page.getByRole("link", { name: /Sources are ready/ })).toHaveCount(0);
    await expect(runCard.getByRole("link", { name: "Sources →" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Analysis progress" })).toHaveCount(0);

    // (h) The check-in card appears; the run genuinely parks here. Paused
    // reads distinct from executing on this tab (028 contract: pause
    // salience) — the trace's header says a check-in waits. While paused,
    // Results is open so the in-progress write-up is reachable; Share and
    // Sources stay open; Plan/History stay open.
    await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("check-in-facts")).toContainText("312 sources · 118 relevant");
    await expect(traceHeader(page)).toContainText("Paused · a check-in is waiting on you");

    for (const label of ["Agent", "Result", "Sources", "Share", "History"]) {
      await expect(nav.getByRole("link", { name: new RegExp(`^${label}`) })).toBeVisible();
    }

    // Answering the suggested option collapses the card to the "Answered" echo.
    const suggestedChoice = page.getByRole("radio", { name: new RegExp(`^${SUGGESTED_OPTION_LABEL}`) });
    await expect(suggestedChoice).toBeVisible();
    await suggestedChoice.click();
    await expect(page.getByText(CHECK_IN_QUESTION)).toHaveCount(0);
    await expect(page.getByText(/^You chose: /)).toBeVisible();

    // (i) The run has now reached "succeeded" — all five stages open. The
    // trace has folded to "Report ready · … · Read it →", pointing at
    // `/result`, and no separate finished notice sits under it.
    await expect(runCompletionLink(page)).toBeVisible({ timeout: 15_000 });
    await expect(runCompletionLink(page)).toHaveAttribute("href", `/tasks/${MOCK_TASK_ID}/result`);
    await expect(traceHeader(page)).toContainText("Report ready");
    await expect(page.getByText(/Evidence search is finished/)).toHaveCount(0);
    // The plan opens from "See plan" at the foot of the open step list
    // (owner, polish round 2: no Plan control in the task nav); Escape
    // closes it.
    await expect(nav.getByRole("button", { name: "Plan", exact: true })).toHaveCount(0);
    await openSteps(page);
    await page.getByRole("button", { name: "See plan" }).click();
    const planPanel = page.getByRole("dialog", { name: /plan/i });
    await expect(planPanel).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(planPanel).toHaveCount(0);
    for (const label of ["Agent", "Result", "Sources", "Share", "History"]) {
      await expect(nav.getByRole("link", { name: new RegExp(`^${label}`) })).toBeVisible();
    }

    // (j) Result: the committed A4 report. The tab is reachable while
    // writing is in progress; a finished run must not replay the in-progress
    // view.
    await nav.getByRole("link", { name: /^Result/ }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/result$`));
    await expect(page.locator(".artefact-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: "What appears to help" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Implications for local action" })).toBeVisible();
    await expect(
      page.getByText(/Pair school food action with safer active-travel routes/),
    ).toBeVisible({ timeout: 5_000 });

    // Demo annotation grammar: the citation numbers ride as one inline chip;
    // clicking it (or the span) opens the "Where this comes from" panel with
    // the quote highlighted in its source passage.
    const marker = page.getByRole("button", { name: /^Citations 1/ });
    await expect(marker).toBeVisible();
    await marker.click();
    await expect(page.getByText("Where this comes from")).toBeVisible();
    await expect(page.getByText(CITATION_QUOTE).first()).toBeVisible();
    await page
      .getByRole("dialog", { name: "Where this comes from" })
      .getByRole("button", { name: CITED_SOURCE_TITLE })
      .click();
    await expect(page).toHaveURL(/[?&]source=/);
    await expect(page.getByRole("dialog", { name: CITED_SOURCE_TITLE })).toBeVisible();
    await page.getByRole("button", { name: "Close panel" }).click();
    await expect(page).not.toHaveURL(/[?&]source=/);

    // Theme-referenced claims surface the named theme: the panel shows the
    // theme's name, description, size, and a deep link into the filtered
    // findings view. Conclusions collapse to their summary by default —
    // expand the section to reach its claims.
    await page.getByRole("button", { name: /Implications for local action/ }).click();
    await page.getByRole("button", { name: "pattern" }).click();
    const themePanel = page.getByRole("dialog", { name: "Where this comes from" });
    await expect(themePanel.getByText("Active-travel offers")).toBeVisible();
    // The source count is a disclosure: expanding lists the member documents,
    // each opening its dossier.
    await themePanel.getByText(/Identified across 2 sources — show them/).click();
    await expect(
      themePanel.getByRole("button", { name: /Childhood obesity prevention in urban primary schools/ }),
    ).toBeVisible();
    // The facet/group filter must survive the navigation — landing on an
    // unfiltered Findings table would look like it worked while quietly
    // showing the wrong thing.
    await themePanel.getByRole("link", { name: "See the findings in this theme" }).click();
    await expect(page).toHaveURL(
      new RegExp(`/tasks/${MOCK_TASK_ID}/sources/findings\\?facet=.*group=`),
    );
    await page.goBack();

    // (k) Sources: Themes is the index subview; Findings and All sources are
    // reached through the Sources layout's own subnav (task 032 folded the
    // old flat "Findings"/"Sources" tabs under one Sources stage).
    await nav.getByRole("link", { name: /^Sources/ }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/sources$`));
    await expect(page.getByText("School food environments")).toBeVisible();

    const sourcesSubnav = page.getByRole("navigation", { name: "Sources" });
    await page.getByRole("link", { name: /School food environments/ }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/sources/all\\?theme=`));
    await page.getByRole("button", { name: "Open the Agent" }).click();
    const overlay = page.getByRole("complementary", { name: "Agent" });
    await expect(overlay).toBeVisible();
    // The overlay is the Agent tab's sidebar folded into one column: with no
    // chat yet the launcher opens the Task Agent itself (nothing is created),
    // its header names it, and the header's list toggle shows the same list
    // with the Task Agent pinned first (038 V8, invariant I8).
    await expect(overlay.getByRole("region", { name: "Task Agent conversation" })).toBeVisible();
    await expect(overlay.getByText("Task Agent").first()).toBeVisible();
    await overlay.getByRole("button", { name: "Chats" }).click();
    const overlayList = overlay.getByRole("region", { name: "Chats" });
    await expect(overlayList.getByRole("button").first()).toHaveAccessibleName("Task Agent");
    await overlayList.getByRole("button", { name: "Task Agent" }).click();
    await expect(overlay.getByRole("region", { name: "Task Agent conversation" })).toBeVisible();
    await overlay.getByRole("button", { name: "Close sidebar" }).click();
    await sourcesSubnav.getByRole("link", { name: "Themes" }).click();
    await sourcesSubnav.getByRole("link", { name: "Findings" }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/sources/findings$`));
    const kindFilter = page.getByRole("group", { name: "Finding kind" });
    await kindFilter.getByRole("button", { name: "Intervention–outcome" }).click();
    await expect(page).toHaveURL(/[?&]profile=iof/);
    await page.getByRole("button", { name: /Expand finding: Universal breakfast provision/ }).click();
    await expect(page.getByRole("heading", { name: "Reported numbers" })).toBeVisible();

    await kindFilter.getByRole("button", { name: "Implementation context" }).click();
    await expect(page).toHaveURL(/[?&]profile=icf/);
    await page.getByRole("button", { name: /Expand finding: Active-travel offers/ }).click();
    await expect(page.getByRole("heading", { name: "Context detail" })).toBeVisible();

    // (l) All sources: a server-side status filter changes the URL and the
    // collection-true shown count.
    await sourcesSubnav.getByRole("link", { name: "All sources" }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/sources/all$`));
    // Scope to the sources table — S6's Search queries section adds its own
    // tables below, and a page-wide `row` count would include them.
    const sourcesTable = page.getByRole("table").first();
    const sourceRows = sourcesTable.getByRole("row");
    await expect(sourceRows.first()).toBeVisible();
    // Default view = Included (041: the screened-in set), sorted on the
    // relevance spectrum.
    const includedCount = mockEvidence.filter(
      (item) => item.status !== "found" && item.status !== "screened_out",
    ).length;
    await expect(sourceRows).toHaveCount(includedCount + 1);
    await expect(page.getByRole("heading", { name: "Search queries" })).toBeVisible();

    // "All" is one click away and shows the whole collection.
    const sourceFilters = page.getByRole("group", { name: "Filter sources" });
    await sourceFilters.getByRole("button", { name: "All", exact: true }).click();
    await expect(page).toHaveURL(/[?&]status=all/);
    await expect(sourceRows).toHaveCount(mockEvidence.length + 1);
    // The retracted verdict lives in the Relevant column's hover button.
    await expect(
      page.getByRole("button", { name: "Excluded — retracted: screening details" }),
    ).toBeVisible();

    await sourceFilters.getByRole("button", { name: "Screened out" }).click();
    await expect(page).toHaveURL(/[?&]status=screened_out/);
    const screenedOut = mockEvidence.filter((item) => item.status === "screened_out").length;
    await expect(sourceRows).toHaveCount(screenedOut + 1);

    // (m) An unknown route renders the honest "nothing here" view.
    await page.goto("/this-route-does-not-exist");
    await expect(page.getByRole("heading", { name: "This task is unavailable" })).toBeVisible();
  });

  // (n) Keyboard check: Tab to a citation marker and open it with Enter.
  // Results is gated on run state: locked with no run / after a failed run,
  // open while executing so the in-progress write-up is reachable. A bare
  // direct navigation still needs a succeeded run to see the finished page.
  test("keyboard: tab to a citation marker and open it with Enter", async ({ page }) => {
    await driveRunToSuccess(page);
    await runCompletionLink(page).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/result$`));
    await expect(
      page.getByRole("heading", { name: "Policy options for healthier childhoods" }),
    ).toBeVisible();
    // Let a citation marker actually attach before tabbing through the page:
    // right after this client-side navigation there's a brief window where
    // the DOM hasn't finished settling, which flakes how many tab presses it
    // takes to reach the first one.
    await expect(page.getByRole("button", { name: /^Citations 1/ })).toBeVisible();

    let found = false;
    for (let i = 0; i < 60 && !found; i++) {
      await page.keyboard.press("Tab");
      const label = await page.evaluate(
        () => document.activeElement?.getAttribute("aria-label") ?? "",
      );
      found = label.startsWith("Citation");
    }
    expect(found).toBe(true);

    await page.keyboard.press("Enter");
    await expect(page.getByText(CITATION_QUOTE).first()).toBeVisible();
  });

  // (o) `prefers-reduced-motion` emulation runs the workspace — through
  // starting a run and reaching the pending check-in — without console errors.
  test("prefers-reduced-motion: the workspace runs cleanly with no console errors", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const pageErrors: unknown[] = [];
    page.on("pageerror", (error) => pageErrors.push(error));
    page.on("console", (message) => {
      if (message.type() === "error") pageErrors.push(message.text());
    });

    await openWorkspaceFromLanding(page);
    // Pre-run: the centred single-column chat, not the two-pane layout — no
    // rail or right-hand pane exists until a run starts.
    await expect(page.getByRole("button", { name: "Start the search" })).toBeVisible();
    await page.getByRole("button", { name: "Start the search" }).click();
    await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });

    expect(pageErrors).toEqual([]);
  });

  // (p) At 1280 and 768 widths, no horizontal body scroll — checked on the
  // tasks list, the pre-run centred single-column workspace, and the
  // two-pane workspace once a run exists (the widest layout in the app —
  // the rail appears only from this point on, so it is never assumed
  // pre-run).
  test("responsive: no horizontal overflow at 1280 and 768 widths", async ({ page }) => {
    for (const width of [1280, 768]) {
      await page.setViewportSize({ width, height: 900 });

      await page.goto("/");
      await expect(page.getByRole("link", { name: mockTask.name })).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);

      await openWorkspaceFromLanding(page);
      // Pre-run: centred single-column chat, no rail.
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);

      // Start a run: the workspace stays a single column (no analysing pane,
      // no rail). The run trace is the progress surface.
      await page.getByRole("button", { name: "Start the search" }).click();
      await expect(page.getByRole("region", { name: "Analysis run" })).toBeVisible({ timeout: 15_000 });
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
      await expect(page.getByRole("button", { name: "Collapse the Task Agent rail" })).toHaveCount(0);
    }
  });

  // (q) The ended trace's fold is a real button: keyboard-operable. Live,
  // the steps are open and the header is not a control (owner, round 6).
  test("keyboard: the ended trace's chevron opens the steps via Enter and closes them via Space", async ({ page }) => {
    await openWorkspaceFromLanding(page);
    await page.getByRole("button", { name: "Start the search" }).click();
    await expect(page.getByRole("list", { name: "Run steps" })).toBeVisible({ timeout: 15_000 });
    await expect(traceFold(page)).toHaveCount(0);
    await answerCheckIn(page);
    await expect(runCompletionLink(page)).toBeVisible({ timeout: 30_000 });
    const fold = traceFold(page);
    await expect(fold).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByRole("list", { name: "Run steps" })).toHaveCount(0);
    await fold.focus();
    await page.keyboard.press("Enter");
    await expect(fold).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("list", { name: "Run steps" })).toBeVisible();
    await fold.focus();
    await page.keyboard.press("Space");
    await expect(fold).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByRole("list", { name: "Run steps" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Minimise" })).toHaveCount(0);
  });

  // (r) Paused on another tab (028 contract: pause salience; task 058, owner
  // round 7: the run strip returns under the tabs, status only). The strip
  // says the check-in waits on History, with no link and no banner; opening
  // the sidebar from its rail lands on the Task Agent, whose trace says the
  // same, with the check-in under it.
  test("paused run: other tabs show the paused strip, no banner, and the sidebar's trace says a check-in waits", async ({ page }) => {
    await openWorkspaceFromLanding(page);
    await page.getByRole("button", { name: "Start the search" }).click();
    await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });

    await lifecycleNav(page).getByRole("link", { name: "History", exact: true }).click();
    const strip = page.getByTestId("run-strip");
    await expect(strip).toHaveAttribute("data-open", "true");
    await expect(strip).toContainText(/Paused\s·\sa check-in is waiting on you/);
    await expect(strip.getByRole("link")).toHaveCount(0);
    await expect(page.getByText("The analysis is paused — a check-in is waiting on you")).toHaveCount(0);
    await page.getByRole("button", { name: "Open the Agent" }).click();
    const sidebar = page.getByRole("complementary", { name: "Agent" });
    await expect(sidebar.getByRole("region", { name: "Analysis run" }).getByTestId("trace-header")).toContainText(
      "Paused · a check-in is waiting on you",
    );
    await expect(sidebar.getByText(CHECK_IN_QUESTION)).toBeVisible();
  });

  // (s) Task 029 chat leg: from the completed results page, open a chat via
  // "Ask about this analysis", send a question, and watch the scripted mock
  // turn (progress -> two deltas -> completed with one citation) render:
  // the activity label, the inline `[1]` marker, the honestly "unchecked"
  // reference that upgrades to its tier verdict once the async enrichment
  // poll's second read lands, and the stop control visible mid-stream. Then
  // manage the chat itself through the library: it lists, its rename round-
  // trips, and archiving removes it from the default (active) list.
  test("chat: ask about the evidence base, watch the citation verdict upgrade, and manage the chat in the library", async ({ page }) => {
    await driveRunToSuccess(page);

    await runCompletionLink(page).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/result$`));
    await expect(page.locator(".artefact-page")).toBeVisible();
    await expect(
      page.getByText(/Pair school food action with safer active-travel routes/),
    ).toBeVisible({ timeout: 5_000 });

    await page.getByRole("button", { name: "Ask about this analysis" }).click();
    // rev 3.4: the chat opens as a side panel BESIDE the artefact — the URL
    // stays on the results route and simply gains the chat param.
    // 038 V8: it is a DRAFT (`?chat=new`) carrying the report as its entry
    // context; no row exists until the first message.
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/result\\?chat=new`));
    await expect(page.getByRole("complementary", { name: "Agent" })).toBeVisible();
    await expect(page.locator(".artefact-page")).toBeVisible();

    // Entry context renders as the "Report" chip (rev 2.6) — scoped to the
    // chat region since the nav also carries a "Result" link.
    const chat = page.getByRole("region", { name: "Chat" });
    await expect(chat.getByRole("link", { name: "Report" })).toBeVisible();

    await page.getByPlaceholder("Ask about the evidence").fill("What does the evidence show about breakfast provision?");
    await chat.getByRole("button", { name: "Send" }).click();
    // The first message created the chat: the URL moves onto its id.
    await expect(page).not.toHaveURL(/chat=new/);

    // The activity label appears, and the stop control is visible while
    // streaming (no need to click it).
    await expect(chat.getByText("Searching the evidence…")).toBeVisible();
    await expect(chat.getByRole("button", { name: "Stop" })).toBeVisible();

    // Streamed prose lands, with its inline `[1]` citation marker.
    await expect(
      chat.getByText(/Universal breakfast provision supported more consistent uptake/),
    ).toBeVisible({ timeout: 10_000 });
    await expect(chat.getByRole("button", { name: "[1]" }).first()).toBeVisible();

    // 030 fold: the claim's own span renders with the report's citation-
    // marker affordance — a distinct clickable region from the literal `[1]`
    // marker above — and opens the claim-keyed "Where this comes from" sheet
    // (the claim text as its blockquote) on click.
    await chat.getByRole("button", { name: MOCK_CHAT_CLAIM_TEXT }).click();
    const claimSheet = page.getByRole("dialog", { name: "Where this comes from" });
    await expect(claimSheet).toBeVisible();
    await expect(claimSheet.getByText(MOCK_CHAT_CLAIM_TEXT)).toBeVisible();
    // 030 fold (Rev 3.6): the sheet's citation block carries the artefact
    // reader's appraisal chip, in parity — the mock citation's
    // appraisal_label.
    await expect(claimSheet.getByText("moderate")).toBeVisible();
    await page.getByRole("button", { name: "Close panel" }).click();
    await expect(claimSheet).toHaveCount(0);

    // The References disclosure starts collapsed (029 Fix D) — expand it to
    // reach the verdict chip. The reference is honestly "unchecked" until
    // the async grounding judge lands, then upgrades to its tier verdict on
    // the enrichment poll's second read (mock: the second GET turns
    // response); the disclosure stays open across that re-render since it's
    // native, uncontrolled `<details>` state.
    await chat.getByText("References (1)").click();
    await expect(chat.getByText("Unchecked · awaiting evidence check")).toBeVisible();
    await expect(chat.getByText("Tier 2 · grounded")).toBeVisible({ timeout: 12_000 });

    // The list (the overlay header's toggle): lists the chat, rename
    // round-trips, archive removes it from the default (active) list.
    await page.getByRole("button", { name: "Chats" }).click();
    const library = page.getByRole("region", { name: "Chats" });
    await expect(library).toBeVisible();
    await expect(library.getByRole("button", { name: "New chat", exact: true })).toBeVisible();

    await library.getByRole("button", { name: "Rename New chat" }).click();
    await library.getByLabel("Chat title").fill("Breakfast provision");
    await library.getByLabel("Chat title").press("Enter");
    await expect(library.getByRole("button", { name: "Breakfast provision", exact: true })).toBeVisible();

    await library.getByRole("button", { name: "Archive" }).click();
    await expect(library.getByRole("button", { name: "Archive" })).toHaveCount(0);
    // Archived chats sit behind a disclosure that starts shut.
    await expect(library.getByRole("heading", { name: "Archived" })).toBeVisible();
    await expect(library.getByRole("button", { name: "Restore" })).toHaveCount(0);
    await library.getByRole("heading", { name: "Archived" }).click();
    await expect(library.getByRole("button", { name: "Restore" })).toBeVisible();

    // The Agent tab on the completed task: the Task Agent is still listed
    // (the run closed the task_agent lineage), New chat opens a draft in the
    // main view, and the Task Agent brings the task_agent pane back.
    await page.getByRole("link", { name: /^Agent/ }).click();
    const chats = page.getByRole("complementary", { name: "Chats" });
    await chats.getByRole("button", { name: "Show chats" }).click();
    await expect(chats.getByRole("button").nth(2)).toHaveAccessibleName("Task Agent");
    await chats.getByRole("button", { name: "New chat" }).first().click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}\\?chat=new`));
    await expect(page.getByRole("region", { name: "Chat" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Task Agent conversation" })).toHaveCount(0);
    await chats.getByRole("button", { name: "Task Agent" }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}$`));
    await expect(page.getByRole("region", { name: "Task Agent conversation" })).toBeVisible();
  });

  // --- Two regressions this slice introduced, found while updating this
  // suite and since FIXED. Kept as ordinary tests so they stay exercised.

  // The theme panel's "See the findings in this theme" link pointed at the
  // retired `/findings` path, and `RedirectToPath` dropped `location.search`
  // on the way through — so the facet/group filter vanished in transit and
  // the reader landed on the unfiltered table. Both were fixed: the link now
  // addresses `/sources/findings` directly, and the redirect forwards its
  // query string for every retired path, not just this one.
  test(
    "the theme panel's findings deep link keeps its facet/group filter",
    async ({ page }) => {
      await driveRunToSuccess(page);
      await runCompletionLink(page).click();
      await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/result$`));
      await page.getByRole("button", { name: /Implications for local action/ }).click();
      await page.getByRole("button", { name: "pattern" }).click();
      await page
        .getByRole("dialog", { name: "Where this comes from" })
        .getByRole("link", { name: "See the findings in this theme" })
        .click();
      await expect(page).toHaveURL(/sources\/findings\?facet=.*group=/);
    },
  );

  // The workspace stays a single column after Start search, including
  // below `lg` — there is no rail to overlap the plan overlay.
  test("below the lg breakpoint, the run trace is the progress surface", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await openWorkspaceFromLanding(page);
    await page.getByRole("button", { name: "Start the search" }).click();
    await expect(page.getByRole("region", { name: "Analysis run" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("button", { name: "Collapse the Task Agent rail" })).toHaveCount(0);
  });
});

// --- Task 058 (N26): the annex's states, asserted against the mock ----------
//
// The mock plays the run in a few seconds, so a state can be on screen for
// well under one polling interval of `expect`. `watchPage` therefore keeps
// every distinct line the page has shown, in order; `seen` asserts on that
// record. The mock reads its scenario from the `/events` request's query
// string, which the app's own stream client never sets, so `useScenario`
// adds it on the way to the mock (the mock installs its fetch at start-up,
// so a Playwright route cannot see these calls).

type Scenario = "default" | "paused" | "failed-partial" | "reload-mid-section" | "paused-strip";

/** Select the mock's scenario for the `/events` request. */
async function useScenario(page: Page, scenario: Scenario): Promise<void> {
  await page.addInitScript((name) => {
    let inner: typeof fetch = window.fetch.bind(window);
    Object.defineProperty(window, "fetch", {
      configurable: true,
      get() {
        return ((input: RequestInfo | URL, init?: RequestInit) => {
          const url = input instanceof Request ? input.url : String(input);
          if (url.includes("/events")) {
            return inner(`${url}${url.includes("?") ? "&" : "?"}mockScenario=${name}`, init);
          }
          return inner(input as RequestInfo, init);
        }) as typeof fetch;
      },
      set(next: typeof fetch) {
        inner = next;
      },
    });
  }, scenario);
}

/** Record every distinct line the page shows, in the order first seen. */
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

/** Wait until a line matching `wanted` has been on the page at some point. */
async function seen(page: Page, wanted: string | RegExp, timeout = 20_000): Promise<void> {
  const matches = (line: string) => (typeof wanted === "string" ? line === wanted : wanted.test(line));
  await expect
    .poll(async () => (await seenLines(page)).some(matches), {
      timeout,
      message: `the page never showed ${String(wanted)}`,
    })
    .toBe(true);
}

async function neverSeen(page: Page, unwanted: RegExp): Promise<void> {
  expect((await seenLines(page)).filter((line) => unwanted.test(line))).toEqual([]);
}

function taskNav(page: Page) {
  return page.getByRole("navigation", { name: "Task" });
}

async function startRun(page: Page): Promise<void> {
  await openWorkspaceFromLanding(page);
  await page.getByRole("button", { name: "Start the search" }).click();
}

async function answerCheckIn(page: Page): Promise<void> {
  await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });
  await page.getByRole("radio", { name: new RegExp(`^${SUGGESTED_OPTION_LABEL}`) }).click();
}

test.describe("task 058 live run states (annex scenes, evidence search)", () => {
  test("scene 1: the run trace, the step and its counts on its row, one row per step", async ({ page }) => {
    await watchPage(page);
    await startRun(page);

    // Live, the header is the turning mark and the elapsed time; the step
    // in progress names itself and what it is doing on its row (lead,
    // round 6), and a screen reader hears the same words from the header.
    await expect(page.getByRole("list", { name: "Run steps" }).getByText("Searching and screening").first()).toBeVisible({
      timeout: 15_000,
    });
    await seen(page, /^Searching and screening · searching · \d+ found so far/);
    await seen(page, /^Searching and screening · screening \d+ new abstracts · \d+ relevant so far/);

    // At the check-in the last finished line carries the counts and link;
    // open, upcoming rows are names only, in plan order.
    await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });
    // The trace binds each "·" to the word before it with a no-break space
    // (a separator never starts a line), so the match takes any space.
    await expect(runTrace(page).getByText(/312 found\s·\s118 relevant/)).toBeVisible();
    await openSteps(page);
    const timeline = page.getByRole("list", { name: "Run steps" });
    const rows = await timeline.getByRole("listitem").allInnerTexts();
    const order = ["Searching and screening", "Classifying", "Mapping", "Writing"].map((label) =>
      rows.findIndex((row) => row.startsWith(label)),
    );
    expect(order).toEqual([0, 1, 2, 3]);
    for (const upcoming of ["Classifying", "Mapping", "Writing"]) {
      const row = rows.find((text) => text.startsWith(upcoming)) ?? "";
      expect(row).not.toContain("·");
      expect(row).not.toMatch(/\d/);
    }

    await answerCheckIn(page);
    await seen(page, /\d+ of 118 classified/);
    await seen(page, /Assigning themes · batch \d of 3/);
    await expect(runCompletionLink(page)).toBeVisible({ timeout: 20_000 });

    await neverSeen(page, /Round \d/i);
    await neverSeen(page, /Shortlist →/);
  });

  test("scene 5: the Result tab before writing is the question and one sentence", async ({ page }) => {
    // The mock always serves a committed report, which would take the
    // page over; answer "no report yet" the way the server does.
    await page.addInitScript(() => {
      let inner: typeof fetch = window.fetch.bind(window);
      Object.defineProperty(window, "fetch", {
        configurable: true,
        get() {
          return ((input: RequestInfo | URL, init?: RequestInit) => {
            const url = input instanceof Request ? input.url : String(input);
            if (new URL(url, window.location.origin).pathname.endsWith("/artefact")) {
              return Promise.resolve(
                new Response(JSON.stringify({ error: { code: "not_found", message: "No report yet." } }), {
                  status: 404,
                  headers: { "Content-Type": "application/json" },
                }),
              );
            }
            return inner(input as RequestInfo, init);
          }) as typeof fetch;
        },
        set(next: typeof fetch) {
          inner = next;
        },
      });
    });
    await startRun(page);
    await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });
    await taskNav(page).getByRole("link", { name: /^Result/ }).click();

    await expect(page.getByRole("heading", { name: mockTask.question ?? "" })).toBeVisible();
    await expect(page.getByText("The report's sections are set out when writing begins.")).toBeVisible();
    await expect(page.getByText("Preparing your results")).toHaveCount(0);
  });

  test("scene 6: the Result tab while writing streams the prose, then settles it", async ({ page }) => {
    await watchPage(page);
    await startRun(page);
    await answerCheckIn(page);
    await taskNav(page).getByRole("link", { name: /^Result/ }).click();

    await expect(page.getByRole("heading", { name: mockTask.question ?? "" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("heading", { name: "What appears to help" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Implications for local action" })).toBeVisible();
    // The action line, then the streamed prose growing, then the check.
    await seen(page, "Looking for: evidence on subsidy uptake among low-income households");
    // The sources the writer reads are named under the heading as the reads
    // land, and its own citations show as the marker's muted chip once they
    // close (task 058, evidence shown live; owner round 7).
    // A checked section carries the report's numbered marker while live, not
    // yet a control, and the references list grows at the foot (round 7).
    await expect(page.getByRole("img", { name: /^Citation 1, .*; details when the report is ready$/ })).toHaveText(
      "[1]",
      { timeout: 20_000 },
    );
    await expect(page.getByRole("region", { name: "References" }).getByRole("listitem").first()).toHaveText(
      `[1]${CITED_SOURCE_TITLE}`,
    );
    await seen(page, "Drawing on 2 sources · Smith 2023 · DfE 2022");
    await seen(page, "Drawing on 5 sources · Smith 2023 · DfE 2022 · Nesta 2021 · and 2 more");
    await expect(page.getByRole("img", { name: /^Cited, being checked: / })).toHaveCount(2, { timeout: 20_000 });
    await expect(page.getByRole("img", { name: "Cited, being checked: Sustrans 2020" })).toHaveText("[·]");
    // The run strip under the tabs says the same step (owner, round 7).
    await expect(page.getByTestId("run-strip")).toContainText(/^Writing/);
    await seen(page, "Checking claims");
    await seen(page, "Revising 1 claim");
    await seen(page, /walking bus saw 6 more children arrive on foot in every 100\.(\s*\[[\d,]+\])?$/, 30_000);
    // Checked, the section keeps its markers in the report's look, not yet
    // controls: one claim citing reference 2, and the repaired sentence
    // citing 2 and 3 on one span, which the report sets as one marker.
    const implications = page.locator("section", { has: page.getByRole("heading", { name: "Implications for local action" }) });
    await expect(implications.getByRole("img", { name: /details when the report is ready$/ })).toHaveText(["[2]", "[2,3]"], {
      timeout: 30_000,
    });
    // The case studies stream card by card in the report's card layout; the
    // first card carries its marker, live or committed.
    await seen(page, "Leeds — Breakfast in every primary", 30_000);
    await seen(page, "Bristol — Walking bus pilots", 30_000);
    const caseStudies = page.locator("section", { has: page.getByRole("heading", { name: "Case studies" }) });
    await expect(caseStudies.getByRole("listitem").first().getByText("[2]")).toBeVisible({ timeout: 30_000 });
    await expect(caseStudies).not.toContainText("**");
    // The references at the foot have grown to the report's three.
    await expect(page.getByRole("region", { name: "References" }).getByRole("listitem")).toHaveCount(3, {
      timeout: 30_000,
    });

    const growing = (await seenLines(page)).filter((line) => line.startsWith("Pair school food action with"));
    expect(new Set(growing.map((line) => line.length)).size).toBeGreaterThan(3);

    // Nothing marks a section as revised once it is done. When the run ends
    // the committed report takes the page by itself (owner, 2026-11-05).
    await neverSeen(page, /being revised|^revised$/i);
    await expect(page.getByTestId("drawing-on")).toHaveCount(0);
    await expect(page.getByTestId("provisional-mark")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Policy options for healthier childhoods" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByRole("button", { name: "Read the full report" })).toHaveCount(0);
    await neverSeen(page, /attaching citations/);
  });

  test("scene 7: on Sources the strip and the sidebar's trace show the run: it runs, pauses and folds to Report ready", async ({
    page,
  }) => {
    await watchPage(page);
    await startRun(page);
    await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });
    await taskNav(page).getByRole("link", { name: /^Sources/ }).click();
    // The strip under the tabs says the run waits (owner, round 7); status
    // only, no link.
    const strip = page.getByTestId("run-strip");
    await expect(strip).toContainText(/a check-in is waiting on you/);
    await expect(strip.getByRole("link")).toHaveCount(0);

    // The sidebar's trace is the run view: opening it lands on the waiting
    // check-in; answer it there, then watch the trace to the end.
    await page.getByRole("button", { name: "Open the Agent" }).click();
    const sidebar = page.getByRole("complementary", { name: "Agent" });
    const trace = sidebar.getByRole("region", { name: "Analysis run" });
    await expect(trace.getByTestId("trace-header")).toContainText("Paused · a check-in is waiting on you", {
      timeout: 15_000,
    });
    await expect(page.getByText("Go to the check-in")).toHaveCount(0);
    await sidebar.getByRole("radio", { name: new RegExp(`^${SUGGESTED_OPTION_LABEL}`) }).click();
    await seen(page, /^Writing · Section \d of \d/, 30_000);
    await expect(trace.getByRole("link", { name: "Read it →" })).toBeVisible({ timeout: 30_000 });
    await expect(trace.getByTestId("trace-header")).toContainText("Report ready");
    // The run has ended: the strip closes.
    await expect(strip).toHaveAttribute("data-open", "false");
  });

  test("scene 7: the paused strip and no banner on another tab while a check-in waits", async ({ page }) => {
    await useScenario(page, "paused-strip");
    await startRun(page);
    await expect(page.getByText(CHECK_IN_QUESTION)).toBeVisible({ timeout: 15_000 });
    // Not on the Agent tab.
    await expect(page.getByTestId("run-strip")).toHaveAttribute("data-open", "false");
    await taskNav(page).getByRole("link", { name: "History", exact: true }).click();

    await expect(page.getByTestId("run-strip")).toContainText(/Paused\s·\sa check-in is waiting on you/);
    await expect(page.getByText("Go to the check-in")).toHaveCount(0);
    await expect(page.getByText("The analysis is paused — a check-in is waiting on you")).toHaveCount(0);
  });

  test("scene 8: a reconnect mid-section shows the prose so far at once", async ({ page }) => {
    // The mock keeps its world in the page, so a literal `page.reload()`
    // would restart the task. This scenario is what the stream sends a
    // reconnecting page: the durable frames at once, then the first half of
    // the section's prose in one `replace`, then the rest.
    await useScenario(page, "reload-mid-section");
    await watchPage(page);
    await startRun(page);
    await taskNav(page).getByRole("link", { name: /^Result/ }).click();

    await seen(page, /^Pair school food action with/, 20_000);
    const lines = (await seenLines(page)).filter((line) => line.startsWith("Pair school food action with"));
    expect(lines[0].length).toBeGreaterThan(80);
    await seen(page, /walking bus saw 6 more children arrive on foot in every 100\.(\s*\[[\d,]+\])?$/, 30_000);
  });

  test("scene 14: a section landing marks Result, visiting clears it, the title announces the report", async ({
    page,
  }) => {
    await startRun(page);
    await answerCheckIn(page);
    const nav = taskNav(page);
    await nav.getByRole("link", { name: /^Sources/ }).click();

    await expect(nav.getByRole("link", { name: /^Result New content/ })).toBeVisible({ timeout: 30_000 });
    await nav.getByRole("link", { name: /^Result/ }).click();
    await expect(nav.getByRole("link", { name: "Result", exact: true })).toBeVisible();
    await nav.getByRole("link", { name: /^Sources/ }).click();
    await expect(page).toHaveTitle(/^● Report ready/, { timeout: 30_000 });
  });

  test("scene 13: the sidebar is the same agent, with the check-in answerable in it", async ({ page }) => {
    await useScenario(page, "paused-strip");
    await startRun(page);
    await expect(page.getByRole("region", { name: "Analysis run" })).toBeVisible({ timeout: 15_000 });
    await taskNav(page).getByRole("link", { name: /^Sources/ }).click();
    await page.getByRole("button", { name: "Open the Agent" }).click();

    const sidebar = page.getByRole("complementary", { name: "Agent" });
    await expect(sidebar.getByText("Task Agent").first()).toBeVisible();
    await expect(sidebar.getByPlaceholder("Replanning unlocks when this run finishes.")).toBeDisabled();
    // The run trace in the sidebar's thread is its run view: no separate run line.
    await expect(sidebar.getByRole("region", { name: "Analysis run" }).getByTestId("trace-header")).toContainText(
      "Paused · a check-in is waiting on you",
      { timeout: 15_000 },
    );
    await expect(sidebar.getByText(CHECK_IN_QUESTION)).toBeVisible();
    const choice = sidebar.getByRole("radio", { name: new RegExp(`^${SUGGESTED_OPTION_LABEL}`) });
    await choice.click();
    await expect(choice).toBeChecked();
  });

  test("scene 11: the planning conversation streams, one step at a time", async ({ page }) => {
    await watchPage(page);
    await page.goto("/new");
    await page.getByRole("button", { name: /Evidence search/ }).click();
    await page
      .getByLabel("Your question")
      .fill("What works to raise take-up of free childcare places among low-income families?");
    await page.getByRole("button", { name: "Start", exact: true }).click();

    // The reply grows before its card appears; "Drafting the plan" holds the place.
    await seen(page, "Drafting the plan");
    await seen(page, "I can search for this. First, is the question as you want it, or do you want to narrow it?");
    const growing = (await seenLines(page)).filter((line) => "I can search for this. First, is the question as you want it, or do you want to narrow it?".startsWith(line) && line.length > 5);
    expect(growing.length).toBeGreaterThan(2);

    await expect(page.getByText("Plan · step 1 of 3 · Question")).toBeVisible();
    await expect(page.getByRole("radio", { name: /^That's my question/ })).toBeVisible();
    await expect(page.getByText("Recommended")).toHaveCount(0);
    await expect(page.getByText("Drafting the plan")).toHaveCount(0, { timeout: 15_000 });

    // The card settles on the choice at once, before the reply lands (owner, 2026-11-05).
    await page.getByRole("radio", { name: /^That's my question/ }).click();
    await expect(page.getByTestId("part-settled").filter({ hasText: /^Question/ }).first()).toBeVisible();
    await expect(page.getByRole("radio", { name: /^That's my question/ })).toHaveCount(0);
    await expect(page.getByText("Plan · step 2 of 3 · Scope")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Start the search" })).toBeVisible();
  });

  test("scene 12: the check-in reads as a question, with one way to stop", async ({ page }) => {
    await startRun(page);
    await expect(page.getByRole("heading", { name: CHECK_IN_QUESTION })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Stop the run" })).toHaveCount(1);
    await expect(page.getByText("Waiting on your input")).toHaveCount(0);

    await page.getByRole("radio", { name: new RegExp(`^${SUGGESTED_OPTION_LABEL}`) }).click();
    await expect(page.getByText(/^You chose: .* · /)).toBeVisible();
  });
});

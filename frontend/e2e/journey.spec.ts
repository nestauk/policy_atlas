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
 * durable planning transcript already formed a ready plan; see
 * `src/mock/fixtures.ts`). Selectors favour roles/labels/text over CSS — the
 * same accessible surface a screen-reader or keyboard user would rely on.
 */

const SUGGESTED_OPTION_LABEL = (mockCheckIn.options ?? []).find(
  (option) => option.suggested,
)?.label;
if (!SUGGESTED_OPTION_LABEL) throw new Error("fixture check-in has no suggested option");

const CITED_SOURCE_TITLE = "Universal breakfast clubs and diet quality";
const CITATION_QUOTE = "Breakfast participation increased when provision was universal.";

/** The task-stage bar (Plan · Results · Sources · Share · History).
 *  The global App nav sits above it; Sources has its own subnav below. */
function lifecycleNav(page: Page) {
  return page.getByRole("navigation", { name: "Task" });
}

/** The in-thread running card's completion link. */
function runCompletionLink(page: Page) {
  return page
    .getByRole("region", { name: "Analysis run" })
    .getByRole("link", { name: "Read the report" });
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
 *  wait for the completion card's "Read the report" link — the same
 *  drive several tests below need before they can reach a stage the
 *  lifecycle only opens once a run has finished. */
async function driveRunToSuccess(page: Page): Promise<void> {
  await openWorkspaceFromLanding(page);
  await page.getByRole("button", { name: "Start search" }).click();
  await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: SUGGESTED_OPTION_LABEL }).click();
  await expect(page.getByText("Waiting on your input")).toHaveCount(0);
  await expect(runCompletionLink(page)).toBeVisible({ timeout: 15_000 });
}

test.describe("mock task-lifecycle journey", () => {
  test("plan through run, results, sources and history", async ({ page }) => {
    // (a) Tasks list: the mock task's row, no per-row rename/archive (task
    // 032 moved that into the header's "Project settings" popover, reachable
    // only once inside a task).
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Tasks" })).toBeVisible();
    await expect(page.getByRole("link", { name: mockTask.name })).toBeVisible();

    // (b) Into the workspace (Plan).
    await page.getByRole("link", { name: mockTask.name }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}`));

    // (c) Rename/archive now lives in the header's "Project settings"
    // popover: inline rename (cancel restores the original, then a real
    // save) and the two-step archive confirm (exercised, then cancelled —
    // the task carries on into the rest of the journey below).
    const settings = page.getByRole("button", { name: "Project settings" });
    await settings.click();

    await page.getByRole("button", { name: "Rename" }).click();
    await page.getByLabel("Project name").fill("A name that gets cancelled");
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByLabel("Project name")).toHaveCount(0);
    await expect(page.getByText(mockTask.name)).toBeVisible();

    const renamedName = "Healthier childhoods in Tower Hamlets (2026 pass)";
    await page.getByRole("button", { name: "Rename" }).click();
    await page.getByLabel("Project name").fill(renamedName);
    await page.getByRole("button", { name: "Save name" }).click();
    await expect(page.getByText(renamedName)).toBeVisible();

    await page.getByRole("button", { name: "Archive" }).click();
    await expect(page.getByRole("button", { name: "Confirm archive" })).toBeVisible();
    await expect(page.getByText("Archiving removes this task")).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("button", { name: "Archive" })).toBeVisible();
    await settings.click(); // close the popover

    // (d) The lifecycle bar shows all five stages from the first moment —
    // with no run yet, Plan and Share are open; Results/Sources/History
    // render but are locked (a `<span aria-disabled>`, not a link).
    const nav = lifecycleNav(page);
    await expect(nav.getByRole("link", { name: "Plan", exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Share", exact: true })).toBeVisible();
    for (const label of ["Results", "Sources", "History"]) {
      await expect(nav.getByRole("link", { name: label, exact: true })).toHaveCount(0);
      await expect(nav.getByText(label)).toBeVisible();
    }

    // (e) Pre-run, the workspace is a centred single-column chat (028 strand
    // 3): no planning rail, no two-pane split — the conversation itself is
    // the surface. The durable seed transcript renders as structured part
    // cards rather than plain reply bubbles: turn 1's question part shows
    // the ✓ confirm recorded via turn 2's canned marker message — the raw
    // marker text never leaks as a visible bubble — and turn 2's scope part
    // is still live, with its editable constraint chips and confirm options.
    await expect(page.getByText("✓ Confirmed")).toBeVisible();
    await expect(page.getByText("[confirm part=question option=confirm]")).toHaveCount(0);
    await expect(page.getByText("UK primary")).toBeVisible();
    await expect(page.getByText("Since 2016")).toBeVisible();
    await expect(page.getByRole("button", { name: "Looks right" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add or change a constraint" })).toBeVisible();

    // (f) The ready plan is two actions at the foot of the thread — review
    // in the side panel, or start. Locked-vocabulary labels live in the panel,
    // not in an expandable card in the chat.
    await expect(page.getByRole("button", { name: "Review the plan" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Start search" })).toBeVisible();

    // (g) Start the analysis — the workspace stays a single-column chat.
    // Progress is a green running card in the thread (not a right-hand
    // analysing pane). The mock races through every pre-synthesise stage
    // with no artificial delay, straight to the paused check-in (see step
    // (h)), so the card's paused heading and stage list are the robust checks.
    await page.getByRole("button", { name: "Start search" }).click();
    const runCard = page.getByRole("region", { name: "Analysis run" });
    await expect(runCard).toBeVisible({ timeout: 15_000 });
    const timeline = page.getByRole("list", { name: "Stage timeline" });
    await expect(timeline.getByText("Searching")).toBeVisible({ timeout: 15_000 });
    await expect(timeline.getByText("Writing")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: /Sources are ready/ })).toBeVisible();
    await expect(runCard.getByRole("link", { name: /Sources are ready/ })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Analysis progress" })).toHaveCount(0);

    // (h) The check-in card appears; the run genuinely parks here. Paused
    // reads distinct from executing on this tab (028 contract: pause
    // salience) — the running card's heading changes. While paused,
    // Results is open so the in-progress write-up is reachable; Share and
    // Sources stay open; Plan/History stay open.
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(mockCheckIn.render)).toBeVisible();
    await expect(runCard.getByRole("heading", { name: "Paused — waiting on you" })).toBeVisible();

    for (const label of ["Plan", "Results", "Sources", "Share", "History"]) {
      await expect(nav.getByRole("link", { name: label, exact: true })).toBeVisible();
    }

    // Answering the suggested option collapses the card to the "Answered" echo.
    const suggestedButton = page.getByRole("button", { name: SUGGESTED_OPTION_LABEL });
    await expect(suggestedButton).toBeVisible();
    await suggestedButton.click();
    await expect(page.getByText("Waiting on your input")).toHaveCount(0);
    await expect(page.getByText("Answered")).toBeVisible();

    // (i) The run has now reached "succeeded" — all five stages open. The
    // completion card's "Read the report" link is also on the page,
    // pointing at `/results`.
    await expect(runCompletionLink(page)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "See plan" })).toBeVisible();
    for (const label of ["Plan", "Results", "Sources", "Share", "History"]) {
      await expect(nav.getByRole("link", { name: label, exact: true })).toBeVisible();
    }

    // (j) Results: the committed A4 report. The tab is reachable while
    // writing is in progress; a finished run must not replay the in-progress
    // view.
    await nav.getByRole("link", { name: "Results", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/results$`));
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
    await nav.getByRole("link", { name: "Sources", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/sources$`));
    await expect(page.getByText("School food environments")).toBeVisible();

    const sourcesSubnav = page.getByRole("navigation", { name: "Sources" });
    await page.getByRole("link", { name: /School food environments/ }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/sources/all\\?theme=`));
    await page.getByRole("button", { name: "Open chat" }).click();
    const overlay = page.getByRole("complementary", { name: "Project chat" });
    await expect(overlay).toBeVisible();
    await overlay.getByRole("button", { name: "Planning" }).click();
    await expect(overlay.getByRole("region", { name: "Planning conversation" })).toBeVisible();
    await overlay.getByRole("button", { name: "Close chat panel" }).click();
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
    // Default view = All, sorted on the relevance spectrum.
    await expect(sourceRows).toHaveCount(mockEvidence.length + 1);
    await expect(page.getByRole("heading", { name: "Search queries" })).toBeVisible();
    // The retracted verdict lives in the Relevant column's hover button.
    await expect(
      page.getByRole("button", { name: "Excluded — retracted: screening details" }),
    ).toBeVisible();

    const sourceFilters = page.getByRole("group", { name: "Filter sources" });
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
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/results$`));
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
    await expect(page.getByRole("button", { name: "Start search" })).toBeVisible();
    await page.getByRole("button", { name: "Start search" }).click();
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });

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
      // no rail). The running card is the progress surface.
      await page.getByRole("button", { name: "Start search" }).click();
      await expect(page.getByRole("region", { name: "Analysis run" })).toBeVisible({ timeout: 15_000 });
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
      await expect(page.getByRole("button", { name: "Collapse the planning rail" })).toHaveCount(0);
    }
  });

  // (q) The running card's Minimise control is keyboard-operable.
  test("keyboard: the running card minimises via Enter and restores via Space", async ({ page }) => {
    await openWorkspaceFromLanding(page);
    await page.getByRole("button", { name: "Start search" }).click();
    const minimise = page.getByRole("button", { name: "Minimise" });
    await expect(minimise).toBeVisible({ timeout: 15_000 });
    await minimise.focus();
    await page.keyboard.press("Enter");
    const expand = page.getByRole("button", { name: "Expand" });
    await expect(expand).toBeVisible();
    await expand.focus();
    await page.keyboard.press("Space");
    await expect(page.getByRole("button", { name: "Minimise" })).toBeVisible();
  });

  // (r) Paused reads distinct from executing on every OTHER tab too (028
  // contract: pause salience) — a cross-tab banner appears everywhere
  // except the workspace itself (where the check-in card already is the
  // live source of truth), naming the waiting check-in explicitly. Kept as
  // its own test: the workspace-tab half of this same check lives inline in
  // the main journey above, at the check-in step. History stays open
  // while paused, so it is the tab used to leave the workspace and
  // observe the banner from elsewhere.
  test("paused run: the cross-tab banner appears on other tabs while a check-in waits", async ({ page }) => {
    await openWorkspaceFromLanding(page);
    await page.getByRole("button", { name: "Start search" }).click();
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });

    await lifecycleNav(page).getByRole("link", { name: "History", exact: true }).click();
    await expect(
      page.getByText("The analysis is paused — a check-in is waiting on you"),
    ).toBeVisible();
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
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/results$`));
    await expect(page.locator(".artefact-page")).toBeVisible();
    await expect(
      page.getByText(/Pair school food action with safer active-travel routes/),
    ).toBeVisible({ timeout: 5_000 });

    await page.getByRole("button", { name: "Ask about this analysis" }).click();
    // rev 3.4: the chat opens as a side panel BESIDE the artefact — the URL
    // stays on the results route and simply gains the chat param.
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/results\\?chat=`));
    await expect(page.getByRole("complementary", { name: "Project chat" })).toBeVisible();
    await expect(page.locator(".artefact-page")).toBeVisible();

    // Entry context renders as the removable "Report" chip (rev 2.6)
    // — scoped to the chat region since the nav also carries a "Results"
    // link.
    const chat = page.getByRole("region", { name: "Chat" });
    await expect(chat.getByRole("link", { name: "Report" })).toBeVisible();

    await page.getByPlaceholder("Ask about the evidence").fill("What does the evidence show about breakfast provision?");
    await chat.getByRole("button", { name: "Send" }).click();

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

    // Library: opens, lists the chat, rename round-trips, archive removes
    // it from the default (active) list.
    await page.getByRole("button", { name: "Chats" }).click();
    const library = page.getByRole("dialog", { name: "Chats" });
    await expect(library).toBeVisible();
    await expect(library.getByRole("button", { name: "New chat", exact: true })).toBeVisible();

    await library.getByRole("button", { name: "Rename New chat" }).click();
    await library.getByLabel("Chat title").fill("Breakfast provision");
    await library.getByLabel("Chat title").press("Enter");
    await expect(library.getByRole("button", { name: "Breakfast provision", exact: true })).toBeVisible();

    await library.getByRole("button", { name: "Archive" }).click();
    await expect(library.getByRole("button", { name: "Archive" })).toHaveCount(0);
    await expect(library.getByRole("heading", { name: "Archived" })).toBeVisible();
    await expect(library.getByRole("button", { name: "Restore" })).toBeVisible();
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
      await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/results$`));
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
  test("below the lg breakpoint, the running card is the progress surface", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await openWorkspaceFromLanding(page);
    await page.getByRole("button", { name: "Start search" }).click();
    await expect(page.getByRole("region", { name: "Analysis run" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("button", { name: "Collapse the planning rail" })).toHaveCount(0);
  });
});

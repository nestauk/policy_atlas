import { expect, test, type Page } from "@playwright/test";

import { MOCK_PROJECT_ID, mockCheckIn, mockProject } from "../src/mock/fixtures";

/**
 * End-to-end mock journey (task 025 I.1; rewritten 027 F.2 for the uplifted
 * demo surfaces). Runs against the dev server in `VITE_MOCK=1` mode (see
 * `playwright.config.ts`), so every step drives the scripted fixture project
 * + SSE narrative in `src/mock/`. The mock project starts with no run — the
 * journey begins at the plan pane and starts the analysis itself, matching
 * the "resumed session" fixture (a durable planning transcript already
 * formed a ready plan; see `src/mock/fixtures.ts`). Selectors favour
 * roles/labels/text over CSS — the same accessible surface a screen-reader
 * or keyboard user would rely on.
 */

const SUGGESTED_OPTION_LABEL = (mockCheckIn.options ?? []).find(
  (option) => option.suggested,
)?.label;
if (!SUGGESTED_OPTION_LABEL) throw new Error("fixture check-in has no suggested option");

const CITED_SOURCE_TITLE = "Universal breakfast clubs and diet quality";
const CITATION_QUOTE = "Breakfast participation increased when provision was universal.";

/** Locate the landing page's project card (the `<li>`, not just the link —
 *  the run-status chip and rename/archive controls sit beside the link, not
 *  inside it). */
function projectCard(page: Page, name: string) {
  return page.locator("li").filter({ has: page.getByRole("link", { name }) });
}

/** (a) Landing renders the mock project card, then (b) navigating into it
 *  opens the workspace. */
async function openWorkspaceFromLanding(page: Page): Promise<void> {
  await page.goto("/");
  const card = projectCard(page, mockProject.name);
  await expect(card).toBeVisible();
  await card.getByRole("link", { name: mockProject.name }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${MOCK_PROJECT_ID}`));
}

test.describe("mock evidence-base journey", () => {
  test("landing rename/archive, plan through run, evidence base, findings and sources", async ({ page }) => {
    // (a) Landing: inline rename (cancel restores the original, then a real
    // save) and the two-step archive confirm (exercised, then cancelled —
    // the project carries on into the rest of the journey below). There is
    // only one fixture project, so these interactions use page-level
    // locators directly — the card's own `<Link>` disappears while editing
    // (the form replaces it), so a locator scoped to "the li with that
    // link" stops matching mid-flow.
    await page.goto("/");
    await expect(page.getByRole("link", { name: mockProject.name })).toBeVisible();

    await page.getByRole("button", { name: "Rename project" }).click();
    await page.getByLabel("Project name").fill("A name that gets cancelled");
    await page.getByRole("button", { name: "Cancel rename" }).click();
    await expect(page.getByRole("heading", { name: mockProject.name })).toBeVisible();

    const renamedName = "Healthier childhoods in Tower Hamlets (2026 pass)";
    await page.getByRole("button", { name: "Rename project" }).click();
    await page.getByLabel("Project name").fill(renamedName);
    await page.getByRole("button", { name: "Save name" }).click();

    await page.getByRole("button", { name: "Archive project" }).click();
    await expect(page.getByRole("button", { name: "Confirm archive" })).toBeVisible();
    await expect(page.getByText("Archiving removes this project")).toBeVisible();
    await page.getByRole("button", { name: "Cancel archive" }).click();
    await expect(page.getByRole("button", { name: "Archive project" })).toBeVisible();

    // (b) Into the workspace.
    await page.getByRole("link", { name: mockProject.name }).click();
    await expect(page).toHaveURL(new RegExp(`/projects/${MOCK_PROJECT_ID}`));

    // (c) Pre-run, the workspace is a centred single-column chat (028 strand
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

    // (d) The ready plan renders as a card inline at the foot of the thread
    // — a compact disclosure: the header button carries the question + ready
    // chip, and ready-draft fields with locked-vocabulary labels (never a raw
    // enum key like "rapid") only render once expanded. Details render
    // expanded by default pre-run (owner, 2026-07-29); the toggle still works
    // both ways.
    await expect(page.getByRole("button", { name: "Toggle plan details" })).toBeVisible();
    await expect(page.getByText("10-15 minutes").first()).toBeVisible();
    await expect(page.getByText("Rapid — top sources, fast pass")).toBeVisible();
    await expect(page.getByText("Geography: United Kingdom (GB)")).toBeVisible();
    await page.getByRole("button", { name: "Toggle plan details" }).click();
    await expect(page.getByText("Rapid — top sources, fast pass")).not.toBeVisible();
    await page.getByRole("button", { name: "Toggle plan details" }).click();
    await expect(page.getByText("Rapid — top sources, fast pass")).toBeVisible();

    // (e) Start the analysis — the two-pane layout (chat + collapsible rail
    // on the left, journey on the right) appears for the first time. The
    // mock races through every pre-synthesise stage with no artificial
    // delay, straight to the paused check-in (see step (f)) — so "Analysing
    // the evidence…" is never reliably observable as its own state here; the
    // timeline and the settled paused heading below are the robust checks.
    await page.getByRole("button", { name: "Start the analysis" }).click();
    const timeline = page.getByRole("list", { name: "Stage timeline" });
    await expect(timeline.getByText("Finding relevant sources")).toBeVisible({ timeout: 15_000 });
    await expect(timeline.getByText("Synthesising the evidence")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Sources found")).toBeVisible();
    await expect(page.getByText(/screened out — kept in the sources table/)).toBeVisible();
    await expect(page.getByText("Where I looked")).toBeVisible();
    await expect(page.getByText("OpenAlex · academic research")).toBeVisible();

    // (f) The check-in card appears; the run genuinely parks here. Paused
    // reads distinct from executing on this tab (028 contract: pause
    // salience) — the journey heading and its status banner both change;
    // the cross-tab variant of this same check is its own test below.
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(mockCheckIn.render)).toBeVisible();
    const journeyPane = page.getByRole("region", { name: "Analysis progress" });
    await expect(journeyPane.getByRole("heading", { name: "Paused — waiting on you" })).toBeVisible();
    await expect(journeyPane.getByText("Paused at a check-in")).toBeVisible();

    // Answering the suggested option collapses the card to the "Answered" echo.
    const suggestedButton = page.getByRole("button", { name: SUGGESTED_OPTION_LABEL });
    await expect(suggestedButton).toBeVisible();
    await suggestedButton.click();
    await expect(page.getByText("Waiting on your input")).toHaveCount(0);
    await expect(page.getByText("Answered")).toBeVisible();

    // (g) Evidence base: A4 frame, the live artefact streaming states
    // (skeleton -> writing -> filled) from the scripted fixture, then the
    // citation claim popover and the source dossier ladder. The run has
    // reached "succeeded" by now, so the completion card's own "Read the
    // evidence base" link is also on the page — `exact` keeps this on the
    // nav tab (Playwright's default name match is a case-insensitive
    // substring, which "Read the evidence base" also satisfies).
    await page.getByRole("link", { name: "Evidence base", exact: true }).click();
    await expect(page.locator(".artefact-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: "What appears to help" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Implications for local action" })).toBeVisible();
    await expect(page.getByText("Writing this section now…")).toBeVisible();
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
    await themePanel.getByRole("link", { name: "See the findings in this theme" }).click();
    await expect(page).toHaveURL(/findings\?facet=.*group=/);
    await page.goBack();

    // (h) Findings: kind filter chips are server-side and URL-addressable;
    // an IOF row expands to "Reported numbers", an ICF row to "Context
    // detail".
    await page.getByRole("link", { name: "Findings" }).click();
    const kindFilter = page.getByRole("group", { name: "Finding kind" });
    await kindFilter.getByRole("button", { name: "Intervention–outcome" }).click();
    await expect(page).toHaveURL(/[?&]profile=iof/);
    await page.getByRole("button", { name: /Expand finding: Universal breakfast provision/ }).click();
    await expect(page.getByRole("heading", { name: "Reported numbers" })).toBeVisible();

    await kindFilter.getByRole("button", { name: "Implementation context" }).click();
    await expect(page).toHaveURL(/[?&]profile=icf/);
    await page.getByRole("button", { name: /Expand finding: Active-travel offers/ }).click();
    await expect(page.getByRole("heading", { name: "Context detail" })).toBeVisible();

    // (i) Sources: a server-side status filter changes the URL and the
    // collection-true shown count. `exact` again keeps this on the nav tab,
    // not the completion card's "All sources" link (same substring-match
    // ambiguity as "Evidence base" above).
    await page.getByRole("link", { name: "Sources", exact: true }).click();
    const sourceRows = page.getByRole("row");
    await expect(sourceRows.first()).toBeVisible();
    // Default view = All, sorted on the relevance spectrum.
    await expect(sourceRows).toHaveCount(10);
    // The retracted verdict lives in the Relevant column's hover button.
    await expect(
      page.getByRole("button", { name: "Excluded — retracted: screening details" }),
    ).toBeVisible();

    const sourceFilters = page.getByRole("group", { name: "Filter sources" });
    await sourceFilters.getByRole("button", { name: "Screened out" }).click();
    await expect(page).toHaveURL(/[?&]status=screened_out/);
    await expect(sourceRows).toHaveCount(2);

    // (j) An unknown route renders the honest "nothing here" view.
    await page.goto("/this-route-does-not-exist");
    await expect(page.getByRole("heading", { name: "This project is unavailable" })).toBeVisible();
  });

  // (k) Keyboard check: Tab to a citation marker and open it with Enter.
  // The evidence-base artefact is served statically in mock mode (no run
  // gating), so this is exercised as an isolated, direct-navigation check
  // rather than re-running the whole journey.
  test("keyboard: tab to a citation marker and open it with Enter", async ({ page }) => {
    await page.goto(`/projects/${MOCK_PROJECT_ID}/evidence-base`);
    await expect(
      page.getByRole("heading", { name: "Policy options for healthier childhoods" }),
    ).toBeVisible();

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

  // (l) `prefers-reduced-motion` emulation runs the workspace — through
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
    await expect(page.getByRole("button", { name: "Start the analysis" })).toBeVisible();
    await page.getByRole("button", { name: "Start the analysis" }).click();
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });

    expect(pageErrors).toEqual([]);
  });

  // (m) At 1280 and 768 widths, no horizontal body scroll — checked on the
  // landing view, the pre-run centred single-column workspace, and the
  // two-pane workspace once a run exists (the widest layout in the app —
  // the rail appears only from this point on, so it is never assumed
  // pre-run).
  test("responsive: no horizontal overflow at 1280 and 768 widths", async ({ page }) => {
    for (const width of [1280, 768]) {
      await page.setViewportSize({ width, height: 900 });

      await page.goto("/");
      await expect(page.getByRole("link", { name: mockProject.name })).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);

      await openWorkspaceFromLanding(page);
      // Pre-run: centred single-column chat, no rail.
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);

      // Start a run to reach the two-pane layout the rail lives in. The mock
      // races through every stage with no delay, so wait on the rail control
      // itself rather than a transient run-status heading.
      await page.getByRole("button", { name: "Start the analysis" }).click();
      await expect(page.getByRole("button", { name: "Collapse the planning rail" })).toBeVisible({ timeout: 15_000 });
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);

      // Same check with the planning rail collapsed — the other rail state.
      await page.getByRole("button", { name: "Collapse the planning rail" }).click();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
      await page.getByRole("button", { name: "Expand the planning rail" }).click();
    }
  });

  // (n) The rail collapse control is keyboard-operable: focus, activate with
  // Enter, re-activate with Space — state follows each activation. The rail
  // only exists once a run has started (pre-run is a single-column chat with
  // no rail at all), so this drives the flow to a started run first.
  test("keyboard: the rail collapse control toggles via Enter and Space", async ({ page }) => {
    await openWorkspaceFromLanding(page);
    await page.getByRole("button", { name: "Start the analysis" }).click();
    const collapse = page.getByRole("button", { name: "Collapse the planning rail" });
    await expect(collapse).toBeVisible({ timeout: 15_000 });
    await collapse.focus();
    await page.keyboard.press("Enter");
    const expand = page.getByRole("button", { name: "Expand the planning rail" });
    await expect(expand).toBeVisible();
    await expand.focus();
    await page.keyboard.press("Space");
    await expect(page.getByRole("button", { name: "Collapse the planning rail" })).toBeVisible();
  });

  // (o) Paused reads distinct from executing on every OTHER tab too (028
  // contract: pause salience) — a cross-tab banner appears everywhere
  // except the workspace itself (where the check-in card already is the
  // live source of truth), naming the waiting check-in explicitly. Kept as
  // its own test: the workspace-tab half of this same check lives inline in
  // the main journey above, at the check-in step.
  test("paused run: the cross-tab banner appears on other tabs while a check-in waits", async ({ page }) => {
    await openWorkspaceFromLanding(page);
    await page.getByRole("button", { name: "Start the analysis" }).click();
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });

    await page.getByRole("link", { name: "Sources" }).click();
    await expect(
      page.getByText("The analysis is paused — a check-in is waiting on you"),
    ).toBeVisible();
  });
});

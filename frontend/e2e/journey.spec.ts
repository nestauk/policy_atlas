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

    // (c) Plan pane: a compact disclosure card — the header button carries
    // the question + ready chip, and ready-draft fields with locked-
    // vocabulary labels (never a raw enum key like "rapid") only render once
    // expanded. `<PaneHeading>` is a styled div, not a heading element — the
    // pane's accessible name comes from its `<section aria-label="Plan">`,
    // which the "region" landmark role picks up.
    await expect(page.getByRole("region", { name: "Plan", exact: true })).toBeVisible();
    await expect(page.getByText("10-15 minutes").first()).toBeVisible();
    await page.getByRole("button", { name: "Toggle plan details" }).click();
    await expect(page.getByText("Rapid — top sources, fast pass")).toBeVisible();
    await expect(page.getByText("Geography: United Kingdom (GB)")).toBeVisible();

    // (d) Rail collapse via keyboard-operable button (planning conversation,
    // left rail). Re-expand afterwards — check-ins now render inside this
    // rail (owner feedback), so it needs to be open for step (f) below.
    await page.getByRole("button", { name: "Collapse the planning rail" }).click();
    const expandRail = page.getByRole("button", { name: "Expand the planning rail" });
    await expect(expandRail).toBeVisible();
    await expandRail.click();
    await expect(page.getByRole("button", { name: "Collapse the planning rail" })).toBeVisible();

    // (e) Start the analysis — the journey pane takes over the right column.
    await page.getByRole("button", { name: "Start the analysis" }).click();
    await expect(page.getByRole("heading", { name: "Analysing the evidence…" })).toBeVisible({ timeout: 15_000 });
    // The timeline list itself lost its "Stage timeline" accessible name in
    // the phase-E rewrite (flagged for the lead in fe-api-smoke.spec.ts) —
    // scope by the section id instead.
    const timeline = page.locator("#journey-timeline");
    await expect(timeline.getByText("Finding relevant sources")).toBeVisible({ timeout: 15_000 });
    await expect(timeline.getByText("Synthesising the evidence")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Sources found")).toBeVisible();
    await expect(page.getByText(/screened out — kept in the sources table/)).toBeVisible();
    await expect(page.getByText("Where I looked")).toBeVisible();
    await expect(page.getByText("OpenAlex · academic research")).toBeVisible();

    // (f) The check-in card appears; answering the suggested option
    // collapses it to the "Answered" echo.
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(mockCheckIn.render)).toBeVisible();
    const suggestedButton = page.getByRole("button", { name: SUGGESTED_OPTION_LABEL });
    await expect(suggestedButton).toBeVisible();
    await suggestedButton.click();
    await expect(page.getByText("Waiting on your input")).toHaveCount(0);
    await expect(page.getByText("Answered")).toBeVisible();

    // (g) Evidence base: A4 frame, the live artefact streaming states
    // (skeleton -> writing -> filled) from the scripted fixture, then the
    // citation claim popover and the source dossier ladder.
    await page.getByRole("link", { name: "Evidence base" }).click();
    await expect(page.locator(".artefact-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: "What appears to help" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Implications for local action" })).toBeVisible();
    await expect(page.getByText("Writing this section now…")).toBeVisible();
    await expect(
      page.getByText(/Pair school food action with safer active-travel routes/),
    ).toBeVisible({ timeout: 5_000 });

    const marker = page.getByRole("button", { name: /^Citation 1:/ });
    await expect(marker).toBeVisible();
    await marker.click();
    await expect(page.getByText(CITATION_QUOTE)).toBeVisible();
    await page.getByRole("button", { name: "Open the source dossier" }).click();
    await expect(page).toHaveURL(/[?&]source=/);
    await expect(page.getByRole("dialog", { name: CITED_SOURCE_TITLE })).toBeVisible();
    await page.getByRole("button", { name: "Close panel" }).click();
    await expect(page).not.toHaveURL(/[?&]source=/);

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
    // collection-true shown count.
    await page.getByRole("link", { name: "Sources" }).click();
    const sourceRows = page.getByRole("row");
    await expect(sourceRows.first()).toBeVisible();
    await expect(sourceRows).toHaveCount(10);
    await expect(page.getByText("Excluded — retracted", { exact: true })).toBeVisible();

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
    await expect(page.getByText(CITATION_QUOTE)).toBeVisible();
  });

  // (l) `prefers-reduced-motion` emulation runs the workspace — through
  // starting a run and reaching the pending check-in — without console errors.
  test("prefers-reduced-motion: the workspace runs cleanly with no console errors", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const pageErrors: unknown[] = [];
    page.on("pageerror", (error) => pageErrors.push(error));

    await openWorkspaceFromLanding(page);
    await expect(page.getByRole("region", { name: "Plan", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Start the analysis" }).click();
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });

    expect(pageErrors).toEqual([]);
  });

  // (m) At 1280 and 768 widths, no horizontal body scroll — checked on the
  // landing view and the two-pane workspace (the widest layout in the app).
  test("responsive: no horizontal overflow at 1280 and 768 widths", async ({ page }) => {
    for (const width of [1280, 768]) {
      await page.setViewportSize({ width, height: 900 });

      await page.goto("/");
      await expect(page.getByRole("link", { name: mockProject.name })).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);

      await openWorkspaceFromLanding(page);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
    }
  });
});

import { expect, test, type Page } from "@playwright/test";

import { MOCK_PROJECT_ID, mockCheckIn, mockProject } from "../src/mock/fixtures";

/**
 * End-to-end mock journey (task 025 I.1). Runs against the dev server in
 * `VITE_MOCK=1` mode (see `playwright.config.ts`), so every step drives the
 * scripted fixture project + SSE narrative in `src/mock/`. Selectors favour
 * roles/labels/text over CSS — the same accessible surface a screen-reader
 * or keyboard user would rely on.
 */

const SUGGESTED_OPTION_LABEL = (mockCheckIn.options ?? []).find(
  (option) => option.suggested,
)?.label;
if (!SUGGESTED_OPTION_LABEL) throw new Error("fixture check-in has no suggested option");

const CITED_SOURCE_TITLE = "Universal breakfast clubs and diet quality";
const CITATION_QUOTE = "Breakfast participation increased when provision was universal.";

/** (a) Landing renders the mock project card with its status chip, then
 *  (b) navigating into it opens the workspace. */
async function openWorkspaceFromLanding(page: Page): Promise<void> {
  await page.goto("/");
  const card = page.getByRole("link", { name: new RegExp(mockProject.name) });
  await expect(card).toBeVisible();
  await expect(card.getByText(/Analysing the evidence/)).toBeVisible();
  await card.click();
  await expect(page).toHaveURL(new RegExp(`/projects/${MOCK_PROJECT_ID}`));
}

test.describe("mock evidence-base journey", () => {
  test("landing through the run, evidence base, sources and landscape", async ({ page }) => {
    // (a) + (b)
    await openWorkspaceFromLanding(page);

    // (c) the run pane shows stage timeline entries from the scripted
    // stream, reaching the pending check-in card.
    const timeline = page.getByRole("list", { name: "Stage timeline" });
    await expect(timeline.getByText("Finding relevant sources")).toBeVisible({ timeout: 15_000 });
    await expect(timeline.getByText("Synthesising the evidence")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Waiting on your input")).toBeVisible();
    await expect(page.getByText(mockCheckIn.render)).toBeVisible();

    // (d) answer the check-in with the suggested option — the card resolves
    // and the run completes.
    const suggestedButton = page.getByRole("button", { name: SUGGESTED_OPTION_LABEL });
    await expect(suggestedButton).toBeVisible();
    await suggestedButton.click();
    await expect(page.getByText("Waiting on your input")).toHaveCount(0);
    await expect(page.getByText("The analysis is complete.")).toBeVisible({ timeout: 15_000 });

    // (e) open the Evidence base view — sections render with citation
    // markers; click a citation marker → the popover shows the quote.
    await page.getByRole("link", { name: "Evidence base" }).click();
    await expect(
      page.getByRole("heading", { name: "Policy options for healthier childhoods" }),
    ).toBeVisible();
    const marker = page.getByRole("button", { name: /^Citation 1:/ });
    await expect(marker).toBeVisible();
    await marker.click();
    await expect(page.getByText(CITATION_QUOTE)).toBeVisible();

    // (f) open the source dossier via the popover — the sheet opens and the
    // URL carries ?source=.
    await page.getByRole("button", { name: "Open the source dossier" }).click();
    await expect(page).toHaveURL(/[?&]source=/);
    await expect(page.getByRole("dialog", { name: CITED_SOURCE_TITLE })).toBeVisible();
    await page.getByRole("button", { name: "Close panel" }).click();
    await expect(page).not.toHaveURL(/[?&]source=/);

    // (g) Sources view lists rows with status chips.
    await page.getByRole("link", { name: "Sources" }).click();
    const sourceRows = page.getByRole("list").locator("li");
    await expect(sourceRows.first()).toBeVisible();
    await expect(sourceRows).toHaveCount(9);
    await expect(page.getByText("screened out", { exact: true }).first()).toBeVisible();

    // (h) Landscape renders at least one chart.
    await page.getByRole("link", { name: "Landscape" }).click();
    await expect(page.locator(".recharts-wrapper svg").first()).toBeVisible({ timeout: 10_000 });
  });

  // (i) Keyboard check: Tab to a citation marker and open it with Enter.
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

  // (j) `prefers-reduced-motion` emulation runs the journey start (a) to (c)
  // without errors.
  test("prefers-reduced-motion: landing through the pending check-in runs cleanly", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const pageErrors: unknown[] = [];
    page.on("pageerror", (error) => pageErrors.push(error));

    await openWorkspaceFromLanding(page);
    await expect(page.getByText("Waiting on your input")).toBeVisible({ timeout: 15_000 });

    expect(pageErrors).toEqual([]);
  });

  // (k) At 1280 and 768 widths, no horizontal body scroll — checked on the
  // landing view and the two-pane workspace (the widest layout in the app).
  test("responsive: no horizontal overflow at 1280 and 768 widths", async ({ page }) => {
    for (const width of [1280, 768]) {
      await page.setViewportSize({ width, height: 900 });

      await page.goto("/");
      await expect(page.getByRole("link", { name: new RegExp(mockProject.name) })).toBeVisible();
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

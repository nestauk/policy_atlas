import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { MOCK_SIGNED_OUT_KEY } from "../src/mock/api";
import { MOCK_TASK_ID, mockCheckIn, mockTask } from "../src/mock/fixtures";

/**
 * Automated accessibility checks (task 067): axe-core against the landing
 * page and the report view, for the WCAG 2.0, 2.1 and 2.2 level A and AA
 * rules. Runs in mock mode with the journey suite.
 *
 * axe finds only what a rule engine can decide from the rendered page: a
 * missing name, a wrong role, a contrast ratio. It finds a minority of real
 * problems. It does not test keyboard order, focus movement, what a screen
 * reader says, zoom, reflow or forced colours: the manual list in
 * docs/tasks/067-accessibility is still needed.
 */
const WCAG_A_AND_AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

/** The violations axe finds on the page, reduced to what a failure message needs. */
async function violations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_A_AND_AA).analyze();
  // The run is real: rules were applied and some passed.
  expect(results.passes.length).toBeGreaterThan(0);
  return results.violations.map((violation) => ({
    rule: violation.id,
    impact: violation.impact,
    help: violation.help,
    where: violation.nodes.map((node) => node.target.join(" ")),
  }));
}

const SUGGESTED_OPTION_LABEL = (mockCheckIn.options ?? []).find((option) => option.suggested)?.label;
if (!SUGGESTED_OPTION_LABEL) throw new Error("fixture check-in has no suggested option");

test.describe("accessibility (axe, WCAG 2.2 A and AA)", () => {
  test("the landing page", async ({ page }) => {
    // The mock session starts signed in unless this flag is set first.
    await page.addInitScript((key) => sessionStorage.setItem(key, "1"), MOCK_SIGNED_OUT_KEY);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "Create policy plans you can trust" })).toBeVisible();
    // Open the request form's errors too, so their markup is checked.
    await page.getByRole("button", { name: "Submit" }).click();
    await expect(page.getByLabel("Email")).toBeFocused();

    expect(await violations(page)).toEqual([]);
  });

  test("the report view", async ({ page }) => {
    test.setTimeout(90_000);
    await page.goto("/");
    await page.getByRole("link", { name: mockTask.name }).click();
    await page.getByRole("button", { name: "Start the search" }).click();
    await page.getByRole("radio", { name: new RegExp(`^${SUGGESTED_OPTION_LABEL}`) }).click({ timeout: 15_000 });
    await page
      .getByRole("region", { name: "Analysis run" })
      .getByRole("link", { name: "Read it →" })
      .click({ timeout: 40_000 });
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}/result$`));
    await expect(page.getByRole("heading", { level: 1, name: mockTask.question ?? "" })).toBeVisible();
    // The committed report, not the live one: its download control is there.
    await expect(page.getByRole("button", { name: /Download/ }).first()).toBeVisible({ timeout: 15_000 });

    expect(await violations(page)).toEqual([]);
  });
});

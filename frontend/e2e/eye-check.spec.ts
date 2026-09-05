import { expect, test } from "@playwright/test";

import { MOCK_TASK_ID, mockTask } from "../src/mock/fixtures";

/**
 * The 028 eye-check, made mechanical where it can be.
 *
 * Task 028 shipped ink-on-blue primary buttons because an unregistered
 * `text-*` token was classified as a text COLOUR and silently dropped
 * `text-white`. Typecheck, lint, 185 tests and the mock e2e were all green.
 * The only thing that caught it was a person looking at the screen.
 *
 * `typeScale.test.ts` guards the token/registration sync — the cause. These
 * tests check the *effect* in a real rendered page: computed colour on a
 * primary button, and no rendered sentence below the 16px floor. They do not
 * replace looking at it (whether each surface landed on the right rung is
 * still a judgement), but they make the specific 028 failure impossible to
 * ship silently again.
 */

/** Parse `rgb(r, g, b)` into its three channels. */
function channels(color: string): [number, number, number] {
  const match = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(color);
  if (match === null) throw new Error(`unparseable colour: ${color}`);
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

test.describe("type scale, checked on the rendered page", () => {
  test("a primary button renders white text on blue — the 028 failure", async ({ page }) => {
    await page.goto("/");
    const primary = page.getByRole("main").getByRole("link", { name: "New task" });
    await expect(primary).toBeVisible();

    const style = await primary.evaluate((node) => {
      const computed = getComputedStyle(node);
      return { color: computed.color, background: computed.backgroundColor };
    });

    const [r, g, b] = channels(style.color);
    expect(
      r > 240 && g > 240 && b > 240,
      `primary button text should be white, got ${style.color}`,
    ).toBe(true);

    const [br, bg, bb] = channels(style.background);
    expect(
      bb > 200 && br < 60 && bg < 60,
      `primary button background should be Nesta blue, got ${style.background}`,
    ).toBe(true);
  });

  test("no sentence renders below the 16px floor", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: mockTask.name }).click();
    await expect(page).toHaveURL(new RegExp(`/tasks/${MOCK_TASK_ID}`));

    // A "sentence" heuristic that will not fight the design: a leaf element
    // whose own text is long enough and contains a space run typical of
    // prose. Labels, chips, counts and timestamps are short, so they stay
    // out of the sample — which is exactly the caption/body distinction the
    // mapping draws.
    const undersized = await page.evaluate(() => {
      const offenders: { text: string; size: string }[] = [];
      for (const node of Array.from(document.querySelectorAll("p, li, dd, td"))) {
        if (node.querySelector("p, li, dd, td") !== null) continue;
        // Caption is the fine-print rung (footer disclaimer, chips). The
        // 16px floor is for body prose, not chrome.
        if (node.closest("footer") !== null) continue;
        const text = (node.textContent ?? "").trim();
        // Prose, not a label: long, and more than a handful of words.
        if (text.length < 60 || text.split(/\s+/).length < 10) continue;
        const size = Number.parseFloat(getComputedStyle(node).fontSize);
        if (size < 16) offenders.push({ text: text.slice(0, 80), size: `${size}px` });
      }
      return offenders;
    });

    expect(
      undersized,
      `these read as sentences but render below 16px:\n${JSON.stringify(undersized, null, 2)}`,
    ).toEqual([]);
  });
});

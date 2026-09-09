import { expect, test } from "@playwright/test";

import { mockProject, mockTask } from "../src/mock/fixtures";

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
  test("the scoping task's Result shows the baseline under its band", async ({ page }) => {
    await page.goto("/new");
    await page.getByRole("button", { name: "Options scoping" }).click();
    await page
      .getByLabel("Your question")
      .fill("How can we reduce the number of young people not in education, employment or training?");
    await page.getByRole("button", { name: "Prepare plan" }).click();
    await expect(page.getByRole("region", { name: "Task Agent conversation" })).toBeVisible();

    await page.getByRole("link", { name: "Result" }).first().click();

    await expect(
      page.getByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Baseline · the situation these options would change · ready · awaiting your confirmation",
      ),
    ).toBeVisible();
    await expect(page.getByText("scoping pass")).toBeVisible();
    // A baseline has no Key findings and no Executive summary / Full report
    // parts framing it.
    await expect(page.getByRole("heading", { name: "Executive summary" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Sources", exact: true }).first()).toBeVisible();
  });
});

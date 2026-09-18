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
  test("the scoping task's Result shows the baseline, headed Baseline", async ({ page }) => {
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
  async function startScopingWalk(page: import("@playwright/test").Page) {
    await page.goto("/new");
    await page.getByRole("button", { name: "Options scoping" }).click();
    await page
      .getByLabel("Your question")
      .fill("How can we reduce the number of young people not in education, employment or training?");
    await page.getByRole("button", { name: "Prepare plan" }).click();
    await expect(page.getByRole("region", { name: "Task Agent conversation" })).toBeVisible();

    await page.getByRole("button", { name: "Review the plan" }).click();
    const plan = page.getByRole("dialog", { name: "Scoping plan" });
    await plan.getByRole("button", { name: "Confirm and build baseline" }).click();
    await plan.getByRole("button", { name: "Close the scoping plan" }).click();
  }

  test("the gate card sits in the thread and the composer takes a question about the baseline", async ({
    page,
  }) => {
    await startScopingWalk(page);

    const thread = page.getByRole("region", { name: "Task Agent conversation" });
    await expect(
      thread.getByRole("heading", { name: "Confirm the plan against the baseline" }),
    ).toBeVisible();
    await expect(
      thread.getByText("Careers advice reaches the young people already in school"),
    ).toBeVisible();
    await expect(thread.getByRole("button", { name: "Confirm plan and build longlist" })).toBeVisible();
    await expect(thread.getByRole("button", { name: "Change the plan" })).toBeVisible();

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
    await thread.getByRole("button", { name: "Change the plan" }).click();

    await expect(thread.getByText("recorded")).toBeVisible();

    await page.getByRole("button", { name: "Review the plan" }).click();
    const plan = page.getByRole("dialog", { name: "Scoping plan" });
    await expect(plan.getByRole("button", { name: "Rebuild baseline" })).toBeVisible();
    await expect(plan.getByRole("button", { name: "Confirm plan and build longlist" })).toBeVisible();
  });
});

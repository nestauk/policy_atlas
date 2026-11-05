import { expect, test } from "@playwright/test";

/**
 * The deliberately thin real-HTTP counterpart to journey.spec.ts. The smoke
 * runner builds the SPA with a short-lived dev-issuer token and starts the
 * real API in stub mode; this file consequently must stay out of the mock
 * Playwright configuration.
 */

let taskId = "";

test.describe.serial("@fe-api-smoke built frontend against real API", () => {
  test("renders the authenticated real task-list response", async ({ page }) => {
    const loadedTasks = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/v1/tasks" &&
        response.request().method() === "GET" &&
        response.status() === 200,
    );

    await page.goto("/");
    await loadedTasks;

    // S4: a first-time account has no active or archived tasks, so `/`
    // redirects to `/new`. The GET 200 above is still the wiring check.
    await expect(page).toHaveURL(/\/new$/);
    await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Evidence search" })).toBeVisible();
  });

  test("creates a task through the real authenticated POST", async ({ page }) => {
    await page.goto("/new");
    await page.getByRole("button", { name: "Evidence search" }).click();
    await page.getByLabel("Your question").fill("FE API smoke task");

    const created = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/v1/tasks" &&
        response.request().method() === "POST" &&
        response.status() === 201,
    );
    await page.getByRole("button", { name: "Start" }).click();
    await created;

    await expect(page).toHaveURL(/\/tasks\/[^/]+$/);
    taskId = new URL(page.url()).pathname.split("/").at(-1) ?? "";
  });

  test("starts a stub run and renders progress from the real SSE tail", async ({ page }) => {
    if (!taskId) throw new Error("real-API task creation did not supply a task id");

    await page.goto(`/tasks/${taskId}`);
    await page.getByLabel("Message the Task Agent").fill("Map school-meal evidence.");
    await page.getByRole("button", { name: "Send" }).click();
    await page.getByLabel("Message the Task Agent").fill("landscape only");
    await page.getByRole("button", { name: "Send" }).click();
    await page.getByRole("button", { name: "Start the search" }).click();

    // "Searching" is the acquire stage — the one component every stub plan
    // starts with. Labels come from the plan-panel vocabulary, not SSE copy.
    // (Never assert discretionary stages such as "Mapping"/characterise: the
    // agent may omit them.)
    // The run trace (task 058) lists every step once its header is opened,
    // live or ended, so this assertion has no race against the stub's
    // near-instant execution.
    await page.getByRole("region", { name: "Analysis run" }).getByRole("button").first().click({ timeout: 30_000 });
    await expect(page.getByRole("list", { name: "Run steps" }).getByText("Searching").first()).toBeVisible({
      timeout: 30_000,
    });
  });
});

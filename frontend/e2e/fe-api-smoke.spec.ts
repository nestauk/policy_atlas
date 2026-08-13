import { expect, test } from "@playwright/test";

/**
 * The deliberately thin real-HTTP counterpart to journey.spec.ts. The smoke
 * runner builds the SPA with a short-lived dev-issuer token and starts the
 * real API in stub mode; this file consequently must stay out of the mock
 * Playwright configuration.
 */

let projectId = "";

test.describe.serial("@fe-api-smoke built frontend against real API", () => {
  test("renders the authenticated real project-list response", async ({ page }) => {
    const loadedProjects = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/v1/projects" &&
        response.request().method() === "GET" &&
        response.status() === 200,
    );

    await page.goto("/");
    await loadedProjects;

    await expect(page.getByRole("heading", { name: "No projects yet" })).toBeVisible();
  });

  test("creates a project through the real authenticated POST", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "New project" }).first().click();
    await page.getByLabel("Project name").fill("FE API smoke project");

    const created = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/v1/projects" &&
        response.request().method() === "POST" &&
        response.status() === 201,
    );
    await page.getByRole("button", { name: "Create project" }).click();
    await created;

    await expect(page).toHaveURL(/\/projects\/[^/]+$/);
    projectId = new URL(page.url()).pathname.split("/").at(-1) ?? "";
  });

  test("starts a stub run and renders progress from the real SSE tail", async ({ page }) => {
    if (!projectId) throw new Error("real-API project creation did not supply a project id");

    await page.goto(`/projects/${projectId}`);
    await page.getByLabel("Message the planner").fill("Map school-meal evidence.");
    await page.getByRole("button", { name: "Send" }).click();
    await page.getByLabel("Message the planner").fill("landscape only");
    await page.getByRole("button", { name: "Send" }).click();
    await page.getByRole("button", { name: "Start the analysis" }).click();

    // "Searching sources" is the acquire stage — the one component every
    // stub plan starts with. (Never assert discretionary stages such as
    // "Mapping the landscape"/characterise: the orchestrator may omit them.)
    // The timeline entry persists after the component completes, so this
    // assertion has no race against the stub's near-instant execution.
    // `.first()` because depth-graded search reruns acquire once per round and
    // the timeline renders a row per stage event — stub mode acquires nothing,
    // so it always runs to the round cap and emits 2+ identical rows. Asserting
    // without `.first()` is a strict-mode violation whose element count tracks
    // the round count (build finding, 2026-08-10). Presence is all this smoke
    // claims; how repeated stages should read is a UX question, not a test one.
    await expect(
      page.getByRole("list", { name: "Stage timeline" }).getByText("Searching sources").first(),
    ).toBeVisible({ timeout: 30_000 });
  });
});

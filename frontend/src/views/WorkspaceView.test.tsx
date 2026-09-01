import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceView } from "./WorkspaceView";

/**
 * The URL leg (task 033 phase 10c, contract § 11 / rubric 37): the Plan
 * route (`/projects/:projectId`) is never wrapped in `LifecycleRoute` — it's
 * open at every run state — so `is_owner` reaching its children is the ONLY
 * defence against a non-owner reaching a mutation surface by address. This
 * mocks `PlanningPane` and `PlanDocument` (both independently, thoroughly
 * covered for their own read-only rendering in `PlanningPane.test.tsx` and
 * the existing `PlanDocument.test.tsx`) to a prop echo, so this test proves
 * only the wiring: navigating here does not redirect, and `WorkspaceView`
 * threads ownership into both.
 */
const projectState = vi.hoisted(() => ({ isOwner: true }));

vi.mock("../api/queries", () => ({
  useProject: () => ({
    data: {
      project_id: "11111111-1111-1111-1111-111111111111",
      name: "Acme project",
      is_owner: projectState.isOwner,
      latest_run: null,
    },
    isError: false,
    error: null,
  }),
}));
vi.mock("../store", () => ({
  useRunStream: () => ({ run: null, stages: [], pendingCheckIn: null, decisions: [], plan: null }),
}));
vi.mock("./workspace/PlanningPane", () => ({
  PlanningPane: ({ isOwner, onReviewPlan }: { isOwner: boolean; onReviewPlan?: () => void }) => (
    <div>
      <span data-testid="planning-pane-is-owner">{String(isOwner)}</span>
      <button type="button" onClick={onReviewPlan}>
        Open plan (test)
      </button>
    </div>
  ),
}));
vi.mock("./workspace/PlanDocument", () => ({
  PlanDocument: ({ readOnly }: { readOnly?: boolean }) => (
    <div data-testid="plan-document-read-only">{String(readOnly ?? false)}</div>
  ),
}));

function renderAtPlanRoute() {
  return render(
    <MemoryRouter initialEntries={["/projects/11111111-1111-1111-1111-111111111111"]}>
      <Routes>
        <Route path="/projects/:projectId" element={<WorkspaceView />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("WorkspaceView — the URL leg (task 033 phase 10c, contract § 11 / rubric 37)", () => {
  it("owner: reaches the Plan route with the mutation surface live, no redirect", () => {
    projectState.isOwner = true;
    renderAtPlanRoute();
    expect(screen.getByTestId("planning-pane-is-owner")).toHaveTextContent("true");
  });

  it("non-owner: reaches the SAME route by address (not redirected) with the read-only variant", async () => {
    projectState.isOwner = false;
    const user = userEvent.setup();
    renderAtPlanRoute();
    // Reachable, not bounced to an error page or elsewhere — `LifecycleRoute`
    // never wraps this route, so a redirect here would have to come from
    // WorkspaceView itself, and it doesn't.
    expect(screen.getByTestId("planning-pane-is-owner")).toHaveTextContent("false");

    // The plan document opened from here (PlanCard's "Review the plan",
    // read action) must render its already-tested read-only variant too.
    await user.click(screen.getByRole("button", { name: "Open plan (test)" }));
    expect(screen.getByTestId("plan-document-read-only")).toHaveTextContent("true");
  });
});

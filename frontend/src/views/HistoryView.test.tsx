import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { HistoryView } from "./HistoryView";

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

vi.mock("../api/queries", () => ({
  useProject: vi.fn(),
  useDecisions: vi.fn(),
  usePlanningTurns: vi.fn(),
}));

function renderHistory() {
  return render(
    <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/history`]}>
      <Routes>
        <Route path="/projects/:projectId/history" element={<HistoryView />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("HistoryView — readable with the Task, not scoped to the caller (task 033 phase 10b, rubric 39)", () => {
  it("renders decisions and planning turns for a caller who does not own the Task", () => {
    // The contract struck rev 2.0's "scopes to the caller": any caller who
    // can read the project sees its decisions and planning turns, not just
    // its owner. This is a verification test, not a behaviour change — no
    // frontend-side owner gate exists here to remove.
    vi.mocked(queries.useProject).mockReturnValue(
      { data: { project_id: PROJECT_ID, name: "A colleague's task", is_owner: false } } as unknown as ReturnType<
        typeof queries.useProject
      >,
    );
    vi.mocked(queries.useDecisions).mockReturnValue(
      {
        data: {
          data: [
            {
              sequence: 1,
              occurred_at: "2026-07-21T09:31:10Z",
              kind: "plan.approved",
              summary: "The plan was approved.",
              decided_by: "user",
              detail: null,
            },
          ],
        },
        isPending: false,
        isError: false,
      } as unknown as ReturnType<typeof queries.useDecisions>,
    );
    vi.mocked(queries.usePlanningTurns).mockReturnValue(
      { data: { data: [] }, isPending: false, isError: false } as unknown as ReturnType<
        typeof queries.usePlanningTurns
      >,
    );

    renderHistory();

    expect(screen.getByText("The plan was approved.")).toBeInTheDocument();
    expect(screen.queryByText(/couldn't be loaded/)).not.toBeInTheDocument();
  });
});

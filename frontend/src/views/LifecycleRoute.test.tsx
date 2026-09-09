import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { LifecycleRoute, RedirectToPath } from "./LifecycleRoute";

vi.mock("../api/queries", () => ({ useTask: vi.fn() }));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="path">{location.pathname}</div>;
}

function mockTask(status: string | null, { pending = false } = {}) {
  vi.mocked(queries.useTask).mockReturnValue({
    isPending: pending,
    data: pending
      ? undefined
      : {
          task_id: TASK_ID,
          latest_run: status === null ? null : { status },
        },
  } as unknown as ReturnType<typeof queries.useTask>);
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocationProbe />
      <Routes>
        <Route path="/tasks/:taskId" element={<div>Plan page</div>} />
        <Route
          path="/tasks/:taskId/results"
          element={
            <LifecycleRoute tab="results">
              <div>Results page</div>
            </LifecycleRoute>
          }
        />
        <Route
          path="/tasks/:taskId/sources"
          element={
            <LifecycleRoute tab="sources">
              <div>Sources page</div>
            </LifecycleRoute>
          }
        />
        <Route path="/tasks/:taskId/evidence-search" element={<RedirectToPath suffix="/results" />} />
        <Route
          path="/tasks/:taskId/decisions"
          element={<RedirectToPath suffix="/history" />}
        />
        <Route path="/tasks/:taskId/history" element={<div>History page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LifecycleRoute — a locked stage is unreachable by URL", () => {
  it("redirects a locked route to Plan rather than showing an empty page", () => {
    mockTask(null);
    renderAt(`/tasks/${TASK_ID}/results`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/tasks/${TASK_ID}`);
    expect(screen.queryByText("Results page")).not.toBeInTheDocument();
    expect(screen.getByText("Plan page")).toBeInTheDocument();
  });

  it("renders the stage when the run state opens it", () => {
    mockTask("succeeded");
    renderAt(`/tasks/${TASK_ID}/results`);
    expect(screen.getByText("Results page")).toBeInTheDocument();
  });

  it("keeps Sources reachable after a failed run", () => {
    mockTask("failed");
    renderAt(`/tasks/${TASK_ID}/sources`);
    expect(screen.getByText("Sources page")).toBeInTheDocument();
  });

  it("keeps Sources reachable while a run is executing", () => {
    mockTask("running");
    renderAt(`/tasks/${TASK_ID}/sources`);
    expect(screen.getByText("Sources page")).toBeInTheDocument();
  });

  it("still locks Results after a failed run", () => {
    mockTask("failed");
    renderAt(`/tasks/${TASK_ID}/results`);
    expect(screen.getByText("Plan page")).toBeInTheDocument();
  });

  it("waits for the task to load before deciding — a cold deep link is not bounced", () => {
    mockTask(null, { pending: true });
    renderAt(`/tasks/${TASK_ID}/results`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/tasks/${TASK_ID}/results`);
    expect(screen.queryByText("Plan page")).not.toBeInTheDocument();
  });
});

describe("RedirectToPath — retired URLs still resolve", () => {
  it.each([
    ["evidence-search", "/results"],
    ["decisions", "/history"],
  ])("sends /%s to %s", (from, to) => {
    mockTask("succeeded");
    renderAt(`/tasks/${TASK_ID}/${from}`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/tasks/${TASK_ID}${to}`);
  });
});

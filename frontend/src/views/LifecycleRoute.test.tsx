import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { LifecycleRoute } from "./LifecycleRoute";

vi.mock("../api/queries", () => ({ useTask: vi.fn() }));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="path">{location.pathname}</div>;
}

function mockTask(status: string | null, { pending = false, access = "full" } = {}) {
  vi.mocked(queries.useTask).mockReturnValue({
    isPending: pending,
    data: pending
      ? undefined
      : {
          task_id: TASK_ID,
          access,
          latest_run: status === null ? null : { status },
        },
  } as unknown as ReturnType<typeof queries.useTask>);
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocationProbe />
      <Routes>
        <Route
          path="/tasks/:taskId"
          element={
            <LifecycleRoute tab="agent">
              <div>Plan page</div>
            </LifecycleRoute>
          }
        />
        <Route
          path="/tasks/:taskId/result"
          element={
            <LifecycleRoute tab="result">
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
        <Route
          path="/tasks/:taskId/share"
          element={
            <LifecycleRoute tab="share">
              <div>Share page</div>
            </LifecycleRoute>
          }
        />
        <Route
          path="/tasks/:taskId/history"
          element={
            <LifecycleRoute tab="history">
              <div>History page</div>
            </LifecycleRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LifecycleRoute — a locked stage is unreachable by URL", () => {
  it("redirects a locked route to Plan rather than showing an empty page", () => {
    mockTask(null);
    renderAt(`/tasks/${TASK_ID}/result`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/tasks/${TASK_ID}`);
    expect(screen.queryByText("Results page")).not.toBeInTheDocument();
    expect(screen.getByText("Plan page")).toBeInTheDocument();
  });

  it("renders the stage when the run state opens it", () => {
    mockTask("succeeded");
    renderAt(`/tasks/${TASK_ID}/result`);
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

  it("opens Results while a run is executing so the in-progress write-up is reachable", () => {
    mockTask("running");
    renderAt(`/tasks/${TASK_ID}/result`);
    expect(screen.getByText("Results page")).toBeInTheDocument();
  });

  it("still locks Results after a failed run", () => {
    mockTask("failed");
    renderAt(`/tasks/${TASK_ID}/result`);
    expect(screen.getByText("Plan page")).toBeInTheDocument();
  });

  it("waits for the task to load before deciding — a cold deep link is not bounced", () => {
    mockTask(null, { pending: true });
    renderAt(`/tasks/${TASK_ID}/result`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/tasks/${TASK_ID}/result`);
    expect(screen.queryByText("Plan page")).not.toBeInTheDocument();
  });
});

describe("LifecycleRoute — public-leg access shows Results and Sources only (task 037)", () => {
  it("sends a public-leg reader's Share URL to Results", () => {
    mockTask("succeeded", { access: "public" });
    renderAt(`/tasks/${TASK_ID}/share`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/tasks/${TASK_ID}/result`);
    expect(screen.queryByText("Share page")).not.toBeInTheDocument();
    expect(screen.getByText("Results page")).toBeInTheDocument();
  });

  it("keeps Results and Sources reachable on the public leg", () => {
    mockTask("succeeded", { access: "public" });
    renderAt(`/tasks/${TASK_ID}/sources`);
    expect(screen.getByText("Sources page")).toBeInTheDocument();
  });

  it("opens Results on the public leg even when the run state would lock it", () => {
    // The backend's public leg is the gate; run-state locks are an
    // owner-side affordance and never apply to the public view.
    mockTask(null, { access: "public" });
    renderAt(`/tasks/${TASK_ID}/result`);
    expect(screen.getByText("Results page")).toBeInTheDocument();
  });

  it("sends a public-leg reader's Plan URL to Results", () => {
    mockTask("succeeded", { access: "public" });
    renderAt(`/tasks/${TASK_ID}`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/tasks/${TASK_ID}/result`);
    expect(screen.queryByText("Plan page")).not.toBeInTheDocument();
    expect(screen.getByText("Results page")).toBeInTheDocument();
  });

  it("sends a public-leg reader's History URL to Results", () => {
    mockTask("succeeded", { access: "public" });
    renderAt(`/tasks/${TASK_ID}/history`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/tasks/${TASK_ID}/result`);
    expect(screen.queryByText("History page")).not.toBeInTheDocument();
    expect(screen.getByText("Results page")).toBeInTheDocument();
  });

  it("does not change graded readers — Share still renders on access 'full'", () => {
    mockTask("succeeded");
    renderAt(`/tasks/${TASK_ID}/share`);
    expect(screen.getByText("Share page")).toBeInTheDocument();
  });
});

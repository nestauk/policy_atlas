import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { LifecycleRoute, RedirectToPath } from "./LifecycleRoute";

vi.mock("../api/queries", () => ({ useProject: vi.fn() }));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="path">{location.pathname}</div>;
}

function mockProject(status: string | null, { pending = false } = {}) {
  vi.mocked(queries.useProject).mockReturnValue({
    isPending: pending,
    data: pending
      ? undefined
      : {
          project_id: PROJECT_ID,
          latest_run: status === null ? null : { status },
        },
  } as unknown as ReturnType<typeof queries.useProject>);
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocationProbe />
      <Routes>
        <Route path="/projects/:projectId" element={<div>Plan page</div>} />
        <Route
          path="/projects/:projectId/results"
          element={
            <LifecycleRoute tab="results">
              <div>Results page</div>
            </LifecycleRoute>
          }
        />
        <Route
          path="/projects/:projectId/sources"
          element={
            <LifecycleRoute tab="sources">
              <div>Sources page</div>
            </LifecycleRoute>
          }
        />
        <Route path="/projects/:projectId/evidence-base" element={<RedirectToPath suffix="/results" />} />
        <Route
          path="/projects/:projectId/decisions"
          element={<RedirectToPath suffix="/history" />}
        />
        <Route path="/projects/:projectId/history" element={<div>History page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LifecycleRoute — a locked stage is unreachable by URL", () => {
  it("redirects a locked route to Plan rather than showing an empty page", () => {
    mockProject(null);
    renderAt(`/projects/${PROJECT_ID}/results`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/projects/${PROJECT_ID}`);
    expect(screen.queryByText("Results page")).not.toBeInTheDocument();
    expect(screen.getByText("Plan page")).toBeInTheDocument();
  });

  it("renders the stage when the run state opens it", () => {
    mockProject("succeeded");
    renderAt(`/projects/${PROJECT_ID}/results`);
    expect(screen.getByText("Results page")).toBeInTheDocument();
  });

  it("keeps Sources reachable after a failed run", () => {
    mockProject("failed");
    renderAt(`/projects/${PROJECT_ID}/sources`);
    expect(screen.getByText("Sources page")).toBeInTheDocument();
  });

  it("keeps Sources reachable while a run is executing", () => {
    mockProject("running");
    renderAt(`/projects/${PROJECT_ID}/sources`);
    expect(screen.getByText("Sources page")).toBeInTheDocument();
  });

  it("still locks Results after a failed run", () => {
    mockProject("failed");
    renderAt(`/projects/${PROJECT_ID}/results`);
    expect(screen.getByText("Plan page")).toBeInTheDocument();
  });

  it("waits for the project to load before deciding — a cold deep link is not bounced", () => {
    mockProject(null, { pending: true });
    renderAt(`/projects/${PROJECT_ID}/results`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/projects/${PROJECT_ID}/results`);
    expect(screen.queryByText("Plan page")).not.toBeInTheDocument();
  });
});

describe("RedirectToPath — retired URLs still resolve", () => {
  it.each([
    ["evidence-base", "/results"],
    ["decisions", "/history"],
  ])("sends /%s to %s", (from, to) => {
    mockProject("succeeded");
    renderAt(`/projects/${PROJECT_ID}/${from}`);
    expect(screen.getByTestId("path")).toHaveTextContent(`/projects/${PROJECT_ID}${to}`);
  });
});

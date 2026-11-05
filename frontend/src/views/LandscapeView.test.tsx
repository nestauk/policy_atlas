import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState, type RunStreamState } from "../store";

import { mockFunnel, mockGroups, mockLandscape } from "../mock/fixtures";
import { LandscapeView } from "./LandscapeView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useTask: vi.fn(),
  useLandscape: vi.fn(),
  useFunnel: vi.fn(),
  useGroups: vi.fn(),
}));

let streamState: RunStreamState = createInitialRunStreamState();
vi.mock("../store", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../store")>()),
  useRunStream: () => streamState,
}));

afterEach(() => {
  streamState = createInitialRunStreamState();
});

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderLandscape() {
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources/landscape`]}>
      <Routes>
        <Route path="/tasks/:taskId/sources/landscape" element={<LandscapeView />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "Tower Hamlets task" } } as unknown as ReturnType<typeof queries.useTask>,
  );
});

describe("LandscapeView", () => {
  it("stacks one centred plot per row so classification labels are not squeezed", () => {
    vi.mocked(queries.useLandscape).mockReturnValue({
      data: mockLandscape,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useLandscape>);
    vi.mocked(queries.useFunnel).mockReturnValue({
      data: mockFunnel,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useFunnel>);
    vi.mocked(queries.useGroups).mockReturnValue({
      data: mockGroups,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useGroups>);

    const { container } = renderLandscape();

    expect(screen.getByText("Evidence types").parentElement?.className).toContain("max-w-3xl");
    expect(screen.getByText("Publication years").parentElement?.className).toContain("max-w-3xl");
    expect(screen.getByText("From search to citation").parentElement?.className).toContain("max-w-3xl");
    expect(container.querySelector(".lg\\:grid-cols-2")).toBeNull();
  });
});

// Owner, round 8: while Classifying runs and no evidence type has landed,
// the chart's place pulses; once a type lands the chart shows.
describe("LandscapeView — while Classifying runs", () => {
  const classifying = (status: "started" | "completed" = "started"): RunStreamState => ({
    ...createInitialRunStreamState(),
    run: { id: "r1", status: "running", startedAt: "2026-11-05T10:00:00Z" },
    stages: [{ stage: "classify", label: "Classifying", status, startedAt: "2026-11-05T10:05:00Z", counts: [] }],
  });
  const reads = (types: Record<string, number>) => {
    vi.mocked(queries.useLandscape).mockReturnValue({
      data: { ...mockLandscape, evidence_types: types },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useLandscape>);
    vi.mocked(queries.useFunnel).mockReturnValue({
      data: mockFunnel,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useFunnel>);
    vi.mocked(queries.useGroups).mockReturnValue({ data: undefined } as unknown as ReturnType<typeof queries.useGroups>);
  };

  it("pulses bars under the Evidence types heading in place of the chart", () => {
    streamState = classifying();
    reads({});
    renderLandscape();
    const pending = screen.getByTestId("evidence-types-pending");
    expect(pending).toHaveAttribute("aria-hidden", "true");
    expect(pending.querySelectorAll(".placeholder-bar").length).toBeGreaterThan(4);
    expect(screen.getByText("Evidence types")).toBeInTheDocument();
  });

  it("pulses nothing once a type has landed, or once Classifying has ended", () => {
    streamState = classifying();
    reads({ "Systematic review": 3 });
    const landed = renderLandscape();
    expect(screen.queryByTestId("evidence-types-pending")).toBeNull();
    landed.unmount();
    streamState = classifying("completed");
    reads({});
    renderLandscape();
    expect(screen.queryByTestId("evidence-types-pending")).toBeNull();
  });
});

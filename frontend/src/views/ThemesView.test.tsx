import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState, type RunStreamState } from "../store";

import { mockLandscape } from "../mock/fixtures";
import { ThemesView } from "./ThemesView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useTask: vi.fn(),
  useLandscape: vi.fn(),
}));

let streamState: RunStreamState = createInitialRunStreamState();
vi.mock("../store", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../store")>()),
  useRunStream: () => streamState,
}));

/** A running run with `stage` in progress (or finished). */
function runWith(stage: "characterise" | "classify", status: "started" | "completed" = "started"): RunStreamState {
  return {
    ...createInitialRunStreamState(),
    run: { id: "r1", status: "running", startedAt: "2026-11-05T10:00:00Z" },
    stages: [{ stage, label: "Mapping", status, startedAt: "2026-11-05T10:05:00Z", counts: [] }],
  };
}

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderThemes() {
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources`]}>
      <Routes>
        <Route path="/tasks/:taskId/sources" element={<ThemesView />} />
        <Route path="/tasks/:taskId/sources/all" element={<div>all sources</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  streamState = createInitialRunStreamState();
  vi.useRealTimers();
});

beforeEach(() => {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "Tower Hamlets task" } } as unknown as ReturnType<typeof queries.useTask>,
  );
});

describe("ThemesView — landscape themes only", () => {
  it("renders a landscape theme's name, size and existing prose description", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: mockLandscape, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    renderThemes();
    expect(screen.getByText("School food environments")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Key themes" })).toBeNull();
    expect(screen.getByText("19 documents")).toBeInTheDocument();
    expect(
      screen.getByText("Meal standards, free breakfast, and food access."),
    ).toBeInTheDocument();
  });

  it("links a landscape theme with a theme_id through to All sources filtered on that theme", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: mockLandscape, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    renderThemes();
    const schoolFood = mockLandscape.themes?.find((theme) => theme.name === "School food environments");
    expect(screen.getByRole("link", { name: /School food environments/ })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all?theme=${schoolFood?.theme_id}`,
    );
    expect(screen.queryByRole("link", { name: /Family support/ })).toBeNull();
  });

  it("shows an empty state when there are no landscape themes", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: { evidence_types: {}, years: {}, themes: [] }, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    renderThemes();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Themes appear once the Mapping step has finished.",
    );
  });
});

// Owner, round 8: while Mapping runs and no theme has landed, the themes'
// rows pulse in place, and the themes refetch every 5 s until it ends.
describe("ThemesView — while Mapping runs", () => {
  const empty = (refetch = vi.fn()) =>
    vi.mocked(queries.useLandscape).mockReturnValue({
      data: { ...mockLandscape, themes: [] },
      isPending: false,
      isError: false,
      refetch,
    } as unknown as ReturnType<typeof queries.useLandscape>);

  it("shows three pulsing theme rows in place of the empty state, and tells a screen reader when themes appear", () => {
    streamState = runWith("characterise");
    empty();
    renderThemes();
    const pending = screen.getByTestId("themes-pending");
    expect(pending).toHaveAttribute("aria-hidden", "true");
    expect(pending.querySelectorAll("li")).toHaveLength(3);
    expect(pending.querySelector(".placeholder-bar")).not.toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("Themes appear once the Mapping step has finished.");
    expect(screen.getByRole("status")).toHaveClass("sr-only");
  });

  it("refetches every 5 s while Mapping runs, and stops when it ends", () => {
    vi.useFakeTimers();
    const refetch = vi.fn();
    streamState = runWith("characterise");
    empty(refetch);
    const view = renderThemes();
    act(() => vi.advanceTimersByTime(10_000));
    expect(refetch).toHaveBeenCalledTimes(2);
    streamState = runWith("characterise", "completed");
    view.rerender(
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources`]}>
        <Routes>
          <Route path="/tasks/:taskId/sources" element={<ThemesView />} />
        </Routes>
      </MemoryRouter>,
    );
    act(() => vi.advanceTimersByTime(10_000));
    expect(refetch).toHaveBeenCalledTimes(2);
  });

  it("pulses nothing once Mapping has ended, or while the run waits on a check-in", () => {
    streamState = runWith("characterise", "completed");
    empty();
    const ended = renderThemes();
    expect(screen.queryByTestId("themes-pending")).toBeNull();
    expect(screen.getByText("Themes appear once the Mapping step has finished.")).toBeVisible();
    ended.unmount();
    streamState = { ...runWith("characterise"), run: { id: "r1", status: "paused", startedAt: "2026-11-05T10:00:00Z" } };
    empty();
    renderThemes();
    expect(screen.queryByTestId("themes-pending")).toBeNull();
  });
});

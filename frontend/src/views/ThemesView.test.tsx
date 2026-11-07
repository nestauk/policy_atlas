import { act, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState, type RunStreamState } from "../store";

import { mockLandscape } from "../mock/fixtures";
import { scopingThemes, ThemesView } from "./ThemesView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useTask: vi.fn(),
  useLandscape: vi.fn(),
  useLonglist: vi.fn(() => ({ data: undefined, isPending: false, isError: false })),
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

// Owner, round 9: from discovery, the themes show by name and description
// while documents are assigned, and their counts fill in place.
describe("ThemesView — the themes while documents are assigned (owner, round 9)", () => {
  const discovered = [
    { label: "School food environments", description: "Meal standards, free breakfast, and food access." },
    { label: "Active travel", description: null },
  ];
  const mapping = (): RunStreamState => ({ ...runWith("characterise"), liveThemes: discovered });

  it("lists the discovered themes in their final layout, a pulsing bar where each count will be", () => {
    streamState = mapping();
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: undefined, isPending: false, isError: true, error: { code: "not_found" }, refetch: vi.fn() } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    renderThemes();
    expect(screen.getByText("School food environments")).toBeInTheDocument();
    expect(screen.getByText("Active travel")).toBeInTheDocument();
    expect(screen.getAllByTestId("theme-count-pulse")).toHaveLength(2);
    expect(screen.queryByTestId("themes-pending")).toBeNull();
    // Not links until the committed themes carry their ids.
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("fills the counts in place, in the discovered order, when the committed landscape lands", () => {
    streamState = mapping();
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: { ...mockLandscape, themes: [] }, isPending: false, isError: false, refetch: vi.fn() } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    const view = renderThemes();
    const before = screen.getByText("Active travel").closest("li");
    vi.mocked(queries.useLandscape).mockReturnValue(
      {
        data: {
          ...mockLandscape,
          themes: [
            { name: "Active travel", size: 30, description: "Walking and cycling to school.", theme_id: null },
            { name: "School food environments", size: 19, description: "Meal standards, free breakfast, and food access.", theme_id: null },
          ],
        },
        isPending: false,
        isError: false,
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    view.rerender(
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources`]}>
        <Routes>
          <Route path="/tasks/:taskId/sources" element={<ThemesView />} />
          <Route path="/tasks/:taskId/sources/all" element={<div>all sources</div>} />
        </Routes>
      </MemoryRouter>,
    );
    const names = screen.getAllByRole("listitem").map((item) => item.querySelector("p")?.textContent);
    expect(names).toEqual(["School food environments", "Active travel"]);
    expect(screen.getByText("Active travel").closest("li")).toBe(before);
    expect(screen.getByText("30 documents")).toHaveClass("anim-swap-in");
  });
});

// Round 13 (owner): an options-scoping task's Themes subtab shows the
// longlist's option clusters (it was empty after a completed run).
describe("ThemesView — an options-scoping task's themes (round 13)", () => {
  const longlist = {
    themes: [
      { theme_id: "t1", name: "Earlier support", description: "Help before young people leave school.", option_ids: ["o2", "o1", "gone"] },
      { theme_id: "t2", name: "Empty theme", description: "", option_ids: [] },
    ],
    options: [
      { option_id: "o1", name: "Youth guarantee", state: "included" },
      { option_id: "o2", name: "Careers advice in schools", state: "excluded" },
    ],
  };

  it("lists each theme's options in the theme's order, leaving out unknown ids and empty themes", () => {
    expect(scopingThemes(longlist as never)).toEqual([
      {
        themeId: "t1",
        name: "Earlier support",
        description: "Help before young people leave school.",
        options: [
          { id: "o2", name: "Careers advice in schools", excluded: true },
          { id: "o1", name: "Youth guarantee", excluded: false },
        ],
      },
    ]);
  });

  it("shows each theme as a section, its description, and its options linking to their cards", () => {
    vi.mocked(queries.useTask).mockReturnValue(
      { data: { name: "NEET task", capability: "options_scoping" } } as unknown as ReturnType<typeof queries.useTask>,
    );
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: undefined, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    vi.mocked(queries.useLonglist).mockReturnValue(
      { data: longlist, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLonglist>,
    );
    renderThemes();
    // The longlist is read for this task.
    expect(vi.mocked(queries.useLonglist)).toHaveBeenLastCalledWith(TASK_ID);
    const section = screen.getByRole("region", { name: "Earlier support" });
    expect(within(section).getByText("Help before young people leave school.")).toBeInTheDocument();
    expect(within(section).getByText("2 options")).toBeInTheDocument();
    const links = within(section).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["Careers advice in schools", "Youth guarantee"]);
    expect(links[1]).toHaveAttribute("href", `/tasks/${TASK_ID}/options/o1`);
    // An excluded option reads in Grey, as the longlist sets it.
    expect(links[0]).toHaveClass("text-grey");
    expect(screen.queryByRole("region", { name: "Empty theme" })).toBeNull();
  });

  it("does not read the longlist on an Evidence search task", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: mockLandscape, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    renderThemes();
    expect(vi.mocked(queries.useLonglist)).toHaveBeenLastCalledWith("");
  });
});

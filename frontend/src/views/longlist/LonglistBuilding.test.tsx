import { act, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";
import * as store from "../../store";
import { createInitialRunStreamState } from "../../store";
import { mockLonglist } from "../../mock/fixtures";
import { LonglistBuilding, LonglistView } from "./LonglistView";

vi.mock("../../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof queries>();
  return { ...actual, useTask: vi.fn(), useOptions: vi.fn(), useLonglist: vi.fn(), usePlan: vi.fn() };
});
vi.mock("../../store", async (importOriginal) => {
  const actual = await importOriginal<typeof store>();
  return { ...actual, useRunStream: vi.fn() };
});
vi.mock("../../api/mutations", () => ({
  useAddOption: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useOptionVerb: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useShortlistVerb: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));
void mutations;

const TASK = "11111111-1111-1111-1111-111111111111";
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

function renderBuilding(rows: unknown[], stage: { key: string; label: string; activity?: string } | null) {
  vi.mocked(queries.useTask).mockReturnValue({
    data: { capability: "options_scoping", active_run: { stage: stage?.key ?? null, stage_label: stage?.label ?? null } },
  } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useOptions).mockReturnValue({ data: { options: rows } } as unknown as ReturnType<typeof queries.useOptions>);
  vi.mocked(queries.useLonglist).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.useLonglist>);
  vi.mocked(queries.usePlan).mockReturnValue({ data: { scoping: { question: "How can we cut the NEET rate?" } } } as unknown as ReturnType<typeof queries.usePlan>);
  const state = createInitialRunStreamState();
  if (stage !== null) {
    state.run = { id: "w", status: "running", startedAt: "2026-11-05T10:00:00Z" };
    state.stages = [{ stage: stage.key as never, label: stage.label, status: "started", startedAt: "2026-11-05T10:00:00Z" }];
    if (stage.activity) {
      state.liveness = { [stage.key]: { activity: stage.activity, heartbeat: false, dropped: 0, occurredAt: new Date().toISOString() } };
    }
  }
  vi.mocked(store.useRunStream).mockReturnValue(state);
  return render(
    <MemoryRouter>
      <LonglistBuilding taskId={TASK} />
    </MemoryRouter>,
  );
}

const row = (n: number, patch: Record<string, unknown> = {}) => ({
  option_id: id(n),
  name: `Option ${n}`,
  description: "",
  origin: "suggested",
  state: "included",
  merged_into_option_id: null,
  search_status: "queued",
  found: null,
  ...patch,
});

afterEach(() => {
  delete (document as { startViewTransition?: unknown }).startViewTransition;
});

describe("LonglistBuilding (task 058, N24; round 10)", () => {
  it("titles the page Longlist with the question under it and each row's own search, and no stage line", () => {
    const { container } = renderBuilding(
      [row(1, { search_status: "searched", found: 312, origin: "from_evidence_search" }), row(2, { search_status: "searching" }), row(3, { origin: "added_by_you" })],
      { key: "option_searches", label: "Searching for each option", activity: "1 of 3 searches done · 312 sources so far" },
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/^Longlist$/);
    expect(screen.getByText("How can we cut the NEET rate?")).toBeInTheDocument();
    // The run status bar above says what the walk does (round 10, D3).
    expect(container.textContent).not.toContain("Searching for each option");
    expect(container.textContent).toContain("Searched · 312 found");
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.getByText("from your report")).toBeInTheDocument();
    expect(screen.getByText("added by you")).toBeInTheDocument();
    expect(screen.getByText("suggested by Policy Atlas")).toBeInTheDocument();
  });

  // Round 10, D3: one turning mark per screen; a searching row breathes the
  // 6 px blue square instead.
  it("marks a searching row with the breathing square, never the turning fold mark", () => {
    const { container } = renderBuilding([row(1, { search_status: "searching" }), row(2, { search_status: "failed" })], {
      key: "option_searches",
      label: "Searching for each option",
    });
    expect(container.querySelector("[data-live-mark]")).toBeNull();
    const searching = within(screen.getByText("Searching").closest("li") as HTMLElement);
    const mark = searching.getByText("Searching").parentElement?.querySelector("[data-tone]");
    expect(mark).toHaveAttribute("data-tone", "running");
    expect(mark).toHaveClass("anim-breathe");
    const failed = screen.getByText("Search failed");
    expect(failed).toHaveClass("text-red");
  });

  it("shows a folded row under its parent and the clustered rows' origin", () => {
    renderBuilding([row(1), row(2, { merged_into_option_id: id(1) }), row(3, { origin: "clustered" })], {
      key: "longlist",
      label: "Clustering into options",
      activity: "options may be folded together or added",
    });
    expect(screen.getByText("Folded into Option 1")).toBeInTheDocument();
    expect(screen.getByText("found in the evidence")).toBeInTheDocument();
  });

  it("carries no qualifier word and no controls while it builds", () => {
    const { container } = renderBuilding([row(1)], null);
    expect(container.textContent).not.toMatch(/provisional|draft|preliminary|tentative/i);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  // Round 10, finding 2: the walk's end changes the page only by adding its
  // controls; the page stays mounted (one component), the rows in place.
  it("hands over to the finished list in place, gaining only its controls", () => {
    const longlist = mockLonglist();
    const rows = (longlist.options ?? []).map((option, n) => row(n + 1, { option_id: option.option_id, name: option.name }));
    const view = renderBuilding(rows, { key: "theme", label: "Grouping into themes" });
    vi.mocked(queries.useLonglist).mockReturnValue({ data: longlist } as unknown as ReturnType<typeof queries.useLonglist>);
    view.rerender(
      <MemoryRouter>
        <LonglistBuilding taskId={TASK} />
      </MemoryRouter>,
    );
    const title = screen.getByRole("heading", { level: 1 });
    const firstRow = screen.getByText("School-based mentoring").closest("li");
    expect(screen.queryByRole("group", { name: "Group by" })).toBeNull();
    view.rerender(
      <MemoryRouter>
        <LonglistView taskId={TASK} longlist={longlist} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1 })).toBe(title);
    expect(screen.getByText("School-based mentoring").closest("li")).toBe(firstRow);
    expect(screen.getByRole("group", { name: "Group by" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "School-based mentoring" })).toBeInTheDocument();
  });

  // Round 10, finding 2: rows move into their themes in a View Transition,
  // the list never blanking; the document carries the regrouping class only
  // while it runs.
  it("moves the rows into their themes inside a View Transition", async () => {
    let finish: () => void = () => {};
    const start = vi.fn((update: () => void) => {
      expect(document.documentElement).toHaveClass("longlist-regrouping");
      update();
      return { finished: new Promise<void>((resolve) => (finish = resolve)) };
    });
    (document as { startViewTransition?: unknown }).startViewTransition = start;
    const longlist = mockLonglist();
    const themes = longlist.themes;
    longlist.themes = [];
    const rows = (longlist.options ?? []).map((option, n) => row(n + 1, { option_id: option.option_id, name: option.name }));
    const view = renderBuilding(rows, { key: "theme", label: "Grouping into themes" });
    vi.mocked(queries.useLonglist).mockReturnValue({ data: { ...longlist } } as unknown as ReturnType<typeof queries.useLonglist>);
    view.rerender(
      <MemoryRouter>
        <LonglistBuilding taskId={TASK} />
      </MemoryRouter>,
    );
    // The exclusion wave moved a row: a regrouping of its own.
    expect(start).toHaveBeenCalledTimes(1);
    await act(async () => {
      finish();
      await Promise.resolve();
    });
    start.mockClear();
    expect(screen.getByRole("list", { name: "Options" })).toBeInTheDocument();
    vi.mocked(queries.useLonglist).mockReturnValue({ data: { ...longlist, themes } } as unknown as ReturnType<typeof queries.useLonglist>);
    view.rerender(
      <MemoryRouter>
        <LonglistBuilding taskId={TASK} />
      </MemoryRouter>,
    );
    expect(start).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { name: /Conditionality and support/ })).toBeInTheDocument();
    const named = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    expect(named.style.getPropertyValue("--longlist-row")).toMatch(/^opt-/);
    await act(async () => {
      finish();
      await Promise.resolve();
    });
    expect(document.documentElement).not.toHaveClass("longlist-regrouping");
  });
});

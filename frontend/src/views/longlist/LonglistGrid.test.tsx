import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockLonglist } from "../../mock/fixtures";
import { LonglistGrid } from "./LonglistGrid";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";

vi.mock("../../api/queries", () => ({ useTask: vi.fn() }));

const shortlistMutate = vi.fn();
const unshortlistMutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useOptionVerb: vi.fn(),
  useShortlistVerb: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderGrid(
  showExcluded = false,
  adjust?: (longlist: ReturnType<typeof mockLonglist>) => void,
  activeRun: unknown = null,
) {
  vi.mocked(queries.useTask).mockReturnValue({ data: { capability: "options_scoping", active_run: activeRun } } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(mutations.useOptionVerb).mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useOptionVerb>);
  vi.mocked(mutations.useShortlistVerb).mockImplementation(
    (_taskId, verb) =>
      ({ mutate: verb === "shortlist" ? shortlistMutate : unshortlistMutate, isPending: false }) as unknown as ReturnType<
        typeof mutations.useShortlistVerb
      >,
  );
  const longlist = mockLonglist();
  adjust?.(longlist);
  return render(
    <MemoryRouter>
      <LonglistGrid taskId={TASK_ID} longlist={longlist} showExcluded={showExcluded} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  shortlistMutate.mockClear();
  unshortlistMutate.mockClear();
});

describe("LonglistGrid", () => {
  it("lays out rows by lever type (plus None fits) and columns by the chosen line, Ambition first", () => {
    renderGrid();
    expect(screen.getByRole("row", { name: /Enforce existing powers/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /None fits/ })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "Lever type",
      "Smaller",
      "Middle",
      "Bigger",
      "Untagged",
    ]);
  });

  // R41: a labelled native select with the seven lines that carry a mark.
  it("offers a labelled Columns chooser with the seven lines, Ambition by default", () => {
    renderGrid();
    const chooser = screen.getByRole("combobox", { name: "Columns" });
    expect(chooser).toHaveValue("ambition");
    expect(within(chooser).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Ambition",
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Coordination requirements",
      "Delivery complexity",
    ]);
  });

  it("re-columns the grid on the chosen line and places options by their mark", async () => {
    const user = userEvent.setup();
    renderGrid(true);
    await user.selectOptions(screen.getByRole("combobox", { name: "Columns" }), "cost");
    const heads = screen.getAllByRole("columnheader").map((header) => header.textContent);
    expect(heads).toEqual(["Lever type", "Cheaper", "Middle", "Costlier", "Untagged"]);
    // The sanctions regime is marked cheaper; mentoring has no cost mark, so Middle.
    const cellIndex = (name: string) => {
      const cell = screen.getByRole("link", { name }).closest("td") as HTMLElement;
      return Array.from((cell.parentElement as HTMLElement).children).indexOf(cell);
    };
    expect(cellIndex("National sanctions regime")).toBe(heads.indexOf("Cheaper"));
    expect(cellIndex("School-based mentoring")).toBe(heads.indexOf("Middle"));
    expect(cellIndex("Youth guarantee")).toBe(heads.indexOf("Untagged"));
    await user.selectOptions(screen.getByRole("combobox", { name: "Columns" }), "delivery_complexity");
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toContain("More complex");
  });

  it("puts an option with no profile in Untagged whatever its ambition, and shows Untagged only then", () => {
    const first = renderGrid(true, (longlist) => {
      const added = longlist.options?.find((option) => option.profile == null);
      if (added === undefined) throw new Error("fixture has no unprofiled option");
      added.ambition = "more";
    });
    const heads = screen.getAllByRole("columnheader").map((header) => header.textContent);
    const cell = screen.getByRole("link", { name: "Youth guarantee" }).closest("td") as HTMLElement;
    expect(Array.from((cell.parentElement as HTMLElement).children).indexOf(cell)).toBe(heads.indexOf("Untagged"));
    first.unmount();
    renderGrid(true, (longlist) => {
      for (const option of longlist.options ?? []) {
        option.profile ??= { lines: [], settings: [] };
      }
    });
    expect(screen.queryByRole("columnheader", { name: "Untagged" })).not.toBeInTheDocument();
  });

  it("shows Middle in the grid, keeps the old band words out, and builds no compare table", () => {
    const { container } = renderGrid();
    expect(screen.getByRole("columnheader", { name: "Middle" })).toBeInTheDocument();
    for (const banned of [/less than most/i, /like most/i, /more than most/i, /do minimum/i, /incremental/i, /structural/i]) {
      expect(container).not.toHaveTextContent(banned);
    }
    expect(container.querySelectorAll("table")).toHaveLength(1);
  });

  it("places each option's tile at its lever/ambition intersection and leaves an empty row empty", () => {
    renderGrid(true);
    const structuralCell = screen.getByRole("link", { name: "National sanctions regime" }).closest("td");
    expect(structuralCell).not.toBeNull();
    expect(within(structuralCell as HTMLElement).getByText("National sanctions regime")).toBeInTheDocument();
    expect(screen.queryByText("no option of this type on the longlist")).not.toBeInTheDocument();
    const emptyRow = screen.getByRole("row", { name: /Convene/ });
    expect(within(emptyRow).queryAllByRole("link")).toHaveLength(0);
  });

  it("hides excluded options until asked", () => {
    renderGrid();
    expect(screen.queryByRole("link", { name: "National sanctions regime" })).not.toBeInTheDocument();
  });

  it("carries the excluded state (struck through) and the no-in-scope-evidence tag on tiles", () => {
    renderGrid(true);
    const excludedLink = screen.getByRole("link", { name: "National sanctions regime" });
    expect(excludedLink.className).toContain("line-through");
    const excludedCell = excludedLink.closest("td") as HTMLElement;
    expect(within(excludedCell).getByText("excluded")).toBeInTheDocument();

    const noInScopeLink = screen.getByRole("link", { name: "School-based mentoring" });
    const noInScopeCell = noInScopeLink.closest("td") as HTMLElement;
    expect(within(noInScopeCell).getByText("no in-scope evidence")).toBeInTheDocument();
  });

  it("folds a crowded cell behind +N more", async () => {
    const user = userEvent.setup();
    const longlist = mockLonglist();
    const base = longlist.options![0];
    longlist.options = Array.from({ length: 9 }, (_, i) => ({
      ...base,
      option_id: `crowd-${i}`,
      name: `Crowd option ${i}`,
      state: "included" as const,
      primary_lever_type: "regulate",
      ambition: "less" as const,
      profile: { lines: [], settings: [] },
    }));
    render(
      <MemoryRouter>
        <LonglistGrid taskId={TASK_ID} longlist={longlist} showExcluded={false} />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole("link", { name: /Crowd option/ })).toHaveLength(4);
    await user.click(screen.getByRole("button", { name: "+5 more" }));
    expect(screen.getAllByRole("link", { name: /Crowd option/ })).toHaveLength(9);
    await user.click(screen.getByRole("button", { name: "Show fewer −" }));
    expect(screen.getAllByRole("link", { name: /Crowd option/ })).toHaveLength(4);
  });

  it("folds a cell of five options to four, with +1 more", () => {
    const longlist = mockLonglist();
    const base = longlist.options![0];
    longlist.options = Array.from({ length: 5 }, (_, i) => ({
      ...base,
      option_id: `five-${i}`,
      name: `Five option ${i}`,
      state: "included" as const,
      primary_lever_type: "regulate",
      ambition: "less" as const,
      profile: { lines: [], settings: [] },
    }));
    render(
      <MemoryRouter>
        <LonglistGrid taskId={TASK_ID} longlist={longlist} showExcluded={false} />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole("link", { name: /Five option/ })).toHaveLength(4);
    expect(screen.getByRole("button", { name: "+1 more" })).toBeInTheDocument();
  });

  it("carries the place word and the shortlist action on tiles", async () => {
    const user = userEvent.setup();
    renderGrid(true);
    // The bundle is Policy Atlas's pick; the youth guarantee was added by you.
    const bundle = screen.getByRole("link", { name: "Universal youth offer bundle" }).closest("li") as HTMLElement;
    expect(within(bundle).getByText("Policy Atlas's pick")).toBeInTheDocument();
    expect(within(bundle).getByRole("button", { name: "Remove from shortlist" })).toBeEnabled();
    const guarantee = screen.getByRole("link", { name: "Youth guarantee" }).closest("li") as HTMLElement;
    expect(within(guarantee).getByText("Added by you")).toBeInTheDocument();
    // A set-aside pick has no word and offers Add.
    const mentoring = screen.getByRole("link", { name: "School-based mentoring" }).closest("li") as HTMLElement;
    expect(within(mentoring).queryByText(/Policy Atlas's pick|Added by you/)).not.toBeInTheDocument();
    await user.click(within(mentoring).getByRole("button", { name: "Add to shortlist" }));
    expect(shortlistMutate).toHaveBeenCalledWith({ optionId: expect.any(String) }, expect.anything());
    // An excluded option offers neither.
    const excluded = screen.getByRole("link", { name: "National sanctions regime" }).closest("li") as HTMLElement;
    expect(within(excluded).queryByRole("button")).not.toBeInTheDocument();
  });

  it("disables the shortlist actions while a walk is running", () => {
    renderGrid(false, undefined, { capability_run_id: "x", status: "running", started_at: "2026-10-27T00:00:00Z" });
    for (const button of screen.getAllByRole("button", { name: /shortlist/ })) expect(button).toBeDisabled();
  });

  it("links a tile through to the option card", () => {
    renderGrid();
    const link = screen.getByRole("link", { name: "Youth guarantee" });
    expect(link).toHaveAttribute("href", expect.stringContaining("/options/"));
  });
});

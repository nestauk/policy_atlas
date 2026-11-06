import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockLonglist } from "../../mock/fixtures";
import { LonglistGrid } from "./LonglistGrid";
import { PublicViewProvider } from "../publicView";

/** Chooses a line from the Columns dropdown. */
async function pickColumn(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByRole("combobox", { name: "Columns" }));
  await user.click(screen.getByRole("option", { name }));
}
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
    renderGrid(true);
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

  // R41: a labelled chooser with the eight lines that carry a mark; round 12:
  // the app's dropdown, not the browser's.
  it("offers a labelled Columns chooser with the eight lines, Ambition by default", async () => {
    const user = userEvent.setup();
    renderGrid();
    const chooser = screen.getByRole("combobox", { name: "Columns" });
    expect(chooser.tagName).toBe("BUTTON");
    expect(chooser).toHaveTextContent("Ambition");
    await user.click(chooser);
    const list = screen.getByRole("listbox", { name: "Columns" });
    expect(within(list).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Ambition",
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Coordination requirements",
      "Delivery complexity",
      "Potential impact",
    ]);
  });

  it("re-columns the grid on the chosen line and places options by their mark", async () => {
    const user = userEvent.setup();
    renderGrid(true);
    await pickColumn(user, "Cost");
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
    await pickColumn(user, "Delivery complexity");
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toContain("More complex");
  });

  // Task 055: Potential impact carries a mark (the owner, 2026-10-27).
  it("columns the grid on Potential impact and places options by its mark", async () => {
    const user = userEvent.setup();
    renderGrid(true);
    await pickColumn(user, "Potential impact");
    const heads = screen.getAllByRole("columnheader").map((header) => header.textContent);
    expect(heads).toEqual(["Lever type", "Lower", "Middle", "Higher", "Untagged"]);
    const cellIndex = (name: string) => {
      const cell = screen.getByRole("link", { name }).closest("td") as HTMLElement;
      return Array.from((cell.parentElement as HTMLElement).children).indexOf(cell);
    };
    expect(cellIndex("National sanctions regime")).toBe(heads.indexOf("Higher"));
    expect(cellIndex("School-based mentoring")).toBe(heads.indexOf("Middle"));
    expect(cellIndex("Universal youth offer bundle")).toBe(heads.indexOf("Lower"));
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

  // Round 10 (finding 13): the lever types with no option are one Grey line
  // under the table, not empty bands (the absence is still the message).
  it("places each option's tile at its lever/ambition intersection and folds the empty lever rows into one line", () => {
    renderGrid(true);
    const structuralCell = screen.getByRole("link", { name: "National sanctions regime" }).closest("td");
    expect(structuralCell).not.toBeNull();
    expect(within(structuralCell as HTMLElement).getByText("National sanctions regime")).toBeInTheDocument();
    expect(screen.queryByText("no option of this type on the longlist")).not.toBeInTheDocument();
    expect(screen.queryByRole("row", { name: /Convene/ })).not.toBeInTheDocument();
    const absent = screen.getByText(/^No options: /);
    expect(absent).toHaveTextContent(/Convene/);
    expect(absent).toHaveClass("text-grey");
    expect(absent).not.toHaveTextContent(/Enforce existing powers|Regulate/);
  });

  it("hides excluded options until asked", () => {
    renderGrid();
    expect(screen.queryByRole("link", { name: "National sanctions regime" })).not.toBeInTheDocument();
  });

  // Round 10 (finding 6): states in words, no chips; red only on the failure word.
  it("carries the excluded state and no in-scope evidence on tiles in words", () => {
    const { container } = renderGrid(true);
    const excludedLink = screen.getByRole("link", { name: "National sanctions regime" });
    expect(excludedLink).toHaveClass("text-grey");
    const excludedCell = excludedLink.closest("td") as HTMLElement;
    // Round 12 (owner): the grey alone marks an excluded option, no red word.
    expect(within(excludedCell).getByText("Excluded")).toHaveClass("text-grey");

    const noInScopeLink = screen.getByRole("link", { name: "School-based mentoring" });
    const noInScopeCell = noInScopeLink.closest("td") as HTMLElement;
    expect(within(noInScopeCell).getByText("No in-scope evidence")).toHaveClass("text-grey");
    expect(container.querySelector("[class*='text-[11.5px]']")).toBeNull();
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

  // Round 12 (owner): the shortlisted lead each cell, the rest after them in
  // their own order; a toggle moves the tile with the regroup's View Transition.
  it("puts the shortlisted first in a cell and moves a tile there when it is shortlisted", () => {
    const start = vi.fn((update: () => void) => {
      update();
      return { finished: Promise.resolve() };
    });
    Object.defineProperty(document, "startViewTransition", { value: start, configurable: true, writable: true });
    try {
      const make = (held: number[]) => {
        const longlist = mockLonglist();
        const base = longlist.options![0];
        longlist.options = Array.from({ length: 4 }, (_, i) => ({
          ...base,
          option_id: `cell-${i}`,
          name: `Cell option ${i}`,
          state: "included" as const,
          primary_lever_type: "regulate",
          ambition: "less" as const,
          profile: { lines: [], settings: [] },
          shortlist: held.includes(i) ? { state: "proposed" as const, reason: "Because." } : null,
        }));
        return longlist;
      };
      const tree = (longlist: ReturnType<typeof mockLonglist>) => (
        <MemoryRouter>
          <LonglistGrid taskId={TASK_ID} longlist={longlist} showExcluded={false} />
        </MemoryRouter>
      );
      renderGrid();
      cleanup();
      const { rerender } = render(tree(make([2])));
      const names = () => screen.getAllByRole("link", { name: /Cell option/ }).map((link) => link.textContent);
      expect(names()).toEqual(["Cell option 2", "Cell option 0", "Cell option 1", "Cell option 3"]);
      expect(start).not.toHaveBeenCalled();
      rerender(tree(make([2, 3])));
      expect(start).toHaveBeenCalledTimes(1);
      expect(names()).toEqual(["Cell option 2", "Cell option 3", "Cell option 0", "Cell option 1"]);
    } finally {
      Reflect.deleteProperty(document, "startViewTransition");
    }
  });

  // Round 12 (owner): the public link reads the grid; a held tile says
  // "Shortlisted" in words and no tile carries a toggle; Columns stays.
  it("is read-only on the public link: no shortlist toggle on a tile, the held word kept", () => {
    renderGrid();
    cleanup();
    render(
      <PublicViewProvider value>
        <MemoryRouter>
          <LonglistGrid taskId={TASK_ID} longlist={mockLonglist()} showExcluded={false} />
        </MemoryRouter>
      </PublicViewProvider>,
    );
    expect(screen.queryByRole("button", { name: /shortlist/i })).not.toBeInTheDocument();
    expect(screen.getAllByText("Shortlisted").length).toBeGreaterThan(0);
    expect(screen.getByRole("combobox", { name: "Columns" })).toBeInTheDocument();
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

  it("carries the shortlist toggle on tiles, in words", async () => {
    const user = userEvent.setup();
    renderGrid(true);
    // The bundle is Policy Atlas's pick; the youth guarantee was added by you.
    const bundle = screen.getByRole("link", { name: "Universal youth offer bundle" }).closest("li") as HTMLElement;
    const held = within(bundle).getByRole("button", { name: "Shortlisted" });
    expect(held).toBeEnabled();
    expect(held).toHaveAttribute("aria-pressed", "true");
    const guarantee = screen.getByRole("link", { name: "Youth guarantee" }).closest("li") as HTMLElement;
    expect(within(guarantee).getByRole("button", { name: "Shortlisted" })).toBeInTheDocument();
    // A set-aside pick offers Add.
    const mentoring = screen.getByRole("link", { name: "School-based mentoring" }).closest("li") as HTMLElement;
    await user.click(within(mentoring).getByRole("button", { name: "Add to shortlist" }));
    expect(shortlistMutate).toHaveBeenCalledWith({ optionId: expect.any(String) }, expect.anything());
    // An excluded option offers neither.
    const excluded = screen.getByRole("link", { name: "National sanctions regime" }).closest("li") as HTMLElement;
    expect(within(excluded).queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows a refused shortlist action's notice under its tile", async () => {
    const user = userEvent.setup();
    shortlistMutate.mockImplementationOnce((_vars, options: { onError: (error: Error) => void }) =>
      options.onError(new Error("network")),
    );
    renderGrid();
    const mentoring = screen.getByRole("link", { name: "School-based mentoring" }).closest("li") as HTMLElement;
    await user.click(within(mentoring).getByRole("button", { name: "Add to shortlist" }));
    expect(within(mentoring).getByRole("alert")).toHaveTextContent("The option couldn't be added to the shortlist. Try again.");
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("disables the shortlist actions while a walk is running", () => {
    renderGrid(false, undefined, { capability_run_id: "x", status: "running", started_at: "2026-10-27T00:00:00Z" });
    for (const button of screen.getAllByRole("button", { name: /shortlist/i })) expect(button).toBeDisabled();
  });

  it("links a tile through to the option card", () => {
    renderGrid();
    const link = screen.getByRole("link", { name: "Youth guarantee" });
    expect(link).toHaveAttribute("href", expect.stringContaining("/options/"));
  });
});

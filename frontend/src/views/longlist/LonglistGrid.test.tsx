import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockLonglist } from "../../mock/fixtures";
import { LonglistGrid } from "./LonglistGrid";
import { PublicViewProvider } from "../publicView";

/** A grid head's name, without its count (round 13: the list's group heading). */
const headName = (header: HTMLElement) => header.querySelector(".uppercase .uppercase")?.textContent ?? header.textContent;

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
  // Round 13 (owner): the grid's heads take the list's group heading, the
  // name in the uppercase Label style in Navy and the count in Meta Grey.
  // Round 13 (owner): the heads take the list's group heading, the name
  // alone, with no count.
  it("heads its columns and rows in the list's group heading style, the name alone", () => {
    renderGrid();
    const head = screen.getAllByRole("columnheader")[1];
    expect(head.querySelector(".uppercase .uppercase")).toHaveClass("text-navy");
    expect(head).not.toHaveTextContent(/options?|shortlisted/);
    const row = screen.getAllByRole("rowheader")[0];
    expect(row.querySelector(".uppercase .uppercase")).toHaveClass("text-navy");
    expect(row).not.toHaveTextContent(/options?|shortlisted/);
  });

  it("lays out rows by lever type (plus Other) and columns by the chosen line, Ambition first", () => {
    renderGrid(true);
    expect(screen.getByRole("row", { name: /Enforce existing powers/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Other/ })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map(headName)).toEqual([
      "Lever",
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
    const heads = screen.getAllByRole("columnheader").map(headName);
    expect(heads).toEqual(["Lever", "Cheaper", "Middle", "Costlier", "Untagged"]);
    // The sanctions regime is marked cheaper; mentoring has no cost mark, so Middle.
    const cellIndex = (name: string) => {
      const cell = screen.getByRole("link", { name }).closest("td") as HTMLElement;
      return Array.from((cell.parentElement as HTMLElement).children).indexOf(cell);
    };
    expect(cellIndex("National sanctions regime")).toBe(heads.indexOf("Cheaper"));
    expect(cellIndex("School-based mentoring")).toBe(heads.indexOf("Middle"));
    expect(cellIndex("Youth guarantee")).toBe(heads.indexOf("Untagged"));
    await pickColumn(user, "Delivery complexity");
    expect(screen.getAllByRole("columnheader").map(headName)).toContain("More complex");
  });

  // Task 055: Potential impact carries a mark (the owner, 2026-10-27).
  it("columns the grid on Potential impact and places options by its mark", async () => {
    const user = userEvent.setup();
    renderGrid(true);
    await pickColumn(user, "Potential impact");
    const heads = screen.getAllByRole("columnheader").map(headName);
    expect(heads).toEqual(["Lever", "Lower", "Middle", "Higher", "Untagged"]);
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
    const heads = screen.getAllByRole("columnheader").map(headName);
    const cell = screen.getByRole("link", { name: "Youth guarantee" }).closest("td") as HTMLElement;
    expect(Array.from((cell.parentElement as HTMLElement).children).indexOf(cell)).toBe(heads.indexOf("Untagged"));
    first.unmount();
    renderGrid(true, (longlist) => {
      for (const option of longlist.options ?? []) {
        option.profile ??= { lines: [], settings: [] };
      }
    });
    expect(screen.queryByRole("columnheader", { name: /^Untagged/ })).not.toBeInTheDocument();
  });

  it("shows Middle in the grid, keeps the old band words out, and builds no compare table", () => {
    const { container } = renderGrid();
    expect(screen.getByRole("columnheader", { name: /^Middle/ })).toBeInTheDocument();
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
    expect(screen.queryByRole("row", { name: /^Convene/ })).not.toBeInTheDocument();
    // Round 13 (owner): under the grid in the row heads' column, "No options
    // for" then each lever on its own line, as heads, not in the table.
    expect(screen.queryByRole("row", { name: /^No options found for/ })).not.toBeInTheDocument();
    const absent = screen.getByRole("group", { name: "No options found for" });
    expect(absent.closest("table")).toBeNull();
    expect(absent).toHaveClass("w-44", "space-y-2");
    // A Line hairline across the grid under its last row, 24 px above the foot.
    expect(absent.parentElement).toHaveClass("border-t", "border-line", "pt-6");
    expect(absent.parentElement).not.toHaveClass("w-44");
    const lines = Array.from(absent.children).map((line) => line.textContent);
    expect(lines[0]).toBe("No options found for");
    expect(lines).toContain("Convene");
    expect(lines).not.toContain("Other");
    expect(lines.join(" ")).not.toMatch(/Enforce existing powers|Regulate/);
    // The words a Body Grey line in sentence case; the
    // names in the heads' style (round 13, owner).
    const [words, ...names] = Array.from(absent.children);
    expect(words).toHaveClass("text-body", "text-grey");
    expect(words).not.toHaveClass("uppercase");
    for (const line of names) expect(line).toHaveClass("uppercase", "text-grey");
  });

  it("hides excluded options until asked", () => {
    renderGrid();
    expect(screen.queryByRole("link", { name: "National sanctions regime" })).not.toBeInTheDocument();
  });

  // Round 10 (finding 6): states in words, no chips; red only on the failure word.
  it("marks an excluded tile with the grey exclude glyph and no in-scope evidence in words", () => {
    const { container } = renderGrid(true);
    const excludedLink = screen.getByRole("link", { name: "National sanctions regime" });
    expect(excludedLink).toHaveClass("text-grey");
    const excludedCell = excludedLink.closest("td") as HTMLElement;
    // Round 13 (owner): no word on an excluded tile; the grey exclude glyph
    // in the toggle's corner, not a control, its exclusion line as the
    // tooltip and its name.
    const tile = excludedLink.closest("li") as HTMLElement;
    expect(within(tile).queryByText("Excluded")).not.toBeInTheDocument();
    expect(within(tile).queryByRole("button")).not.toBeInTheDocument();
    const mark = within(tile).getByTestId("tile-excluded");
    expect(mark).toHaveClass("text-grey", "absolute", "-top-2", "-right-2", "h-10", "w-10");
    expect(mark.querySelector("svg")).toHaveAttribute("width", "24");
    expect(mark).toHaveAccessibleName(/^(Excluded by you|Breaks ")/);
    expect(within(excludedCell).queryByText(/^Excluded$/)).not.toBeInTheDocument();

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
  // their own order; a toggle moves the tile there in place, with no View
  // Transition (round 13, owner: only a new Columns line runs one).
  it("puts the shortlisted first in a cell and moves a tile there in place when it is shortlisted", () => {
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
      expect(start).not.toHaveBeenCalled();
      expect(names()).toEqual(["Cell option 2", "Cell option 3", "Cell option 0", "Cell option 1"]);
      // Show excluded updates in place too; a new Columns line moves the tiles.
      const shown = make([2, 3]);
      rerender(
        <MemoryRouter>
          <LonglistGrid taskId={TASK_ID} longlist={shown} showExcluded />
        </MemoryRouter>,
      );
      expect(start).not.toHaveBeenCalled();
      rerender(
        <MemoryRouter>
          <LonglistGrid taskId={TASK_ID} longlist={shown} showExcluded line="potential_impact" />
        </MemoryRouter>,
      );
      expect(start).toHaveBeenCalledTimes(1);
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
    expect(screen.queryByRole("button", { name: /^(Add to|Remove from) shortlist$/ })).not.toBeInTheDocument();
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
    const held = within(bundle).getByRole("button", { name: "Remove from shortlist" });
    expect(held).toBeEnabled();
    expect(held).toHaveAttribute("aria-pressed", "true");
    const guarantee = screen.getByRole("link", { name: "Youth guarantee" }).closest("li") as HTMLElement;
    expect(within(guarantee).getByRole("button", { name: "Remove from shortlist" })).toBeInTheDocument();
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
    for (const button of screen.getAllByRole("button", { name: /^(Add to|Remove from) shortlist$/ })) expect(button).toBeDisabled();
  });

  it("links a tile through to the option card", () => {
    renderGrid();
    const link = screen.getByRole("link", { name: "Youth guarantee" });
    expect(link).toHaveAttribute("href", expect.stringContaining("/options/"));
  });
});

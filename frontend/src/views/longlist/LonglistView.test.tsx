import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MOCK_OPTION_ID_EXCLUDED, MOCK_OPTION_ID_NO_IN_SCOPE, mockLonglist } from "../../mock/fixtures";
import { GROUP_BY_INFO, LonglistView } from "./LonglistView";
import { PublicViewProvider } from "../publicView";
import {
  MOCK_OPTION_ID_PACKAGE,
} from "../../mock/fixtures";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  usePlan: vi.fn(),
  useRuns: vi.fn(),
  useOptions: vi.fn(),
  useLonglist: vi.fn(),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();
const addMutate = vi.fn();

const shortlistMutate = vi.fn();
const unshortlistMutate = vi.fn();
const suggestMutate = vi.fn();
const patchMutate = vi.fn();

// The finished list reads no live names, but the page asks the stream (round 11).
vi.mock("../../store", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../store")>();
  return { ...actual, useRunStream: vi.fn(() => actual.createInitialRunStreamState()) };
});

vi.mock("../../api/mutations", () => ({
  useAddOption: vi.fn(),
  useOptionVerb: vi.fn(),
  useShortlistVerb: vi.fn(),
  useSuggestMore: vi.fn(),
  usePatchPlan: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

/** The finished list as it opens (round 12, D1: its groups shut). */
function renderClosedLonglist(
  taskOverrides: Partial<{ active_run: unknown }> = {},
  adjust?: (longlist: ReturnType<typeof mockLonglist>) => void,
  runs: { purpose?: string | null; status: string; capability_run_id: string }[] = [],
) {
  vi.mocked(queries.useTask).mockReturnValue(
    {
      data: { name: "NEET task", capability: "options_scoping", active_run: taskOverrides.active_run ?? null },
    } as unknown as ReturnType<
      typeof queries.useTask
    >,
  );
  vi.mocked(queries.usePlan).mockReturnValue(
    { data: { scoping: { question: "How can we cut the NEET rate?" } } } as unknown as ReturnType<typeof queries.usePlan>,
  );
  vi.mocked(mutations.useOptionVerb).mockImplementation(
    (_taskId, verb) =>
      ({ mutate: verb === "exclude" ? excludeMutate : includeMutate, isPending: false }) as unknown as ReturnType<
        typeof mutations.useOptionVerb
      >,
  );
  vi.mocked(mutations.useShortlistVerb).mockImplementation(
    (_taskId, verb) =>
      ({ mutate: verb === "shortlist" ? shortlistMutate : unshortlistMutate, isPending: false }) as unknown as ReturnType<
        typeof mutations.useShortlistVerb
      >,
  );
  vi.mocked(mutations.useSuggestMore).mockReturnValue(
    { mutate: suggestMutate, isPending: false, isError: false } as unknown as ReturnType<typeof mutations.useSuggestMore>,
  );
  vi.mocked(mutations.usePatchPlan).mockReturnValue(
    { mutate: patchMutate, isPending: false, isError: false } as unknown as ReturnType<typeof mutations.usePatchPlan>,
  );
  vi.mocked(queries.useRuns).mockReturnValue({ data: { data: runs } } as unknown as ReturnType<typeof queries.useRuns>);
  // A finished list opened cold: the options read has not answered.
  vi.mocked(queries.useOptions).mockReturnValue({ data: undefined } as unknown as ReturnType<typeof queries.useOptions>);
  vi.mocked(mutations.useAddOption).mockReturnValue(
    { mutate: addMutate, isPending: false } as unknown as ReturnType<typeof mutations.useAddOption>,
  );
  const longlist = mockLonglist();
  adjust?.(longlist);
  vi.mocked(queries.useLonglist).mockReturnValue({ data: longlist } as unknown as ReturnType<typeof queries.useLonglist>);
  return render(
    <PublicViewProvider value={publicLink}>
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
        <Routes>
          <Route path="/tasks/:taskId/result" element={<LonglistView taskId={TASK_ID} longlist={longlist} />} />
        </Routes>
      </MemoryRouter>
    </PublicViewProvider>,
  );
}

/** Whether the next render sits in the public link's view (round 12). */
let publicLink = false;

/** The finished list with its groups opened by "Show all", for the tests
 *  that read rows. */
function renderLonglist(...args: Parameters<typeof renderClosedLonglist>) {
  const rendered = renderClosedLonglist(...args);
  const showAll = screen.queryByRole("button", { name: "Show all" });
  if (showAll !== null) fireEvent.click(showAll);
  return rendered;
}

beforeEach(() => {
  publicLink = false;
  shortlistMutate.mockClear();
  unshortlistMutate.mockClear();
  suggestMutate.mockClear();
  patchMutate.mockClear();
  excludeMutate.mockClear();
  includeMutate.mockClear();
  addMutate.mockClear();
});

describe("LonglistView", () => {
  // Round 10 (finding 2, D2, C4): one title from the build to the finished
  // list, the question under it; no kind label, no "scoping pass" chip.
  it("titles the page Longlist with the plan's question under it, the counts and how it was read", () => {
    renderLonglist();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/^Longlist$/);
    expect(screen.getByText("How can we cut the NEET rate?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "1 excluded" })).toHaveAttribute("href", "#excluded-options");
    // Round 11 (review finding 2): the shortlist the reader assembles is counted.
    expect(screen.getByText(/^4 options in 2 themes/)).toHaveTextContent(
      "4 options in 2 themes and 2 levers · 2 shortlisted · 1 excluded · 1 with no in-scope evidence",
    );
    // At the list's foot, not over it (review finding 22).
    expect(screen.getByText("Read from titles and abstracts")).toBeInTheDocument();
    expect(screen.queryByText("scoping pass")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Longlist$/i, { selector: "p" })).not.toBeInTheDocument();
  });

  // Task 046, amendment 4 (R83): no "0 excluded"; the excluded part is a link in list mode, text in grid mode.
  it("leaves the excluded part out of the header when none is excluded", () => {
    renderLonglist({}, (longlist) => {
      longlist.counts.excluded = 0;
    });
    expect(screen.getByText(/^4 options in 2 themes/)).toHaveTextContent(
      "4 options in 2 themes and 2 levers · 2 shortlisted · 1 with no in-scope evidence",
    );
    expect(screen.queryByText(/excluded/)).not.toBeInTheDocument();
  });

  it("shows the excluded part as plain text in grid mode", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: "Grid" }));
    expect(screen.queryByRole("link", { name: "1 excluded" })).not.toBeInTheDocument();
    expect(screen.getByText(/^4 options in 2 themes/)).toHaveTextContent("· 1 excluded ·");
  });

  // Round 12, D1 (owner: "the groups should be collapsed by default"): the
  // finished list opens on the count line and every group heading shut with
  // its count; Show all in the controls row opens them, Hide all folds them.
  it("opens with every group shut, each heading with its count, and Show all opens them", async () => {
    const user = userEvent.setup();
    renderClosedLonglist();
    expect(screen.queryByText("School-based mentoring")).not.toBeInTheDocument();
    const theme = screen.getByRole("button", { name: /^Conditionality and support \d+ options?$/ });
    expect(theme).toHaveAttribute("aria-expanded", "false");
    await user.click(screen.getByRole("button", { name: "Show all" }));
    expect(screen.getByText("School-based mentoring")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Conditionality and support/ })).toHaveAttribute("aria-expanded", "true");
    await user.click(screen.getByRole("button", { name: "Hide all" }));
    expect(screen.queryByText("School-based mentoring")).not.toBeInTheDocument();
  });

  // Round 12 (owner): a group's count and its Show / Hide stand at the right
  // of the heading's line, the count in Meta Grey, the control on the edge;
  // Show all ends the controls row on the same edge.
  it("puts the count and then Show / Hide at the heading line's right, and Show all last in the controls row", () => {
    renderClosedLonglist();
    const heading = screen.getByRole("button", { name: /^A universal offer 1 option$/ });
    const parts = Array.from(heading.children);
    expect(parts).toHaveLength(3);
    expect(parts[0]).toHaveTextContent(/^A universal offer$/);
    expect(parts[0]).toHaveClass("flex-1");
    expect(parts[1]).toHaveTextContent(/^1 option$/);
    expect(parts[1]).toHaveClass("text-meta", "text-grey", "text-right");
    expect(parts[2]).toHaveTextContent(/^Show$/);
    const showAll = screen.getByRole("button", { name: "Show all" });
    expect(showAll.nextElementSibling).toBeNull();
    // Round 12 (owner): the name in Navy, the count Grey; no contents
    // sidebar, the list on the page's full column.
    expect(parts[0]).toHaveClass("text-navy");
    expect(screen.queryByRole("navigation", { name: /contents/i })).toBeNull();
    expect(document.querySelector(".longlist-paper")).toHaveClass("md:max-w-[1180px]");
    // Round 12 (owner): a Line hairline above and below the controls row.
    expect(screen.getByTestId("longlist-controls")).toHaveClass("border-y", "border-line", "py-3");
  });

  // Round 12 (owner): what a theme and a lever are, in an "i" beside Group
  // by; no intro sentence on the page.
  it("says what a theme and a lever are in the i beside Group by", async () => {
    renderClosedLonglist();
    const info = screen.getByRole("button", { name: "What a theme and a lever are" });
    expect(info).toHaveClass("size-6");
    expect(GROUP_BY_INFO).toEqual([
      "Theme: a group of options that work in a similar way.",
      "Lever: the kind of action government takes.",
    ]);
    act(() => info.focus());
    for (const line of GROUP_BY_INFO) expect((await screen.findAllByText(line)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^Theme: a group/, { selector: "main p" })).toBeNull();
  });

  it("gathers excluded options in one collapsed section at the end, headed Excluded with its count", async () => {
    const user = userEvent.setup();
    renderLonglist();
    expect(screen.queryByText("National sanctions regime")).not.toBeInTheDocument();
    const heading = screen.getByRole("button", { name: /^Excluded 1 option$/ });
    await user.click(heading);
    expect(screen.getByText("National sanctions regime")).toBeInTheDocument();
  });

  // Round 11 (review finding 3): a theme heading says its count, not its instruments.
  it("tags each row with its lever only, no mark and no ambition word, and counts the theme's options", async () => {
    renderLonglist();
    expect(screen.getByRole("button", { name: /^A universal offer 1 option$/ })).toBeInTheDocument();
    expect(screen.queryByText(/regulation only/)).toBeNull();
    const row = screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement;
    expect(within(row).getByText("Regulate")).toBeInTheDocument();
    expect(row).not.toHaveTextContent(/Smaller|Bigger|Cheaper|Costlier|Middle|Do minimum|Incremental|Structural/);
  });

  it("groups by lever type, with the theme on each row, and offers no ambition grouping", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(within(screen.getByRole("group", { name: "Group by" })).getByRole("button", { name: "Lever type" }));
    expect(screen.getByRole("button", { name: /^Provide a service 1 option$/ })).toBeInTheDocument();
    expect(screen.getByText("Deliver or fund a service or programme directly to people.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Conditionality and support/ })).not.toBeInTheDocument();
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    expect(within(row).getByText("Conditionality and support")).toBeInTheDocument();
    const groupBy = screen.getByRole("group", { name: "Group by" });
    expect(within(groupBy).getAllByRole("button").map((button) => button.textContent)).toEqual(["Theme", "Lever type"]);
    expect(screen.queryByRole("button", { name: /^Untagged/ })).not.toBeInTheDocument();
  });

  it("keeps the retired words and 'Middle' out of the list", async () => {
    const { container } = renderLonglist();
    for (const banned of [/less than most/i, /like most/i, /more than most/i, /do minimum/i, /incremental/i, /structural/i, /Middle/]) {
      expect(container).not.toHaveTextContent(banned);
    }
  });

  // Task 046, amendment 4 (R84): the list has no facet chips and no match line.
  it("has no Setting, Where tried, Who can act or Tried on facet and no match line", () => {
    renderLonglist();
    for (const name of ["Setting", "Where tried", "Who can act", "Tried on", "Measures"]) {
      expect(screen.queryByRole("group", { name })).not.toBeInTheDocument();
    }
    expect(screen.queryByText(/options? match/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No option matches/)).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Group by" })).toBeInTheDocument();
  });

  // R85; round 11 (review finding 4): the grey line carries the signal's
  // first part only; the rest is the card's.
  it("carries the evidence signal's first part on the grey line, without a document count part", async () => {
    renderLonglist({}, (longlist) => {
      const mentoring = (longlist.options ?? []).find((o) => o.name === "School-based mentoring");
      if (mentoring) {
        mentoring.document_count = 3;
        mentoring.evaluated_count = 0;
      }
    });
    const rich = within(screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement);
    expect(rich.getByText("5 documents evaluated it")).toBeInTheDocument();
    expect(rich.queryByText("4 more describe it")).toBeNull();
    expect(rich.queryByText("Measures 2 of your 2 outcomes")).toBeNull();
    expect(rich.queryByText("9 documents")).not.toBeInTheDocument();
    const bare = within(screen.getByText("School-based mentoring").closest("li") as HTMLElement);
    expect(bare.getByText("No evaluations, 3 documents describe it")).toBeInTheDocument();
    expect(bare.queryByText("3 documents")).not.toBeInTheDocument();
  });

  it("keeps the list's own words free of 'studies', 'serves' and 'aimed at'", async () => {
    const user = userEvent.setup();
    const { container } = renderLonglist();
    await user.click(screen.getByRole("button", { name: /^Excluded/ }));
    expect(container).not.toHaveTextContent(/\bstudies\b|\bserves\b|aimed at/i);
  });

  it("summarises a collapsed theme with its description and option names, plus a No theme section", () => {
    renderLonglist();
    expect(
      screen.getByText("Options that attach an obligation or targeted help to the existing offer."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /No theme/ })).toBeInTheDocument();
  });

  it("an excluded row shows its evidence and exclusion reason; its relation is the card's", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: /^Excluded/ }));
    const row = screen.getByText("National sanctions regime").closest("li");
    expect(row).not.toBeNull();
    const scoped = within(row as HTMLElement);
    expect(scoped.getByText("3 documents evaluated it")).toBeInTheDocument();
    expect(scoped.queryByText("6 documents")).not.toBeInTheDocument();
    // Round 12 (owner): the exclusion in the meta line's grey, who set it
    // aside first, no red word; the row keeps every other row's sizes.
    expect(scoped.queryByText("Excluded:")).not.toBeInTheDocument();
    const exclusion = scoped.getByText(/^Breaks "Only include options a local authority can fund directly" · /);
    expect(exclusion).toHaveClass("text-meta", "text-grey");
    expect(within(row as HTMLElement).getByRole("link", { name: "National sanctions regime" }).closest("p")).toHaveClass("text-body");
    expect(scoped.queryByText("part of Universal youth offer bundle")).toBeNull();
  });

  // Round 11 (review finding 4): relations and origin words are the card's.
  it("shows the added-by-you entrant's no-documents signal and leaves relations and origin to the card", async () => {
    renderLonglist();
    const packageRow = screen.getByText("Universal youth offer bundle").closest("li");
    expect(within(packageRow as HTMLElement).queryByText("includes National sanctions regime")).toBeNull();
    const addedRow = screen.getByText("Youth guarantee").closest("li");
    expect(within(addedRow as HTMLElement).getByText("No documents yet")).toBeInTheDocument();
    expect(within(addedRow as HTMLElement).queryByText("added by you")).toBeNull();
  });

  it("Exclude asks for a reason and posts once", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    const input = within(row).getByPlaceholderText("Why exclude this option?");
    await user.type(input, "Duplicates the mentoring pilot");
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    expect(excludeMutate).toHaveBeenCalledTimes(1);
    expect(excludeMutate).toHaveBeenCalledWith(
      { optionId: MOCK_OPTION_ID_NO_IN_SCOPE, reason: "Duplicates the mentoring pilot" },
      expect.anything(),
    );
  });

  // Deviation 46 (owner, 2026-09-24): the reason is optional on the button too.
  it("Exclude with a blank reason posts no reason", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    expect(excludeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_NO_IN_SCOPE }, expect.anything());
  });

  // F15: a refused exclude says why, next to its row.
  it("shows the conflict sentence when an exclude is refused", async () => {
    excludeMutate.mockImplementationOnce((_input, options: { onError: (error: unknown) => void }) =>
      options.onError(Object.assign(new Error("busy"), { code: "run_active", status: 409 })),
    );
    const user = userEvent.setup();
    renderLonglist();
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    expect(within(row).getByRole("alert")).toHaveTextContent(/A run is already active/);
  });

  // F15: nothing to exclude or include while a walk runs.
  it("disables Exclude and Include again while a walk is active", async () => {
    const user = userEvent.setup();
    renderLonglist({ active_run: { capability_run_id: "run-1", status: "running", started_at: "now" } });
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    expect(within(row).getByRole("button", { name: "Exclude" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /^Excluded/ }));
    const excludedRow = screen.getByText("National sanctions regime").closest("li") as HTMLElement;
    expect(within(excludedRow).getByRole("button", { name: "Include again" })).toBeDisabled();
  });

  // Round 10 (finding 6): the meta line is whole fields, the middot bound
  // to the field before it, so no wrapped line starts with one; the
  // no-in-scope state is words at its end, not a yellow chip.
  it("binds each middot to the field before it and ends with No in-scope evidence as words", () => {
    renderLonglist();
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    const fields = [...row.querySelectorAll("p > span.inline-block, p > span > span.inline-block")];
    expect(fields.length).toBeGreaterThan(2);
    for (const field of fields.slice(0, -1)) expect(field.textContent).toMatch(/ ·,$/);
    expect(fields[fields.length - 1].textContent).toBe("No in-scope evidence");
    expect(row.querySelector("[class*='text-[11.5px]']")).toBeNull();
  });

  it("Include again posts once for an excluded option", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: /^Excluded/ }));
    const row = screen.getByText("National sanctions regime").closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Include again" }));
    expect(includeMutate).toHaveBeenCalledTimes(1);
    expect(includeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_EXCLUDED }, expect.anything());
  });

  it("Add an option posts once and is disabled while a walk is active", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const input = screen.getByLabelText("Add an option");
    await user.type(input, "A new option");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(addMutate).toHaveBeenCalledTimes(1);
    expect(addMutate).toHaveBeenCalledWith({ text: "A new option" }, expect.anything());
  });

  it("disables Add an option while a walk is active", () => {
    renderLonglist({ active_run: { capability_run_id: "run-1", status: "running", started_at: "now" } });
    expect(screen.getByLabelText("Add an option")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
  });

  it("toggles to the reduced grid, where excluded options need the Show excluded toggle", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: "Grid" }));
    expect(screen.getByRole("columnheader", { name: "Smaller" })).toBeInTheDocument();
    expect(screen.queryByText("Conditionality and support")).not.toBeInTheDocument();
    expect(screen.queryByText("National sanctions regime")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Show excluded/ }));
    expect(screen.getByText("National sanctions regime")).toBeInTheDocument();
  });
});

describe("LonglistView — the view switches (round 10, findings 3 and 13)", () => {
  it("draws Group by and List / Grid as outline switches with aria-pressed, never a filled chip", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const groupBy = within(screen.getByRole("group", { name: "Group by" }));
    expect(groupBy.getByRole("button", { name: "Theme" })).toHaveAttribute("aria-pressed", "true");
    expect(groupBy.getByRole("button", { name: "Lever type" })).toHaveAttribute("aria-pressed", "false");
    for (const button of [...groupBy.getAllByRole("button"), ...within(screen.getByRole("group", { name: "View" })).getAllByRole("button")]) {
      expect(button.className).toContain("border");
      expect(button.className).not.toMatch(/bg-blue/);
    }
    await user.click(groupBy.getByRole("button", { name: "Lever type" }));
    expect(groupBy.getByRole("button", { name: "Lever type" })).toHaveAttribute("aria-pressed", "true");
  });

  it("offers no grid on a phone", () => {
    const matchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })) as unknown as typeof window.matchMedia;
    try {
      renderLonglist();
      expect(screen.queryByRole("group", { name: "View" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Grid" })).not.toBeInTheDocument();
      expect(screen.getByRole("group", { name: "Group by" })).toBeInTheDocument();
    } finally {
      window.matchMedia = matchMedia;
    }
  });
});

describe("LonglistView — the shortlist toggle on rows (task 055; round 10, finding 6)", () => {
  it("says the state in words, pressed on a row that holds a place", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const held = within(screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement).getByRole("button", {
      name: "Shortlisted",
    });
    expect(held).toHaveAttribute("aria-pressed", "true");
    const open = within(screen.getByText("School-based mentoring").closest("li") as HTMLElement).getByRole("button", {
      name: "Add to shortlist",
    });
    expect(open).toHaveAttribute("aria-pressed", "false");
    await user.click(held);
    expect(unshortlistMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_PACKAGE }, expect.anything());
    await user.click(open);
    expect(shortlistMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_NO_IN_SCOPE }, expect.anything());
    // The place word left the meta line: the toggle says it.
    expect(screen.queryByText("Policy Atlas's pick")).not.toBeInTheDocument();
  });

  // Round 12 (owner): the shortlisted lead each group, the rest after them
  // in their own order; a toggle moves the row there with the regroup's
  // View Transition, never a blank.
  it("puts the shortlisted first in every group", () => {
    renderLonglist();
    const groups = screen.getAllByRole("list").filter((list) => list.closest("section") !== null);
    expect(groups.length).toBeGreaterThan(0);
    for (const group of groups) {
      const held = Array.from(group.children).map(
        (row) => within(row as HTMLElement).queryByRole("button", { name: "Shortlisted" }) !== null,
      );
      expect(held).toEqual([...held].sort((a, b) => Number(b) - Number(a)));
    }
  });

  it("moves a row to the head of its group when it is shortlisted, through the regroup's View Transition", () => {
    const start = vi.fn((update: () => void) => {
      update();
      return { finished: Promise.resolve() };
    });
    Object.defineProperty(document, "startViewTransition", { value: start, configurable: true, writable: true });
    try {
      // Two options in one theme, none on the shortlist.
      const twoInATheme = (longlist: ReturnType<typeof mockLonglist>) => {
        const theme = (longlist.themes ?? [])[0];
        theme.option_ids = [...(theme.option_ids ?? []), MOCK_OPTION_ID_PACKAGE];
        longlist.themes = [theme, ...(longlist.themes ?? []).slice(1)];
      };
      const { rerender } = renderLonglist({}, (longlist) => {
        twoInATheme(longlist);
        for (const option of longlist.options ?? []) option.shortlist = null;
      });
      const group = screen
        .getAllByRole("list")
        .find((list) => list.closest("section") !== null && list.children.length >= 2) as HTMLElement;
      const names = () => Array.from(group.children).map((row) => within(row as HTMLElement).getAllByRole("link")[0].textContent);
      const before = names();
      const last = before[before.length - 1] as string;
      const next = mockLonglist();
      twoInATheme(next);
      for (const option of next.options ?? []) {
        option.shortlist = option.name === last ? { state: "added_by_you", reason: null } : null;
      }
      vi.mocked(queries.useLonglist).mockReturnValue({ data: next } as unknown as ReturnType<typeof queries.useLonglist>);
      rerender(
        <PublicViewProvider value={false}>
          <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
            <Routes>
              <Route path="/tasks/:taskId/result" element={<LonglistView taskId={TASK_ID} longlist={next} />} />
            </Routes>
          </MemoryRouter>
        </PublicViewProvider>,
      );
      expect(start).toHaveBeenCalledTimes(1);
      expect(names()).toEqual([last, ...before.slice(0, -1)]);
    } finally {
      Reflect.deleteProperty(document, "startViewTransition");
    }
  });

  // Round 12 (owner): the public link reads the list and changes nothing;
  // the group controls stay.
  it("is read-only on the public link: the held word, no toggle, Exclude, Include again or Add an option", async () => {
    publicLink = true;
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: /^Excluded/ }));
    expect(screen.queryByRole("button", { name: /shortlist/i })).not.toBeInTheDocument();
    expect(screen.getAllByText("Shortlisted").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Exclude" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Include again" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Add an option")).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Group by" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hide all" })).toBeInTheDocument();
  });

  it("disables every toggle while a walk runs", () => {
    renderLonglist({ active_run: { capability_run_id: "x", status: "running", started_at: "2026-10-27T00:00:00Z" } });
    for (const button of screen.getAllByRole("button", { name: /shortlist/i })) expect(button).toBeDisabled();
  });
});

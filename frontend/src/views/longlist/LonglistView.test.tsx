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
import { TOGGLE_GLYPH_SIZE } from "./optionActions";
import { REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";

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
    // Round 13 (owner): no "Read from titles and abstracts" note on the page.
    expect(screen.queryByText(/Read from titles and abstracts/)).not.toBeInTheDocument();
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

  // Round 13 (owner): "View as" before the switch, the grid's Columns on the
  // same row, and the lever types with no option said plainly in both views.
  it("labels the switch View as, puts Columns on the left in the grid, and names the levers with no option", async () => {
    const user = userEvent.setup();
    renderLonglist();
    expect(screen.getByText("View as")).toHaveClass("text-meta", "text-grey");
    expect(screen.queryByRole("combobox", { name: "Columns" })).not.toBeInTheDocument();
    await user.click(within(screen.getByRole("group", { name: "View as" })).getByRole("button", { name: "Grid" }));
    const columns = screen.getByRole("combobox", { name: "Columns" });
    const controls = screen.getByTestId("longlist-controls");
    // Its visible label before it, the controls row's label style (round 13, owner).
    const columnsLabel = within(controls).getByText("Columns");
    expect(columnsLabel).toHaveClass("text-meta", "text-grey");
    expect(columnsLabel.compareDocumentPosition(columns) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Columns on the left; the view switch keeps the right edge in both views.
    expect(controls.firstElementChild?.contains(columns)).toBe(true);
    expect(controls.lastElementChild?.contains(screen.getByRole("group", { name: "View as" }))).toBe(true);
    // Round 13 (owner): listed under the grid, as heads.
    const absent = screen.getByRole("group", { name: "No options found for" });
    expect(absent).not.toHaveTextContent(/Other/);
    await user.click(within(screen.getByRole("group", { name: "View as" })).getByRole("button", { name: "List" }));
    expect(controls.lastElementChild?.contains(screen.getByRole("group", { name: "View as" }))).toBe(true);
    await user.click(within(screen.getByRole("group", { name: "Group by" })).getByRole("button", { name: "Lever" }));
    // The lever grouping's last heading, the names one Grey line under it.
    // Round 13 (owner): the words a Body Grey line, not a heading.
    expect(screen.queryByRole("heading", { name: "No options found for" })).not.toBeInTheDocument();
    const words = within(screen.getByRole("region", { name: "No options found for" })).getByTestId("no-options-for");
    expect(words).toHaveClass("text-body", "text-grey");
    expect(words).not.toHaveClass("uppercase");
    expect(words.nextElementSibling).toHaveClass("uppercase", "text-grey");
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
    const heading = screen.getByRole("button", { name: /^A universal offer 1 option · 1 shortlisted$/ });
    const parts = Array.from(heading.children);
    expect(parts).toHaveLength(3);
    expect(parts[0]).toHaveTextContent(/^A universal offer$/);
    expect(parts[0]).toHaveClass("flex-1");
    expect(parts[1]).toHaveTextContent(/^1 option · 1 shortlisted$/);
    expect(parts[1]).toHaveClass("text-meta", "text-grey", "text-right");
    expect(parts[2]).toHaveTextContent(/^Show$/);
    // Round 13 (owner): Show all with Group by on the left; View as on the right edge.
    const showAll = screen.getByRole("button", { name: "Show all" });
    // Round 13 (owner): Show all at the count line's right, under the
    // controls row and inside the hairlines.
    const countLine = screen.getByText(/^4 options in 2 themes/);
    expect(showAll.parentElement).toBe(countLine.parentElement);
    expect(showAll.previousElementSibling).toBe(countLine);
    const block = screen.getByTestId("longlist-controls-block");
    expect(block.firstElementChild).toBe(screen.getByTestId("longlist-controls"));
    expect(block.lastElementChild).toBe(countLine.parentElement);
    // Round 12 (owner): the name in Navy, the count Grey; no contents
    // sidebar, the list on the page's full column.
    expect(parts[0]).toHaveClass("text-navy");
    expect(screen.queryByRole("navigation", { name: /contents/i })).toBeNull();
    expect(document.querySelector(".longlist-paper")).toHaveClass("md:max-w-[1180px]");
    // Round 12 (owner): a Line hairline above and below the controls row.
    expect(screen.getByTestId("longlist-controls-block")).toHaveClass("border-y", "border-line", "py-3");
  });

  // Round 12 (owner): what a theme and a lever are, in an "i" beside Group
  // by; no intro sentence on the page.
  it("says what a theme and a lever are in the i beside Group by", async () => {
    renderClosedLonglist();
    const info = screen.getByRole("button", { name: "What a theme and a lever are" });
    expect(info).toHaveClass("size-6");
    expect(GROUP_BY_INFO).toEqual([
      "Theme: a group of options that work in a similar way.",
      "Lever: the kind of action that the policy takes.",
    ]);
    act(() => info.focus());
    for (const line of GROUP_BY_INFO) expect((await screen.findAllByText(line)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^Theme: a group/, { selector: "main p" })).toBeNull();
  });

  // Round 13 (owner): Excluded is a section, its heading at the page's
  // section size with its description; inside it only groups, the options
  // excluded one by one under "Options", shut like the others.
  it("ends with an Excluded section of groups, the single exclusions under Options, shut", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const section = screen.getByRole("region", { name: "Excluded" });
    const heading = within(section).getByRole("heading", { level: 2, name: "Excluded" });
    expect(heading).toHaveClass(...REPORT_SECTION_HEADING_CLASS.split(" "));
    expect(heading).not.toHaveClass("uppercase");
    expect(heading.nextElementSibling).toHaveTextContent("Excluded from shortlisting by a constraint or by you.");
    expect(section).toHaveClass("border-t", "border-line", "mt-8", "pt-8");
    // No loose rows: every row sits in a group.
    expect(Array.from(section.children).filter((child) => child.tagName === "UL")).toHaveLength(0);
    expect(screen.queryByText("National sanctions regime")).not.toBeInTheDocument();
    const options = within(section).getByRole("button", { name: /^Options 1 option/ });
    expect(options).toHaveAttribute("aria-expanded", "false");
    expect(options.closest("h3")).not.toBeNull();
    await user.click(options);
    expect(screen.getByText("National sanctions regime")).toBeInTheDocument();
  });

  // Round 11 (review finding 3): a theme heading says its count, not its instruments.
  it("tags each row with its lever only, no mark and no ambition word, and counts the theme's options", async () => {
    renderLonglist();
    expect(screen.getByRole("button", { name: /^A universal offer 1 option · 1 shortlisted$/ })).toBeInTheDocument();
    expect(screen.queryByText(/regulation only/)).toBeNull();
    const row = screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement;
    expect(within(row).getByText("Regulate")).toBeInTheDocument();
    expect(row).not.toHaveTextContent(/Smaller|Bigger|Cheaper|Costlier|Middle|Do minimum|Incremental|Structural/);
  });

  it("groups by lever type, with the theme on each row, and offers no ambition grouping", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(within(screen.getByRole("group", { name: "Group by" })).getByRole("button", { name: "Lever" }));
    expect(screen.getByRole("button", { name: /^Provide a service 1 option$/ })).toBeInTheDocument();
    expect(screen.getByText("Deliver or fund a service or programme directly to people.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Conditionality and support/ })).not.toBeInTheDocument();
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    expect(within(row).getByText("Conditionality and support")).toBeInTheDocument();
    const groupBy = screen.getByRole("group", { name: "Group by" });
    expect(within(groupBy).getAllByRole("button").map((button) => button.textContent)).toEqual(["Theme", "Lever"]);
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
  // Round 13 (owner: avoid information overload): the grey line carries the
  // document count alone; the evaluated / describe split is the card's.
  it("carries the document count alone on the grey line, not the evaluated / describe split", async () => {
    renderLonglist({}, (longlist) => {
      const mentoring = (longlist.options ?? []).find((o) => o.name === "School-based mentoring");
      if (mentoring) {
        mentoring.document_count = 3;
        mentoring.evaluated_count = 0;
      }
    });
    const rich = within(screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement);
    expect(rich.getByText("9 documents")).toBeInTheDocument();
    expect(rich.queryByText(/evaluated it|describe it/)).toBeNull();
    const bare = within(screen.getByText("School-based mentoring").closest("li") as HTMLElement);
    expect(bare.getByText("3 documents")).toBeInTheDocument();
    expect(bare.queryByText(/No evaluations/)).toBeNull();
  });

  it("keeps the list's own words free of 'studies', 'serves' and 'aimed at'", async () => {
    const user = userEvent.setup();
    const { container } = renderLonglist();
    await user.click(screen.getByRole("button", { name: /^Options \d/ }));
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
    await user.click(screen.getByRole("button", { name: /^Options \d/ }));
    const row = screen.getByText("National sanctions regime").closest("li");
    expect(row).not.toBeNull();
    const scoped = within(row as HTMLElement);
    expect(scoped.getByText("6 documents")).toBeInTheDocument();
    expect(scoped.queryByText(/evaluated it/)).not.toBeInTheDocument();
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

  // Round 13 (owner): Exclude leaves the rows; a group heading excludes
  // every included option in it, the reason saying which group.
  it("has no Exclude on a row", () => {
    renderLonglist();
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    expect(within(row).queryByRole("button", { name: /Exclude|Include again|Option actions/ })).not.toBeInTheDocument();
  });

  it("excludes every included option in a theme at once from its heading, the theme as the reason, none twice", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const section = screen.getByRole("button", { name: /^Conditionality and support/ }).closest("section") as HTMLElement;
    // Round 13 (owner): at the open group's foot, not on the heading.
    const heading = within(section).getByRole("heading", { level: 2 });
    expect(within(heading).queryByRole("button", { name: /Exclude/ })).not.toBeInTheDocument();
    // The first line inside the open group, before the rows (round 13, owner).
    const control = within(section).getByRole("button", { name: "Exclude theme" });
    const firstRow = within(section).getAllByRole("listitem")[0];
    expect(control.compareDocumentPosition(firstRow) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // On the description's line, at its right edge (the toggles' column);
    // the box-overlap check with Show / Hide is in the scoping e2e.
    const description = within(section).getByText(/./, { selector: "p.text-grey" });
    expect(description.parentElement).toContainElement(control);
    expect(within(section).getByTestId("edge-action")).toBe(control);
    // The words, then the glyph at the row toggle's size, centred in its 40 px width
    // (one column with the toggles; one constant for both).
    const glyph = within(control).getByTestId("edge-action-glyph");
    expect(control.lastElementChild).toBe(glyph);
    expect(glyph).toHaveClass("w-10");
    expect(glyph).not.toHaveClass("h-10");
    const toggle = within(section).getAllByRole("button", { name: /^(Add to|Remove from) shortlist$/ })[0];
    expect(glyph.querySelector("svg")).toHaveAttribute("width", String(TOGGLE_GLYPH_SIZE));
    expect(toggle.querySelector("svg")).toHaveAttribute("width", String(TOGGLE_GLYPH_SIZE));
    await user.click(control);
    // The theme holds an excluded option and an included one: only the included one is posted.
    expect(excludeMutate).toHaveBeenCalledTimes(1);
    expect(excludeMutate).toHaveBeenCalledWith(
      { optionId: MOCK_OPTION_ID_NO_IN_SCOPE, reason: "with the theme Conditionality and support" },
      expect.anything(),
    );
    expect(within(section).queryByRole("textbox")).not.toBeInTheDocument();
  });


  it("says which group went on each option it set aside", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const section = screen.getByRole("button", { name: /^A universal offer/ }).closest("section") as HTMLElement;
    await user.click(within(section).getByRole("button", { name: "Exclude theme" }));
    expect(excludeMutate).toHaveBeenCalledWith(
      { optionId: MOCK_OPTION_ID_PACKAGE, reason: "with the theme A universal offer" },
      expect.anything(),
    );
  });

  // Round 13 (owner): an excluded theme shows as a group under Excluded,
  // collapsible like an included group and shut by default, its description
  // showing while shut; open, Include again its first line, then its rows
  // reading "Excluded by you" alone; the single exclusions after it.
  it("groups a theme excluded whole under Excluded as a collapsible group, before the single exclusions", async () => {
    const user = userEvent.setup();
    renderLonglist({}, (longlist) => {
      const bundle = (longlist.options ?? []).find((option) => option.option_id === MOCK_OPTION_ID_PACKAGE);
      if (bundle) {
        bundle.state = "excluded";
        bundle.exclusion = { by: "user", constraint: "your decision", reason: "with the theme A universal offer" };
      }
    });
    // No longer a theme of its own on the list: only its group in Excluded.
    const excluded = screen.getByRole("region", { name: "Excluded" });
    for (const button of screen.getAllByRole("button", { name: /^A universal offer/ })) expect(excluded).toContainElement(button);
    // A hairline sets Excluded apart from the groups above it.
    expect(excluded).toHaveClass("border-t", "border-line", "mt-8", "pt-8");
    const toggle = within(excluded).getByRole("button", { name: /^A universal offer/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle.closest("h3")).not.toBeNull();
    expect(toggle).toHaveTextContent(/^A universal offer 1 optionShow$/);
    const group = toggle.closest("section") as HTMLElement;
    // Shut: the description shows, the rows and Include again do not.
    expect(within(group).getByText("A single, non-conditional offer replacing today's patchwork.")).toHaveClass("text-grey");
    expect(within(group).queryByText("Universal youth offer bundle")).not.toBeInTheDocument();
    expect(within(group).queryByRole("button", { name: "Include theme again" })).not.toBeInTheDocument();
    await user.click(toggle);
    // The group's control says what it brings back; an option's stays "Include again".
    const include = within(group).getByRole("button", { name: "Include theme again" });
    expect(within(group).getAllByRole("button", { name: "Include again" }).length).toBeGreaterThan(0);
    const firstRow = within(group).getAllByRole("listitem")[0];
    expect(include.compareDocumentPosition(firstRow) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(group).getByText("Universal youth offer bundle")).toBeInTheDocument();
    // The heading names the theme; the row does not repeat it.
    expect(within(firstRow).getByText(/^Excluded by you/)).toHaveTextContent(/^Excluded by you$/);
    // "Add a reason" is the option card's only (round 13, owner).
    expect(within(excluded).queryByRole("button", { name: "Add a reason" })).not.toBeInTheDocument();
    expect(within(firstRow).queryByText(/with the theme/)).not.toBeInTheDocument();
    // The option excluded one by one lists after the group, under Options.
    await user.click(within(excluded).getByRole("button", { name: /^Options \d/ }));
    const single = within(excluded).getByText("National sanctions regime");
    expect(group.compareDocumentPosition(single) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(group).not.toContainElement(single);
    await user.click(include);
    expect(includeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_PACKAGE }, expect.anything());
  });

  // Round 13 (owner): one row for both states; an excluded row adds only its
  // exclusion line, with Include again on the row.
  it("gives an excluded row the included row's lines plus its exclusion line and Include again", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: /^Options \d/ }));
    const row = screen.getByText("National sanctions regime").closest("li") as HTMLElement;
    // No theme on the grey line, as an included row under a theme.
    expect(row).not.toHaveTextContent("Conditionality and support");
    expect(within(row).getByText("6 documents")).toBeInTheDocument();
    // Include again on the action column, the group's Exclude's form: words,
    // then the undo glyph at the row toggle's size; not on the exclusion line.
    const include = within(row).getByRole("button", { name: "Include again" });
    expect(include).toHaveAttribute("data-testid", "edge-action");
    expect(include.lastElementChild?.querySelector("svg")).toHaveAttribute("width", String(TOGGLE_GLYPH_SIZE));
    expect(within(row).getByText(/^Excluded by you|^Breaks/)).not.toContainElement(include);
    await user.click(include);
    expect(includeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_EXCLUDED }, expect.anything());
  });

  // Round 13 (owner): a reason given on the option card reads as text on
  // the row's exclusion line; the row offers no form of its own.
  it("shows a reason given on the card as text on the row, under the group's heading without its words", async () => {
    const user = userEvent.setup();
    renderLonglist({}, (longlist) => {
      const bundle = (longlist.options ?? []).find((option) => option.option_id === MOCK_OPTION_ID_PACKAGE);
      if (bundle) {
        bundle.state = "excluded";
        bundle.exclusion = { by: "user", constraint: "your decision", reason: "with the theme A universal offer: Too costly" };
      }
    });
    await user.click(screen.getByRole("button", { name: /^A universal offer/ }));
    const row = screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement;
    expect(within(row).getByText(/^Excluded by you/)).toHaveTextContent(/^Excluded by you · Too costly$/);
    expect(within(row).queryByRole("button", { name: "Add a reason" })).not.toBeInTheDocument();
    expect(within(row).queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("disables a group's Exclude while a walk is active", () => {
    renderLonglist({ active_run: { capability_run_id: "run-1", status: "running", started_at: "now" } });
    const section = screen.getByRole("button", { name: /^Conditionality and support/ }).closest("section") as HTMLElement;
    expect(within(section).getByRole("button", { name: "Exclude theme" })).toBeDisabled();
  });

  it("offers nothing on a shut group", () => {
    renderClosedLonglist();
    const section = screen.getByRole("button", { name: /^Conditionality and support/ }).closest("section") as HTMLElement;
    expect(within(section).queryByRole("button", { name: /Exclude|Include( theme| lever)? again/ })).not.toBeInTheDocument();
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
    expect(screen.getByRole("columnheader", { name: /^Smaller/ })).toBeInTheDocument();
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
    expect(groupBy.getByRole("button", { name: "Lever" })).toHaveAttribute("aria-pressed", "false");
    for (const button of [...groupBy.getAllByRole("button"), ...within(screen.getByRole("group", { name: "View as" })).getAllByRole("button")]) {
      expect(button.className).toContain("border");
      expect(button.className).not.toMatch(/bg-blue/);
    }
    await user.click(groupBy.getByRole("button", { name: "Lever" }));
    expect(groupBy.getByRole("button", { name: "Lever" })).toHaveAttribute("aria-pressed", "true");
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
      expect(screen.queryByRole("group", { name: "View as" })).not.toBeInTheDocument();
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
      name: "Remove from shortlist",
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
        (row) => within(row as HTMLElement).queryByRole("button", { name: "Remove from shortlist" }) !== null,
      );
      expect(held).toEqual([...held].sort((a, b) => Number(b) - Number(a)));
    }
  });

  // Round 13 (owner): a shortlist toggle updates in place; only a regroup
  // runs the View Transition (it glitched over the header).
  it("moves a row to the head of its group when it is shortlisted, in place with no View Transition", () => {
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
      expect(start).not.toHaveBeenCalled();
      expect(names()).toEqual([last, ...before.slice(0, -1)]);
      // A whole theme excluded is a regroup: it moves.
      const regrouped = mockLonglist();
      twoInATheme(regrouped);
      const theme = (regrouped.themes ?? [])[0];
      for (const option of regrouped.options ?? []) {
        if ((theme.option_ids ?? []).includes(option.option_id)) {
          option.state = "excluded";
          option.exclusion = { by: "user", constraint: "your decision", reason: `with the theme ${theme.name}` };
        }
      }
      vi.mocked(queries.useLonglist).mockReturnValue({ data: regrouped } as unknown as ReturnType<typeof queries.useLonglist>);
      rerender(
        <PublicViewProvider value={false}>
          <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
            <Routes>
              <Route path="/tasks/:taskId/result" element={<LonglistView taskId={TASK_ID} longlist={regrouped} />} />
            </Routes>
          </MemoryRouter>
        </PublicViewProvider>,
      );
      expect(start).toHaveBeenCalledTimes(1);
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
    await user.click(screen.getByRole("button", { name: /^Options \d/ }));
    expect(screen.queryByRole("button", { name: /^(Add to|Remove from) shortlist$/ })).not.toBeInTheDocument();
    expect(screen.getAllByText("Shortlisted").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /^(Exclude|Include again)$/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Add an option")).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Group by" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hide all" })).toBeInTheDocument();
  });

  it("disables every toggle while a walk runs", () => {
    renderLonglist({ active_run: { capability_run_id: "x", status: "running", started_at: "2026-10-27T00:00:00Z" } });
    for (const button of screen.getAllByRole("button", { name: /^(Add to|Remove from) shortlist$/ })) expect(button).toBeDisabled();
  });
});

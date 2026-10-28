import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MOCK_OPTION_ID_EXCLUDED, MOCK_OPTION_ID_NO_IN_SCOPE, mockLonglist } from "../../mock/fixtures";
import { LonglistView } from "./LonglistView";
import { rowMetaParts } from "./longlistPresentation";
import {
  MOCK_OPTION_ID_PACKAGE,
} from "../../mock/fixtures";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  usePlan: vi.fn(),
  useRuns: vi.fn(),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();
const addMutate = vi.fn();

const shortlistMutate = vi.fn();
const unshortlistMutate = vi.fn();
const suggestMutate = vi.fn();
const patchMutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useAddOption: vi.fn(),
  useOptionVerb: vi.fn(),
  useShortlistVerb: vi.fn(),
  useSuggestMore: vi.fn(),
  usePatchPlan: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderLonglist(
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
  vi.mocked(mutations.useAddOption).mockReturnValue(
    { mutate: addMutate, isPending: false } as unknown as ReturnType<typeof mutations.useAddOption>,
  );
  const longlist = mockLonglist();
  adjust?.(longlist);
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
      <Routes>
        <Route path="/tasks/:taskId/result" element={<LonglistView taskId={TASK_ID} longlist={longlist} />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  shortlistMutate.mockClear();
  unshortlistMutate.mockClear();
  suggestMutate.mockClear();
  patchMutate.mockClear();
  excludeMutate.mockClear();
  includeMutate.mockClear();
  addMutate.mockClear();
});

describe("LonglistView", () => {
  it("renders the depth tag, the plan's question as the title and the counts line", () => {
    renderLonglist();
    const tag = screen.getByText("scoping pass");
    expect(tag).toHaveAttribute(
      "title",
      "Screened on titles and abstracts · nothing read in full · document set not confirmed",
    );
    expect(screen.getByRole("heading", { name: "How can we cut the NEET rate?" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "1 excluded" })).toHaveAttribute("href", "#excluded-options");
    expect(screen.getByText(/^4 options in 2 themes/)).toHaveTextContent(
      "4 options in 2 themes · 1 excluded · 1 with no in-scope evidence",
    );
  });

  // Task 046, amendment 4 (R83): no "0 excluded"; the excluded part is a link in list mode, text in grid mode.
  it("leaves the excluded part out of the header when none is excluded", () => {
    renderLonglist({}, (longlist) => {
      longlist.counts.excluded = 0;
    });
    expect(screen.getByText(/^4 options in 2 themes/)).toHaveTextContent(
      "4 options in 2 themes · 1 with no in-scope evidence",
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

  it("opens with every theme collapsed and Expand all opens them", async () => {
    const user = userEvent.setup();
    renderLonglist();
    expect(screen.queryByText("School-based mentoring")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Conditionality and support/ })).toHaveAttribute("aria-expanded", "false");
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    expect(screen.getByText("School-based mentoring")).toBeInTheDocument();
  });

  it("gathers excluded options in one collapsed section at the end", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    expect(screen.queryByText("National sanctions regime")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Excluded options/ }));
    expect(screen.getByText("National sanctions regime")).toBeInTheDocument();
  });

  it("tags each row with its lever only, no mark and no ambition word, and names the theme's instruments", async () => {
    const user = userEvent.setup();
    renderLonglist();
    expect(screen.getByRole("button", { name: /A universal offer.*1 option · regulation only/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const row = screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement;
    expect(within(row).getByText("Regulate")).toBeInTheDocument();
    expect(row).not.toHaveTextContent(/Smaller|Bigger|Cheaper|Costlier|Middle|Do minimum|Incremental|Structural/);
  });

  it("groups by lever type, with the theme on each row, and offers no ambition grouping", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(within(screen.getByRole("group", { name: "Group by" })).getByRole("button", { name: "Lever type" }));
    expect(screen.getByRole("button", { name: /^Provide a service.*1 option · 1 theme/ })).toBeInTheDocument();
    expect(screen.getByText("Deliver or fund a service or programme directly to people.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Conditionality and support/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    expect(within(row).getByText("Conditionality and support")).toBeInTheDocument();
    const groupBy = screen.getByRole("group", { name: "Group by" });
    expect(within(groupBy).getAllByRole("button").map((button) => button.textContent)).toEqual(["Theme", "Lever type"]);
    expect(screen.queryByRole("button", { name: /^Untagged/ })).not.toBeInTheDocument();
  });

  it("keeps the retired words and 'Middle' out of the list", async () => {
    const user = userEvent.setup();
    const { container } = renderLonglist();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
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

  // R85: the grey line ends in the evidence signal; the document count is not its own part.
  it("carries the evidence signal on the grey line, without a document count part", async () => {
    const user = userEvent.setup();
    renderLonglist({}, (longlist) => {
      const mentoring = (longlist.options ?? []).find((o) => o.name === "School-based mentoring");
      if (mentoring) {
        mentoring.document_count = 3;
        mentoring.evaluated_count = 0;
      }
    });
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const rich = within(screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement);
    expect(rich.getByText("5 documents evaluated it")).toBeInTheDocument();
    expect(rich.getByText("4 more describe it")).toBeInTheDocument();
    expect(rich.getByText("Evaluated in the United Kingdom")).toBeInTheDocument();
    expect(rich.getByText("Measures 2 of your 2 outcomes")).toBeInTheDocument();
    expect(rich.queryByText("9 documents")).not.toBeInTheDocument();
    const bare = within(screen.getByText("School-based mentoring").closest("li") as HTMLElement);
    expect(bare.getByText("No evaluations, 3 documents describe it")).toBeInTheDocument();
    expect(bare.queryByText("3 documents")).not.toBeInTheDocument();
  });

  it("keeps the list's own words free of 'studies', 'serves' and 'aimed at'", async () => {
    const user = userEvent.setup();
    const { container } = renderLonglist();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    await user.click(screen.getByRole("button", { name: /Excluded options/ }));
    expect(container).not.toHaveTextContent(/\bstudies\b|\bserves\b|aimed at/i);
  });

  it("summarises a collapsed theme with its description and option names, plus a No theme section", () => {
    renderLonglist();
    expect(
      screen.getByText("Options that attach an obligation or targeted help to the existing offer."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /No theme/ })).toBeInTheDocument();
  });

  it("an excluded row shows its count, exclusion reason and relation", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: /Excluded options/ }));
    const row = screen.getByText("National sanctions regime").closest("li");
    expect(row).not.toBeNull();
    const scoped = within(row as HTMLElement);
    expect(scoped.getByText("3 documents evaluated it")).toBeInTheDocument();
    expect(scoped.queryByText("6 documents")).not.toBeInTheDocument();
    expect(
      scoped.getByText('excluded: breaks "Only include options a local authority can fund directly"'),
    ).toBeInTheDocument();
    expect(scoped.getByText("part of Universal youth offer bundle")).toBeInTheDocument();
  });

  it("shows a package's has_part relation and the added-by-you entrant's no-documents signal", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const packageRow = screen.getByText("Universal youth offer bundle").closest("li");
    expect(within(packageRow as HTMLElement).getByText("includes National sanctions regime")).toBeInTheDocument();
    const addedRow = screen.getByText("Youth guarantee").closest("li");
    expect(within(addedRow as HTMLElement).getByText("No documents yet")).toBeInTheDocument();
    expect(within(addedRow as HTMLElement).getByText("added by you")).toBeInTheDocument();
  });

  it("Exclude asks for a reason and posts once", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
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
    await user.click(screen.getByRole("button", { name: "Expand all" }));
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
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    await user.click(within(row).getByRole("button", { name: "Exclude" }));
    expect(within(row).getByRole("alert")).toHaveTextContent(/A run is already active/);
  });

  // F15: nothing to exclude or include while a walk runs.
  it("disables Exclude and Include again while a walk is active", async () => {
    const user = userEvent.setup();
    renderLonglist({ active_run: { capability_run_id: "run-1", status: "running", started_at: "now" } });
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    expect(within(row).getByRole("button", { name: "Exclude" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /Excluded options/ }));
    const excludedRow = screen.getByText("National sanctions regime").closest("li") as HTMLElement;
    expect(within(excludedRow).getByRole("button", { name: "Include again" })).toBeDisabled();
  });

  // F3: the list row names the report section too.
  it("names the report section on a from-your-evidence-search row", () => {
    const option = mockLonglist().options?.[0];
    if (option === undefined) throw new Error("fixture has no option");
    expect(
      rowMetaParts({ ...option, origin: "from_evidence_search", from_section: "What works", relations: [] }),
    ).toContain("from your evidence search · What works");
  });

  it("Include again posts once for an excluded option", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: /Excluded options/ }));
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

describe("LonglistView — shortlist actions on rows (task 055)", () => {
  it("List rows carry the place word on the grey line and the shortlist action", () => {
    renderLonglist();
    expect(rowMetaParts(mockLonglist().options!.find((o) => o.option_id === MOCK_OPTION_ID_PACKAGE)!)).toContain(
      "Policy Atlas's pick",
    );
    expect(
      rowMetaParts(mockLonglist().options!.find((o) => o.option_id === MOCK_OPTION_ID_NO_IN_SCOPE)!),
    ).not.toContain("Policy Atlas's pick");
  });

  it("List rows show Add and Remove, disabled while a walk runs", async () => {
    const user = userEvent.setup();
    renderLonglist({ active_run: { capability_run_id: "x", status: "running", started_at: "2026-10-27T00:00:00Z" } });
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    for (const button of screen.getAllByRole("button", { name: /shortlist/ })) expect(button).toBeDisabled();
  });
});

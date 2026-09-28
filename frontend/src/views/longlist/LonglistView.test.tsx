import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MOCK_OPTION_ID_EXCLUDED, MOCK_OPTION_ID_NO_IN_SCOPE, mockLonglist } from "../../mock/fixtures";
import { LonglistView } from "./LonglistView";
import { ambitionLabel, checksSummary, rowMetaParts } from "./longlistPresentation";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  usePlan: vi.fn(),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();
const addMutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useAddOption: vi.fn(),
  useExcludeOption: vi.fn(),
  useIncludeOption: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderLonglist(taskOverrides: Partial<{ active_run: unknown }> = {}) {
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
  vi.mocked(mutations.useExcludeOption).mockReturnValue(
    { mutate: excludeMutate, isPending: false } as unknown as ReturnType<typeof mutations.useExcludeOption>,
  );
  vi.mocked(mutations.useIncludeOption).mockReturnValue(
    { mutate: includeMutate, isPending: false } as unknown as ReturnType<typeof mutations.useIncludeOption>,
  );
  vi.mocked(mutations.useAddOption).mockReturnValue(
    { mutate: addMutate, isPending: false } as unknown as ReturnType<typeof mutations.useAddOption>,
  );
  const longlist = mockLonglist();
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
      <Routes>
        <Route path="/tasks/:taskId/result" element={<LonglistView taskId={TASK_ID} longlist={longlist} />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
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
    expect(screen.getByText("4 options in 2 themes · 1 excluded · 1 with no in-scope evidence")).toBeInTheDocument();
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

  it("tags each row with its lever and ambition and names the theme's instruments", async () => {
    const user = userEvent.setup();
    renderLonglist();
    expect(screen.getByRole("button", { name: /A universal offer.*1 option · regulation only/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const row = screen.getByText("Universal youth offer bundle").closest("li") as HTMLElement;
    expect(within(row).getByText("Regulate · Do minimum")).toBeInTheDocument();
  });

  it("groups by lever type and by ambition, with the theme on each row", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(within(screen.getByRole("group", { name: "Group by" })).getByRole("button", { name: "Lever type" }));
    expect(screen.getByRole("button", { name: /^Provide a service.*1 option · 1 theme/ })).toBeInTheDocument();
    expect(screen.getByText("Deliver or fund a service or programme directly to people.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Conditionality and support/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const row = screen.getByText("School-based mentoring").closest("li") as HTMLElement;
    expect(within(row).getByText("Conditionality and support")).toBeInTheDocument();
    await user.click(within(screen.getByRole("group", { name: "Group by" })).getByRole("button", { name: "Ambition" }));
    expect(screen.getByRole("button", { name: /^Incremental/ })).toBeInTheDocument();
    expect(screen.getByText(/^Adds a new scheme, service, rule, charge or offer inside the present structure\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Untagged/ })).toBeInTheDocument();
  });

  it("filters rows with the Setting facet", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const settingGroup = screen.getByRole("group", { name: "Setting" });
    await user.click(within(settingGroup).getByRole("button", { name: "Community centre" }));
    expect(screen.getByText("School-based mentoring")).toBeInTheDocument();
    expect(screen.queryByText("Youth guarantee")).not.toBeInTheDocument();
  });

  it("filters rows with the Where tried facet", async () => {
    const user = userEvent.setup();
    renderLonglist();
    const whereGroup = screen.getByRole("group", { name: "Where tried" });
    await user.click(within(whereGroup).getByRole("button", { name: "Other" }));
    expect(screen.getByText("School-based mentoring")).toBeInTheDocument();
    expect(screen.queryByText("Youth guarantee")).not.toBeInTheDocument();
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
    expect(scoped.getByText("6 documents")).toBeInTheDocument();
    expect(
      scoped.getByText('excluded: breaks "Only include options a local authority can fund directly"'),
    ).toBeInTheDocument();
    expect(scoped.getByText("part of Universal youth offer bundle")).toBeInTheDocument();
  });

  it("shows a package's has_part relation and the added-by-you entrant's zero-document note", async () => {
    const user = userEvent.setup();
    renderLonglist();
    await user.click(screen.getByRole("button", { name: "Expand all" }));
    const packageRow = screen.getByText("Universal youth offer bundle").closest("li");
    expect(within(packageRow as HTMLElement).getByText("includes National sanctions regime")).toBeInTheDocument();
    const addedRow = screen.getByText("Youth guarantee").closest("li");
    expect(within(addedRow as HTMLElement).getByText("no documents found yet")).toBeInTheDocument();
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
    expect(screen.getByRole("columnheader", { name: "Do minimum" })).toBeInTheDocument();
    expect(screen.queryByText("Conditionality and support")).not.toBeInTheDocument();
    expect(screen.queryByText("National sanctions regime")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Show excluded/ }));
    expect(screen.getByText("National sanctions regime")).toBeInTheDocument();
  });
});

describe("longlistPresentation", () => {
  it("labels the stored ambition key and agrees the verdict verb with the count", () => {
    expect(ambitionLabel("do_minimum")).toBe("Do minimum");
    expect(checksSummary(["passes"])).toBe("1 passes.");
    expect(checksSummary(["breaks", "breaks", "passes", "cannot_check"])).toBe(
      "2 break, 1 passes, 1 cannot be checked yet.",
    );
    expect(checksSummary([])).toBe("");
  });
});

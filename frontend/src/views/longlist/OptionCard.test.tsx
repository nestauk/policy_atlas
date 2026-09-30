import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  MOCK_OPTION_ID_ADDED_BY_YOU,
  MOCK_OPTION_ID_EXCLUDED,
  MOCK_OPTION_ID_NO_IN_SCOPE,
  mockLonglistOptionCards,
} from "../../mock/fixtures";
import { TooltipProvider } from "../../ui/radix/Tooltip";
import { OptionCard } from "./OptionCard";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  useOption: vi.fn(),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useExcludeOption: vi.fn(),
  useIncludeOption: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderCard(optionId: string, overrides: Record<string, unknown> = {}) {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "NEET task" } } as unknown as ReturnType<typeof queries.useTask>,
  );
  vi.mocked(queries.useOption).mockReturnValue(
    {
      data: { ...mockLonglistOptionCards[optionId], ...overrides },
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useOption>,
  );
  vi.mocked(mutations.useExcludeOption).mockReturnValue(
    { mutate: excludeMutate, isPending: false } as unknown as ReturnType<typeof mutations.useExcludeOption>,
  );
  vi.mocked(mutations.useIncludeOption).mockReturnValue(
    { mutate: includeMutate, isPending: false } as unknown as ReturnType<typeof mutations.useIncludeOption>,
  );
  return render(
    <TooltipProvider>
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/options/${optionId}`]}>
        <Routes>
          <Route path="/tasks/:taskId/options/:optionId" element={<OptionCard />} />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>,
  );
}

beforeEach(() => {
  excludeMutate.mockClear();
  includeMutate.mockClear();
});

describe("OptionCard", () => {
  it("renders the breadcrumb, title, description and one grey header line, with no boxes or chips", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByRole("link", { name: "Longlist" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/result?view=longlist`,
    );
    expect(screen.getByRole("heading", { name: "National sanctions regime" })).toBeInTheDocument();
    expect(screen.queryByText("scoping pass")).not.toBeInTheDocument();
    expect(screen.getByText("A duty to withdraw benefits on refusal of an offer")).toBeInTheDocument();
    // One grey line: lever type, origin, relations (and "also found as" when present).
    const line = screen.getByText(
      "Enforce existing powers · clustered from 6 documents · part of Universal youth offer bundle",
    );
    expect(line).toHaveClass("text-grey");
    // No snapshot boxes.
    expect(screen.queryByText("Origin")).not.toBeInTheDocument();
    expect(screen.queryByText("3 of 6")).not.toBeInTheDocument();
    // The origin section is gone.
    expect(screen.queryByRole("button", { name: /Where it came from/ })).not.toBeInTheDocument();
  });

  it("renders the evidence-base sentences, where tried, and the documents as source cards", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByRole("heading", { name: "Evidence" })).toBeInTheDocument();
    expect(screen.queryByText(/comparable systems|OECD/)).not.toBeInTheDocument();
    expect(
      screen.getAllByText("6 documents name this option: 3 evaluated it, 2 described it and 1 mentioned it.").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Read from titles and abstracts only")).toBeInTheDocument();
    expect(screen.queryByText(/were read from the abstract only/)).not.toBeInTheDocument();
    expect(screen.getByText("Benefit sanctions for young jobseekers: a systematic review")).toBeInTheDocument();
    expect(screen.getByText("Strong · Systematic review · Evaluated it · multiple countries")).toBeInTheDocument();
    expect(screen.queryByText("A mention is not support.")).not.toBeInTheDocument();
  });

  // Task 046, amendment 3 (R66): the transferability line goes.
  it("renders the no-in-scope-evidence row where it applies and no transferability row", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.queryByText(/Transferable to/)).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "No in-scope evidence: none of the 4 documents pass Evidence from the UK and other high-income countries only.",
      ),
    ).toBeInTheDocument();
  });

  // F5: the in-scope record exists for every option once the plan restricts
  // scope; the line is for the options with none in scope only.
  it("hides the no-in-scope-evidence row for an option with in-scope evidence", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { no_in_scope_evidence: false });
    expect(screen.queryByText(/No in-scope evidence:/)).not.toBeInTheDocument();
  });

  // F3: the evidence-search origin names the report section it came from.
  it("names the report section on a from-your-evidence-search option", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, {
      origin: "from_evidence_search",
      from_section: "What works for young people",
      relations: [],
    });
    expect(
      screen.getByText("Provide a service · from your evidence search · What works for young people"),
    ).toBeInTheDocument();
  });

  // Owner ruling 2026-09-24: a duplicate is merged into the kept option.
  it("names the duplicates merged into the option", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { also_found_as: ["Guarantee scheme", "Job offer"] });
    expect(screen.getByText(/· also found as: Guarantee scheme, Job offer$/)).toBeInTheDocument();
  });

  it("says nothing about merges when there are none", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.queryByText(/also found as/i)).not.toBeInTheDocument();
  });

  // Task 046, amendment 3 (R67): one linked title (plain without a row), one grey meta line.
  it("shows each document with a linked or plain title and one meta line", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [
        { task_source_snapshot_id: "doc-1", title: "Linked paper", role: "evaluated", evidence_type: "Systematic review", tier: "Strong", year: 2021, place: "United Kingdom" },
        { task_source_snapshot_id: null, title: "Plain paper", role: "mentioned", evidence_type: null, tier: null, year: null, place: null },
      ],
    });
    expect(screen.getByRole("link", { name: "Linked paper" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all?source=doc-1&option=${MOCK_OPTION_ID_EXCLUDED}`,
    );
    expect(screen.getByText("Plain paper")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Plain paper" })).not.toBeInTheDocument();
    // The place follows the role (task 046, amendment 3; R72).
    expect(screen.getByText("Strong · Systematic review · Evaluated it · United Kingdom · 2021")).toBeInTheDocument();
    expect(screen.queryByText(/inherited from a linked task/)).not.toBeInTheDocument();
  });

  // Task 046, amendment 3 (R59, R72): where tried as two levels, with document counts.
  it("shows where tried as the top levels with the places below, each with its documents", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const list = screen.getByRole("list", { name: "Where tried" });
    const tops = within(list).getAllByRole("listitem").filter((item) => item.parentElement === list);
    expect(tops.map((item) => item.firstChild?.textContent)).toEqual([
      "United Kingdom · 4 documents",
      "Multiple countries · 2 documents",
    ]);
    expect(within(tops[0]).getByText("England · 3 documents")).toBeInTheDocument();
    expect(within(tops[0]).getByText("United Kingdom · 1 document")).toBeInTheDocument();
    expect(within(tops[1]).getByText("12 high-income countries · 1 document")).toBeInTheDocument();
  });

  it("says the two non-country places as places on a document's meta line", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [
        { task_source_snapshot_id: "doc-1", title: "Stated", role: "evaluated", evidence_type: null, tier: null, year: null, place: "other" },
        { task_source_snapshot_id: "doc-2", title: "Unstated", role: "evaluated", evidence_type: null, tier: null, year: null, place: "not stated" },
      ],
    });
    expect(screen.getByText("Evaluated it · other place")).toBeInTheDocument();
    expect(screen.getByText("Evaluated it · place not stated")).toBeInTheDocument();
  });

  it("shows five documents, then all of them on request", async () => {
    const documents = Array.from({ length: 7 }, (_, index) => ({
      task_source_snapshot_id: `doc-${index}`,
      title: `Paper ${index}`,
      role: "described",
      evidence_type: null,
      tier: null,
      year: null,
      place: null,
    }));
    renderCard(MOCK_OPTION_ID_EXCLUDED, { documents });
    expect(screen.getByText("Paper 4")).toBeInTheDocument();
    expect(screen.queryByText("Paper 5")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show all 7" }));
    expect(screen.getByText("Paper 6")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show all/ })).not.toBeInTheDocument();
  });

  it("says so when no documents are found", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { documents: [] });
    expect(screen.getByText("No documents found yet.")).toBeInTheDocument();
  });

  // Task 046, contract item 1: the tried-on line, from the evidence profile.
  it("shows the tried-on line when the evidence profile carries one", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByText("Tried on: 18-24 year-olds in Northern England (2 documents).")).toBeInTheDocument();
  });

  it("shows every tried-on kind with its count, the target unit first", () => {
    const evidence = mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].evidence;
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evidence: {
        ...evidence,
        tried_on: [
          { kind: "young people", documents: 3 },
          { kind: "schools", documents: 2 },
          { kind: "councils", documents: 1 },
        ],
      },
    });
    expect(screen.getByText("Tried on: young people (3 documents), schools (2), councils (1).")).toBeInTheDocument();
  });

  // Task 046, amendment 3 (B13): the record-level lines are gone.
  it("shows no Populations, Settings or Outcomes measured line", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.queryByText(/^Populations:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Settings:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Outcomes measured:/)).not.toBeInTheDocument();
  });

  it("shows no tried-on line when the evidence profile carries none", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { evidence: { ...mockLonglistOptionCards[MOCK_OPTION_ID_NO_IN_SCOPE].evidence, tried_on: [] } });
    expect(screen.queryByText(/Tried on:/)).not.toBeInTheDocument();
  });

  // Task 046, amendment 3 (R63): the Examples block, the programme names.
  it("shows the Examples block, each programme name with its documents", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByText("Examples")).toBeInTheDocument();
    expect(screen.getByText("National sanctions regime (6 documents)")).toBeInTheDocument();
    expect(screen.getByText("Benefit sanctions pilot (2 documents)")).toBeInTheDocument();
  });

  it("shows at most five examples and at most six design features", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      examples: Array.from({ length: 7 }, (_, index) => ({ name: `Programme ${index}`, documents: 1 })),
      design: {
        ...mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].design,
        design_features: Array.from({ length: 8 }, (_, index) => `feature ${index}`),
      },
    });
    expect(screen.getByText("Programme 4 (1 document)")).toBeInTheDocument();
    expect(screen.queryByText("Programme 5 (1 document)")).not.toBeInTheDocument();
    expect(screen.getByText("Feature 5")).toBeInTheDocument();
    expect(screen.queryByText("Feature 6")).not.toBeInTheDocument();
  });

  it("shows no Examples block when the option has none", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.queryByText("Examples")).not.toBeInTheDocument();
  });

  // Task 046, amendment 3 (§ 2.5): "Lever: <primary>, with <secondary>." and the reason under it.
  it("shows the lever line with its secondary types, the reason under it, and no 'also touches'", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const line = screen.getByText(/Enforce existing powers, with Regulate\./);
    expect(line).toHaveTextContent("Lever: Enforce existing powers, with Regulate.");
    expect(line.querySelector("strong")).toHaveTextContent("Lever:");
    const reason = screen.getByText("The council withholds a benefit payment when a young person refuses an offer.");
    expect(line.compareDocumentPosition(reason) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText(/also touches/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Primary lever type/)).not.toBeInTheDocument();
  });

  it("shows the lever line with no 'with' part when there are no secondary types", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { secondary_lever_types: [], lever_reason: null });
    expect(screen.getByText(/Enforce existing powers\.$/)).toHaveTextContent("Lever: Enforce existing powers.");
    expect(screen.queryByText(/, with /)).not.toBeInTheDocument();
  });

  it("joins two secondary types with 'and'", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { secondary_lever_types: ["regulate", "provide a service"] });
    expect(screen.getByText(/with Regulate and Provide a service\./)).toBeInTheDocument();
  });

  it("puts the lever sentences in the body text size, not the meta size", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const reason = screen.getByText("The council withholds a benefit payment when a young person refuses an offer.");
    expect(reason).toHaveClass("text-body");
    expect(reason).not.toHaveClass("text-meta");
    expect(screen.getByText("A duty to withdraw benefits on refusal of an offer").closest("li")?.parentElement).toHaveClass("text-body");
    expect(screen.getByText("Read from titles and abstracts only")).toHaveClass("text-body");
    expect(screen.getByText("Read from titles and abstracts only")).not.toHaveClass("text-meta");
    const header = screen.getByText(/^Enforce existing powers · clustered/);
    expect(header).toHaveClass("text-body");
    expect(header).not.toHaveClass("text-meta");
  });

  // Task 046, amendment 3 (B13): no runner-up line (the field left the read model).
  it("shows no runner-up line", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.queryByText(/Runner-up lever type:/)).not.toBeInTheDocument();
  });

  it("never renders the words \"how sure\"", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.queryByText(/how sure/i)).not.toBeInTheDocument();
  });

  it("Exclude asks for a reason and posts once", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    await user.click(screen.getByRole("button", { name: "Exclude" }));
    await user.type(screen.getByPlaceholderText("Why exclude this option?"), "Duplicates another option");
    await user.click(screen.getByRole("button", { name: "Exclude" }));
    expect(excludeMutate).toHaveBeenCalledTimes(1);
    expect(excludeMutate).toHaveBeenCalledWith(
      { optionId: MOCK_OPTION_ID_NO_IN_SCOPE, reason: "Duplicates another option" },
      expect.anything(),
    );
  });

  it("shows Include again for an excluded option", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: "Include again" }));
    expect(includeMutate).toHaveBeenCalledTimes(1);
    expect(includeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_EXCLUDED }, expect.anything());
  });

  // Task 046, amendment 3 (§ 2.5): ambition leaves "What it is"; Delivered through stays.
  it("shows the delivery setting in What it is, and no ambition or authority line there", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const lever = screen.getByText(/Enforce existing powers, with Regulate\./);
    const delivered = screen.getByText("Delivered through: Jobcentre · Secondary school");
    expect(lever.compareDocumentPosition(delivered) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText(/^Ambition:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Needs action by/)).not.toBeInTheDocument();
  });

  it("has no 'What it is for' section and no Populations, Settings or Outcomes measured line", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.queryByRole("heading", { name: /What it is for/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/What it is for/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Populations/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Settings/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Outcomes measured/)).not.toBeInTheDocument();
  });

  // The profile section: collapsed = seven cells, with "Middle" for no mark.
  it("opens 'What it would take' collapsed: seven cells in order, 'Middle' for no mark", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    const at = (title: string) => headings.findIndex((text) => text?.startsWith(title));
    expect(at("What it is")).toBeLessThan(at("What it would take"));
    expect(at("What it would take")).toBeLessThan(at("Evidence"));
    const toggle = screen.getByRole("button", { name: /What it would take/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveTextContent("Policy Atlas's estimate");
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    const cells = within(section).getAllByRole("listitem");
    expect(cells.map((cell) => cell.textContent)).toEqual([
      "AmbitionBigger",
      "CostCheaper",
      "Time to set upMiddle",
      "Time to effectSlower",
      "Workforce requirementsMiddle",
      "Coordination requirementsHigher",
      "Delivery complexityMiddle",
    ]);
    expect(within(section).queryByText("Who decides")).not.toBeInTheDocument();
    expect(within(section).queryByText("Dependencies")).not.toBeInTheDocument();
    expect(within(section).queryByRole("link")).not.toBeInTheDocument();
    expect(within(section).queryByText(/Costs are mostly staff time/)).not.toBeInTheDocument();
  });

  it("says 'Middle' for an ambition with no mark", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    expect(within(section).getAllByRole("listitem")[0]).toHaveTextContent("AmbitionMiddle");
  });

  it("shows a table after a click on the heading, Ambition first, then the eight lines", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: /What it would take/ }));
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    const rows = within(section).getAllByRole("row");
    expect(rows).toHaveLength(9);
    expect(within(rows[0]).getByRole("rowheader")).toHaveTextContent("Ambition");
    expect(rows[0]).toHaveTextContent("Bigger");
    expect(rows[0]).toHaveTextContent("Changes who is entitled to a national benefit");
    expect(rows.slice(1).map((row) => within(row).getByRole("rowheader").textContent)).toEqual([
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Who decides",
      "Dependencies",
      "Coordination requirements",
      "Delivery complexity",
    ]);
    expect(rows[1]).toHaveTextContent("Cheaper");
    expect(rows[2]).toHaveTextContent("Middle");
    expect(within(section).getByText("Costs are mostly staff time; no capital spend is reported.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /What it would take/ })).toHaveTextContent("Policy Atlas's estimate");
  });

  // Amendment 3 (§ 2.5): the authority label sits on the "Who decides" row, only with an entry.
  it("puts the authority word and sentence on the Who decides row", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: /What it would take/ }));
    const who = screen.getByRole("rowheader", { name: "Who decides" }).closest("tr") as HTMLElement;
    expect(within(who).getByText("Needs action by the Department for Work and Pensions")).toBeInTheDocument();
    // The line's own sentence follows the word; the constrain reason stays off the card (22b).
    expect(
      within(who).getByText("The local authority decides, with the Department for Work and Pensions consulted."),
    ).toBeInTheDocument();
    expect(within(who).queryByText(/set nationally/)).not.toBeInTheDocument();
    const dependencies = screen.getByRole("rowheader", { name: "Dependencies" }).closest("tr") as HTMLElement;
    expect(dependencies).not.toHaveTextContent(/Needs action by/);
  });

  it("names 'another body' when the authority has none, and shows no authority word without an entry", async () => {
    const user = userEvent.setup();
    const first = renderCard(MOCK_OPTION_ID_EXCLUDED, {
      authority: { label: "needs_action_by", body: null, reason: "It is national." },
    });
    await user.click(screen.getByRole("button", { name: /What it would take/ }));
    expect(screen.getByText("Needs action by another body")).toBeInTheDocument();
    // The row keeps the line's own sentence; the constrain reason stays off the card (22b).
    expect(screen.queryByText("It is national.")).not.toBeInTheDocument();
    first.unmount();
    renderCard(MOCK_OPTION_ID_EXCLUDED, { authority: null });
    await user.click(screen.getByRole("button", { name: /What it would take/ }));
    const who = screen.getByRole("rowheader", { name: "Who decides" }).closest("tr") as HTMLElement;
    expect(who).not.toHaveTextContent(/Needs action by|Within your power|Unclear who can act/);
  });

  it("has no 'What it would take' section for an option with no profile", () => {
    renderCard(MOCK_OPTION_ID_ADDED_BY_YOU);
    expect(screen.queryByRole("button", { name: /What it would take/ })).not.toBeInTheDocument();
    expect(document.getElementById("what-it-would-take")).toBeNull();
  });

  // Amendment 3 (§ 2.7): one outcomes table.
  it("shows the outcomes table: a plan row with its serves mark, then a row for each other kind", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const evidence = document.getElementById("evidence-base") as HTMLElement;
    const table = within(evidence).getAllByRole("table")[0];
    const headers = within(table).getAllByRole("columnheader").map((header) => header.textContent);
    expect(headers).toEqual(["Outcome", "Documents", "Evaluated"]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((row) => row.textContent)).toEqual([
      "NEET rate at 6 monthsserves33",
      "earnings10",
    ]);
  });

  it("puts a plan outcome the option does not serve in the table without the mark, in plan order", () => {
    const evidence = mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].evidence;
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evidence: {
        ...evidence,
        outcome_counts: {
          evaluating_documents: 1,
          by_outcome: [
            { outcome: "Attendance", documents: 0, evaluated: 0 },
            { outcome: "NEET rate at 6 months", documents: 1, evaluated: 1 },
          ],
          other: [],
        },
      },
    });
    const table = within(document.getElementById("evidence-base") as HTMLElement).getAllByRole("table")[0];
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((row) => row.textContent)).toEqual(["Attendance00", "NEET rate at 6 monthsserves11"]);
  });

  it("shows no outcomes table when the option has no outcome counts", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    const evidence = document.getElementById("evidence-base") as HTMLElement;
    expect(within(evidence).queryByRole("table")).not.toBeInTheDocument();
  });

  // Amendment 3 (§ 2.5): the order inside the evidence section.
  it("orders the evidence section: outcomes table, roles, where tried, tried on, the note, the documents", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const evidence = document.getElementById("evidence-base") as HTMLElement;
    const nodes = [
      within(evidence).getByRole("table"),
      within(evidence).getAllByText("6 documents name this option: 3 evaluated it, 2 described it and 1 mentioned it.").pop() as HTMLElement,
      within(evidence).getByText("Where tried"),
      within(evidence).getByText(/^Tried on:/),
      within(evidence).getByText("Read from titles and abstracts only"),
      within(evidence).getByText("Conditionality and NEET outcomes: a local authority review"),
    ];
    for (let index = 1; index < nodes.length; index += 1) {
      expect(nodes[index - 1].compareDocumentPosition(nodes[index]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  // Checks: the user's boundaries and preferences first; the built-ins in one line unless one fails.
  it("shows the user's boundary and preference first and the built-in checks in one line when all pass", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const section = document.getElementById("constraints") as HTMLElement;
    const items = within(section).getAllByRole("listitem").map((item) => item.textContent ?? "");
    expect(items[0]).toMatch(/breaks\./);
    expect(items[1]).toMatch(/^Prefer options with a lower cost per participant/);
    expect(items[2]).toBe("Built-in checks: all pass.");
    expect(items).toHaveLength(3);
    expect(within(section).queryByText(/Relevant to the stated outcomes/)).not.toBeInTheDocument();
    expect(within(section).getByText("breaks.")).toHaveClass("text-red");
  });

  it("shows the built-in checks in full when one fails or cannot be checked", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    const section = document.getElementById("constraints") as HTMLElement;
    expect(within(section).queryByText("Built-in checks:")).not.toBeInTheDocument();
    expect(within(section).getByText(/Relevant to the stated outcomes/)).toBeInTheDocument();
    expect(within(section).getByText(/Distinct from the other options/)).toBeInTheDocument();
    expect(within(section).getByText(/Within scope/)).toBeInTheDocument();
    expect(within(section).getByText("cannot check.")).toHaveClass("text-grey");
  });
});

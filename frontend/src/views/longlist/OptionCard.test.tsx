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
import * as presentation from "./longlistPresentation";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  useOption: vi.fn(),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useOptionVerb: vi.fn(),
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
  vi.mocked(mutations.useOptionVerb).mockImplementation(
    (_taskId, verb) =>
      ({ mutate: verb === "exclude" ? excludeMutate : includeMutate, isPending: false }) as unknown as ReturnType<
        typeof mutations.useOptionVerb
      >,
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

  // Task 046, amendment 3 (R66): the transferability line goes.
  it("renders the no-in-scope-evidence row where it applies and no transferability row", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.queryByText(/Transferable to/)).not.toBeInTheDocument();
    expect(
      screen.getByText(
        /None of its 4 documents pass Evidence from the UK and other high-income countries only\./,
      ),
    ).toBeInTheDocument();
  });

  // F5: the in-scope record exists for every option once the plan restricts
  // scope; the line is for the options with none in scope only.
  it("hides the no-in-scope-evidence row for an option with in-scope evidence", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { no_in_scope_evidence: false });
    expect(screen.queryByText(/None of its \d+ documents pass/)).not.toBeInTheDocument();
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
    expect(at("How it works")).toBeLessThan(at("What it would take"));
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


  // --- Task 046, amendment 4 (R76-R82; S36): the card's structure ----------------------------

  const doc = (index: number, role: string, extra: Record<string, unknown> = {}) => ({
    task_source_snapshot_id: `doc-${index}`,
    title: `Paper ${index}`,
    role,
    evidence_type: "Systematic review",
    tier: "Strong",
    year: 2021,
    place: "United Kingdom",
    place_detail: null,
    programme_name: null,
    tried_on_kind: null,
    measured: null,
    records_count: 1,
    design_feature_not_stated: false,
    source_task_id: null,
    ...extra,
  });
  const evidenceOf = (id: string) => mockLonglistOptionCards[id].evidence;
  const evidenceSection = () => document.getElementById("evidence-base") as HTMLElement;

  it("shows the evidence signal under the grey line, in the rich form", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const signal = screen.getByText(
      "3 documents evaluated it · 3 more describe it · Evaluated in the United Kingdom · Measures 1 of your 2 outcomes",
    );
    const grey = screen.getByText(/^Enforce existing powers · clustered/);
    expect(grey.compareDocumentPosition(signal) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows the evidence signal in its no-evaluation, no-place and no-document forms", () => {
    const first = renderCard(MOCK_OPTION_ID_EXCLUDED, { evaluated_count: 0, document_count: 3 });
    expect(screen.getByText("No evaluations, 3 documents describe it")).toBeInTheDocument();
    first.unmount();
    const second = renderCard(MOCK_OPTION_ID_EXCLUDED, { evaluated_countries: [], outcomes_evaluated: 0 });
    expect(
      screen.getByText(
        "3 documents evaluated it · 3 more describe it · No evaluation gives a place · Measures none of your outcomes",
      ),
    ).toBeInTheDocument();
    second.unmount();
    renderCard(MOCK_OPTION_ID_EXCLUDED, { document_count: 0, evaluated_count: 0, documents: [] });
    expect(screen.getByText("No documents yet")).toBeInTheDocument();
  });

  it("orders the sections How it works, What it would take, Evidence, with no Checks", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent ?? "");
    expect(headings.map((text) => ["How it works", "What it would take", "Evidence"].find((name) => text.startsWith(name)))).toEqual([
      "How it works",
      "What it would take",
      "Evidence",
    ]);
    expect(document.getElementById("constraints")).toBeNull();
    expect(screen.queryByText(/Built-in checks/)).not.toBeInTheDocument();
    expect(document.getElementById("how-it-works")).not.toBeNull();
  });

  it("puts the lever reason under the lever line in grey", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const reason = screen.getByText("The council withholds a benefit payment when a young person refuses an offer.");
    expect(reason).toHaveClass("text-grey");
  });

  it("introduces the features with the lead-in, and has no Delivered through line or Examples block", () => {
    const first = renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByText("Delivered in jobcentres and in secondary schools. It typically involves:")).toBeInTheDocument();
    expect(screen.queryByText(/Delivered through/)).not.toBeInTheDocument();
    expect(screen.queryByText("Examples")).not.toBeInTheDocument();
    first.unmount();
    const second = renderCard(MOCK_OPTION_ID_ADDED_BY_YOU);
    expect(screen.getByText("It typically involves:")).toBeInTheDocument();
    second.unmount();
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      profile: { ...mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].profile, settings: ["school", "home"] },
    });
    expect(screen.getByText("Delivered in schools and at home. It typically involves:")).toBeInTheDocument();
  });

  it("shows at most six design features", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      design: {
        ...mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].design,
        design_features: Array.from({ length: 8 }, (_, index) => `feature ${index}`),
      },
    });
    expect(screen.getByText("Feature 5")).toBeInTheDocument();
    expect(screen.queryByText("Feature 6")).not.toBeInTheDocument();
  });

  it("opens the Evidence section with the opener in its three forms", () => {
    const first = renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(within(evidenceSection()).getAllByText("Evaluated in 3 documents. 3 more describe or recommend it.").length).toBeGreaterThan(0);
    first.unmount();
    const second = renderCard(MOCK_OPTION_ID_EXCLUDED, { evaluated_count: 0, document_count: 4 });
    expect(within(evidenceSection()).getAllByText("No evaluations. 4 documents describe or recommend it.").length).toBeGreaterThan(0);
    second.unmount();
    renderCard(MOCK_OPTION_ID_EXCLUDED, { evaluated_count: 0, document_count: 0, documents: [] });
    expect(within(evidenceSection()).getAllByText("No document names this option yet.").length).toBeGreaterThan(0);
  });

  it("lists your outcomes with counts, 'none' and 'not a target of this option'", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evidence: {
        ...evidenceOf(MOCK_OPTION_ID_EXCLUDED),
        outcome_counts: {
          evaluating_documents: 3,
          by_outcome: [
            { outcome: "NEET rate at 6 months", documents: 3, evaluated: 3 },
            { outcome: "Attendance", documents: 0, evaluated: 0 },
            { outcome: "Wellbeing", documents: 1, evaluated: 1 },
          ],
        },
      },
    });
    const section = evidenceSection();
    expect(within(section).getByText("Your outcomes")).toBeInTheDocument();
    const rows = within(within(section).getByRole("list", { name: "Your outcomes" })).getAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual([
      "NEET rate at 6 months3 evaluations",
      "Attendancenonenot a target of this option",
      "Wellbeing1 evaluationnot a target of this option",
    ]);
    expect(within(rows[1]).getByText("none")).toHaveClass("text-grey");
    expect(within(section).queryByRole("table")).not.toBeInTheDocument();
    expect(within(section).queryByText(/serves/i)).not.toBeInTheDocument();
  });

  it("says in one line when no evaluation measured any outcome, and shows no line when the plan has none", () => {
    const outcome = (name: string) => ({ outcome: name, documents: 1, evaluated: 0 });
    const first = renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evidence: {
        ...evidenceOf(MOCK_OPTION_ID_EXCLUDED),
        outcome_counts: { evaluating_documents: 0, by_outcome: [outcome("A"), outcome("B"), outcome("C")] },
      },
    });
    expect(screen.getByText("No evaluation measured any of your three outcomes.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Your outcomes" })).not.toBeInTheDocument();
    first.unmount();
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.queryByText("Your outcomes")).not.toBeInTheDocument();
  });

  it("shows the place sentences in served order, the Where country tinted", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const block = evidenceSection();
    const places = within(block).getAllByRole("term").map((term) => term.textContent);
    expect(places).toEqual(["United Kingdom", "No single place"]);
    const terms = within(block).getAllByRole("term");
    expect(terms[0].closest("div")).toHaveClass("bg-aqua-tint");
    expect(terms[1].closest("div")).not.toHaveClass("bg-aqua-tint");
    expect(within(block).getByText(/One moderate local evaluation of the Benefit sanctions pilot/)).toBeInTheDocument();
  });

  it("leaves the place block out when no place has a sentence", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { place_sentences: [] });
    expect(screen.queryByText("Where it has been evaluated")).not.toBeInTheDocument();
  });

  it("puts the documents behind a closed disclosure with the note, in two groups", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [doc(1, "evaluated"), doc(2, "evaluated"), doc(3, "described"), doc(4, "mentioned"), doc(5, "recommended")],
    });
    const details = evidenceSection().querySelector("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(within(details).getByText("Documents · 5 · read from titles and abstracts only")).toBeInTheDocument();
    expect(within(details).getByText("Evaluated it · 2")).toBeInTheDocument();
    expect(within(details).getByText("Describe or recommend it · 3")).toBeInTheDocument();
    const titles = within(details).getAllByRole("link").map((link) => link.textContent);
    expect(titles).toEqual(["Paper 1", "Paper 2", "Paper 3", "Paper 4", "Paper 5"]);
  });

  it("leaves out a group with no documents", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { documents: [doc(1, "described")] });
    expect(screen.queryByText(/^Evaluated it · /)).not.toBeInTheDocument();
    expect(screen.getByText("Describe or recommend it · 1")).toBeInTheDocument();
  });

  it("shows a document in three lines: title, record parts, quality parts", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [
        doc(1, "evaluated", {
          programme_name: "Youth Guarantee",
          place: "United Kingdom",
          place_detail: "south-west England",
          tried_on_kind: "16-24 year-olds",
          measured: "NEET rate at 6 months",
        }),
      ],
    });
    const title = screen.getByRole("link", { name: "Paper 1" });
    const recordLine = title.closest("li")?.querySelectorAll("p")[1] as HTMLElement;
    expect(recordLine).toHaveTextContent(
      "Youth Guarantee · United Kingdom (south-west England) · 16-24 year-olds · NEET rate at 6 months",
    );
    expect(recordLine).toHaveClass("text-grey");
    expect(within(recordLine).getByText("Youth Guarantee").tagName).toBe("STRONG");
    expect(screen.getByText("Strong · Systematic review · 2021")).toHaveClass("text-grey");
  });

  it("shows five lines a group, then all on request", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: Array.from({ length: 7 }, (_, index) => doc(index, "evaluated")),
    });
    expect(screen.queryByText("Paper 5")).not.toBeInTheDocument();
    expect(screen.getByText("Paper 4")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show all 7" }));
    expect(screen.getByText("Paper 6")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show all/ })).not.toBeInTheDocument();
  });

  it("links '+N more' to the dossier with the option, only when several records name the option", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [doc(1, "evaluated", { records_count: 3 }), doc(2, "evaluated", { records_count: 1 })],
    });
    expect(screen.getByRole("link", { name: "+2 more" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all?source=doc-1&option=${MOCK_OPTION_ID_EXCLUDED}`,
    );
    expect(screen.getAllByRole("link", { name: /more$/ })).toHaveLength(1);
  });

  it("shows a linked-task document with its title and quality line only", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [
        doc(1, "mentioned", {
          task_source_snapshot_id: null,
          source_task_id: "linked",
          records_count: 0,
          programme_name: "Ignored",
          tried_on_kind: "Ignored kind",
        }),
      ],
    });
    expect(screen.getByText("Paper 1")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Paper 1" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Ignored/)).not.toBeInTheDocument();
    expect(screen.queryByText(/more$/)).not.toBeInTheDocument();
    expect(screen.getByText("Strong · Systematic review · 2021")).toBeInTheDocument();
  });

  it("shows the thin card: the opener, one outcomes line and no place block", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evaluated_count: 0,
      document_count: 2,
      place_sentences: [],
      documents: [doc(1, "described"), doc(2, "recommended")],
      evidence: {
        ...evidenceOf(MOCK_OPTION_ID_EXCLUDED),
        outcome_counts: { evaluating_documents: 0, by_outcome: [{ outcome: "A", documents: 2, evaluated: 0 }] },
      },
    });
    const section = evidenceSection();
    expect(within(section).getAllByText("No evaluations. 2 documents describe or recommend it.").length).toBeGreaterThan(0);
    expect(within(section).getByText("No evaluation measured any of your outcome.")).toBeInTheDocument();
    expect(within(section).queryByText("Where it has been evaluated")).not.toBeInTheDocument();
  });

  it("shows the empty card: one line, no list, no note", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { document_count: 0, evaluated_count: 0, documents: [], place_sentences: [] });
    const section = evidenceSection();
    expect(within(section).getAllByText("No document names this option yet.").length).toBeGreaterThan(0);
    expect(section.querySelector("details")).toBeNull();
    expect(within(section).queryByText(/read from titles and abstracts only/)).not.toBeInTheDocument();
    expect(within(section).queryByText("Your outcomes")).not.toBeInTheDocument();
  });

  describe("the callout under the description (R78)", () => {
    const judgement = (constraint_id: string, verdict: string) => ({
      constraint_id,
      constraint_text: `Rule ${constraint_id}.`,
      verdict,
      reason: "Because.",
    });
    const guess = (constraint_id: string, leaning: string) => ({
      constraint_id,
      constraint_text: `Rule ${constraint_id}.`,
      guess: "A guess.",
      leaning,
    });
    const calloutOf = (overrides: Record<string, unknown>) =>
      renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, {
        no_in_scope_evidence: false,
        judgements: [],
        guesses: [],
        ...overrides,
      });

    it("says a breaking judgement once when it is the constraint the option is excluded for (30b)", () => {
      const constraint = mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].exclusion?.constraint ?? "";
      renderCard(MOCK_OPTION_ID_EXCLUDED, {
        judgements: [{ constraint_id: "req-1", constraint_text: constraint, verdict: "breaks", reason: "It is a levy." }],
      });
      const callout = screen.getByText(/^excluded$/).closest("p")?.parentElement;
      expect(callout).not.toBeNull();
      expect(callout?.querySelectorAll("p").length).toBe(1);
      expect(screen.queryByText(/^breaks$/)).toBeNull();
    });

    it("shows a broken constraint with the red chip", () => {
      calloutOf({ judgements: [judgement("req-1", "breaks")] });
      expect(screen.getByText("breaks")).toBeInTheDocument();
      expect(screen.getByText('Breaks "Rule req-1". Because.', { exact: false })).toBeInTheDocument();
    });

    it("shows a constraint that cannot be checked in the grey form", () => {
      calloutOf({ judgements: [judgement("req-1", "cannot_check")] });
      expect(screen.getByText('Cannot check "Rule req-1". Because.', { exact: false })).toBeInTheDocument();
    });

    it("shows a guess that likely falls short with the yellow chip", () => {
      calloutOf({ guesses: [guess("pref-1", "likely_falls_short")] });
      expect(screen.getByText("may fall short")).toBeInTheDocument();
      expect(screen.getByText('"Rule pref-1". A guess.', { exact: false })).toBeInTheDocument();
    });

    it("shows a guess that cannot be said in the grey form", () => {
      calloutOf({ guesses: [guess("pref-1", "cannot_say")] });
      expect(screen.getByText('Cannot check "Rule pref-1". A guess.', { exact: false })).toBeInTheDocument();
    });

    it("shows nothing for a pass or a likely meets", () => {
      calloutOf({ judgements: [judgement("req-1", "passes")], guesses: [guess("pref-1", "likely_meets")] });
      expect(screen.queryByText(/Rule req-1|Rule pref-1/)).not.toBeInTheDocument();
    });

    it("shows nothing for a built-in check that breaks", () => {
      calloutOf({ judgements: [judgement("relevant", "breaks"), judgement("in_scope", "cannot_check")] });
      expect(screen.queryByText(/Rule relevant|Rule in_scope/)).not.toBeInTheDocument();
    });
  });

  // R90: the words "studies", "serves", "aimed at" and "study" are not authored on the card.
  it("uses none of the retired words in its authored text", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const clone = (document.querySelector("main") ?? document.body).cloneNode(true) as HTMLElement;
    // Source text (document titles, evidence types) may hold them; the authored text may not.
    clone.querySelectorAll("li a, li p.font-bold").forEach((node) => node.remove());
    expect(clone.textContent ?? "").not.toMatch(/\bstud(y|ies)\b|\bserves?\b|aimed at/i);
  });

  it("uses none of the retired words in the presentation module's exported strings", () => {
    const exported = Object.values(presentation).filter((value) => typeof value !== "function");
    expect(JSON.stringify(exported)).not.toMatch(/\bstud(y|ies)\b|\bserves?\b|aimed at/i);
    const samples = [
      presentation.evidenceOpener(2, 5),
      presentation.evidenceSignal({
        document_count: 5,
        evaluated_count: 2,
        evaluated_countries: [{ country: "Denmark", documents: 2 }],
        outcomes_evaluated: 1,
        outcomes_total: 2,
      }),
      presentation.deliveredLeadIn(["school"]),
      presentation.noOutcomeMeasuredLine(3),
      presentation.documentsSummary(4),
    ];
    expect(samples.join(" ")).not.toMatch(/\bstud(y|ies)\b|\bserves?\b|aimed at/i);
  });
});

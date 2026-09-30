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
  it("renders the breadcrumb, title, depth tag and What it is", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByRole("link", { name: "Longlist" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/result?view=longlist`,
    );
    expect(screen.getByRole("heading", { name: "National sanctions regime" })).toBeInTheDocument();
    expect(screen.getByText("scoping pass")).toBeInTheDocument();
    expect(screen.getByText("A duty to withdraw benefits on refusal of an offer")).toBeInTheDocument();
    // Task 046, R29: the lever line is followed by its reason.
    expect(screen.getByText(/^Primary lever type: Enforce existing powers; it also touches Regulate\./)).toBeInTheDocument();
    expect(
      screen.getByText("Ambition: Bigger. Changes who is entitled to a national benefit, not just how it is delivered."),
    ).toBeInTheDocument();
  });

  it("renders the evidence-base sentences, where tried, and the documents as source cards", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByRole("heading", { name: "What the evidence base holds so far" })).toBeInTheDocument();
    expect(screen.getByText("6 documents: 4 from United Kingdom, 2 from comparable systems (OECD).")).toBeInTheDocument();
    expect(
      screen.getAllByText("6 documents name this option: 3 evaluated it, 2 described it and 1 mentioned it.").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("2 of the 6 were read from the abstract only.")).toBeInTheDocument();
    expect(screen.getByText("Benefit sanctions for young jobseekers: a systematic review")).toBeInTheDocument();
    expect(screen.getByText("Strong · Systematic review · Evaluated it")).toBeInTheDocument();
    expect(screen.queryByText("A mention is not support.")).not.toBeInTheDocument();
  });

  it("renders the transferability row and the no-in-scope-evidence row where they apply", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.getByText("Transferable to United Kingdom:")).toBeInTheDocument();
    expect(screen.getByText("checked at assessment.")).toBeInTheDocument();
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
      screen.getAllByText("From your evidence search · What works for young people.").length,
    ).toBeGreaterThan(0);
  });

  // Owner ruling 2026-09-24: a duplicate is merged into the kept option.
  it("names the duplicates merged into the option", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { also_found_as: ["Guarantee scheme", "Job offer"] });
    expect(screen.getByText("Also found as: Guarantee scheme, Job offer")).toBeInTheDocument();
  });

  it("says nothing about merges when there are none", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.queryByText(/Also found as/)).not.toBeInTheDocument();
  });

  // Task 046, amendment 3 (R67): one linked title (plain without a row), one grey meta line.
  it("shows each document with a linked or plain title and one meta line", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [
        { task_source_snapshot_id: "doc-1", title: "Linked paper", role: "evaluated", evidence_type: "Systematic review", tier: "Strong", year: 2021, where_tried_group: "where" },
        { task_source_snapshot_id: null, title: "Plain paper", role: "mentioned", evidence_type: null, tier: null, year: null, where_tried_group: "where" },
      ],
    });
    expect(screen.getByRole("link", { name: "Linked paper" })).toHaveAttribute("href", `/tasks/${TASK_ID}/sources/all?source=doc-1`);
    expect(screen.getByText("Plain paper")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Plain paper" })).not.toBeInTheDocument();
    expect(screen.getByText("Strong · Systematic review · Evaluated it · 2021")).toBeInTheDocument();
    expect(screen.queryByText(/inherited from a linked task/)).not.toBeInTheDocument();
  });

  it("shows five documents, then all of them on request", async () => {
    const documents = Array.from({ length: 7 }, (_, index) => ({
      task_source_snapshot_id: `doc-${index}`,
      title: `Paper ${index}`,
      role: "described",
      evidence_type: null,
      tier: null,
      year: null,
      where_tried_group: "where",
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

  it("shows no tried-on line when the evidence profile carries none", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { evidence: { ...mockLonglistOptionCards[MOCK_OPTION_ID_NO_IN_SCOPE].evidence, tried_on: [] } });
    expect(screen.queryByText(/Tried on:/)).not.toBeInTheDocument();
  });

  // Task 046, contract item 2: the variants block, folded seeds marked "suggested by Policy Atlas".
  it("shows the variants block, a folded seed row naming its origin", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByText("Variants")).toBeInTheDocument();
    expect(screen.getByText("National sanctions regime · 6 documents")).toBeInTheDocument();
    expect(screen.getByText("Benefit sanctions pilot · 2 documents · suggested by Policy Atlas")).toBeInTheDocument();
  });

  it("shows no variants block when the option has none", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(screen.queryByText("Variants")).not.toBeInTheDocument();
  });

  // Task 046, contract item 3: the runner-up lever type, beside the lever.
  it("shows the runner-up lever type when one is recorded", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByText("Runner-up lever type: Regulate.")).toBeInTheDocument();
  });

  // Task 046, R29: the lever line carries the reason, as the ambition line does;
  // the section summary (shown when collapsed) keeps the short form.
  it("follows the lever line with its reason, the summary without it", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(
      screen.getByText(
        "Primary lever type: Enforce existing powers; it also touches Regulate. The council withholds a benefit payment when a young person refuses an offer.",
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /What it is\b(?! for)/ }));
    expect(
      screen.getByText("Primary lever type: Enforce existing powers; it also touches Regulate."),
    ).toBeInTheDocument();
  });

  it("shows the lever line alone when no reason is recorded", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { lever_reason: null });
    expect(
      screen.getByText("Primary lever type: Enforce existing powers; it also touches Regulate."),
    ).toBeInTheDocument();
  });

  it("shows no runner-up line when none is recorded", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
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

  // R44: the ambition line, its shapes.
  it("shows the ambition as a level word and reason, a reason alone, or nothing", () => {
    const first = renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    expect(
      screen.getByText("Ambition: Adds support alongside the existing offer rather than changing who runs it."),
    ).toBeInTheDocument();
    first.unmount();
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE, { ambition_reason: "" });
    expect(screen.queryByText(/^Ambition/)).not.toBeInTheDocument();
  });

  // R41: the delivery setting follows the ambition; R43: then the authority.
  it("shows the delivery setting and the authority line after the ambition", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const ambition = screen.getByText(/^Ambition: Bigger\./);
    const delivered = screen.getByText("Delivered through: Jobcentre · Secondary school");
    const authority = screen.getByText(
      "Needs action by the Department for Work and Pensions. The benefit is set nationally, so a council cannot change it alone.",
    );
    expect(ambition.compareDocumentPosition(delivered) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(delivered.compareDocumentPosition(authority) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("names 'another body' when the authority has none, and shows no line without an authority", () => {
    const first = renderCard(MOCK_OPTION_ID_EXCLUDED, {
      authority: { label: "needs_action_by", body: null, reason: "It is national." },
    });
    expect(screen.getByText("Needs action by another body. It is national.")).toBeInTheDocument();
    first.unmount();
    renderCard(MOCK_OPTION_ID_EXCLUDED, { authority: null });
    expect(screen.queryByText(/Needs action by|Within your power|Unclear who can act/)).not.toBeInTheDocument();
  });

  // R37: the section sits between What it is for and the evidence base,
  // collapsed on open, with the estimate label beside the heading.
  it("opens 'What it would take' collapsed: the eight cells show, the sentences do not", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    const at = (title: string) => headings.findIndex((text) => text?.startsWith(title));
    expect(at("What it is for")).toBeLessThan(at("What it would take"));
    expect(at("What it would take")).toBeLessThan(at("What the evidence base holds so far"));
    const toggle = screen.getByRole("button", { name: /What it would take/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveTextContent("Estimate, before assessment");
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    const cells = within(section).getAllByRole("listitem");
    expect(cells.map((cell) => cell.textContent)).toEqual([
      "CostCheaper",
      "Time to set up",
      "Time to effectSlower",
      "Workforce requirements",
      "Who decides",
      "Dependencies",
      "Coordination requirementsHigher",
      "Delivery complexity",
    ]);
    expect(within(section).queryByRole("link")).not.toBeInTheDocument();
    expect(within(section).queryByText(/Costs are mostly staff time/)).not.toBeInTheDocument();
  });

  it("shows the eight lines as a definition list after a click on the heading, label still beside it", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: /What it would take/ }));
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    expect(section.querySelector("dl")).not.toBeNull();
    expect(section.querySelectorAll("dt")).toHaveLength(8);
    expect(within(section).getByText("Costs are mostly staff time; no capital spend is reported.")).toBeInTheDocument();
    const cost = within(section).getByText("Cost").closest("dt") as HTMLElement;
    expect(cost).toHaveTextContent("CostCheaper");
    const who = within(section).getByText("Who decides").closest("dt") as HTMLElement;
    expect(who.textContent).toBe("Who decides");
    expect(screen.getByRole("button", { name: /What it would take/ })).toHaveTextContent(
      "Estimate, before assessment",
    );
  });

  it("has no 'What it would take' section for an option with no profile", () => {
    renderCard(MOCK_OPTION_ID_ADDED_BY_YOU);
    expect(screen.queryByRole("button", { name: /What it would take/ })).not.toBeInTheDocument();
    expect(document.getElementById("what-it-would-take")).toBeNull();
  });

  // R42: outcome counts, no direction and no verdict.
  it("adds the outcome counts to the evidence section", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.getByText("3 documents evaluated this option.")).toBeInTheDocument();
    expect(screen.getByText("NEET rate at 6 months: 3 documents")).toBeInTheDocument();
  });

  it("words one document and no documents, and shows nothing when none evaluated", () => {
    const evidence = mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].evidence;
    const first = renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evidence: {
        ...evidence,
        outcome_counts: {
          evaluating_documents: 1,
          by_outcome: [
            { outcome: "Attendance", documents: 1 },
            { outcome: "Wellbeing", documents: 0 },
          ],
        },
      },
    });
    expect(screen.getByText("1 document evaluated this option.")).toBeInTheDocument();
    expect(screen.getByText("Attendance: 1 document")).toBeInTheDocument();
    expect(screen.getByText("Wellbeing: no documents")).toBeInTheDocument();
    first.unmount();
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evidence: { ...evidence, outcome_counts: { evaluating_documents: 0, by_outcome: [{ outcome: "Attendance", documents: 0 }] } },
    });
    expect(screen.queryByText(/evaluated this option/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Attendance:/)).not.toBeInTheDocument();
  });

  it("uses none of the retired words, and 'Middle' belongs to the grid only", async () => {
    const user = userEvent.setup();
    const { container } = renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: /What it would take/ }));
    for (const banned of [/less than most/i, /like most/i, /more than most/i, /do minimum/i, /incremental/i, /structural/i, /Middle/, /a guess rather than evidence/]) {
      expect(container).not.toHaveTextContent(banned);
    }
  });
});

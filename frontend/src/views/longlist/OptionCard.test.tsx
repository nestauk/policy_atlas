import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  MOCK_OPTION_ID_ADDED_BY_YOU,
  MOCK_OPTION_ID_EXCLUDED,
  MOCK_OPTION_ID_NO_IN_SCOPE,
  mockLonglistOptionCards,
} from "../../mock/fixtures";
import { TooltipProvider } from "../../ui/radix/Tooltip";
import { OptionCard } from "./OptionCard";
import { PublicViewProvider } from "../publicView";
import * as presentation from "./longlistPresentation";
import * as queries from "../../api/queries";
import * as mutations from "../../api/mutations";
import { TOGGLE_GLYPH_SIZE } from "./optionActions";
import { CARD_FROM_SHORTLIST } from "./OptionCard";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  useOption: vi.fn(),
  usePlan: vi.fn(() => ({ data: undefined })),
}));

const excludeMutate = vi.fn();
const includeMutate = vi.fn();

const shortlistMutate = vi.fn();
const unshortlistMutate = vi.fn();

// The dossier sheet is the report's; here a stand-in shows where it opens.
vi.mock("./OptionDossier", () => ({
  OptionDossier: ({ sourceId, optionId, onClose }: { sourceId: string; optionId: string; onClose: () => void }) => (
    <div role="dialog" aria-label="Source dossier">
      {sourceId} for {optionId}
      <button type="button" onClick={onClose}>
        Close the dossier
      </button>
    </div>
  ),
}));

vi.mock("../../api/mutations", () => ({
  useOptionVerb: vi.fn(),
  useShortlistVerb: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

/** Where the router is, for the dossier's in-place test. */
function LocationProbe() {
  const location = useLocation();
  return <p data-testid="location">{`${location.pathname}${location.search}`}</p>;
}

function renderCard(optionId: string, overrides: Record<string, unknown> = {}, entryState: unknown = null) {
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
  vi.mocked(mutations.useShortlistVerb).mockImplementation(
    (_taskId, verb) =>
      ({ mutate: verb === "shortlist" ? shortlistMutate : unshortlistMutate, isPending: false }) as unknown as ReturnType<
        typeof mutations.useShortlistVerb
      >,
  );
  return render(
    <TooltipProvider>
      <PublicViewProvider value={publicLink}>
      <MemoryRouter initialEntries={[{ pathname: `/tasks/${TASK_ID}/options/${optionId}`, state: entryState }]}>
        <Routes>
          <Route
            path="/tasks/:taskId/options/:optionId"
            element={
              <>
                <OptionCard />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
      </PublicViewProvider>
    </TooltipProvider>,
  );
}

/** Presses the option card's Exclude or Include again (round 13: a quiet
 *  text control on the card only). */
async function chooseFromOptionMenu(user: ReturnType<typeof userEvent.setup>, scope: HTMLElement, item: string) {
  await user.click(within(scope).getByRole("button", { name: item }));
}

/** Whether the next render sits in the public link's view (round 12). */
let publicLink = false;

/** A paragraph by its whole text, though bold runs split it (round 12). */
const paragraph = (text: string) =>
  screen.getByText((_, element) => element?.tagName === "P" && element.textContent === text);

beforeEach(() => {
  publicLink = false;
  excludeMutate.mockClear();
  includeMutate.mockClear();
  shortlistMutate.mockClear();
  unshortlistMutate.mockClear();
});

describe("OptionCard — shortlist (task 055)", () => {
  // Round 12 (owner): the Sources subsection went, the standing with it.
  it("shows no rung line on the card", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.queryByText("Evaluated · 1 RCT, 2 observational")).not.toBeInTheDocument();
  });



  // Round 13 (owner): on the card both controls take one form, the glyph
  // then the words in the quiet style, side by side, at one glyph size.
  it("shows Shortlisted beside the filled check, pressed, beside Exclude, and pressing it gives the place up", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_ADDED_BY_YOU);
    const toggle = screen.getByRole("button", { name: "Shortlisted" });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle.firstElementChild?.tagName.toLowerCase()).toBe("svg");
    expect(toggle.querySelector("circle")).toHaveAttribute("fill", "currentColor");
    const exclude = screen.getByRole("button", { name: "Exclude" });
    expect(exclude.firstElementChild?.tagName.toLowerCase()).toBe("svg");
    expect(toggle.parentElement).toBe(exclude.parentElement);
    expect(toggle.querySelector("svg")).toHaveAttribute("width", String(TOGGLE_GLYPH_SIZE));
    expect(exclude.querySelector("svg")).toHaveAttribute("width", String(TOGGLE_GLYPH_SIZE));
    await user.click(toggle);
    expect(unshortlistMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_ADDED_BY_YOU }, expect.anything());
  });

  it("offers Add to shortlist on a set-aside option", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    const toggle = screen.getByRole("button", { name: "Add to shortlist" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(shortlistMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_NO_IN_SCOPE }, expect.anything());
  });

  it("offers no shortlist action on an excluded option", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    expect(screen.queryByRole("button", { name: /^(Add to|Remove from) shortlist$/ })).not.toBeInTheDocument();
  });
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
    // The breadcrumb names the page's kind: no "Option" label (round 10, C4).
    expect(screen.queryByText(/^Option$/i)).not.toBeInTheDocument();
    expect(screen.getByText("A duty to withdraw benefits on refusal of an offer")).toBeInTheDocument();
    // One grey line: origin, relations (and "also found as" when present);
    // the lever is said once, in How it works (round 10, finding 7).
    const line = screen.getByText("found in the evidence · part of Universal youth offer bundle");
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
    expect(screen.getByText("from your report · What works for young people")).toBeInTheDocument();
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
    // Round 12 (owner): one sentence, no "Lever" eyebrow over it.
    const line = paragraph("Lever: enforcement, with regulation.");
    expect(line.previousElementSibling).toBeNull();
    expect(screen.queryByText(/^Lever$/)).not.toBeInTheDocument();
    // Only the lever nouns are strong (round 12, owner).
    expect(Array.from(line.querySelectorAll("strong")).map((node) => node.textContent)).toEqual(["enforcement", "regulation"]);
    const reason = screen.getByText("The council withholds a benefit payment when a young person refuses an offer.");
    expect(line.compareDocumentPosition(reason) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText(/also touches/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Primary lever type/)).not.toBeInTheDocument();
  });

  // Round 12 (owner): the lever nouns and the delivery setting in Semibold
  // Navy, the rest of each sentence regular.
  it("bolds the lever nouns and the delivery setting's words", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const lever = screen.getByText(/^Lever: /);
    expect(Array.from(lever.querySelectorAll("strong")).map((node) => node.textContent)).toEqual(["enforcement", "regulation"]);
    expect(lever.querySelector("strong")).toHaveClass("font-semibold", "text-navy");
    const leadIn = screen.getByText(/^Delivered /);
    // The mock profile names whom it acts on (round 12, the setting call).
    expect(Array.from(leadIn.querySelectorAll("strong")).map((node) => node.textContent)).toEqual([
      "in jobcentres and in secondary schools",
      "young jobseekers",
      "work coaches",
      "councils",
    ]);
    expect(leadIn).toHaveTextContent(/It typically involves:$/);
  });

  // Round 12 (owner): whom it acts on is the model's call, in How it works.
  it("says whom the option acts on from the profile, after the setting, the names strong", () => {
    const profile = mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].profile;
    renderCard(MOCK_OPTION_ID_EXCLUDED, { profile: { ...profile, acts_on: ["food outlets", "parents", "councils"] } });
    const leadIn = paragraph("Delivered in jobcentres and in secondary schools. Acts on food outlets, parents and councils. It typically involves:");
    expect(Array.from(leadIn.querySelectorAll("strong")).map((node) => node.textContent)).toEqual([
      "in jobcentres and in secondary schools",
      "food outlets",
      "parents",
      "councils",
    ]);
  });

  it("says nothing about whom it acts on when the profile names none", () => {
    const profile = mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].profile;
    renderCard(MOCK_OPTION_ID_EXCLUDED, { profile: { ...profile, acts_on: [] } });
    expect(screen.queryByText(/Acts on/)).not.toBeInTheDocument();
  });

  it("shows the lever line with no 'with' part when there are no secondary types", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { secondary_lever_types: [], lever_reason: null });
    expect(paragraph("Lever: enforcement.")).toBeInTheDocument();
    expect(screen.queryByText(/, with /)).not.toBeInTheDocument();
  });

  it("joins two secondary types with 'and'", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { secondary_lever_types: ["regulate", "provide a service"] });
    expect(screen.getByText((_, element) => element?.tagName === "P" && /with regulation and services\.$/.test(element.textContent ?? ""))).toBeInTheDocument();
  });

  // Round 11 (item 4): every sentence at Body, every label and secondary
  // line at Meta; no Lead on the card.
  // Round 12 (owner, item 28): the card reads at the report's scale: its
  // sentences at the report's body (Lead from md, Body on a phone), its
  // facts lines and labels at Meta, nothing smaller.
  it("sets the card's sentences at the report's body and its secondary lines at Meta", () => {
    const { container } = renderCard(MOCK_OPTION_ID_EXCLUDED);
    const reason = screen.getByText("The council withholds a benefit payment when a young person refuses an offer.");
    expect(reason.closest(".text-lead.max-md\\:text-body")).not.toBeNull();
    expect(reason).not.toHaveClass("text-meta");
    expect(screen.getByText("A duty to withdraw benefits on refusal of an offer").closest(".text-lead")).not.toBeNull();
    expect(screen.getByText(/^A statutory duty/)).toHaveClass("text-lead", "max-md:text-body");
    const header = screen.getByText(/^found in the evidence · part of/);
    expect(header).toHaveClass("text-meta");
    expect(container.querySelector(".text-caption")).toBeNull();
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

  // Round 13 (owner): Exclude acts at once; "Add a reason" follows.
  it("excludes at once, with no reason asked first", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    await chooseFromOptionMenu(user, document.body, "Exclude");
    expect(excludeMutate).toHaveBeenCalledTimes(1);
    expect(excludeMutate).toHaveBeenCalledWith({ optionId: MOCK_OPTION_ID_NO_IN_SCOPE }, expect.anything());
    expect(screen.queryByPlaceholderText("Why exclude this option?")).not.toBeInTheDocument();
  });

  it("offers Add a reason after the reader's own exclusion, saving it through the exclusion route", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      exclusion: { by: "user", constraint: "your decision", reason: "with the theme Conditionality and support" },
    });
    await user.click(screen.getByRole("button", { name: "Add a reason" }));
    await user.type(screen.getByRole("textbox", { name: "Why exclude this option?" }), "Too costly");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(excludeMutate).toHaveBeenCalledWith(
      { optionId: MOCK_OPTION_ID_EXCLUDED, reason: "with the theme Conditionality and support: Too costly" },
      expect.anything(),
    );
  });


  it("shows Include again for an excluded option", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await chooseFromOptionMenu(user, document.body, "Include again");
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

  // The profile section: collapsed = the marked cells, then "Middle" said
  // once for the rest (round 10, lead ruling on finding 7).
  // Round 12 (owner): shut, the profile is one sentence of the lines not in
  // the middle; Evidence comes before it.
  // Round 12 (owner): shut, the profile is one sentence of the lines not in
  // the middle, the takeaways in Semibold Navy; Evidence comes before it.
  it("opens 'What it could take' shut, as an intro line and the points", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    const at = (title: string) => headings.findIndex((text) => text?.startsWith(title));
    expect(at("How it works")).toBeLessThan(at("Evidence"));
    expect(at("Evidence")).toBeLessThan(at("What it could take"));
    const toggle = screen.getByRole("button", { name: /What it could take/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).not.toHaveTextContent("Policy Atlas's estimate");
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    // Round 12 (owner): an intro line, then the points as the report's
    // square bullets, ambition and impact first; no bold runs.
    const intro = within(section).getByText("Compared with the other options on the longlist, this option is:");
    expect(intro.closest(".text-lead")).not.toBeNull();
    const points = within(section).getAllByRole("listitem").map((item) => item.textContent);
    expect(points).toEqual([
      "More ambitious",
      "Higher potential impact",
      "Costs less",
      "Slower to show results",
      "Needs more coordination",
    ]);
    expect(within(section).getAllByRole("listitem")[0].querySelector("[data-bullet]")).toHaveClass("bg-blue");
    expect(section.querySelector("strong")).toBeNull();
    expect(within(section).queryByText(/^Middle on /)).not.toBeInTheDocument();
    expect(within(section).queryByRole("table")).not.toBeInTheDocument();
  });

  it("calls an unmarked ambition Average ambition, the first point", () => {
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    expect(within(section).getAllByRole("listitem")[0]).toHaveTextContent(/^Average ambition$/);
  });

  it("shows a table after a click on the heading: ambition, potential impact, the compared lines, then the rest", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: /What it could take/ }));
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    const rows = within(section).getAllByRole("row");
    expect(rows).toHaveLength(10);
    expect(within(rows[0]).getByRole("rowheader")).toHaveTextContent("Ambition");
    expect(rows[0]).toHaveTextContent("Bigger");
    expect(rows[0]).toHaveTextContent("Changes who is entitled to a national benefit");
    // Round 13 (owner): ambition, potential impact, the lines that compare,
    // then those that do not.
    expect(rows.slice(1).map((row) => within(row).getByRole("rowheader").textContent)).toEqual([
      "Potential impact",
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Coordination requirements",
      "Delivery complexity",
      "Who decides",
      "Dependencies",
    ]);
    expect(rows[1]).toHaveTextContent("Moderate if it works");
    expect(rows[1]).toHaveTextContent("Higher");
    expect(rows[2]).toHaveTextContent("Cheaper");
    expect(rows[3]).toHaveTextContent("Middle");
    // The name and the mark at the block's size, the name in Grey.
    const name = within(rows[2]).getByRole("rowheader");
    expect(name).toHaveClass("text-grey");
    expect(name.className).not.toMatch(/\btext-(meta|caption|body)\b/);
    expect(within(rows[2]).getByText("Cheaper").className).not.toMatch(/\btext-(meta|caption|body)\b/);
    expect(within(section).getByText("Costs are mostly staff time; no capital spend is reported.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /What it could take/ })).not.toHaveTextContent("Policy Atlas's estimate");
  });

  // Round 12 (owner): "Policy Atlas's estimate" is an info hover after the
  // heading, a focusable glyph outside the heading's button, whose tooltip
  // says what the block is.
  it("puts the estimate behind a focusable i after the heading, its tooltip saying what it is", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const info = screen.getByRole("button", { name: "Policy Atlas's estimate" });
    const heading = screen.getByRole("button", { name: /What it could take/ });
    expect(heading.contains(info)).toBe(false);
    expect(info.closest("h2")).toBeNull();
    expect(info.querySelector("svg")).not.toBeNull();
    expect(info).toHaveClass("size-6");
    act(() => info.focus());
    expect(info).toHaveFocus();
    expect(
      (await screen.findAllByText("Policy Atlas's estimate from the abstracts. Not an assessment.")).length,
    ).toBeGreaterThan(0);
  });

  it("shows eight lines for a profile written before Potential impact existed", async () => {
    const user = userEvent.setup();
    const profile = mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].profile;
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      profile: { ...profile, lines: profile!.lines.filter((line) => line.key !== "potential_impact") },
    });
    await user.click(screen.getByRole("button", { name: /What it could take/ }));
    const section = document.getElementById("what-it-would-take") as HTMLElement;
    expect(within(section).getAllByRole("row")).toHaveLength(9);
    expect(within(section).queryByRole("rowheader", { name: "Potential impact" })).not.toBeInTheDocument();
    expect(within(section).queryByText("Potential impact")).not.toBeInTheDocument();
  });

  // Task 055: Potential impact carries a mark (the owner, 2026-10-27).
  it("words the Potential impact mark: Higher for more, Middle for none", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: /What it could take/ }));
    const marked = screen.getByRole("rowheader", { name: "Potential impact" }).closest("tr") as HTMLElement;
    expect(within(marked).getByText("Higher")).toBeInTheDocument();
    cleanup();
    renderCard(MOCK_OPTION_ID_NO_IN_SCOPE);
    await user.click(screen.getByRole("button", { name: /What it could take/ }));
    const unmarked = screen.getByRole("rowheader", { name: "Potential impact" }).closest("tr") as HTMLElement;
    expect(within(unmarked).getByText("Middle")).toBeInTheDocument();
  });

  // Amendment 3 (§ 2.5): the authority label sits on the "Who decides" row, only with an entry.
  it("puts the authority word and sentence on the Who decides row", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    await user.click(screen.getByRole("button", { name: /What it could take/ }));
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
    await user.click(screen.getByRole("button", { name: /What it could take/ }));
    expect(screen.getByText("Needs action by another body")).toBeInTheDocument();
    // The row keeps the line's own sentence; the constrain reason stays off the card (22b).
    expect(screen.queryByText("It is national.")).not.toBeInTheDocument();
    first.unmount();
    renderCard(MOCK_OPTION_ID_EXCLUDED, { authority: null });
    await user.click(screen.getByRole("button", { name: /What it could take/ }));
    const who = screen.getByRole("rowheader", { name: "Who decides" }).closest("tr") as HTMLElement;
    expect(who).not.toHaveTextContent(/Needs action by|Within your power|Unclear who can act/);
  });

  it("has no 'What it could take' section for an option with no profile", () => {
    renderCard(MOCK_OPTION_ID_ADDED_BY_YOU);
    expect(screen.queryByRole("button", { name: /What it could take/ })).not.toBeInTheDocument();
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
    ...extra,
  });
  const evidenceSection = () => document.getElementById("evidence-base") as HTMLElement;

  // Round 12 (owner: the one-line signal "looks messy and doesn't read
  // well"): one short sentence per fact, in a fixed order, nothing bold.
  it("has no Sources lines: the places, then the documents' disclosure, and no outcomes line", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const section = evidenceSection();
    expect(within(section).queryByText("Sources")).not.toBeInTheDocument();
    expect(within(section).queryByText(/^Measures/)).not.toBeInTheDocument();
    const places = within(section).getByText("Where it has been evaluated");
    const toggle = within(section).getByRole("button", { name: /^Show \d+ documents?( · |$)/ });
    expect(places.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  // Round 12 (owner): the short blocks are always open; only What it could
  // take and the documents fold.
  it("has no Show / Hide on How it works or Evidence, only on What it could take and the documents", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    for (const name of ["How it works", "Evidence"]) {
      const heading = screen.getByRole("heading", { level: 2, name });
      expect(within(heading).queryByRole("button")).toBeNull();
    }
    expect(screen.queryByRole("button", { name: /^How it works/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Evidence/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /What it could take/ })).toHaveAttribute("aria-expanded", "false");
    expect(within(evidenceSection()).getByRole("button", { name: /^Show \d+ documents/ })).toBeInTheDocument();
  });

  // Round 12 (owner): Your outcomes, one ruled row per plan outcome, between
  // the places and the documents; absent when the plan has none.
  it("shows Your target and outcomes as a ruled table, measured and discussed, or Not covered in grey", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [
        doc(1, "evaluated", { measured: "NEET rate at 6 months" }),
        doc(2, "evaluated", { measured: "NEET rate at 6 months" }),
        doc(3, "described", { measured: "NEET rate at 6 months" }),
      ],
      evidence: {
        outcome_counts: {
          evaluating_documents: 2,
          by_outcome: [
            { outcome: "NEET rate at 6 months", documents: 3, evaluated: 2 },
            { outcome: "Wellbeing", documents: 0, evaluated: 0 },
          ],
        },
      },
    });
    const section = evidenceSection();
    const heading = within(section).getByRole("heading", { level: 3, name: "Your target and outcomes" });
    const table = within(section).getByRole("table", { name: "Your target and outcomes" });
    const rows = within(table).getAllByRole("row");
    expect(rows.map((row) => row.textContent)).toEqual([
      "NEET rate at 6 monthsMeasured in 2Discussed in 1",
      "WellbeingNot covered",
    ]);
    expect(within(rows[1]).getByText("Not covered").closest("td")).toHaveClass("text-grey");
    // The table takes the block's reading size, as the places list (round 12, owner).
    expect(table.className).not.toMatch(/text-(body|meta|lead|caption)/);
    // One line each (round 13, owner).
    expect(within(rows[0]).getByText("Measured in 2")).toHaveClass("block");
    expect(within(rows[0]).getByText("Discussed in 1")).toHaveClass("block");
    const places = within(section).getByRole("heading", { level: 3, name: "Where it has been evaluated" });
    const toggle = within(section).getByRole("button", { name: /^Show \d+ documents/ });
    // Round 13 (owner): first in Evidence, above where it has been evaluated.
    expect(heading.compareDocumentPosition(places) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(heading.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  // Round 12 (owner): the plan's target is the table's first row.
  it("puts the plan's target first: directly targeted in N, or not directly targeted", () => {
    vi.mocked(queries.usePlan).mockReturnValue({
      data: { scoping: { target_unit: { text: "16-24 year-olds", origin: "from_your_question" } } },
    } as unknown as ReturnType<typeof queries.usePlan>);
    try {
      const first = renderCard(MOCK_OPTION_ID_EXCLUDED, {
        documents: [
          doc(1, "evaluated", { tried_on_kind: "16-24 year-olds" }),
          doc(2, "evaluated", { tried_on_kind: "16-24 year-olds" }),
          doc(3, "described", { tried_on_kind: "parents" }),
          doc(4, "described", { tried_on_kind: "employers" }),
          doc(5, "described", { tried_on_kind: "employers" }),
        ],
        evidence: { outcome_counts: { evaluating_documents: 0, by_outcome: [] } },
      });
      const rows = within(screen.getByRole("table", { name: "Your target and outcomes" })).getAllByRole("row");
      expect(rows[0]).toHaveTextContent(/^16-24 year-oldsDirectly targeted in 2$/);
      first.unmount();
      renderCard(MOCK_OPTION_ID_EXCLUDED, {
        documents: [doc(1, "evaluated", { tried_on_kind: "adults" })],
        evidence: { outcome_counts: { evaluating_documents: 0, by_outcome: [] } },
      });
      const value = within(screen.getByRole("table", { name: "Your target and outcomes" })).getByText("Not directly targeted");
      expect(value).toHaveClass("text-grey");
      // No document's target known: the target row is left out.
      cleanup();
      renderCard(MOCK_OPTION_ID_EXCLUDED, {
        documents: [doc(1, "evaluated", { tried_on_kind: null, measured: "NEET rate at 6 months" })],
      });
      const table = screen.getByRole("table", { name: "Your target and outcomes" });
      expect(within(table).queryByText("16-24 year-olds")).not.toBeInTheDocument();
      expect(within(table).queryByText(/directly targeted/i)).not.toBeInTheDocument();
    } finally {
      vi.mocked(queries.usePlan).mockReturnValue({ data: undefined } as unknown as ReturnType<typeof queries.usePlan>);
    }
  });

  it("has no table when the plan has no target unit and no outcomes", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { evidence: { outcome_counts: { evaluating_documents: 0, by_outcome: [] } } });
    expect(within(evidenceSection()).queryByRole("heading", { name: "Your target and outcomes" })).not.toBeInTheDocument();
  });

  // Round 12 (owner): with no evaluation the section keeps its subheading
  // and says so, then the documents.
  it("keeps Where it has been evaluated with one grey line when nothing evaluated the option", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evaluated_count: 0,
      document_count: 2,
      documents: [doc(1, "described"), doc(2, "recommended")],
    });
    const section = evidenceSection();
    const heading = within(section).getByRole("heading", { level: 3, name: "Where it has been evaluated" });
    const line = within(section).getByText("Not evaluated in any of these sources.");
    expect(line).toHaveClass("text-grey");
    expect(heading.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(section).queryByRole("list", { name: "Where it has been evaluated" })).not.toBeInTheDocument();
    expect(within(section).queryByLabelText("Where it has been evaluated")).not.toBeInTheDocument();
    const toggle = within(section).getByRole("button", { name: /^Show 2 documents/ });
    expect(line.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("says the empty card's one line and offers no documents", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { document_count: 0, evaluated_count: 0, documents: [] });
    expect(within(evidenceSection()).getByText("No document names this option yet.")).toBeInTheDocument();
    expect(within(evidenceSection()).queryByRole("button", { name: /documents/ })).not.toBeInTheDocument();
  });

  // Round 11 (item 4): three blocks; round 12 (owner): the third is "Evidence" again.
  it("orders the sections How it works, Evidence, What it could take, with no Checks", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent ?? "");
    expect(headings.map((text) => ["How it works", "What it could take", "Evidence"].find((name) => text.startsWith(name)))).toEqual([
      "How it works",
      "Evidence",
      "What it could take",
    ]);
    expect(screen.queryByText("Where it stands")).not.toBeInTheDocument();
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
    expect(paragraph(
      "Delivered in jobcentres and in secondary schools. Acts on young jobseekers, work coaches and councils. It typically involves:",
    )).toBeInTheDocument();
    expect(screen.queryByText(/Delivered through/)).not.toBeInTheDocument();
    expect(screen.queryByText("Examples")).not.toBeInTheDocument();
    first.unmount();
    const second = renderCard(MOCK_OPTION_ID_ADDED_BY_YOU);
    expect(screen.getByText("It typically involves:")).toBeInTheDocument();
    second.unmount();
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      profile: { ...mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED].profile, settings: ["school", "home"], acts_on: [] },
    });
    expect(paragraph("Delivered in schools and at home. It typically involves:")).toBeInTheDocument();
  });

  // Round 12 (owner): the report's Electric Blue square bullets.
  it("lists the design features with the report's square bullets", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const item = screen.getByText("A duty to withdraw benefits on refusal of an offer").closest("li") as HTMLElement;
    expect(item.querySelector("[data-bullet]")).toHaveClass("bg-blue", "size-1.5");
    expect(item.closest("ul")).toHaveClass("list-none");
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

  // Round 10, C7: the header's evidence line says the counts; the section
  // opens with the maturity line, and only an option with no document says so.

  // Round 12 (owner): the plan's own place leads the list with no mark of its own.
  it("shows the place sentences in served order, with no mark or tint on the plan's place", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED);
    const block = evidenceSection();
    const places = within(block).getAllByRole("term").map((term) => term.textContent);
    expect(places).toEqual(["United Kingdom", "Several countries"]);
    for (const term of within(block).getAllByRole("term")) expect(term.querySelector(".bg-navy")).toBeNull();
    expect(block.querySelector("[class*='aqua']")).toBeNull();
    expect(within(block).getByText(/One moderate local evaluation of the Benefit sanctions pilot/)).toBeInTheDocument();
  });

  it("leaves the place block out when no place has a sentence", () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { place_sentences: [] });
    expect(screen.queryByText("Where it has been evaluated")).not.toBeInTheDocument();
  });

  /** Open the documents disclosure (round 10: the chevron with Show / Hide). */
  // Round 12 (owner): the documents are a disclosure, closed by default.
  const openDocuments = async () => {
    const toggle = within(evidenceSection()).getByRole("button", { name: /^Show \d+ documents?( · |$)/ });
    await userEvent.click(toggle);
    return toggle;
  };

  it("folds the documents behind Show N documents, closed, then lists them in two groups", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [doc(1, "evaluated"), doc(2, "evaluated"), doc(3, "described"), doc(4, "mentioned"), doc(5, "recommended")],
    });
    const section = evidenceSection();
    const toggle = within(section).getByRole("button", { name: "Show 5 documents · 2 evaluated it · 3 describe it" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(section).queryByText(/^Paper 1/)).not.toBeInTheDocument();
    await openDocuments();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveTextContent("Hide documents");
    expect(within(section).getByText("Read from titles and abstracts only.")).toBeInTheDocument();
    expect(within(section).getByText("Evaluated it · 2")).toBeInTheDocument();
    expect(within(section).getByText("Describe or recommend it · 3")).toBeInTheDocument();
    const titles = within(section)
      .getAllByRole("link")
      .map((link) => link.textContent)
      .filter((text) => text?.startsWith("Paper"));
    expect(titles).toEqual(["Paper 1", "Paper 2", "Paper 3", "Paper 4", "Paper 5"]);
  });

  it("leaves out a group with no documents", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, { documents: [doc(1, "described")] });
    await openDocuments();
    expect(screen.queryByText(/^Evaluated it · /)).not.toBeInTheDocument();
    expect(screen.getByText("Describe or recommend it · 1")).toBeInTheDocument();
  });

  // Round 12 (owner): the reference, then its facts at Body in Grey: where
  // and how, then the outcome on its own line; the group is a subheading.
  // Round 12 (owner): the reference, then a small labelled list of its
  // facts (Where, Type, Targeted, Measures), the labels at Meta Grey and the
  // values at the block's size; the group is a subheading.
  it("shows a document as its reference, then a labelled list of its facts", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [
        doc(1, "evaluated", {
          programme_name: "Youth Guarantee",
          place_detail: "south-west England",
          tried_on_kind: "16-24 year-olds",
          measured: "NEET rate at 6 months",
          records_count: 3,
        }),
      ],
    });
    await openDocuments();
    const title = screen.getByRole("link", { name: "Paper 1" });
    const item = title.closest("li") as HTMLElement;
    // No authors and no venue: the title and its year still read.
    expect(item.querySelector("p")).toHaveTextContent(/^Paper 1 \(2021\)\.$/);
    const rows = Array.from(item.querySelectorAll("dl > div")).map((row) => [
      row.querySelector("dt")?.textContent,
      row.querySelector("dd")?.textContent,
    ]);
    expect(rows).toEqual([
      ["Where", "United Kingdom"],
      ["Type", "Systematic review"],
      ["Targeted", "16-24 year-olds"],
      ["Measures", "NEET rate at 6 months"],
    ]);
    // One size for the whole entry (round 12, owner): no size class of its
    // own anywhere in it, the labels in Grey.
    expect(item.querySelector("dt")).toHaveClass("text-grey");
    for (const node of Array.from(item.querySelectorAll("*"))) {
      expect(node.getAttribute("class") ?? "").not.toMatch(/\btext-(body|meta|caption|lead)\b/);
    }
    expect(item).not.toHaveTextContent(/·|also found as|Design/);
    const group = screen.getByRole("heading", { level: 3, name: "Evaluated it · 1" });
    expect(group).toHaveClass("font-semibold", "text-navy");
    expect(group.className).not.toMatch(/\btext-(body|meta|caption)\b/);
    expect(screen.getByRole("heading", { level: 3, name: "Where it has been evaluated" })).toHaveClass("text-lead", "font-bold");
    expect(screen.queryByText(/Youth Guarantee|Strong · /)).not.toBeInTheDocument();
  });

  it("shows five lines a group, then all on request", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: Array.from({ length: 7 }, (_, index) => doc(index, "evaluated")),
    });
    await openDocuments();
    expect(screen.queryByText("Paper 5")).not.toBeInTheDocument();
    expect(screen.getByText("Paper 4")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show all 7" }));
    expect(screen.getByText("Paper 6")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show all/ })).not.toBeInTheDocument();
  });

  // Round 12: the reference in the References form, as the report's list.
  // Round 13 (owner): no authors; the title first, the year in brackets
  // after it, then the venue; the title as the report's References show it.
  it("reads a document's reference as the title, its year, then the venue, with no authors", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [doc(1, "evaluated", { authors: ["Sampleton, A.", "Mockford, C."], venue: "Journal of Youth Policy" })],
    });
    await openDocuments();
    const title = screen.getByRole("link", { name: "Paper 1" });
    const reference = title.closest("p") as HTMLElement;
    expect(reference.textContent).toBe("Paper 1 (2021). Journal of Youth Policy.");
    expect(reference).not.toHaveTextContent(/Sampleton/);
    expect(title).toHaveClass("text-navy", "decoration-line-2", "hover:decoration-navy");
    expect(within(reference).getByText("Journal of Youth Policy.")).toHaveClass("text-grey");
  });

  // Round 12 (owner): "+N more" was unclear: the other records are words on
  // the facts line, and only the title opens the dossier.
  // Round 12 (owner): documents a hairline apart, and the same documents in
  // Sources under the list.
  it("rules the documents apart and links to them in Sources, filtered by the option", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [doc(1, "evaluated"), doc(2, "evaluated"), doc(3, "described")],
    });
    await openDocuments();
    const list = screen.getByRole("link", { name: "Paper 1" }).closest("ul") as HTMLElement;
    expect(list).toHaveClass("divide-y", "divide-line");
    expect(screen.getByRole("link", { name: "See these 3 documents in Sources" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all?option=${MOCK_OPTION_ID_EXCLUDED}`,
    );
  });

  // Round 12 (owner): no "+N more" and no "also found as" on the card; the
  // dossier keeps the provenance, and only the title opens it.
  it("says nothing of the other records, with no '+N more' link; the title opens the dossier", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [doc(1, "evaluated", { records_count: 3 }), doc(2, "evaluated", { records_count: 1 })],
    });
    await openDocuments();
    expect(screen.queryByRole("link", { name: /more$/ })).not.toBeInTheDocument();
    expect(within(evidenceSection()).queryByText(/other records?/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Paper 1" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/options/${MOCK_OPTION_ID_EXCLUDED}?source=doc-1&option=${MOCK_OPTION_ID_EXCLUDED}`,
    );
  });

  // Round 12 (owner bug): an option opened from a scrolled longlist opened
  // at the foot of the page; it opens at its top, focus on its title.
  it("opens at the top of the scrolling pane with focus on the title", () => {
    vi.mocked(queries.useOption).mockReturnValue(
      { data: undefined, isPending: true, isError: false } as unknown as ReturnType<typeof queries.useOption>,
    );
    vi.mocked(queries.useTask).mockReturnValue({ data: { name: "NEET task" } } as unknown as ReturnType<typeof queries.useTask>);
    vi.mocked(mutations.useOptionVerb).mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useOptionVerb>);
    vi.mocked(mutations.useShortlistVerb).mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useShortlistVerb>);
    const tree = () => (
      <TooltipProvider>
        <div data-testid="pane" style={{ overflowY: "auto" }}>
          <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/options/${MOCK_OPTION_ID_EXCLUDED}`]}>
            <Routes>
              <Route path="/tasks/:taskId/options/:optionId" element={<OptionCard />} />
            </Routes>
          </MemoryRouter>
        </div>
      </TooltipProvider>
    );
    const { rerender } = render(tree());
    const pane = screen.getByTestId("pane");
    pane.scrollTop = 900;
    vi.mocked(queries.useOption).mockReturnValue(
      { data: mockLonglistOptionCards[MOCK_OPTION_ID_EXCLUDED], isPending: false, isError: false } as unknown as ReturnType<
        typeof queries.useOption
      >,
    );
    rerender(tree());
    expect(pane.scrollTop).toBe(0);
    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
    // Once per option: a later render leaves the reader where they are.
    pane.scrollTop = 300;
    rerender(tree());
    expect(pane.scrollTop).toBe(300);
  });

  // Round 12 (owner): the public link reads the card and changes nothing;
  // the documents and their dossier stay.
  it("is read-only on the public link: the held word, no toggle, no Exclude, the dossier kept", async () => {
    publicLink = true;
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_ADDED_BY_YOU, { document_count: 1, evaluated_count: 1, documents: [doc(1, "evaluated")] });
    expect(screen.queryByRole("button", { name: /^(Add to|Remove from) shortlist$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^(Exclude|Include again)$/ })).not.toBeInTheDocument();
    await openDocuments();
    await user.click(screen.getByRole("link", { name: "Paper 1" }));
    expect(screen.getByRole("dialog", { name: "Source dossier" })).toBeInTheDocument();
  });

    // Round 12 (owner bug): a document opens its dossier over the card; the
  // reader stays on the option card, not the Sources tab, and Close returns.
  it("opens a document's dossier over the card, staying on the card's URL, and closes back to it", async () => {
    const user = userEvent.setup();
    renderCard(MOCK_OPTION_ID_EXCLUDED, { documents: [doc(1, "evaluated")] });
    await openDocuments();
    await user.click(screen.getByRole("link", { name: "Paper 1" }));
    const sheet = screen.getByRole("dialog", { name: "Source dossier" });
    expect(sheet).toHaveTextContent(`doc-1 for ${MOCK_OPTION_ID_EXCLUDED}`);
    expect(screen.getByTestId("location")).toHaveTextContent(
      `/tasks/${TASK_ID}/options/${MOCK_OPTION_ID_EXCLUDED}?source=doc-1&option=${MOCK_OPTION_ID_EXCLUDED}`,
    );
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close the dossier" }));
    expect(screen.queryByRole("dialog", { name: "Source dossier" })).not.toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent(new RegExp(`^/tasks/${TASK_ID}/options/${MOCK_OPTION_ID_EXCLUDED}$`));
  });

  it("shows a linked-task document's title unlinked, with its facts", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      documents: [
        doc(1, "mentioned", {
          task_source_snapshot_id: null,
          records_count: 0,
          programme_name: "Ignored",
          tried_on_kind: "Ignored kind",
        }),
      ],
    });
    await openDocuments();
    expect(screen.getByText("Paper 1")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Paper 1" })).not.toBeInTheDocument();
    const item = screen.getByText("Paper 1").closest("li") as HTMLElement;
    // The programme stays off; whom it targeted shows (round 12, owner).
    expect(Array.from(item.querySelectorAll("dt")).map((term) => term.textContent)).toEqual(["Where", "Type", "Targeted"]);
    expect(item).toHaveTextContent("Ignored kind");
  });

  it("shows the thin card: the not-evaluated line, no place list and no outcomes line", async () => {
    renderCard(MOCK_OPTION_ID_EXCLUDED, {
      evaluated_count: 0,
      document_count: 2,
      place_sentences: [],
      documents: [doc(1, "described"), doc(2, "recommended")],
    });
    const section = evidenceSection();
    // Round 12 (owner): the subheading stays and says nothing evaluated it.
    expect(within(section).getByText("Not evaluated in any of these sources.")).toBeInTheDocument();
    expect(within(section).queryByLabelText("Where it has been evaluated")).not.toBeInTheDocument();
    expect(within(section).queryByText(/^Measures/)).not.toBeInTheDocument();
    await openDocuments();
    expect(within(section).getByText("Describe or recommend it · 2")).toBeInTheDocument();
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
      // Said once, in the exclusion's facts; no notice repeats it.
      const block = screen.getByTestId("card-exclusion");
      expect(within(block).getByText("Constraint")).toBeInTheDocument();
      expect(screen.queryByText("Does not meet:")).toBeNull();
    });

    // Round 15 (owner): the exclusion sits at the top of the card, under the
    // title and its line, above How it works; not in the Evidence section.
    it("puts the exclusion at the top of the card, above How it works", () => {
      renderCard(MOCK_OPTION_ID_EXCLUDED, {
        exclusion: { by: "user", constraint: "your decision", reason: "" },
      });
      const block = screen.getByTestId("card-exclusion");
      expect(block).toHaveTextContent(/^Excluded/);
      expect(within(block).getByRole("button", { name: "Add a reason" })).toBeInTheDocument();
      expect(block.closest("header")).not.toBeNull();
      const howItWorks = screen.getByRole("heading", { name: "How it works" });
      expect(block.compareDocumentPosition(howItWorks) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(document.getElementById("evidence-base")).not.toContainElement(block);
      // The header's Include again stays with the card's controls.
      expect(screen.getByRole("button", { name: "Include again" })).toBeInTheDocument();
    });

    // Round 15 (owner): opened from the Shortlist page the breadcrumb leads
    // back there; from the longlist, or on a direct load, to the Longlist.
    it("leads the breadcrumb back to the Shortlist when opened from it, else to the Longlist", () => {
      const { unmount } = renderCard(MOCK_OPTION_ID_EXCLUDED, {}, CARD_FROM_SHORTLIST);
      const crumbs = () => screen.getByRole("navigation", { name: "Breadcrumb" });
      expect(within(crumbs()).getByRole("link", { name: "Shortlist" })).toHaveAttribute(
        "href",
        `/tasks/${TASK_ID}/result?view=shortlist`,
      );
      unmount();
      renderCard(MOCK_OPTION_ID_EXCLUDED);
      expect(within(crumbs()).getByRole("link", { name: "Longlist" })).toHaveAttribute(
        "href",
        `/tasks/${TASK_ID}/result?view=longlist`,
      );
      expect(within(crumbs()).queryByRole("link", { name: "Shortlist" })).not.toBeInTheDocument();
    });

    // Round 15 (owner): the dossier's labelled facts: who excluded it as the
    // Red heading line (no By row), then Constraint and Why, labels in Meta
    // Grey at a fixed width; "Add a reason" after the Why value when it invites one.
    it("lays a constraint's exclusion out as Does not meet a constraint, then Constraint and Why", () => {
      renderCard(MOCK_OPTION_ID_EXCLUDED, {
        exclusion: {
          by: "constrain",
          constraint: "Only include options a local authority can fund directly.",
          reason: "A local authority cannot fund this directly.",
        },
      });
      const block = screen.getByTestId("card-exclusion");
      const title = block.firstElementChild as HTMLElement;
      expect(title).toHaveTextContent(/^Does not meet a constraint$/);
      expect(title).toHaveClass("text-red");
      const rows = Array.from(block.querySelectorAll("dl > div")).map((row) => [
        row.querySelector("dt")?.textContent,
        row.querySelector("dd")?.textContent,
      ]);
      expect(rows).toEqual([
        ["Constraint", "Only include options a local authority can fund directly"],
        ["Why", "A local authority cannot fund this directly."],
      ]);
      expect(within(block).queryByText("By")).not.toBeInTheDocument();
      for (const label of Array.from(block.querySelectorAll("dt"))) expect(label).toHaveClass("text-meta", "text-grey");
      expect(block.querySelector("dl > div")?.className).toContain("grid-cols-[7.5rem_minmax(0,1fr)]");
      expect(block).not.toHaveTextContent(/Breaks/);
      expect(within(block).queryByRole("button", { name: "Add a reason" })).not.toBeInTheDocument();
    });

    it("heads your group exclusion Excluded by you with the theme, and offers Add a reason as the Why value", () => {
      renderCard(MOCK_OPTION_ID_EXCLUDED, {
        exclusion: { by: "user", constraint: "your decision", reason: "with the theme A universal offer" },
      });
      const block = screen.getByTestId("card-exclusion");
      expect(within(block).queryByText("Constraint")).not.toBeInTheDocument();
      const why = within(block).getByText("Why").nextElementSibling as HTMLElement;
      expect(within(why).getByRole("button", { name: "Add a reason" })).toBeInTheDocument();
      expect(block.firstElementChild).toHaveTextContent(/^Excluded by you · with the theme A universal offer$/);
      expect(block.firstElementChild).toHaveClass("text-red");
      expect(within(block).queryByText("By")).not.toBeInTheDocument();
    });

    // Round 10 (finding 7): a flat block on the sheet, no card and no chips;
    // each notice a word in its tone, red only for a failure.
    it("sits on the sheet as a flat block, never a card inside it", () => {
      calloutOf({ judgements: [judgement("req-1", "breaks")] });
      const block = screen.getByText("Does not meet:").closest("p")?.parentElement as HTMLElement;
      expect(block.className).toContain("border-l");
      expect(block.className).not.toMatch(/shadow|bg-paper/);
      expect(block.querySelector("[class*='text-[11.5px]']")).toBeNull();
    });

    it("shows a broken constraint with its word in red", () => {
      calloutOf({ judgements: [judgement("req-1", "breaks")] });
      // Round 15 (owner): "Does not meet", never "Breaks".
      expect(screen.getByText("Does not meet:")).toHaveClass("text-red");
      expect(screen.getByText("Does not meet:").closest("p")).toHaveTextContent('Does not meet: "Rule req-1". Because.');
      expect(document.body).not.toHaveTextContent(/Breaks/);
    });

    it("shows a constraint that cannot be checked in the grey form", () => {
      calloutOf({ judgements: [judgement("req-1", "cannot_check")] });
      expect(screen.getByText("Cannot check:")).toHaveClass("text-grey");
      expect(screen.getByText("Cannot check:").closest("p")).toHaveTextContent('Cannot check: "Rule req-1". Because.');
    });

    it("shows a guess that likely falls short with its word in Navy", () => {
      calloutOf({ guesses: [guess("pref-1", "likely_falls_short")] });
      expect(screen.getByText("May fall short:")).toHaveClass("text-navy");
      expect(screen.getByText('"Rule pref-1". A guess.', { exact: false })).toBeInTheDocument();
    });

    it("shows a guess that cannot be said in the grey form", () => {
      calloutOf({ guesses: [guess("pref-1", "cannot_say")] });
      expect(screen.getByText("Cannot check:").closest("p")).toHaveTextContent('Cannot check: "Rule pref-1". A guess.');
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
      presentation.middleSummary(6, 8),
      presentation.evidenceSignal({
        document_count: 5,
        evaluated_count: 2,
        evaluated_countries: [{ country: "Denmark", documents: 2 }],
        outcomes_evaluated: 1,
        outcomes_total: 2,
      }),
      presentation.deliveredLeadIn(["school"]),
      presentation.documentsToggleWords(false, 2, 2),
      presentation.documentsSummary(4),
    ];
    expect(samples.join(" ")).not.toMatch(/\bstud(y|ies)\b|\bserves?\b|aimed at/i);
  });
});

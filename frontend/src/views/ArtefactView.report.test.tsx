import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { ArtefactView } from "./ArtefactView";
import { forgetReportExpand } from "./ArtefactOutline";
import * as queries from "../api/queries";
import * as store from "../store";
import * as conversationState from "./workspace/chat/conversationState";

/*
 * The committed report page, round 10 (task 058): the title block, the facts
 * line, the order of the page and its contents, the heading outline, the
 * markers as the one control per claim, and the phone's contents.
 */

const TASK_ID = "02da1b53-7104-4724-9944-f145e165b847";
const QUESTION = "What raises take-up of free school meals?";

vi.mock("../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof queries>();
  return {
    ...actual,
    useTask: vi.fn(),
    // Task 054: the chats gate reads the theory graph (none here).
    useToc: vi.fn(() => ({ data: undefined })),
    useArtefact: vi.fn(),
    useConversations: vi.fn(),
    useLandscape: vi.fn(),
    useFunnel: vi.fn(),
    useApiClient: vi.fn(),
    useEvidence: vi.fn(),
    useFindings: vi.fn(),
    useSourceDossier: vi.fn(),
    usePlan: vi.fn(),
    useRuns: vi.fn(),
  };
});

vi.mock("../store", async (importOriginal) => {
  const actual = await importOriginal<typeof store>();
  return { ...actual, useRunStream: vi.fn() };
});

vi.mock("./workspace/chat/conversationState", async (importOriginal) => {
  const actual = await importOriginal<typeof conversationState>();
  return { ...actual, useActiveConversation: vi.fn(), useConversationMutations: vi.fn() };
});

vi.mock("../lib/title", () => ({ useDocumentTitle: vi.fn() }));

const citation = (n: number, title: string, extra: Record<string, unknown> = {}) => ({
  citation_id: `cit-${n}`,
  n,
  source_id: `src-${n}`,
  source_title: title,
  quote: `Quote ${n}.`,
  ...extra,
});

const KF_PROSE = "- Cost decides take-up: families weigh the charge first.";
const KF_CLAIM = "families weigh the charge first";
const BODY_PROSE = "Letters raised take-up in two councils.";

const artefact = {
  artefact_id: "c930515b-a383-4e58-bdb6-d43d47f2bdd3",
  title: "Generated title for the download",
  coverage_snapshot: { source_count: 12, included: 118 },
  most_relevant_notes: [{ source_id: "src-7", note: "The largest trial." }],
  references: [
    { n: 7, title: "School meals trial", year: 2021, venue: "BMJ Open" },
    { n: 12, title: "Council letters", year: 2023, venue: null },
  ],
  sections: [
    {
      title: "Key findings",
      role: "key_findings" as const,
      blocks: [
        {
          block_id: "kf",
          prose: KF_PROSE,
          claims: [
            {
              claim_id: "kf-1",
              claim_type: "citation" as const,
              // The verdict is the claim's (round 13).
              grounding_tier: "tier_2",
              text: KF_CLAIM,
              span: [KF_PROSE.indexOf(KF_CLAIM), KF_PROSE.indexOf(KF_CLAIM) + KF_CLAIM.length],
              citations: [
                citation(12, "Council letters"),
                citation(7, "School meals trial", {
                  appraisal_label: "Very strong",
                  evidence_type: "Systematic Review and Meta-Analysis",
                }),
              ],
            },
          ],
        },
      ],
    },
    {
      title: "Case studies",
      role: "case_studies" as const,
      blocks: [{ block_id: "cs", prose: "", claims: [] }],
      cards: [
        {
          card_id: "card-1",
          title: "Leeds pilot",
          prose: "Take-up rose.",
          strength: "Very strong",
          design: "RCTs and Quasi-Experimental Studies",
          claims: [],
        },
      ],
    },
    {
      title: "What families said about the cost of a school meal in the cities",
      role: "standard" as const,
      blocks: [
        {
          block_id: "body",
          prose: BODY_PROSE,
          claims: [
            {
              claim_id: "body-1",
              claim_type: "citation" as const,
              // The verdict is the claim's (round 13).
              grounding_tier: "tier_2",
              text: BODY_PROSE,
              span: [0, BODY_PROSE.length],
              citations: [citation(7, "School meals trial")],
            },
          ],
        },
      ],
    },
  ],
};

type Landscape = { isError: boolean; data?: Record<string, unknown> };

function renderReport({
  landscape = { isError: false, data: { years: { 2019: 1, 2024: 2 }, evidence_types: { "Systematic Review and Meta-Analysis": 2 } } },
  publicView = false,
  funnel,
  plan = null,
}: { landscape?: Landscape; publicView?: boolean; funnel?: Record<string, number>; plan?: unknown } = {}) {
  vi.mocked(queries.useTask).mockReturnValue({
    data: {
      task_id: TASK_ID,
      name: "Free school meals",
      question: QUESTION,
      latest_run: { capability_run_id: "run-1", status: "succeeded", ended_at: "2026-11-05T12:00:00Z" },
    },
  } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useArtefact).mockReturnValue({
    isPending: false,
    isError: false,
    data: artefact,
  } as unknown as ReturnType<typeof queries.useArtefact>);
  vi.mocked(queries.useConversations).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<
    typeof queries.useConversations
  >);
  vi.mocked(queries.useLandscape).mockReturnValue(landscape as unknown as ReturnType<typeof queries.useLandscape>);
  vi.mocked(queries.useFunnel).mockReturnValue({ data: funnel } as unknown as ReturnType<typeof queries.useFunnel>);
  vi.mocked(queries.useApiClient).mockReturnValue({} as ReturnType<typeof queries.useApiClient>);
  vi.mocked(queries.usePlan).mockReturnValue({ data: plan } as unknown as ReturnType<typeof queries.usePlan>);
  vi.mocked(queries.useRuns).mockReturnValue({ data: undefined } as unknown as ReturnType<typeof queries.useRuns>);
  vi.mocked(store.useRunStream).mockReturnValue(createInitialRunStreamState());
  vi.mocked(conversationState.useActiveConversation).mockReturnValue({
    setActiveConversation: vi.fn(),
    openDraftChat: vi.fn(),
  } as unknown as ReturnType<typeof conversationState.useActiveConversation>);
  vi.mocked(conversationState.useConversationMutations).mockReturnValue({
    create: vi.fn(),
  } as unknown as ReturnType<typeof conversationState.useConversationMutations>);
  const path = publicView ? `/public/${TASK_ID}/result` : `/tasks/${TASK_ID}/result`;
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/tasks/:taskId/result" element={<ArtefactView />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

function stubNarrow(narrow: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("max-width") ? narrow : false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

describe("the committed report page (task 058, round 10)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    // Each test opens the report fresh: the expand state is the task's.
    forgetReportExpand(TASK_ID);
    // An in-page link records its hash; the next page opens clean.
    history.replaceState(null, "", "/");
  });

  it("titles the page with the question and puts both actions on one line above the facts", () => {
    renderReport();
    const header = screen.getByRole("heading", { level: 1 }).closest("header") as HTMLElement;
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(QUESTION);
    expect(screen.queryByRole("heading", { name: artefact.title })).toBeNull();
    const plan = within(header).getByRole("button", { name: "See the plan" });
    const ask = within(header).getByRole("button", { name: "Ask about this analysis" });
    expect(plan.parentElement).toBe(ask.parentElement);
    expect(plan.parentElement).toHaveClass("print-hide", "flex");
    const facts = header.querySelector("dl") as HTMLElement;
    expect(plan.parentElement?.compareDocumentPosition(facts)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("states the facts on one line: sources linking to the references, the years, no study types", async () => {
    const user = userEvent.setup();
    renderReport();
    const facts = document.querySelector("header dl") as HTMLElement;
    const pairs = [...facts.querySelectorAll("dt")].map((dt) => `${dt.textContent}: ${dt.nextElementSibling?.textContent}`);
    expect(pairs).toEqual(["Sources: 12 cited out of 118 included", "Published: 2019–2024"]);
    // The count opens this page's References, not the Sources tab (owner,
    // round 11).
    const count = within(facts).getByRole("link", { name: "12 cited out of 118 included" });
    expect(count).toHaveAttribute("href", "#references");
    expect(facts).toHaveClass("text-meta");
    expect(screen.queryByText("Study types")).toBeNull();
    const references = screen.getByRole("region", { name: "References" });
    expect(within(references).queryByRole("list")).toBeNull();
    await user.click(count);
    expect(within(references).getByRole("list")).toBeInTheDocument();
    expect(window.location.hash).toBe("#references");
  });

  it("puts the date on its own line under the title, with its year", () => {
    renderReport();
    const title = screen.getByRole("heading", { level: 1 });
    const dateline = title.nextElementSibling as HTMLElement;
    expect(dateline).toHaveTextContent("Last updated 5 November 2026");
    expect(dateline).toHaveClass("text-meta", "text-grey");
    expect(dateline.querySelector("time")).toHaveTextContent("5 November 2026");
    expect(document.querySelector("header dl")).not.toHaveTextContent("Last updated");
  });

  it("orders the page and its contents: most relevant sources ending the executive summary, the method last", () => {
    renderReport();
    const nav = screen.getByRole("navigation", { name: "Contents" });
    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Executive summary",
      "Key findings",
      "Case studies",
      // Back above the Full report (owner, round 11).
      "Most relevant sources",
      "Full report",
      // In full: the sidebar wraps a long title rather than cutting it.
      "What families said about the cost of a school meal in the cities",
      "References",
      "How the evidence was gathered",
    ]);
    const cases = screen.getByRole("heading", { name: "Case studies" });
    const sources = screen.getByRole("heading", { name: "Most relevant sources" });
    const fullReport = screen.getByRole("heading", { name: "Full report" });
    expect(cases.compareDocumentPosition(sources) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(sources.compareDocumentPosition(fullReport) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("leaves the method out of the contents when its section will not render", () => {
    renderReport({ landscape: { isError: true } });
    const nav = screen.getByRole("navigation", { name: "Contents" });
    expect(within(nav).queryByRole("link", { name: "How the evidence was gathered" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "How the evidence was gathered" })).toBeNull();
  });

  it("sets the method's counts as a ruled table, the figures in one column, under one heading", async () => {
    const user = userEvent.setup();
    renderReport({ funnel: { found: 312, relevant: 118, quality_checked: 90, read_in_full: 64, selected: 40, cited: 12 } });
    const method = screen.getByRole("heading", { level: 2, name: "How the evidence was gathered" });
    const section = method.closest("section") as HTMLElement;
    // Shut: the one line, at the References' size.
    expect(within(section).getByText("312 found → 118 included → 12 cited")).toHaveClass("text-lead", "max-md:text-body");
    await user.click(within(method).getByRole("button"));
    const counts = within(section).getByRole("table", { name: "How the evidence was gathered" });
    const rows = within(counts)
      .getAllByRole("row")
      .map((row) => [...row.children].map((cell) => cell.textContent).join(" "));
    // The Landscape funnel's names; quality-checked is not one of the five.
    expect(rows).toEqual(["Found 312", "Relevant 118", "Full text 64", "Shortlisted 40", "Cited 12"]);
    expect(within(counts).getAllByRole("cell").every((cell) => cell.classList.contains("tabular-nums"))).toBe(true);
    expect(within(counts).getAllByRole("cell").every((cell) => cell.classList.contains("text-right"))).toBe(true);
    // The plain sentence stays; the distributions are tables with captions,
    // not headings, so the outline keeps one heading for the section.
    expect(section).toHaveTextContent("The rest of this section covers only the cited sources; the Landscape tab shows the whole search.");
    expect(within(section).getByRole("table", { name: "Evidence types" })).toBeInTheDocument();
    expect(within(section).getAllByRole("heading")).toHaveLength(1);
  });

  it("links the method's rows to the sources table where it can filter, the label in the Link style (owner, round 12)", async () => {
    const user = userEvent.setup();
    renderReport({
      funnel: { found: 312, relevant: 118, read_in_full: 64, selected: 40, cited: 12 },
      landscape: {
        isError: false,
        data: {
          years: { 2019: 1 },
          evidence_types: { "Systematic Review and Meta-Analysis": 2 },
          geographies: { "United Kingdom": 2, "Not reported": 1 },
          themes: [{ theme_id: "t-1", name: "School food", size: 2 }],
        },
      },
    });
    const method = screen.getByRole("heading", { level: 2, name: "How the evidence was gathered" });
    const section = method.closest("section") as HTMLElement;
    await user.click(within(method).getByRole("button"));
    const all = `/tasks/${TASK_ID}/sources/all`;
    const href = (name: string) => within(section).getByRole("link", { name }).getAttribute("href");
    expect(href("Found")).toBe(`${all}?status=all`);
    expect(href("Relevant")).toBe(`${all}?status=Included`);
    expect(href("Cited")).toBe(`${all}?cited=true`);
    expect(href("Full text")).toBe(`${all}?depth=full_text`);
    // The References' quiet link, not Electric Blue (owner, round 13).
    for (const link of within(section).getAllByRole("link").filter((node) => node.closest("table") !== null)) {
      expect(link).toHaveClass("text-navy", "decoration-line-2");
      expect(link).not.toHaveClass("text-blue");
    }
    // The clickable-only rule: the table has no filter for these.
    for (const plain of ["Shortlisted", "Not reported"]) {
      expect(within(section).queryByRole("link", { name: plain })).toBeNull();
      expect(within(section).getByText(plain)).toBeInTheDocument();
    }
    expect(href("Systematic review and meta-analysis")).toBe(
      `${all}?cited=true&type=Systematic+Review+and+Meta-Analysis`,
    );
    expect(href("2019")).toBe(`${all}?cited=true&year_from=2019&year_to=2019`);
    expect(href("United Kingdom")).toBe(`${all}?cited=true&country=United+Kingdom`);
    expect(href("School food")).toBe(`${all}?cited=true&theme=t-1`);
    // The label is the link; the count stays a plain right-aligned figure.
    const theme = within(section).getByRole("link", { name: "School food" }).closest("tr") as HTMLElement;
    expect(within(theme).getAllByRole("link")).toHaveLength(1);
    expect(within(theme).getByRole("cell")).toHaveClass("text-right");
  });

  it("outlines parts as h2 and their sections as h3, collapsible headings holding their button", () => {
    renderReport();
    const outline = screen
      .getAllByRole("heading")
      .filter((heading) => heading.closest("main") !== null)
      .map((heading) => `${heading.tagName} ${heading.textContent?.replace(/(Show|Hide)$/, "").trim()}`);
    expect(outline).toEqual([
      `H1 ${QUESTION}`,
      "H2 Executive summary",
      "H3 Key findings",
      "H3 Case studies",
      "H4 Leeds pilot",
      "H3 Most relevant sources",
      "H2 Full report",
      "H3 What families said about the cost of a school meal in the cities",
      "H2 References",
      "H2 How the evidence was gathered",
    ]);
    const body = screen.getByRole("heading", { level: 3, name: /What families said/ });
    expect(body.querySelector("button")).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "Show all" })).toBeInTheDocument();
  });

  it("makes the marker the claim's one control, its numbers sorted and named for what it opens", async () => {
    const user = userEvent.setup();
    renderReport();
    const findings = screen.getByRole("heading", { name: "Key findings" }).closest("section") as HTMLElement;
    const marker = within(findings).getByRole("button", { name: "Sources 7 and 12" });
    expect(marker).toHaveTextContent("[7,12]");
    expect(marker).toHaveClass("citation-number", "ml-1");
    expect(marker).not.toHaveClass("mx-1");
    // The words are not a tab stop; the marker is.
    const words = within(findings).getByText(KF_CLAIM);
    expect(words).not.toHaveAttribute("tabindex");
    expect(words).not.toHaveAttribute("role");
    // The preview opens on the marker's keyboard focus too.
    marker.focus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Council letters");
    await user.keyboard("{Escape}");
    // One source names its title.
    await user.click(screen.getByRole("button", { name: /What families said/ }));
    expect(screen.getByRole("button", { name: "Source 7: School meals trial" })).toHaveTextContent("[7]");
  });

  it("shows the claim's verdict once under the Claim, the citation boxes holding the source and the quote (round 13)", async () => {
    const user = userEvent.setup();
    renderReport();
    const findings = screen.getByRole("heading", { name: "Key findings" }).closest("section") as HTMLElement;
    await user.click(within(findings).getByRole("button", { name: "Sources 7 and 12" }));
    const sheet = await screen.findByRole("dialog");
    expect(sheet.querySelectorAll("[data-judge-block]")).toHaveLength(1);
    expect(within(sheet).getAllByText("Tier 2 · grounded")).toHaveLength(1);
    const boxes = sheet.querySelectorAll("[data-citation-block]");
    expect(boxes).toHaveLength(2);
    for (const box of boxes) expect(box.querySelector("[data-judge-block]")).toBeNull();
  });

  it("titles the report with the plan's refined question, the task's question without one (round 14)", () => {
    const view = renderReport({
      plan: { plan: { question: "What raises take-up of free school meals among eligible families?" } },
    });
    expect(
      screen.getByRole("heading", { level: 1, name: "What raises take-up of free school meals among eligible families?" }),
    ).toBeInTheDocument();
    view.unmount();
    renderReport();
    expect(screen.getByRole("heading", { level: 1, name: QUESTION })).toBeInTheDocument();
  });

  it("sets the boxes' marks line under the title: type, strength with its square, then the facts at Meta Grey (round 14)", () => {
    renderReport();
    const card = screen.getByRole("heading", { level: 4, name: "Leeds pilot" }).closest("li") as HTMLElement;
    const sources = screen.getByRole("heading", { name: "Most relevant sources" }).closest("section") as HTMLElement;
    const entry = within(sources).getAllByRole("listitem")[0];
    for (const box of [card, entry]) {
      // No chips: one marks line.
      expect(box.querySelector(".text-\\[11\\.5px\\]")).toBeNull();
      const line = box.querySelector("[data-marks-line]") as HTMLElement;
      expect(line).toHaveClass("text-meta", "text-grey");
      expect(within(line).getByTestId("strength-mark")).toBeInTheDocument();
    }
    expect(card.querySelector("[data-marks-line]")).toHaveTextContent(
      /^RCTs and quasi-experimental studies\s*·\s*Very strong$/,
    );
    // Under the title, before the prose.
    const title = within(card).getByRole("heading", { level: 4 });
    expect(title.nextElementSibling).toHaveAttribute("data-marks-line");
    expect(entry.querySelector("[data-marks-line]")).toHaveTextContent(
      /^Systematic review and meta-analysis\s*·\s*Very strong\s*·\s*Cited by 2 claims$/,
    );
  });

  it("sets the method as one column: every table at the prose measure, one figure column, figures alone (round 14)", async () => {
    const user = userEvent.setup();
    renderReport({
      funnel: { found: 312, relevant: 118, read_in_full: 64, selected: 40, cited: 12 },
      landscape: {
        isError: false,
        data: { years: { 2019: 1 }, evidence_types: { "Systematic Review and Meta-Analysis": 2 }, themes: [{ theme_id: "t-1", name: "School food", size: 2 }] },
      },
    });
    const method = screen.getByRole("heading", { level: 2, name: "How the evidence was gathered" });
    const section = method.closest("section") as HTMLElement;
    await user.click(within(method).getByRole("button"));
    const tables = within(section).getAllByRole("table");
    expect(tables.length).toBe(4);
    for (const table of tables) {
      expect(table).toHaveClass("w-full", "max-w-prose-measure", "table-fixed");
      expect(table.className).not.toMatch(/32rem/);
      for (const cell of within(table).getAllByRole("cell")) {
        expect(cell).toHaveClass("w-20", "text-right", "tabular-nums", "text-navy");
        expect(cell.textContent).toMatch(/^\d+$/);
      }
    }
    // One spacing between the parts, and the sentence once.
    expect(tables[0].parentElement).toHaveClass("space-y-8");
    expect(within(section).getAllByText(/covers only the cited sources/)).toHaveLength(1);
  });

  it("sets the appraisal chip in the soft tone and evidence types in sentence case", () => {
    renderReport();
    const card = screen.getByRole("heading", { level: 4, name: "Leeds pilot" }).closest("li") as HTMLElement;
    expect(within(card).getByText("Very strong")).not.toHaveClass("text-blue");
    expect(within(card).getByText("RCTs and quasi-experimental studies")).toBeInTheDocument();
    const sources = screen.getByRole("heading", { name: "Most relevant sources" }).closest("section") as HTMLElement;
    expect(within(sources).getByText("Systematic review and meta-analysis")).toBeInTheDocument();
    // The source title is a link to its dossier; each entry in the case
    // studies' ruled card (owner, round 11).
    expect(within(sources).getByRole("link", { name: "School meals trial" })).toHaveAttribute(
      "href",
      expect.stringContaining("source=src-7"),
    );
    expect(within(sources).getByRole("list")).toHaveClass("grid", "gap-3");
    for (const entry of within(sources).getAllByRole("listitem")) {
      expect(entry).toHaveClass("border", "border-line", "p-4");
    }
    expect(card).toHaveClass("border", "border-line", "p-4");
  });

  it("folds the contents under the title block on a phone, closing once a section is chosen", async () => {
    stubNarrow(true);
    const user = userEvent.setup();
    renderReport();
    const contents = screen
      .getAllByRole("navigation", { name: "Contents" })
      .find((nav) => nav.classList.contains("md:hidden")) as HTMLElement;
    expect(contents).toBeDefined();
    // Under the title block, before the executive summary.
    const header = screen.getByRole("heading", { level: 1 }).closest("header") as HTMLElement;
    expect(header.nextElementSibling).toBe(contents);
    const toggle = within(contents).getByRole("button", { name: "Contents" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(contents).queryByRole("link")).toBeNull();
    await user.click(toggle);
    await user.click(within(contents).getByRole("link", { name: "References" }));
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(contents).queryByRole("link")).toBeNull();
  });

  it("carries no phone contents on a wide screen", () => {
    stubNarrow(false);
    renderReport();
    expect(screen.getAllByRole("navigation", { name: "Contents" })).toHaveLength(1);
  });
});


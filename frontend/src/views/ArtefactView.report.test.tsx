import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { ArtefactView, reportDateLabel } from "./ArtefactView";
import { evidenceTypeLabel } from "./artefactPresentation";
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
  grounding_tier: "tier_2",
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
}: { landscape?: Landscape; publicView?: boolean } = {}) {
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
  vi.mocked(queries.useFunnel).mockReturnValue({ data: undefined } as ReturnType<typeof queries.useFunnel>);
  vi.mocked(queries.useApiClient).mockReturnValue({} as ReturnType<typeof queries.useApiClient>);
  vi.mocked(queries.usePlan).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.usePlan>);
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

  it("states the facts on one line: sources as a link, the years, the date with its year, no study types", () => {
    renderReport();
    const facts = document.querySelector("header dl") as HTMLElement;
    const pairs = [...facts.querySelectorAll("dt")].map((dt) => `${dt.textContent}: ${dt.nextElementSibling?.textContent}`);
    expect(pairs).toEqual([
      "Sources: 12 cited out of 118 included",
      "Published: 2019–2024",
      "Last updated: 5 November 2026",
    ]);
    expect(within(facts).getByRole("link", { name: "12 cited out of 118 included" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all?cited=true`,
    );
    expect(facts).toHaveClass("text-meta");
    expect(screen.queryByText("Study types")).toBeNull();
  });

  it("orders the page and its contents: most relevant sources just before the references, then the method", () => {
    renderReport();
    const nav = screen.getByRole("navigation", { name: "Contents" });
    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Executive summary",
      "Key findings",
      "Case studies",
      "Full report",
      // In full: the sidebar wraps a long title rather than cutting it.
      "What families said about the cost of a school meal in the cities",
      "Most relevant sources",
      "References",
      "How the evidence was gathered",
    ]);
    const sources = screen.getByRole("heading", { name: "Most relevant sources" });
    const references = screen.getByRole("heading", { name: "References" });
    const body = screen.getByRole("heading", { name: /What families said/ });
    expect(body.compareDocumentPosition(sources) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(sources.compareDocumentPosition(references) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("leaves the method out of the contents when its section will not render", () => {
    renderReport({ landscape: { isError: true } });
    const nav = screen.getByRole("navigation", { name: "Contents" });
    expect(within(nav).queryByRole("link", { name: "How the evidence was gathered" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "How the evidence was gathered" })).toBeNull();
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
      "H2 Full report",
      "H3 What families said about the cost of a school meal in the cities",
      "H3 Most relevant sources",
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

  it("sets the appraisal chip in the soft tone and evidence types in sentence case", () => {
    renderReport();
    const card = screen.getByRole("heading", { level: 4, name: "Leeds pilot" }).closest("li") as HTMLElement;
    expect(within(card).getByText("Very strong")).not.toHaveClass("text-blue");
    expect(within(card).getByText("RCTs and quasi-experimental studies")).toBeInTheDocument();
    const sources = screen.getByRole("heading", { name: "Most relevant sources" }).closest("section") as HTMLElement;
    expect(within(sources).getByText("Systematic review and meta-analysis")).toBeInTheDocument();
    // The source title is a link to its dossier, the entries ruled, not boxed.
    expect(within(sources).getByRole("link", { name: "School meals trial" })).toHaveAttribute(
      "href",
      expect.stringContaining("source=src-7"),
    );
    expect(within(sources).getByRole("list")).toHaveClass("divide-y", "border-t");
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

describe("reportDateLabel", () => {
  it("always carries the year when asked, for the facts line", () => {
    const now = new Date("2026-11-06T10:00:00Z");
    expect(reportDateLabel("2026-11-05T12:00:00Z", now)).toBe("5 November");
    expect(reportDateLabel("2026-11-05T12:00:00Z", now, true)).toBe("5 November 2026");
  });
});

describe("evidenceTypeLabel", () => {
  it("writes the classifier's labels in sentence case, acronyms kept", () => {
    expect(evidenceTypeLabel("Systematic Review and Meta-Analysis")).toBe("Systematic review and meta-analysis");
    expect(evidenceTypeLabel("RCTs and Quasi-Experimental Studies")).toBe("RCTs and quasi-experimental studies");
    expect(evidenceTypeLabel("Other (Non-evidence documents)")).toBe("Other (non-evidence documents)");
    expect(evidenceTypeLabel("Unknown / Insufficient information")).toBe("Unknown / insufficient information");
    expect(evidenceTypeLabel("Cohort study")).toBe("Cohort study");
  });
});

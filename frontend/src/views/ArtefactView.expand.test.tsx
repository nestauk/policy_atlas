import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { ArtefactView } from "./ArtefactView";
import { forgetReportExpand, useForgetReportExpandOnLeave } from "./ArtefactOutline";
import * as queries from "../api/queries";
import * as store from "../store";
import * as conversationState from "./workspace/chat/conversationState";

/*
 * The committed report page, round 12 (task 058): the expand state kept per
 * task while the reader moves between its tabs and forgotten when they leave
 * it, the case-study and most-relevant-source chips (classification then
 * strength, the reasons on hover), and the claim provenance sheet's one type
 * scale. The watched-live path is in `ArtefactView.live.test.tsx`.
 */

const TASK_ID = "5b0d7f3e-21c4-4a6e-9a59-2f7c1d8e4b10";
const QUESTION = "What raises take-up of free school meals?";
const TYPE_REASON = "Explicit systematic search and synthesis across 42 trials.";

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
  quote: "Charges stopped families taking a place.",
  grounding_tier: "tier_2",
  ...extra,
});

const KF_PROSE = "- Cost decides take-up: families weigh the charge first.";
const KF_CLAIM = "families weigh the charge first";
const CARD_PROSE = "Take-up rose from 18% to 61% in two years.";
const body = (title: string, prose: string, id: string) => ({
  title,
  role: "standard" as const,
  summary: `${title} in one line.`,
  summary_status: "verified" as const,
  blocks: [{ block_id: id, prose, claims: [] }],
});

const artefact = {
  artefact_id: "c930515b-a383-4e58-bdb6-d43d47f2bdd3",
  title: "Generated title for the download",
  coverage_snapshot: { source_count: 2, included: 40 },
  most_relevant_notes: [],
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
                citation(7, "School meals trial", {
                  appraisal_label: "Very strong",
                  evidence_type: "Systematic Review and Meta-Analysis",
                  grounding_rationale: "The passage gives the take-up figures directly.",
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
          prose: CARD_PROSE,
          since_year: 2019,
          claims: [
            {
              claim_id: "card-claim",
              claim_type: "citation" as const,
              text: CARD_PROSE,
              span: [0, CARD_PROSE.length],
              citations: [
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
    body("Costs and charges", "Charges decide take-up.", "b1"),
    body("Letters and outreach", "Letters raised take-up in two councils.", "b2"),
  ],
};

const dossierRead = vi.fn();

function wire() {
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
  vi.mocked(queries.useLandscape).mockReturnValue({ isError: false, data: undefined } as unknown as ReturnType<
    typeof queries.useLandscape
  >);
  vi.mocked(queries.useFunnel).mockReturnValue({ data: undefined } as ReturnType<typeof queries.useFunnel>);
  // The chunk-context read behind the provenance sheet's passage.
  vi.mocked(queries.useApiClient).mockReturnValue({
    GET: async () => ({
      data: {
        context: "Charges stopped families taking a place. Few came back.",
        previous: "The survey ran in 2021.",
        next: null,
        span_start: 0,
        span_end: 10,
        clamped: false,
        year: 2021,
        venue: "BMJ Open",
        authorships: [{ name: "Alex Sampleton", institutions: ["University of Exampleshire"] }],
      },
    }),
  } as unknown as ReturnType<typeof queries.useApiClient>);
  vi.mocked(queries.useSourceDossier).mockImplementation((_taskId, sourceId) => {
    dossierRead(sourceId);
    return {
      isPending: false,
      isError: false,
      data: { classification_reason: TYPE_REASON },
    } as unknown as ReturnType<typeof queries.useSourceDossier>;
  });
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
}

function renderReport() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
          <Routes>
            <Route path="/tasks/:taskId/result" element={<ArtefactView />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

const sectionToggle = (title: string) => screen.getByRole("button", { name: new RegExp(`^${title}`) });

function LeavesTask({ taskId }: { taskId: string }) {
  useForgetReportExpandOnLeave(taskId);
  return null;
}

describe("the report's expand state (owner, round 12)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    wire();
  });
  afterEach(() => {
    forgetReportExpand(TASK_ID);
  });

  it("opens a finished report fresh with its sections shut and the control on Show all", () => {
    renderReport();
    expect(sectionToggle("Costs and charges")).toHaveAttribute("aria-expanded", "false");
    expect(sectionToggle("Letters and outreach")).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "References" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "Show all" })).toBeInTheDocument();
  });

  it("keeps what the reader left while they move between the task's tabs", async () => {
    const user = userEvent.setup();
    const first = renderReport();
    await user.click(screen.getByRole("button", { name: "Show all" }));
    await user.click(sectionToggle("Letters and outreach"));
    expect(sectionToggle("Costs and charges")).toHaveAttribute("aria-expanded", "true");
    expect(sectionToggle("Letters and outreach")).toHaveAttribute("aria-expanded", "false");
    // To Sources and back: the Result tab's route unmounts and mounts again.
    first.unmount();
    renderReport();
    expect(screen.getByRole("button", { name: "Hide all" })).toBeInTheDocument();
    expect(sectionToggle("Costs and charges")).toHaveAttribute("aria-expanded", "true");
    expect(sectionToggle("Letters and outreach")).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "References" })).toHaveAttribute("aria-expanded", "true");
  });

  it("forgets it when the reader leaves the task, so coming back is a fresh entry", async () => {
    const user = userEvent.setup();
    const first = renderReport();
    const shell = render(<LeavesTask taskId={TASK_ID} />);
    await user.click(screen.getByRole("button", { name: "Show all" }));
    first.unmount();
    // Leaving the task: the task shell unmounts its hook (or the task changes).
    shell.unmount();
    renderReport();
    expect(screen.getByRole("button", { name: "Show all" })).toBeInTheDocument();
    expect(sectionToggle("Costs and charges")).toHaveAttribute("aria-expanded", "false");
  });
});

describe("the case-study and most-relevant-source chips (owner, round 12)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    wire();
  });
  afterEach(() => {
    forgetReportExpand(TASK_ID);
  });

  it("reads classification, then strength with the Sources table's tone square, both with the help cursor", () => {
    renderReport();
    const card = screen.getByRole("heading", { level: 4, name: "Leeds pilot" }).closest("li") as HTMLElement;
    const sources = screen.getByRole("heading", { name: "Most relevant sources" }).closest("section") as HTMLElement;
    for (const entry of [card, within(sources).getAllByRole("listitem")[0]]) {
      const type = within(entry).getByText("Systematic review and meta-analysis");
      const strength = within(entry).getByText("Very strong");
      // Classification first, the strength after it.
      expect(type.compareDocumentPosition(strength) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      const mark = within(entry).getByTestId("strength-mark");
      expect(mark).toHaveAttribute("data-tone", "green");
      // The Sources table's own square and colour (round 12: green, yellow, red).
      expect(mark).toHaveClass("bg-green", "size-1.5");
      expect(type.closest(".cursor-help")).not.toBeNull();
      expect(strength.closest(".cursor-help")).not.toBeNull();
    }
    // Nothing is read until a hover asks for the reasoning.
    expect(dossierRead).not.toHaveBeenCalled();
  });

  it("shows the classification's reasoning from the cited source on hover", async () => {
    const user = userEvent.setup();
    renderReport();
    const card = screen.getByRole("heading", { level: 4, name: "Leeds pilot" }).closest("li") as HTMLElement;
    await user.hover(within(card).getByText("Systematic review and meta-analysis"));
    const typeTip = await screen.findByRole("tooltip");
    expect(typeTip).toHaveTextContent(TYPE_REASON);
    const sizeOf = (tip: HTMLElement) => {
      // The Tooltip's own content element carries its type size.
      const content = [...document.querySelectorAll("[data-side]")].find((node) => node.contains(tip)) ?? tip;
      return { meta: content.classList.contains("text-meta"), caption: content.classList.contains("text-caption") };
    };
    const typeSize = sizeOf(typeTip);
    expect(dossierRead).toHaveBeenCalledWith("src-7");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull());
    await user.hover(within(card).getByText("Very strong"));
    await waitFor(() =>
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        "Very strong evidence strength — appraised from the document type: Systematic review and meta-analysis.",
      ),
    );
    // Both hovers at the one size, Meta, through the Tooltip itself.
    expect(typeSize).toEqual({ meta: true, caption: false });
    expect(sizeOf(screen.getByRole("tooltip"))).toEqual({ meta: true, caption: false });
  });
});

describe("the claim provenance sheet (owner, round 12)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    wire();
  });
  afterEach(() => {
    forgetReportExpand(TASK_ID);
  });

  it("sets the claim, then the quote, the source line, the evidence and the judge's words, ruled, with no chips", async () => {
    const user = userEvent.setup();
    renderReport();
    const findings = screen.getByRole("heading", { name: "Key findings" }).closest("section") as HTMLElement;
    await user.click(within(findings).getByRole("button", { name: "Source 7: School meals trial" }));
    const sheet = await screen.findByRole("dialog");
    const quote = await within(sheet).findByText("Charges stopped families taking a place.");
    expect(quote.tagName).toBe("MARK");
    // The source line reads as its reference does; the name is the one bold.
    const name = within(sheet).getByRole("button", { name: "School meals trial" });
    const line = name.closest("p") as HTMLElement;
    expect(line).toHaveTextContent("[7] Sampleton A (2021). School meals trial. BMJ Open.");
    expect(name).toHaveClass("font-bold");
    const bold = [...sheet.querySelectorAll(".font-bold, .font-semibold, .font-extrabold, strong, b")].filter(
      (node) => node.closest("[role=dialog] > div:first-child") === null,
    );
    expect(bold).toEqual([name]);
    // The quote comes before the source line.
    expect(quote.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The evidence at Meta, the judge's words under the verdict's Meta label.
    expect(within(sheet).getByText("Systematic review and meta-analysis").closest("p")).toHaveClass("text-meta");
    const verdict = within(sheet).getByText("Tier 2 · grounded");
    expect(verdict).toHaveClass("text-meta", "text-grey");
    expect(verdict.nextElementSibling).toHaveTextContent("The passage gives the take-up figures directly.");
    expect(verdict.nextElementSibling).toHaveClass("text-body");
    // No chips, no caption-sized type, one rule between the blocks.
    expect(sheet.querySelector(".text-\\[11\\.5px\\]")).toBeNull();
    expect(sheet.querySelector(".text-caption")).toBeNull();
    const blocks = within(sheet).getByText(KF_CLAIM).closest(".divide-y") as HTMLElement;
    expect(blocks).toHaveClass("divide-line");
    expect(blocks.children).toHaveLength(2);
  });
});

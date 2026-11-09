import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { ArtefactView } from "./ArtefactView";
import { AuthContext } from "../auth/AuthContext";
import type { AuthApi } from "../auth/types";
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
  ...extra,
});

const KF_PROSE = "- Cost decides take-up: families weigh the charge first.";
const KF_CLAIM = "families weigh the charge first";
const CARD_PROSE = "Take-up rose from 18% to 61% in two years.";
const COSTS_PROSE = "Charges decide take-up.";
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
              // The verdict is the claim's (round 13).
              grounding_tier: "tier_2",
              grounding_rationale: "The passage gives the take-up figures directly.",
              text: KF_CLAIM,
              span: [KF_PROSE.indexOf(KF_CLAIM), KF_PROSE.indexOf(KF_CLAIM) + KF_CLAIM.length],
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
              // The verdict is the claim's (round 13).
              grounding_tier: "tier_2",
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
    {
      ...body("Costs and charges", COSTS_PROSE, "b1"),
      blocks: [
        {
          block_id: "b1",
          prose: COSTS_PROSE,
          claims: [
            {
              // Two quotes from one source, and a second source.
              claim_id: "costs-1",
              claim_type: "citation" as const,
              grounding_tier: "tier_2",
              text: COSTS_PROSE,
              span: [0, COSTS_PROSE.length],
              citations: [
                citation(7, "School meals trial", { citation_id: "cit-7a", quote: "First quote." }),
                citation(7, "School meals trial", { citation_id: "cit-7b", quote: "Second quote." }),
                citation(12, "Council letters", { citation_id: "cit-12", quote: "Third quote." }),
              ],
            },
          ],
        },
      ],
    },
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
      data: { source_id: sourceId, title: "School meals trial", cited: true, classification_reason: TYPE_REASON },
    } as unknown as ReturnType<typeof queries.useSourceDossier>;
  });
  vi.mocked(queries.useEvidence).mockReturnValue({ data: undefined, isPending: false } as unknown as ReturnType<
    typeof queries.useEvidence
  >);
  vi.mocked(queries.useFindings).mockReturnValue({ data: undefined, isPending: false } as unknown as ReturnType<
    typeof queries.useFindings
  >);
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

const signedOut: AuthApi = {
  getAccessToken: async () => null,
  signIn: vi.fn(),
  signOut: vi.fn(),
  onUnauthenticated: vi.fn(),
  user: null,
  status: "unauthenticated",
};

function renderReport() {
  return render(
    <AuthContext.Provider value={signedOut}>
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
          <Routes>
            <Route path="/tasks/:taskId/result" element={<ArtefactView />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>
    </AuthContext.Provider>,
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

  it("sets the labelled Claim, the claim's one Judge, then the sources: the source line once, each quote labelled (round 13)", async () => {
    const user = userEvent.setup();
    renderReport();
    const findings = screen.getByRole("heading", { name: "Key findings" }).closest("section") as HTMLElement;
    await user.click(within(findings).getByRole("button", { name: "Source 7: School meals trial" }));
    const sheet = await screen.findByRole("dialog");
    const quote = await within(sheet).findByText("Charges stopped families taking a place.");
    // The claim's block: "Claim" over its words behind the blue rule.
    const claim = within(sheet).getByText(KF_CLAIM);
    expect(claim.parentElement).toHaveClass("border-l-2", "border-l-blue", "pl-3");
    expect(claim.parentElement?.previousElementSibling).toHaveTextContent("Claim");
    // The claim's one verdict, directly under the Claim, before the sources.
    const judge = sheet.querySelector("[data-judge-block]") as HTMLElement;
    expect(judge.closest("[data-citation-block]")).toBeNull();
    expect(claim.parentElement?.parentElement?.nextElementSibling).toBe(judge);
    expect(judge.querySelectorAll("[data-testid='ai-mark']")).toHaveLength(1);
    const verdict = within(judge).getByText("Tier 2 · grounded");
    expect(verdict).toHaveClass("font-semibold", "text-navy");
    expect(verdict.parentElement).toHaveClass("bg-blue-tint-2");
    expect(within(judge).getByText("The passage gives the take-up figures directly.")).toHaveClass("text-grey");
    // One label over the boxes, counting sources.
    const labels = [...sheet.querySelectorAll("[data-provenance-label]")].map((label) => label.textContent);
    expect(labels).toEqual(["Claim", "Judge", "Source", "Quote"]);
    // One box, a hairline all round; the coloured rule is the Claim's alone.
    const block = sheet.querySelector("[data-citation-block]") as HTMLElement;
    expect(block).toHaveClass("border", "border-line", "p-4");
    expect(sheet.querySelectorAll("[class*='border-l-2'], [class*='border-l-[3px]']")).toHaveLength(1);
    // Title first, then the authors, year and venue in Grey.
    const name = within(block).getByRole("button", { name: "School meals trial" });
    expect(name.closest("p")).toHaveTextContent(/^\[7\]\s*School meals trial$/);
    expect(within(block).getByText("Sampleton A · 2021 · BMJ Open")).toHaveClass("text-grey");
    // The evidence type carries its reasoning on hover, as the badges do.
    const type = within(block).getByText("Systematic review and meta-analysis");
    expect(type).toHaveClass("reason-word");
    expect(type.closest(".cursor-help")).not.toBeNull();
    expect(quote.tagName).toBe("MARK");
    expect(name.compareDocumentPosition(quote) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // One type scale and no chips (round 12).
    expect(sheet.querySelector(".text-\\[11\\.5px\\]")).toBeNull();
    expect(sheet.querySelector(".text-caption")).toBeNull();
    await user.hover(type);
    await waitFor(() => expect(screen.getByRole("tooltip")).toHaveTextContent(TYPE_REASON));
  });

  it("groups a claim's citations by source: one box per source, its quotes each labelled, the label counting sources", async () => {
    const user = userEvent.setup();
    renderReport();
    await user.click(screen.getByRole("button", { name: /^Costs and charges/ }));
    const body = screen.getByRole("heading", { name: /Costs and charges/ }).closest("section") as HTMLElement;
    await user.click(within(body).getByRole("button", { name: /^Sources? 7/ }));
    const sheet = await screen.findByRole("dialog");
    await waitFor(() => expect(sheet.querySelectorAll("[data-citation-block]")).toHaveLength(2));
    const boxes = [...sheet.querySelectorAll("[data-citation-block]")] as HTMLElement[];
    expect(boxes).toHaveLength(2);
    // The label over the boxes counts sources, never quotes.
    expect(within(sheet).getByText("Sources · 2")).toHaveAttribute("data-provenance-label");
    // Two quotes from one source: the source line once, two labelled quotes.
    expect(within(boxes[0]).getAllByRole("button", { name: "School meals trial" })).toHaveLength(1);
    const labels0 = [...boxes[0].querySelectorAll("[data-provenance-label]")].map((label) => label.textContent);
    expect(labels0).toEqual(["Quote 1", "Quote 2"]);
    // The second source in its own box with its one quote.
    expect(within(boxes[1]).getByRole("button", { name: "Council letters" })).toBeInTheDocument();
    // A single quote keeps "Quote".
    const labels1 = [...boxes[1].querySelectorAll("[data-provenance-label]")].map((label) => label.textContent);
    expect(labels1).toEqual(["Quote"]);
    // One verdict for the claim.
    expect(sheet.querySelectorAll("[data-judge-block]")).toHaveLength(1);
  });

  it("offers Back to the claim on a source opened from the sheet, and returns to the same claim", async () => {
    const user = userEvent.setup();
    renderReport();
    const findings = screen.getByRole("heading", { name: "Key findings" }).closest("section") as HTMLElement;
    await user.click(within(findings).getByRole("button", { name: "Source 7: School meals trial" }));
    const sheet = await screen.findByRole("dialog");
    await user.click(within(sheet).getByRole("button", { name: "School meals trial" }));
    // "Back" on screen, "Back to the claim" by name and in its tooltip.
    const back = await screen.findByRole("button", { name: "Back to the claim" });
    expect(back).toHaveTextContent(/^Back$/);
    expect(back.querySelector("svg")).not.toBeNull();
    await user.hover(back);
    await waitFor(() => expect(screen.getByRole("tooltip")).toHaveTextContent("Back to the claim"));
    // In the dossier's header, before the close button.
    expect(back.compareDocumentPosition(screen.getByRole("button", { name: "Close panel" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await user.click(back);
    const again = await screen.findByRole("dialog");
    await waitFor(() => expect(within(again).getByText(KF_CLAIM)).toBeInTheDocument());
    expect(within(again).queryByRole("button", { name: "Back to the claim" })).toBeNull();
  });

  it("offers no Back control on a source opened from elsewhere on the page", async () => {
    const user = userEvent.setup();
    renderReport();
    const sources = screen.getByRole("heading", { name: "Most relevant sources" }).closest("section") as HTMLElement;
    await user.click(within(sources).getByRole("link", { name: "School meals trial" }));
    await screen.findByRole("dialog");
    expect(screen.queryByRole("button", { name: "Back to the claim" })).toBeNull();
  });
});


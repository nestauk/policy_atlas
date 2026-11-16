import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import * as store from "../store";
import { createInitialRunStreamState } from "../store";
import type { LiveSection, RunStatus, RunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { ArtefactView } from "./ArtefactView";
import { forgetReportExpand } from "./ArtefactOutline";
import * as conversationState from "./workspace/chat/conversationState";

/*
 * The Result tab's page states around a run (task 058, N8 and N11): before
 * writing, a paused run, a re-run over an existing report, and the report
 * that stays ready until the reader opens it.
 */

const TASK_ID = "02da1b53-7104-4724-9944-f145e165b847";
const QUESTION = "What works to raise take-up of free childcare places?";
const ARTEFACT_ID = "c930515b-a383-4e58-bdb6-d43d47f2bdd3";

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
  return {
    ...actual,
    useActiveConversation: vi.fn(),
    useConversationMutations: vi.fn(),
  };
});

vi.mock("../lib/title", () => ({ useDocumentTitle: vi.fn() }));

const committedArtefact = {
  artefact_id: ARTEFACT_ID,
  title: "The old report",
  coverage_snapshot: null,
  most_relevant_notes: [],
  references: [],
  sections: [
    {
      title: "Body",
      role: "standard" as const,
      blocks: [{ block_id: "body", prose: "Body prose.", claims: [] }],
    },
  ],
};

interface World {
  artefact: typeof committedArtefact | null;
  latestRun: { capability_run_id: string; status: RunStatus; started_at: string; ended_at: string | null } | null;
  stream: RunStreamState;
}

const world: World = { artefact: null, latestRun: null, stream: createInitialRunStreamState() };

function streamOf(status: RunStatus, sections: LiveSection[] = [], id = "run-2"): RunStreamState {
  return {
    ...createInitialRunStreamState(),
    run: { id, status, startedAt: "2026-11-05T09:58:00Z" },
    liveSections: Object.fromEntries(sections.map((section) => [section.index, section])),
  };
}

function wire() {
  vi.mocked(queries.useTask).mockImplementation(
    () =>
      ({
        data: { task_id: TASK_ID, name: "Childcare take-up", question: QUESTION, latest_run: world.latestRun },
      }) as unknown as ReturnType<typeof queries.useTask>,
  );
  vi.mocked(queries.useArtefact).mockImplementation(
    () =>
      (world.artefact === null
        ? { isPending: false, isError: true, error: { error: { code: "not_found" } }, data: undefined }
        : { isPending: false, isError: false, data: world.artefact }) as unknown as ReturnType<
        typeof queries.useArtefact
      >,
  );
  vi.mocked(queries.useConversations).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<
    typeof queries.useConversations
  >);
  vi.mocked(queries.useLandscape).mockReturnValue({ data: undefined } as unknown as ReturnType<
    typeof queries.useLandscape
  >);
  vi.mocked(queries.useFunnel).mockReturnValue({ data: undefined } as ReturnType<typeof queries.useFunnel>);
  vi.mocked(queries.useApiClient).mockReturnValue({} as ReturnType<typeof queries.useApiClient>);
  vi.mocked(queries.usePlan).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.usePlan>);
  vi.mocked(queries.useRuns).mockReturnValue({
    data: {
      data: [
        { capability_run_id: "run-1", artefact_id: ARTEFACT_ID, status: "succeeded", ended_at: "2026-11-03T15:00:00Z" },
        { capability_run_id: "run-2", artefact_id: null, status: "running", ended_at: null },
      ],
    },
  } as unknown as ReturnType<typeof queries.useRuns>);
  vi.mocked(store.useRunStream).mockImplementation(() => world.stream);
  vi.mocked(conversationState.useActiveConversation).mockReturnValue({
    setActiveConversation: vi.fn(),
  } as unknown as ReturnType<typeof conversationState.useActiveConversation>);
}

function page() {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/result`]}>
          <Routes>
            <Route path="/tasks/:taskId/result" element={<ArtefactView />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

const SECTIONS: LiveSection[] = [
  { index: 0, title: "Key findings", focus: "", state: "planned" },
  { index: 1, title: "Costs and funding", focus: "", state: "writing" },
];

describe("ArtefactView around a run", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-11-05T10:00:00Z"));
    world.artefact = null;
    world.latestRun = { capability_run_id: "run-2", status: "running", started_at: "2026-11-05T09:58:00Z", ended_at: null };
    world.stream = streamOf("running");
    wire();
  });
  afterEach(() => {
    vi.useRealTimers();
    forgetReportExpand(TASK_ID);
  });

  it("before writing shows the question and one sentence, not the old card", () => {
    render(page());
    expect(screen.getByRole("heading", { level: 1, name: QUESTION })).toBeInTheDocument();
    expect(screen.getByText("The report's sections are set out when writing begins.")).toBeInTheDocument();
    expect(screen.queryByText(/Preparing your results/)).toBeNull();
  });

  it("titles the live page with the plan's refined question (round 14)", () => {
    vi.mocked(queries.usePlan).mockReturnValue({
      data: { plan: { question: "What raises take-up of funded childcare among eligible families?" } },
    } as unknown as ReturnType<typeof queries.usePlan>);
    world.stream = streamOf("running", SECTIONS);
    render(page());
    expect(
      screen.getByRole("heading", { level: 1, name: "What raises take-up of funded childcare among eligible families?" }),
    ).toBeInTheDocument();
  });

  it("keeps the live body while the run is paused on a check-in", () => {
    world.stream = streamOf("paused", SECTIONS);
    render(page());
    expect(screen.getByRole("heading", { name: "Costs and funding" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: QUESTION })).toBeInTheDocument();
  });

  it("puts one plain line above an existing report while a new run starts", () => {
    world.artefact = committedArtefact;
    render(page());
    expect(screen.getByTestId("rerun-notice")).toHaveTextContent(
      "This report is from 3 November 2026. A new run started 2 min ago.",
    );
    // No button: the status bar and the sidebar are the routes to the run.
    expect(screen.queryByRole("button", { name: /run/i })).toBeNull();
    expect(screen.getByRole("heading", { name: "Body" })).toBeInTheDocument();
  });

  it("shows no re-run line while replaying the run that made the report", () => {
    world.artefact = committedArtefact;
    world.latestRun = { capability_run_id: "run-1", status: "succeeded", started_at: "2026-11-03T14:40:00Z", ended_at: "2026-11-03T15:00:00Z" };
    world.stream = streamOf("running", [], "run-1");
    render(page());
    expect(screen.queryByTestId("rerun-notice")).toBeNull();
  });

  it("keeps a run watched while writing on its live page until the committed report lands, then swaps", async () => {
    const view = render(page());
    world.stream = streamOf("running", SECTIONS);
    view.rerender(page());
    // The run ends: the stream says so first, while the read models still
    // show it running. The live page holds; nothing asks for a click.
    world.stream = streamOf("succeeded", [
      { ...SECTIONS[0], state: "filled", prose: "Headline." },
      { ...SECTIONS[1], state: "filled", prose: "Costs prose." },
    ]);
    view.rerender(page());
    expect(screen.getByRole("heading", { name: "Costs and funding" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Body" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Read the full report" })).toBeNull();

    // The read models catch up: the committed report takes the page.
    world.latestRun = { capability_run_id: "run-2", status: "succeeded", started_at: "2026-11-05T09:58:00Z", ended_at: "2026-11-05T10:00:00Z" };
    world.artefact = committedArtefact;
    view.rerender(page());
    expect(await screen.findByRole("heading", { name: "Body" })).toBeInTheDocument();
    // The title is still the question: the heading does not change at the
    // swap, and the generated title is the download's name only (round 10, D1).
    expect(screen.getByRole("heading", { level: 1, name: QUESTION })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "The old report" })).toBeNull();
    expect(screen.queryByText("Report ready")).toBeNull();
  });

  it("swaps in place: the same page and section elements, sections left open, what arrives fades in", async () => {
    const LIVE_PROSE = "Costs prose.";
    const view = render(page());
    world.stream = streamOf("running", SECTIONS);
    view.rerender(page());
    world.stream = streamOf("succeeded", [
      { ...SECTIONS[0], state: "filled", prose: "Headline." },
      {
        ...SECTIONS[1],
        state: "filled",
        prose: LIVE_PROSE,
        citations: [
          { start: 0, end: 12, n: 2, sourceId: "s1", title: "Smith 2023", citationId: null, claimId: null, quote: "" },
        ],
        // The verdict is the claim's (round 13).
        checkedClaims: [{ claimId: null, start: 0, end: 12, tier: "tier_2", rationale: null }],
      },
    ]);
    view.rerender(page());
    const main = screen.getByRole("main");
    const costs = screen.getByRole("heading", { name: "Costs and funding" }).closest("section") as HTMLElement;
    expect(within(costs).getByRole("img", { name: /^Citation 2, Smith 2023/ })).toHaveTextContent("[2]");

    world.latestRun = { capability_run_id: "run-2", status: "succeeded", started_at: "2026-11-05T09:58:00Z", ended_at: "2026-11-05T10:00:00Z" };
    world.artefact = {
      ...committedArtefact,
      title: QUESTION,
      sections: [
        { title: "Key findings", role: "key_findings" as const, blocks: [{ block_id: "kf", prose: "Headline.", claims: [] }] },
        {
          title: "Costs and funding",
          role: "standard" as const,
          blocks: [
            {
              block_id: "costs",
              prose: LIVE_PROSE,
              claims: [
                {
                  claim_id: "c1",
                  claim_type: "citation" as const,
                  text: LIVE_PROSE,
                  span: [0, 12],
                  grounding_tier: "tier_2",
                  citations: [{ citation_id: "x", n: 1, source_title: "Smith 2023", quote: "q" }],
                },
              ],
            },
          ],
        },
      ],
    } as unknown as typeof committedArtefact;
    view.rerender(page());
    // The page and the section are the same elements: React updated them.
    expect(screen.getByRole("main")).toBe(main);
    const after = screen.getByRole("heading", { name: "Costs and funding" }).closest("section") as HTMLElement;
    expect(after).toBe(costs);
    // The section the reader was reading stays open; its control fades in.
    expect(within(after).getByRole("button", { name: /Costs and funding/ })).toHaveAttribute("aria-expanded", "true");
    expect(within(after).getAllByText("Hide")[0].closest(".anim-swap-in")).not.toBeNull();
    // The marker is a control now, and its new number fades in.
    const marker = within(after).getByRole("button", { name: "Source 1: Smith 2023" });
    expect(marker).toHaveClass("anim-swap-in");
  });

  it("opens a report the reader watched being written with every section open and Hide all, kept across tabs (owner, round 12)", () => {
    const view = render(page());
    world.stream = streamOf("running", SECTIONS);
    view.rerender(page());
    world.stream = streamOf("succeeded", [
      { ...SECTIONS[0], state: "filled", prose: "Headline." },
      { ...SECTIONS[1], state: "filled", prose: "Costs prose." },
    ]);
    view.rerender(page());
    world.latestRun = { capability_run_id: "run-2", status: "succeeded", started_at: "2026-11-05T09:58:00Z", ended_at: "2026-11-05T10:00:00Z" };
    world.artefact = {
      ...committedArtefact,
      sections: [
        { title: "Key findings", role: "key_findings" as const, blocks: [{ block_id: "kf", prose: "Headline.", claims: [] }] },
        { title: "Costs and funding", role: "standard" as const, blocks: [{ block_id: "costs", prose: "Costs prose.", claims: [] }] },
        // Not on the live page: it takes the control's state.
        { title: "Outreach", role: "standard" as const, blocks: [{ block_id: "out", prose: "Outreach prose.", claims: [] }] },
      ],
    } as unknown as typeof committedArtefact;
    view.rerender(page());
    expect(screen.getByRole("button", { name: "Hide all" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Costs and funding/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /^Outreach/ })).toHaveAttribute("aria-expanded", "true");
    // To Sources and back: the Result tab mounts again on the same state.
    view.unmount();
    render(page());
    expect(screen.getByRole("button", { name: "Hide all" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Costs and funding/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /^Outreach/ })).toHaveAttribute("aria-expanded", "true");
  });

  it("swaps at a cut under reduced motion", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
    const view = render(page());
    world.stream = streamOf("running", SECTIONS);
    view.rerender(page());
    world.stream = streamOf("succeeded", [{ ...SECTIONS[1], state: "filled", prose: "Costs prose." }]);
    view.rerender(page());
    world.latestRun = { capability_run_id: "run-2", status: "succeeded", started_at: "2026-11-05T09:58:00Z", ended_at: "2026-11-05T10:00:00Z" };
    world.artefact = committedArtefact;
    view.rerender(page());
    expect(document.querySelector(".anim-swap-in")).toBeNull();
    vi.unstubAllGlobals();
  });

  it("serves the hover and the provenance sheet from a checked section while the run is live (round 8)", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const PROSE = "Costs prose.";
    world.stream = streamOf("running", [
      SECTIONS[0],
      {
        ...SECTIONS[1],
        state: "filled",
        prose: PROSE,
        citations: [
          {
            start: 0,
            end: 12,
            n: 2,
            sourceId: "s1",
            title: "Smith 2023",
            citationId: "cit-1",
            claimId: "claim-1",
            quote: "Charges stopped families taking a place.",
          },
        ],
        // The verdict is the claim's (round 13).
        checkedClaims: [{ claimId: "claim-1", start: 0, end: 12, tier: "tier_2", rationale: null }],
      },
      { index: 2, title: "Outreach", focus: "", state: "writing" },
    ]);
    render(page());
    const costs = screen.getByRole("heading", { name: "Costs and funding" }).closest("section") as HTMLElement;
    // The judged marker is a control now, as on the committed report.
    const marker = within(costs).getByRole("button", { name: "Source 2: Smith 2023" });
    expect(marker).toHaveTextContent("[2]");
    // Hover: the citation's title, its quote and its tier.
    await user.hover(within(costs).getByText(PROSE));
    const tip = await screen.findByRole("tooltip");
    expect(tip).toHaveTextContent("Smith 2023");
    expect(tip).toHaveTextContent("Charges stopped families taking a place.");
    expect(tip).toHaveTextContent("Tier 2 · grounded");
    await user.unhover(within(costs).getByText(PROSE));
    // Click: the sheet, built from what the run knows.
    await user.click(marker);
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getByText(PROSE)).toBeInTheDocument();
    expect(within(sheet).getByText("Tier 2 · grounded")).toBeInTheDocument();
    // The title is not a link before the commit; the quote stands in for the
    // passage the lookup could not give here; no rationale, no appraisal.
    expect(within(sheet).getByText("Smith 2023").closest("button")).toBeNull();
    expect(await within(sheet).findByText("“Charges stopped families taking a place.”")).toBeInTheDocument();
    expect(within(sheet).queryByText(/^Judge:/)).toBeNull();
  });

  it("keeps a live claim's sheet on what the run knows while an older report is held under the re-run", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    world.artefact = {
      ...committedArtefact,
      sections: [
        {
          title: "Body",
          role: "standard" as const,
          blocks: [
            {
              block_id: "body",
              prose: "Body prose.",
              claims: [
                {
                  claim_id: "claim-1",
                  claim_type: "citation" as const,
                  text: "Body prose.",
                  span: [0, 11],
                  citations: [{ citation_id: "old", n: 1, source_id: "s1", source_title: "Smith 2023", quote: "Old quote." }],
                },
              ],
            },
          ],
        },
      ],
    } as unknown as typeof committedArtefact;
    world.stream = streamOf("running", [
      {
        ...SECTIONS[1],
        state: "filled",
        prose: "Costs prose.",
        citations: [
          { start: 0, end: 12, n: 2, sourceId: "s1", title: "Smith 2023", citationId: "cit-1", claimId: "claim-1", quote: "New quote." },
        ],
        checkedClaims: [{ claimId: "claim-1", start: 0, end: 12, tier: "tier_2", rationale: null }],
      },
      { index: 2, title: "Outreach", focus: "", state: "writing" },
    ]);
    render(page());
    await user.click(screen.getByRole("button", { name: "Source 2: Smith 2023" }));
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getByText("Costs prose.")).toBeInTheDocument();
    expect(within(sheet).getByText("Smith 2023").closest("button")).toBeNull();
    expect(await within(sheet).findByText("“New quote.”")).toBeInTheDocument();
  });

  it("keeps the opening paragraph and the most relevant sources in place at the swap; only their additions fade in", () => {
    const INTRO = "This report sets out what raises take-up.";
    const NOTE = "The largest trial of direct payment.";
    const view = render(page());
    world.stream = {
      ...streamOf("succeeded", [
        { index: 0, title: "Key findings", focus: "", state: "filled", role: "key_findings", prose: "- Headline." },
        { index: 1, title: "Costs and funding", focus: "", state: "filled", role: "body", prose: "Costs prose." },
        { index: 2, title: "Full report", focus: "", state: "filled", role: "intro", prose: INTRO },
      ]),
      liveSourceNotes: [{ sourceId: "s1", title: "Smith 2023", note: NOTE }],
    } as RunStreamState;
    // Watched while it ran.
    world.stream = { ...world.stream, run: { id: "run-2", status: "running", startedAt: "2026-11-05T09:58:00Z" } };
    view.rerender(page());
    world.stream = { ...world.stream, run: { id: "run-2", status: "succeeded", startedAt: "2026-11-05T09:58:00Z" } };
    view.rerender(page());
    const liveIntro = screen.getByText(INTRO);
    const liveNote = screen.getByText(NOTE).closest("li") as HTMLElement;

    world.latestRun = { capability_run_id: "run-2", status: "succeeded", started_at: "2026-11-05T09:58:00Z", ended_at: "2026-11-05T10:00:00Z" };
    world.artefact = {
      ...committedArtefact,
      title: QUESTION,
      full_report_intro: INTRO,
      most_relevant_notes: [{ source_id: "s1", note: NOTE }],
      sections: [
        { title: "Key findings", role: "key_findings" as const, blocks: [{ block_id: "kf", prose: "- Headline.", claims: [] }] },
        {
          title: "Costs and funding",
          role: "standard" as const,
          blocks: [
            {
              block_id: "costs",
              prose: "Costs prose.",
              claims: [
                {
                  claim_id: "c1",
                  claim_type: "citation" as const,
                  text: "Costs prose.",
                  span: [0, 12],
                  grounding_tier: "tier_2",
                  citations: [
                    { citation_id: "x", n: 1, source_id: "s1", source_title: "Smith 2023", quote: "q", appraisal_label: "Strong" },
                  ],
                },
              ],
            },
          ],
        },
      ],
    } as unknown as typeof committedArtefact;
    view.rerender(page());
    // The same elements, not faded in again.
    const intro = screen.getByText(INTRO);
    expect(intro).toBe(liveIntro);
    expect(intro).not.toHaveClass("anim-swap-in");
    const note = screen.getByText(NOTE).closest("li") as HTMLElement;
    expect(note).toBe(liveNote);
    expect(note.closest(".anim-swap-in")).toBeNull();
    // What the committed report adds to them does fade in: the title as a
    // link, the chips.
    expect(within(note).getByRole("link", { name: "Smith 2023" })).toBeInTheDocument();
    expect(within(note).getByText("Cited by 1 claim").closest(".anim-swap-in")).not.toBeNull();
  });

  it("opens the report at once when the run had finished before the page loaded", () => {
    world.artefact = committedArtefact;
    world.latestRun = { capability_run_id: "run-2", status: "succeeded", started_at: "2026-11-05T09:58:00Z", ended_at: "2026-11-05T10:00:00Z" };
    world.stream = streamOf("succeeded", [{ ...SECTIONS[1], state: "filled", prose: "Costs prose." }]);
    render(page());
    expect(screen.getByRole("heading", { name: "Body" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: QUESTION })).toBeInTheDocument();
    expect(screen.queryByText("Report ready")).toBeNull();
  });
});

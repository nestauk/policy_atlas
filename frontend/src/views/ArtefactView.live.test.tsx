import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import * as store from "../store";
import { createInitialRunStreamState } from "../store";
import type { LiveSection, RunStatus, RunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { ArtefactView } from "./ArtefactView";
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
  });

  it("before writing shows the question and one sentence, not the old card", () => {
    render(page());
    expect(screen.getByRole("heading", { level: 1, name: QUESTION })).toBeInTheDocument();
    expect(screen.getByText("The report's sections are set out when writing begins.")).toBeInTheDocument();
    expect(screen.queryByText(/Preparing your results/)).toBeNull();
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
      "This report is from 3 November. A new run started 2 min ago.",
    );
    // No button: the strip and the sidebar are the routes to the run.
    expect(screen.queryByRole("button", { name: /run/i })).toBeNull();
    expect(screen.getByRole("heading", { name: "The old report" })).toBeInTheDocument();
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
    expect(screen.queryByRole("heading", { name: "The old report" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Read the full report" })).toBeNull();

    // The read models catch up: the committed report takes the page.
    world.latestRun = { capability_run_id: "run-2", status: "succeeded", started_at: "2026-11-05T09:58:00Z", ended_at: "2026-11-05T10:00:00Z" };
    world.artefact = committedArtefact;
    view.rerender(page());
    expect(await screen.findByRole("heading", { name: "The old report" })).toBeInTheDocument();
    expect(screen.queryByText("Report ready")).toBeNull();
  });

  it("opens the report at once when the run had finished before the page loaded", () => {
    world.artefact = committedArtefact;
    world.latestRun = { capability_run_id: "run-2", status: "succeeded", started_at: "2026-11-05T09:58:00Z", ended_at: "2026-11-05T10:00:00Z" };
    world.stream = streamOf("succeeded", [{ ...SECTIONS[1], state: "filled", prose: "Costs prose." }]);
    render(page());
    expect(screen.getByRole("heading", { name: "The old report" })).toBeInTheDocument();
    expect(screen.queryByText("Report ready")).toBeNull();
  });
});

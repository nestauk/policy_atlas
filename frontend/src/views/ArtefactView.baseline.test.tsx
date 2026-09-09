import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { ArtefactView } from "./ArtefactView";
import { mockBaselineArtefact } from "../mock/fixtures";
import * as queries from "../api/queries";
import * as store from "../store";
import * as conversationState from "./workspace/chat/conversationState";

/**
 * Result for an options-scoping baseline (task 044 phase 4.3, deliverable 9;
 * A17, C18): the band, the roll-up's depth label, and the flat outline that
 * a baseline's section list produces — eight required titles with the
 * proposed one in place, Sources last, and no Key findings anywhere.
 */

const TASK_ID = "02da1b53-7104-4724-9944-f145e165b847";

vi.mock("../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof queries>();
  return {
    ...actual,
    useTask: vi.fn(),
    useArtefact: vi.fn(),
    useConversations: vi.fn(),
    useLandscape: vi.fn(),
    useApiClient: vi.fn(),
    useEvidence: vi.fn(),
    useFindings: vi.fn(),
    useSourceDossier: vi.fn(),
    useFunnel: vi.fn(),
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

const GATE_WALK = {
  capability_run_id: "10000000-0000-4000-8000-000000000001",
  status: "paused",
  started_at: "2026-09-09T10:00:00Z",
  ended_at: null,
  plan_version: 1,
};

function renderBaseline({
  runs = [GATE_WALK],
  planVersion = 1,
  baselineConfirmed = null as { artefact_id: string; plan_version: number } | null,
  artefact = mockBaselineArtefact as unknown,
} = {}) {
  vi.mocked(queries.useTask).mockReturnValue({
    data: {
      task_id: TASK_ID,
      name: "Cutting NEET numbers in Tower Hamlets",
      capability: "options_scoping",
      latest_run: { capability_run_id: GATE_WALK.capability_run_id, status: "paused" },
    },
  } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useArtefact).mockReturnValue({
    isPending: false,
    isError: false,
    data: artefact,
  } as unknown as ReturnType<typeof queries.useArtefact>);
  vi.mocked(queries.usePlan).mockReturnValue({
    data: { version: planVersion, scoping: { baseline_confirmed: baselineConfirmed } },
  } as unknown as ReturnType<typeof queries.usePlan>);
  vi.mocked(queries.useRuns).mockReturnValue({
    data: { data: runs },
  } as unknown as ReturnType<typeof queries.useRuns>);
  vi.mocked(queries.useConversations).mockReturnValue({
    data: { data: [] },
  } as unknown as ReturnType<typeof queries.useConversations>);
  vi.mocked(queries.useLandscape).mockReturnValue({ data: undefined } as unknown as ReturnType<
    typeof queries.useLandscape
  >);
  vi.mocked(queries.useFunnel).mockReturnValue({ data: undefined } as unknown as ReturnType<
    typeof queries.useFunnel
  >);
  vi.mocked(queries.useApiClient).mockReturnValue({} as ReturnType<typeof queries.useApiClient>);
  vi.mocked(store.useRunStream).mockReturnValue(createInitialRunStreamState());
  vi.mocked(conversationState.useActiveConversation).mockReturnValue({
    setActiveConversation: vi.fn(),
    openDraftChat: vi.fn(),
  } as unknown as ReturnType<typeof conversationState.useActiveConversation>);
  vi.mocked(conversationState.useConversationMutations).mockReturnValue({
    create: vi.fn(),
  } as unknown as ReturnType<typeof conversationState.useConversationMutations>);

  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
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

describe("ArtefactView — the options-scoping baseline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("heads the profile with the baseline's own title and the roll-up's depth label", () => {
    renderBaseline();
    expect(
      screen.getByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).toBeInTheDocument();
    expect(screen.getByText("scoping pass")).toBeInTheDocument();
    expect(screen.queryByText("Report")).not.toBeInTheDocument();
  });

  it("bands the profile with what it is, what it is for, and the walk's state in words", () => {
    renderBaseline();
    expect(
      screen.getByText(
        "Baseline · the situation these options would change · ready · awaiting your confirmation",
      ),
    ).toBeInTheDocument();
  });

  it("switches the state word once the plan is confirmed", () => {
    renderBaseline({
      baselineConfirmed: { artefact_id: mockBaselineArtefact.artefact_id, plan_version: 1 },
    });
    expect(
      screen.getByText(
        "Baseline · the situation these options would change · plan confirmed · the longlist arrives with the next stage",
      ),
    ).toBeInTheDocument();
  });

  it("marks the plan version only after the plan has changed since the walk", () => {
    renderBaseline();
    expect(screen.queryByText(/built from plan version/)).not.toBeInTheDocument();

    renderBaseline({ planVersion: 4 });
    expect(
      screen.getByText(/· built from plan version 1$/),
    ).toBeInTheDocument();
  });

  it("outlines the required sections in order with the proposed one in place and Sources last", () => {
    renderBaseline();
    const outline = screen.getByRole("navigation", { name: /contents/i });
    const entries = within(outline)
      .getAllByRole("link")
      .map((link) => link.textContent);
    expect(entries).toEqual([
      "In place",
      "Trend",
      "Who",
      "Changing",
      "Contested",
      "Tracking",
      "Cost of inaction",
      "Key assumption",
      "Sources",
      "Method",
    ]);
  });

  it("frames no Executive summary or Full report part around a baseline", () => {
    renderBaseline();
    expect(screen.queryByText("Key findings")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Executive summary" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Full report" })).not.toBeInTheDocument();
  });

  it("leaves an Evidence search report exactly as it was — no band, no depth label", () => {
    renderBaseline({
      artefact: { ...mockBaselineArtefact, template: null, depth_label: null },
    });
    expect(screen.getByText("Report")).toBeInTheDocument();
    expect(screen.queryByText(/the situation these options would change/)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Executive summary" })).toBeInTheDocument();
  });
});

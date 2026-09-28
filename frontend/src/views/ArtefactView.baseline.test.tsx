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
    useLonglist: vi.fn(),
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

// The longlist view is Phase 6.2's; the switch only has to mount it.
vi.mock("./longlist/LonglistView", () => ({
  LonglistView: ({ taskId, longlist }: { taskId: string; longlist: { run_id: string } }) => (
    <div>
      Longlist view for {taskId} from {longlist.run_id}
    </div>
  ),
}));

const GATE_WALK = {
  capability_run_id: "10000000-0000-4000-8000-000000000001",
  status: "paused",
  started_at: "2026-09-09T10:00:00Z",
  ended_at: null,
  plan_version: 1,
  // Synthesise (and the artefact it writes) has already happened by the
  // time the walk parks on the gate (task 044 review, C6).
  artefact_id: mockBaselineArtefact.artefact_id,
};

function renderBaseline({
  runs = [GATE_WALK],
  planVersion = 1,
  baselineConfirmed = null as { artefact_id: string; plan_version: number } | null,
  artefact = mockBaselineArtefact as unknown,
  hasLonglist = false,
  path = `/tasks/${TASK_ID}/result`,
} = {}) {
  vi.mocked(queries.useTask).mockReturnValue({
    data: {
      task_id: TASK_ID,
      name: "Cutting NEET numbers in Tower Hamlets",
      capability: "options_scoping",
      latest_run: { capability_run_id: GATE_WALK.capability_run_id, status: "paused" },
      has_longlist: hasLonglist,
    },
  } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useLonglist).mockReturnValue({
    isPending: false,
    data: hasLonglist ? { run_id: "run-longlist" } : null,
  } as unknown as ReturnType<typeof queries.useLonglist>);
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
        <MemoryRouter initialEntries={[path]}>
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

  it("heads the profile with the baseline's own title under the word Baseline", () => {
    renderBaseline();
    expect(
      screen.getByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Baseline")).toBeInTheDocument();
    expect(screen.queryByText("scoping pass")).not.toBeInTheDocument();
    expect(screen.queryByText("Report")).not.toBeInTheDocument();
  });

  it("carries no band under the title — the plan document owns the walk's state (owner, 2026-09-18)", () => {
    renderBaseline({
      baselineConfirmed: { artefact_id: mockBaselineArtefact.artefact_id, plan_version: 1 },
      planVersion: 4,
    });
    expect(screen.queryByText(/the situation these options would change/)).not.toBeInTheDocument();
    expect(screen.queryByText(/awaiting your confirmation/)).not.toBeInTheDocument();
    expect(screen.queryByText(/built from plan version/)).not.toBeInTheDocument();
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

describe("ArtefactView — the Result's view switch (task 045, deliverable 9)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("before a longlist exists there is no switch: the Result is the baseline", () => {
    renderBaseline();
    expect(screen.queryByRole("tablist", { name: "Result view" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).toBeInTheDocument();
  });

  it("once a longlist exists: Baseline · Longlist · Report, opening on the longlist, Report not yet available", () => {
    renderBaseline({ hasLonglist: true });
    const tabs = within(screen.getByRole("tablist", { name: "Result view" })).getAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      "Baseline",
      "Longlist",
      "Report· available after assessment",
    ]);
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(tabs[2]).toBeDisabled();
    expect(screen.getByText(`Longlist view for ${TASK_ID} from run-longlist`)).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).not.toBeInTheDocument();
  });

  it("switches to the baseline and back", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderBaseline({ hasLonglist: true });
    await user.click(screen.getByRole("tab", { name: "Baseline" }));
    expect(
      screen.getByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(`Longlist view for ${TASK_ID} from run-longlist`)).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Longlist" }));
    expect(screen.getByText(`Longlist view for ${TASK_ID} from run-longlist`)).toBeInTheDocument();
  });

  it("?view=baseline opens the baseline directly", () => {
    renderBaseline({ hasLonglist: true, path: `/tasks/${TASK_ID}/result?view=baseline` });
    expect(screen.getByRole("tab", { name: "Baseline" })).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("heading", { name: "Do nothing: current policy and trajectory" }),
    ).toBeInTheDocument();
  });
});

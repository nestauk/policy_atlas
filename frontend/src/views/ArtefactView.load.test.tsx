import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { ArtefactView } from "./ArtefactView";
import * as queries from "../api/queries";
import * as store from "../store";
import * as conversationState from "./workspace/chat/conversationState";

const PROJECT_ID = "02da1b53-7104-4724-9944-f145e165b847";

vi.mock("../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof queries>();
  return {
    ...actual,
    useProject: vi.fn(),
    useArtefact: vi.fn(),
    useConversations: vi.fn(),
    useLandscape: vi.fn(),
    useFunnel: vi.fn(),
    useApiClient: vi.fn(),
    useEvidence: vi.fn(),
    useFindings: vi.fn(),
    useSourceDossier: vi.fn(),
  };
});

vi.mock("../store", async (importOriginal) => {
  const actual = await importOriginal<typeof store>();
  return {
    ...actual,
    useRunStream: vi.fn(),
  };
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

const loadedArtefact = {
  artefact_id: "c930515b-a383-4e58-bdb6-d43d47f2bdd3",
  title: "Reducing NEETs",
  summary: "Summary text.",
  summary_status: "verified" as const,
  coverage_snapshot: { source_count: 10, included: 50 },
  most_relevant_notes: [{ source_id: "src-1", note: "A note." }],
  references: [{ n: 1, title: "Source one", year: 2020, venue: null }],
  sections: [
    {
      title: "Key findings",
      role: "key_findings" as const,
      blocks: [{ block_id: "kf", prose: "- Lead: detail.", claims: [] }],
    },
    {
      title: "Case studies",
      role: "case_studies" as const,
      blocks: [{ block_id: "cs", prose: "", claims: [] }],
      cards: [
        {
          card_id: "card-1",
          title: "Norway — IPS",
          prose: "Lead sentence. Result sentence here.",
          result_claim_id: "claim-result",
          strength: "Strong",
          design: "RCT",
          since_year: 2019,
          claims: [
            {
              claim_id: "claim-result",
              claim_type: "citation" as const,
              text: "Result sentence here.",
              span: [15, 36],
              citations: [{ n: 1, source_title: "Source one", citation_id: "c1" }],
            },
          ],
        },
      ],
    },
    {
      title: "Body",
      role: "standard" as const,
      blocks: [{ block_id: "body", prose: "Body prose.", claims: [] }],
    },
  ],
};

function renderResults(initialPending: boolean) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  let pending = initialPending;

  vi.mocked(queries.useProject).mockImplementation(
    () =>
      ({
        data: {
          project_id: PROJECT_ID,
          name: "Reducing NEETs",
          latest_run: {
            capability_run_id: "run-1",
            status: "succeeded",
            ended_at: "2026-08-01T12:00:00Z",
          },
        },
      }) as ReturnType<typeof queries.useProject>,
  );
  vi.mocked(queries.useArtefact).mockImplementation(
    () =>
      ({
        isPending: pending,
        isError: false,
        data: pending ? undefined : loadedArtefact,
      }) as ReturnType<typeof queries.useArtefact>,
  );
  vi.mocked(queries.useConversations).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<
    typeof queries.useConversations
  >);
  vi.mocked(queries.useLandscape).mockReturnValue({ data: { years: { 2020: 1 } } } as unknown as ReturnType<
    typeof queries.useLandscape
  >);
  vi.mocked(queries.useFunnel).mockReturnValue({ data: undefined } as ReturnType<
    typeof queries.useFunnel
  >);
  vi.mocked(queries.useApiClient).mockReturnValue({} as ReturnType<typeof queries.useApiClient>);
  vi.mocked(store.useRunStream).mockReturnValue(createInitialRunStreamState());
  vi.mocked(conversationState.useActiveConversation).mockReturnValue({
    setActiveConversation: vi.fn(),
  } as unknown as ReturnType<typeof conversationState.useActiveConversation>);
  vi.mocked(conversationState.useConversationMutations).mockReturnValue({
    create: vi.fn(),
  } as unknown as ReturnType<typeof conversationState.useConversationMutations>);

  const view = render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/results`]}>
          <Routes>
            <Route path="/projects/:projectId/results" element={<ArtefactView />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );

  return {
    rerenderLoaded: () => {
      pending = false;
      view.rerender(
        <QueryClientProvider client={queryClient}>
          <TooltipProvider>
            <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/results`]}>
              <Routes>
                <Route path="/projects/:projectId/results" element={<ArtefactView />} />
              </Routes>
            </MemoryRouter>
          </TooltipProvider>
        </QueryClientProvider>,
      );
    },
  };
}

describe("ArtefactView load transition", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("survives pending → loaded without tripping hook order", () => {
    const { rerenderLoaded } = renderResults(true);
    expect(screen.getByLabelText("Loading the evidence base")).toBeInTheDocument();
    rerenderLoaded();
    expect(screen.getByRole("heading", { name: "Reducing NEETs" })).toBeInTheDocument();
    expect(screen.getByText("Norway — IPS")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});

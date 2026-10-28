import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "../ui/radix/Tooltip";
import { SourceDossier } from "./ArtefactView";
import * as queries from "../api/queries";

const TASK_ID = "02da1b53-7104-4724-9944-f145e165b847";
const SOURCE_ID = "c930515b-a383-4e58-bdb6-d43d47f2bdd3";

vi.mock("../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof queries>();
  return {
    ...actual,
    useApiClient: vi.fn(),
    useEvidence: vi.fn(),
    useFindings: vi.fn(),
    useSourceDossier: vi.fn(),
    useSourceRecords: vi.fn(),
    useTask: vi.fn(),
  };
});

function mockQueries({
  evidencePending,
  dossierFetching,
}: {
  evidencePending: boolean;
  dossierFetching: boolean;
}) {
  vi.mocked(queries.useEvidence).mockReturnValue({
    isPending: evidencePending,
    data: evidencePending ? undefined : { data: [] },
  } as unknown as ReturnType<typeof queries.useEvidence>);
  // A disabled dossier query (no source id yet) is pending but not loading.
  vi.mocked(queries.useSourceDossier).mockReturnValue({
    isPending: true,
    isLoading: dossierFetching,
    isError: false,
    data: undefined,
  } as unknown as ReturnType<typeof queries.useSourceDossier>);
  vi.mocked(queries.useFindings).mockReturnValue({
    isPending: true,
    data: undefined,
  } as unknown as ReturnType<typeof queries.useFindings>);
  vi.mocked(queries.useTask).mockReturnValue({
    data: { capability: "evidence_search" },
  } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useSourceRecords).mockReturnValue({
    isPending: false,
    data: undefined,
  } as unknown as ReturnType<typeof queries.useSourceRecords>);
}

function renderDossier(sourceRef: string) {
  return render(
    <TooltipProvider>
      <SourceDossier taskId={TASK_ID} sourceRef={sourceRef} onClose={() => {}} />
    </TooltipProvider>,
  );
}

describe("SourceDossier loading states", () => {
  it("shows a single loading line while the title lookup waits on evidence", () => {
    mockQueries({ evidencePending: true, dossierFetching: false });
    renderDossier("Some source title");
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });

  it("shows the not-found line without a stuck loading line on a title miss", () => {
    mockQueries({ evidencePending: false, dossierFetching: false });
    renderDossier("A title the evidence list does not carry");
    expect(screen.getByText("This source isn't in the evidence list yet.")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("opens by id without waiting on the evidence lookup", () => {
    mockQueries({ evidencePending: true, dossierFetching: true });
    renderDossier(SOURCE_ID);
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(
      screen.queryByText("This source isn't in the evidence list yet."),
    ).not.toBeInTheDocument();
  });
});

// Task 046, amendment 3 (R67): the exported dossier takes the option id the
// card's document link carries, and on a scoping task its slot reads
// "In this option".
describe("SourceDossier on an options-scoping task", () => {
  const OPTION_ID = "a0000000-0000-4000-8000-00000000000a";

  it("reads the option's records under \"In this option\"", () => {
    mockQueries({ evidencePending: false, dossierFetching: false });
    vi.mocked(queries.useSourceDossier).mockReturnValue({
      isPending: false,
      isLoading: false,
      isError: false,
      data: { source_id: SOURCE_ID, title: "A document", origin: "OpenAlex", tags: [] },
    } as unknown as ReturnType<typeof queries.useSourceDossier>);
    vi.mocked(queries.useTask).mockReturnValue({
      data: { capability: "options_scoping" },
    } as unknown as ReturnType<typeof queries.useTask>);
    vi.mocked(queries.useSourceRecords).mockReturnValue({
      isPending: false,
      data: {
        task_source_snapshot_id: SOURCE_ID,
        records: [
          {
            option_id: OPTION_ID,
            option_name: "Youth guarantee",
            record_id: "r-1",
            intervention: "youth guarantee",
            setting: null,
            unit: null,
            outcome: null,
            study_geography: "England",
            role: "evaluated",
          },
        ],
      },
    } as unknown as ReturnType<typeof queries.useSourceRecords>);
    render(
      <TooltipProvider>
        <SourceDossier taskId={TASK_ID} sourceRef={SOURCE_ID} optionId={OPTION_ID} onClose={() => {}} />
      </TooltipProvider>,
    );
    expect(vi.mocked(queries.useSourceRecords)).toHaveBeenLastCalledWith(
      TASK_ID, SOURCE_ID, OPTION_ID, { enabled: true },
    );
    expect(screen.getByText("In this option")).toBeInTheDocument();
    expect(screen.getByText("youth guarantee")).toBeInTheDocument();
    expect(screen.getByText("England")).toBeInTheDocument();
    expect(screen.queryByText("Setting")).not.toBeInTheDocument();
    expect(screen.queryByText("Findings from this source")).not.toBeInTheDocument();
  });
});

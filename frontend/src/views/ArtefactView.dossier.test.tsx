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

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockEvidence, mockLandscape } from "../mock/fixtures";
import { ToastProvider } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { SourcesView } from "./SourcesView";
import * as mutations from "../api/mutations";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useProject: vi.fn(),
  useLandscape: vi.fn(),
  useEvidence: vi.fn(),
  useFindings: vi.fn(),
  useSourceDossier: vi.fn(),
}));

vi.mock("../api/mutations", () => ({
  useSetSourceNotRelevant: vi.fn(),
}));

const setNotRelevant = vi.fn();

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

/** The school-food theme in `mockLandscape` — the fixture theme that
 *  carries a `theme_id` and so is eligible for the sources theme filter. */
const SCHOOL_FOOD_THEME_ID = mockLandscape.themes?.find((theme) => theme.name === "School food environments")
  ?.theme_id as string;

function evidencePage(rows: typeof mockEvidence = mockEvidence) {
  return { data: rows, pagination: { page: 1, page_size: 50, total_items: rows.length } };
}

/** Surfaces the current URL search string so tests can assert on it
 *  without reaching into router internals. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.search}</div>;
}

function renderSources() {
  return render(
    <ToastProvider>
    <TooltipProvider>
      <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/sources`]}>
        <Routes>
          <Route
            path="/projects/:projectId/sources"
            element={(
              <>
                <SourcesView />
                <LocationProbe />
              </>
            )}
          />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>
    </ToastProvider>,
  );
}

function lastEvidenceQuery() {
  const calls = vi.mocked(queries.useEvidence).mock.calls;
  return calls.at(-1)?.[1];
}

beforeEach(() => {
  setNotRelevant.mockClear();
  vi.mocked(mutations.useSetSourceNotRelevant).mockReturnValue(
    { mutate: setNotRelevant, isPending: false } as unknown as ReturnType<
      typeof mutations.useSetSourceNotRelevant
    >,
  );
  vi.mocked(queries.useProject).mockReturnValue(
    { data: { name: "Tower Hamlets project" } } as unknown as ReturnType<typeof queries.useProject>,
  );
  vi.mocked(queries.useLandscape).mockReturnValue(
    { data: mockLandscape } as unknown as ReturnType<typeof queries.useLandscape>,
  );
  vi.mocked(queries.useFindings).mockReturnValue(
    { data: undefined, isPending: false } as unknown as ReturnType<typeof queries.useFindings>,
  );
  vi.mocked(queries.useSourceDossier).mockReturnValue(
    { data: undefined, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useSourceDossier>,
  );
  vi.mocked(queries.useEvidence).mockReturnValue({
    data: evidencePage(),
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof queries.useEvidence>);
});

describe("SourcesView — sortable table (028 strand 7)", () => {
  it("keeps Origin a plain, non-sortable header (its filter select aside)", () => {
    renderSources();
    const header = screen.getByRole("columnheader", { name: /Origin/ });
    expect(header).not.toHaveAttribute("aria-sort");
    expect(within(header).queryByRole("button")).toBeNull();
  });

  it("gives the renamed Evidence strength header a sort button with an accessible name", () => {
    renderSources();
    expect(screen.getByRole("button", { name: "Sort by evidence strength" })).toBeInTheDocument();
    // The old inline "Strength" header text is gone — renamed everywhere.
    expect(screen.queryByRole("columnheader", { name: "Strength" })).toBeNull();
  });

  it("adds a sortable Evidence type header alongside the other four sort dimensions", () => {
    renderSources();
    expect(screen.getByRole("button", { name: "Sort by source" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sort by year" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sort by evidence type" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sort by status" })).toBeInTheDocument();
  });

  it("cycles a header none → default direction → opposite → none, updating the URL and the evidence query", async () => {
    const user = userEvent.setup();
    renderSources();
    const yearButton = screen.getByRole("button", { name: "Sort by year" });
    const yearHeader = screen.getByRole("columnheader", { name: /Year/ });
    expect(yearHeader).toHaveAttribute("aria-sort", "none");
    // No explicit sort → the relevance-spectrum default.
    expect(lastEvidenceQuery()).toMatchObject({ sort: "relevance", order: "desc" });

    // Year's first click lands on desc — the server's own default for `sort=year`.
    await user.click(yearButton);
    expect(screen.getByTestId("location")).toHaveTextContent("sort=year&order=desc");
    expect(screen.getByRole("columnheader", { name: /Year/ })).toHaveAttribute("aria-sort", "descending");
    expect(lastEvidenceQuery()).toMatchObject({ sort: "year", order: "desc" });

    await user.click(screen.getByRole("button", { name: "Sort by year" }));
    expect(screen.getByTestId("location")).toHaveTextContent("sort=year&order=asc");
    expect(screen.getByRole("columnheader", { name: /Year/ })).toHaveAttribute("aria-sort", "ascending");
    expect(lastEvidenceQuery()).toMatchObject({ sort: "year", order: "asc" });

    await user.click(screen.getByRole("button", { name: "Sort by year" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("sort=");
    expect(screen.getByRole("columnheader", { name: /Year/ })).toHaveAttribute("aria-sort", "none");
    // Cycling off an explicit sort falls back to the relevance default.
    expect(lastEvidenceQuery()).toMatchObject({ sort: "relevance", order: "desc" });
  });

  it("starts a non-year column ascending on its first click", async () => {
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: "Sort by status" }));
    expect(screen.getByTestId("location")).toHaveTextContent("sort=status&order=asc");
    expect(lastEvidenceQuery()).toMatchObject({ sort: "status", order: "asc" });
  });

  it("offers a theme select scoped to themes carrying a theme_id, defaulting to All themes", () => {
    renderSources();
    const select = screen.getByRole("combobox", { name: "Key theme" });
    expect(within(select).getByRole("option", { name: "All themes" })).toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "School food environments" })).toBeInTheDocument();
    // "Family support" carries no theme_id in the fixture — it must not
    // offer a selection that can never round-trip against the API.
    expect(within(select).queryByRole("option", { name: "Family support" })).toBeNull();
  });

  it("sets the theme param and the evidence query when a theme is chosen", async () => {
    const user = userEvent.setup();
    renderSources();
    const select = screen.getByRole("combobox", { name: "Key theme" });
    await user.selectOptions(select, SCHOOL_FOOD_THEME_ID);
    expect(screen.getByTestId("location")).toHaveTextContent(`theme=${SCHOOL_FOOD_THEME_ID}`);
    expect(lastEvidenceQuery()).toMatchObject({ theme: SCHOOL_FOOD_THEME_ID });
  });

  it("shows a sources count footer from the pagination total", () => {
    renderSources();
    expect(screen.getByText(`${mockEvidence.length} sources`)).toBeInTheDocument();
  });
});

describe("SourcesView — fixture-driven render (mock mode)", () => {
  it("renders the real mock/fixtures.ts evidence rows without breaking on the new columns", () => {
    renderSources();
    // Row for a source carrying both an evidence type and an appraisal
    // tier renders them as two distinct chips, not one merged cell.
    expect(screen.getByText("Cohort study")).toBeInTheDocument();
    expect(screen.getByText("Moderate confidence")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(mockEvidence.length + 1); // + header row
  });
});

describe("SourcesView — refinement batch (owner live-demo list, 2026-08-05)", () => {
  it("defaults to All on the relevance spectrum, Relevant header marked descending", () => {
    renderSources();
    expect(lastEvidenceQuery()).toMatchObject({
      status: undefined,
      sort: "relevance",
      order: "desc",
    });
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("columnheader", { name: /Relevant/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
  });

  it("Included narrows via the status param", async () => {
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: "Included" }));
    expect(screen.getByTestId("location")).toHaveTextContent("status=Included");
    expect(lastEvidenceQuery()).toMatchObject({ status: ["Included"] });
  });

  it("binds the Year header's range filter to the query", async () => {
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: "Filter by year range" }));
    const fromInput = screen.getByLabelText("From");
    await user.type(fromInput, "2021");
    await user.tab();
    expect(screen.getByTestId("location")).toHaveTextContent("year_from=2021");
    expect(lastEvidenceQuery()).toMatchObject({ year_from: 2021 });
  });

  it("binds the header-mounted origin, evidence type and strength filters to the query", async () => {
    const user = userEvent.setup();
    renderSources();
    const originSelect = screen.getByRole("combobox", { name: "Filter by origin" });
    // Uploaded is not offered — document upload isn't a live feature.
    expect(within(originSelect).queryByRole("option", { name: "Uploaded" })).toBeNull();
    await user.selectOptions(originSelect, "Overton");
    expect(screen.getByTestId("location")).toHaveTextContent("origin=Overton");
    expect(lastEvidenceQuery()).toMatchObject({ origin: "Overton" });

    // Evidence-type options come from the landscape distribution.
    const typeSelect = screen.getByRole("combobox", { name: "Filter by evidence type" });
    expect(within(typeSelect).getByRole("option", { name: "Local evaluation" })).toBeInTheDocument();
    await user.selectOptions(typeSelect, "Systematic review");
    expect(lastEvidenceQuery()).toMatchObject({ evidence_type: "Systematic review" });

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Filter by evidence strength" }),
      "Moderate",
    );
    expect(lastEvidenceQuery()).toMatchObject({ strength: "Moderate" });
  });

  it("hovers Abstract only with a human-readable reason", () => {
    renderSources();
    const hints = screen.getAllByRole("button", { name: "Abstract only: why" });
    expect(hints.length).toBeGreaterThan(0);
  });

  it("renders the Relevant column as a verdict with confidence, reasoning behind a hover", () => {
    renderSources();
    // The screened-in breakfast-clubs row: ✓ + its screening confidence.
    const verdicts = screen.getAllByRole("button", { name: "Relevant: screening details" });
    expect(verdicts.length).toBeGreaterThan(0);
    expect(screen.getByText("91%")).toBeInTheDocument();
    // The retracted row keeps its honest verdict.
    expect(screen.getByRole("button", { name: "Excluded — retracted: screening details" })).toBeInTheDocument();
  });

  it("shows read depth in the Status column and drops the cited-redundant ladder label", () => {
    renderSources();
    expect(screen.getAllByText("Read in full").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Abstract only").length).toBeGreaterThan(0);
    expect(screen.queryByText("Cited in the evidence base")).toBeNull();
  });
});

describe("SourcesView — not-relevant feedback (032)", () => {
  it("flags an unflagged row and reflects the server's flag state", async () => {
    const user = userEvent.setup();
    renderSources();
    const flags = screen.getAllByRole("button", { name: "Flag as not relevant" });
    expect(flags).toHaveLength(mockEvidence.length);
    await user.click(flags[0]);
    expect(setNotRelevant).toHaveBeenCalledTimes(1);
    expect(setNotRelevant.mock.calls[0][0]).toEqual({
      sourceId: mockEvidence[0].source_id,
      notRelevant: true,
    });
  });

  it("offers the undo on an already-flagged row and sends false", async () => {
    const user = userEvent.setup();
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: evidencePage([{ ...mockEvidence[0], not_relevant: true }]),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useEvidence>);
    renderSources();
    const undo = screen.getByRole("button", { name: "Flagged as not relevant — undo" });
    expect(undo).toHaveAttribute("aria-pressed", "true");
    await user.click(undo);
    expect(setNotRelevant.mock.calls[0][0]).toEqual({
      sourceId: mockEvidence[0].source_id,
      notRelevant: false,
    });
  });

  it("leaves the machine-derived row untouched when a source is flagged", () => {
    // mockEvidence[7] is the cited row. Feedback only means the flag changes
    // the flag and nothing else — same status, strength, citation state.
    const rowText = (notRelevant: boolean) => {
      vi.mocked(queries.useEvidence).mockReturnValue({
        data: evidencePage([{ ...mockEvidence[7], not_relevant: notRelevant }]),
        isPending: false,
        isError: false,
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof queries.useEvidence>);
      const view = renderSources();
      const row = screen.getAllByRole("row")[1];
      const text = row.textContent;
      view.unmount();
      return text;
    };
    expect(rowText(true)).toEqual(rowText(false));
  });
});

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockEvidence, mockLandscape } from "../mock/fixtures";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { SourcesView } from "./SourcesView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useProject: vi.fn(),
  useLandscape: vi.fn(),
  useEvidence: vi.fn(),
  useFindings: vi.fn(),
  useSourceDossier: vi.fn(),
}));

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
    </TooltipProvider>,
  );
}

function lastEvidenceQuery() {
  const calls = vi.mocked(queries.useEvidence).mock.calls;
  return calls.at(-1)?.[1];
}

beforeEach(() => {
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
  it("keeps Origin a plain, non-sortable header", () => {
    renderSources();
    const header = screen.getByRole("columnheader", { name: "Origin" });
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
    expect(lastEvidenceQuery()).toMatchObject({ sort: undefined, order: undefined });

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
    expect(lastEvidenceQuery()).toMatchObject({ sort: undefined, order: undefined });
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

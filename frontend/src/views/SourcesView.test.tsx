import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mockCoverage, mockEvidence, mockFunnel, mockLandscape, mockSourceDossiers } from "../mock/fixtures";
import { createInitialRunStreamState, type RunStreamState, type StageEntry } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { SourceDossierBody, SourcesView } from "./SourcesView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useApiClient: vi.fn(() => ({ GET: vi.fn() })),
  useTask: vi.fn(),
  useLandscape: vi.fn(),
  useCoverage: vi.fn(),
  useEvidence: vi.fn(),
  useFindings: vi.fn(),
  useSourceDossier: vi.fn(),
  useSourceRecords: vi.fn(),
  useFunnel: vi.fn(),
}));

// The shell's run stream: idle by default, set per test for the default
// filter during a run (task 058, N16).
let streamState: RunStreamState = createInitialRunStreamState();
vi.mock("../store", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../store")>()),
  useRunStream: () => streamState,
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";

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

function renderSources(rows?: typeof mockEvidence) {
  if (rows !== undefined) {
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: evidencePage(rows),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useEvidence>);
  }
  return render(sourcesTree());
}

function sourcesTree() {
  return (
    <TooltipProvider>
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources`]}>
        <Routes>
          <Route
            path="/tasks/:taskId/sources"
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
  );
}

function lastEvidenceQuery() {
  const calls = vi.mocked(queries.useEvidence).mock.calls;
  return calls.at(-1)?.[1];
}

beforeEach(() => {
  streamState = createInitialRunStreamState();
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "Tower Hamlets task" } } as unknown as ReturnType<typeof queries.useTask>,
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
  vi.mocked(queries.useSourceRecords).mockReturnValue(
    { data: undefined, isPending: false } as unknown as ReturnType<typeof queries.useSourceRecords>,
  );
  vi.mocked(queries.useFunnel).mockReturnValue(
    { data: mockFunnel } as unknown as ReturnType<typeof queries.useFunnel>,
  );
  vi.mocked(queries.useCoverage).mockReturnValue(
    { data: mockCoverage } as unknown as ReturnType<typeof queries.useCoverage>,
  );
  vi.mocked(queries.useEvidence).mockReturnValue({
    data: evidencePage(),
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof queries.useEvidence>);
});

describe("SourcesView — the default filter during a run (task 058, N16)", () => {
  const stage = (name: StageEntry["stage"], status: StageEntry["status"]): StageEntry => ({
    stage: name,
    label: "Searching and screening",
    status,
    startedAt: "2026-11-05T10:00:00Z",
  });
  const running = (stages: StageEntry[]): RunStreamState => ({
    ...createInitialRunStreamState(),
    run: { id: "run-1", status: "running", startedAt: "2026-11-05T10:00:00Z" },
    stages,
  });

  it("shows All while screening has not finished", () => {
    streamState = running([stage("acquire", "completed"), stage("screen", "started")]);
    renderSources();
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(lastEvidenceQuery()).toMatchObject({ status: undefined });
  });

  it("returns to Included once screening has completed", () => {
    streamState = running([stage("acquire", "completed"), stage("screen", "completed")]);
    renderSources();
    expect(screen.getByRole("button", { name: "Included" })).toHaveAttribute("aria-pressed", "true");
    expect(lastEvidenceQuery()).toMatchObject({ status: ["Included"] });
  });

  it("keeps Included for a task with no live stream and no run in flight", () => {
    renderSources();
    expect(screen.getByRole("button", { name: "Included" })).toHaveAttribute("aria-pressed", "true");
  });
});

// Owner, round 8: while a stage runs, the cells it will fill pulse where
// their value is absent, and the table refetches every 5 s until it ends.
describe("SourcesView — pulsing cells while a stage runs (owner, round 8)", () => {
  afterEach(() => vi.useRealTimers());
  const running = (stage: StageEntry["stage"], status: StageEntry["status"] = "started", run = "running" as const) => ({
    ...createInitialRunStreamState(),
    run: { id: "run-1", status: run, startedAt: "2026-11-05T10:00:00Z" },
    stages: [{ stage, label: "Screening", status, startedAt: "2026-11-05T10:00:00Z", counts: [] }],
  }) as RunStreamState;
  const row = (overrides: Partial<(typeof mockEvidence)[number]>) => ({ ...mockEvidence[0], ...overrides });
  const rows = (items: typeof mockEvidence, refetch = vi.fn()) =>
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: evidencePage(items),
      isPending: false,
      isError: false,
      refetch,
    } as unknown as ReturnType<typeof queries.useEvidence>);
  /** The pulse in a row's cell under the column headed `header`. */
  const pulseIn = (title: string, header: string) => {
    const table = screen.getAllByRole("table")[0];
    const headers = within(table).getAllByRole("columnheader");
    const column = headers.findIndex((th) => th.textContent?.startsWith(header));
    const tr = within(table).getAllByRole("row").find((r) => r.textContent?.includes(title)) as HTMLElement;
    return tr.querySelectorAll("td")[column].querySelector("[data-testid='cell-pulse']");
  };

  it("pulses Relevant on a source not yet screened while screening runs, and not on a screened one", () => {
    streamState = running("screen");
    rows([
      row({ source_id: "a", title: "Waiting source", screen_status: null }),
      row({ source_id: "b", title: "Screened source", screen_status: "relevant", screen_confidence: 0.9 }),
    ]);
    renderSources();
    expect(pulseIn("Waiting source", "Relevant")).not.toBeNull();
    expect(pulseIn("Screened source", "Relevant")).toBeNull();
    expect(pulseIn("Waiting source", "Relevant")).toHaveAttribute("aria-hidden", "true");
    expect(pulseIn("Waiting source", "Relevant")?.querySelector(".placeholder-bar")).not.toBeNull();
  });

  it("pulses the evidence type and strength of relevant sources lacking them while classifying runs", () => {
    streamState = running("classify");
    rows([
      row({ source_id: "a", title: "Unclassified source", screen_status: "relevant", evidence_type: null, appraisal_tier: null }),
      row({ source_id: "b", title: "Off-topic source", screen_status: "not_relevant", evidence_type: null, appraisal_tier: null }),
    ]);
    renderSources();
    expect(pulseIn("Unclassified source", "Evidence type")).not.toBeNull();
    expect(pulseIn("Unclassified source", "Evidence strength")).not.toBeNull();
    expect(pulseIn("Off-topic source", "Evidence type")).toBeNull();
  });

  it("pulses Status on a relevant source not yet read while the full texts are read, in place of its label", () => {
    streamState = running("ingest");
    rows([
      row({ source_id: "a", title: "Unread source", screen_status: "relevant", read_in_full: false, status: "relevant" }),
      row({ source_id: "b", title: "Read source", screen_status: "relevant", read_in_full: true, status: "read_in_full" }),
    ]);
    renderSources();
    expect(pulseIn("Unread source", "Status")).not.toBeNull();
    expect(screen.queryByText("Abstract only")).toBeNull();
    expect(pulseIn("Read source", "Status")).toBeNull();
    expect(screen.getByText("Full text")).toBeInTheDocument();
  });

  it("pulses nothing once the stage has ended, or while the run waits on a check-in", () => {
    streamState = running("screen", "completed");
    rows([row({ source_id: "a", title: "Waiting source", screen_status: null })]);
    const ended = renderSources();
    expect(screen.queryByTestId("cell-pulse")).toBeNull();
    ended.unmount();
    streamState = running("screen", "started", "paused" as never);
    renderSources();
    expect(screen.queryByTestId("cell-pulse")).toBeNull();
  });

  it("refetches every 5 s while a stage that feeds the table runs, and not otherwise", () => {
    vi.useFakeTimers();
    const refetch = vi.fn();
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: mockLandscape, refetch: vi.fn() } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    streamState = running("screen");
    rows([row({ source_id: "a", title: "Waiting source", screen_status: null })], refetch);
    const view = renderSources();
    act(() => vi.advanceTimersByTime(10_000));
    expect(refetch).toHaveBeenCalledTimes(2);
    view.unmount();
    refetch.mockClear();
    streamState = running("synthesise");
    renderSources();
    act(() => vi.advanceTimersByTime(10_000));
    expect(refetch).not.toHaveBeenCalled();
  });
});

describe("SourcesView — sortable table (028 strand 7)", () => {
  it("heads six sortable columns; Origin and Cited fold into the source's second line (round 10)", () => {
    renderSources();
    const table = screen.getAllByRole("table")[0];
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((th) => th.textContent)).toEqual([
      "Source", "Year", "Evidence type", "Evidence strength", "Relevant", "Status",
    ]);
    for (const th of headers) expect(th).toHaveAttribute("aria-sort");
    // The cited source's line: venue, the year (phones only), origin, the chip.
    const cited = mockEvidence.find((item) => item.cited) as (typeof mockEvidence)[number];
    const row = within(table).getAllByRole("row").find((r) => r.textContent?.includes(cited.title)) as HTMLElement;
    const line = row.querySelector(".sources-meta") as HTMLElement;
    expect(line.textContent).toBe(`${cited.venue} · ${cited.year} · ${cited.origin}Cited`);
    expect(within(line).getByText(String(cited.year))).toHaveClass("lg:hidden");
    expect(within(line).getByText("Cited")).toHaveClass("sources-cited");
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

  // The theme filter is an app-styled Popover listbox (040 amendment), not a
  // native <select> — options exist only while the menu is open. The trigger's
  // accessible name is label + current selection ("Key theme All themes").
  it("offers a theme select scoped to themes carrying a theme_id, defaulting to All themes", async () => {
    const user = userEvent.setup();
    renderSources();
    const trigger = screen.getByRole("button", { name: /^Key theme/ });
    expect(trigger).toHaveTextContent("All themes");
    await user.click(trigger);
    const listbox = screen.getByRole("listbox", { name: "Key theme" });
    expect(within(listbox).getByRole("option", { name: "All themes" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "School food environments" })).toBeInTheDocument();
    // "Family support" carries no theme_id in the fixture — it must not
    // offer a selection that can never round-trip against the API.
    expect(within(listbox).queryByRole("option", { name: "Family support" })).toBeNull();
  });

  it("sets the theme param and the evidence query when a theme is chosen", async () => {
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: /^Key theme/ }));
    await user.click(screen.getByRole("option", { name: "School food environments" }));
    expect(screen.getByTestId("location")).toHaveTextContent(`theme=${SCHOOL_FOOD_THEME_ID}`);
    expect(lastEvidenceQuery()).toMatchObject({ theme: SCHOOL_FOOD_THEME_ID });
  });

  // 040 review finding: the native <select> gave arrow keys for free — the
  // popover listbox must keep the keyboard path (focus opens on the current
  // option, arrows move, Enter picks).
  it("supports keyboard selection: focus lands in the listbox, arrows move, Enter picks", async () => {
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: /^Key theme/ }));
    expect(screen.getByRole("option", { name: "All themes" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("option", { name: "School food environments" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByTestId("location")).toHaveTextContent(`theme=${SCHOOL_FOOD_THEME_ID}`);
    expect(lastEvidenceQuery()).toMatchObject({ theme: SCHOOL_FOOD_THEME_ID });
  });

  it("shows a sources count between the filters and the table, the download beside it", () => {
    renderSources();
    const count = screen.getAllByRole("status").find((node) => node.textContent === `${mockEvidence.length} sources`);
    expect(count).toBeDefined();
    // Download CSV is an outline control on the count's row, not a primary.
    const download = screen.getByRole("button", { name: "Download CSV" });
    expect(download).toHaveClass("border-line-2");
    expect(download).not.toHaveClass("cutout");
    expect(count?.parentElement).toContainElement(download);
  });

  it("folds the committed search queries to one line at the top, the chevron opening one table", async () => {
    const user = userEvent.setup();
    renderSources();
    const block = screen.getByTestId("search-queries");
    // At the top of All sources, before the filters (owner, round 9).
    expect(block.compareDocumentPosition(screen.getByRole("group", { name: "Filter sources" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const toggle = within(block).getByRole("button", { name: "5 search queries · 128 results · Show" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(block).queryByRole("table")).toBeNull();
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveTextContent(/Hide$/);
    const table = within(block).getByRole("table");
    // One table: the backend once per group, as a row-group label.
    expect(within(table).getByRole("rowheader", { name: "OpenAlex" })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "Overton" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Query" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Results" })).toBeInTheDocument();
    expect(table).toHaveClass("text-meta");
    const query = within(table).getByText("childhood obesity school intervention UK");
    // Queries wrap on words.
    expect(query).toHaveClass("break-words");
    expect(query).not.toHaveClass("break-all");
    expect(within(table).getByText("34")).toHaveClass("tabular-nums");
  });
});

// Owner, round 9: the queries show as they go out, the table waits for the
// first results, and what lands while a stage runs fades in.
describe("SourcesView — the search as it runs (owner, round 9)", () => {
  const searching = (queriesOut: RunStreamState["liveSearchQueries"], status: StageEntry["status"] = "started") =>
    ({
      ...createInitialRunStreamState(),
      run: { id: "run-1", status: "running", startedAt: "2026-11-05T10:00:00Z" },
      stages: [{ stage: "acquire", label: "Searching", status, startedAt: "2026-11-05T10:00:00Z", counts: [] }],
      liveSearchQueries: queriesOut,
    }) as RunStreamState;
  const empty = () =>
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: evidencePage([]),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useEvidence>);

  it("lists the queries as they go out, a pulse until each count returns, and hides the table until results land", () => {
    vi.mocked(queries.useCoverage).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.useCoverage>);
    empty();
    streamState = searching([
      { backend: "openalex", query: "primary school food environment obesity", kind: "topic", results: 34 },
      { backend: "openalex", query: "school meals uptake", kind: "semantic", results: null },
      { backend: "overton", query: "Following citations from 50 sources", kind: "citations", results: 1184 },
    ]);
    renderSources();
    const block = screen.getByTestId("search-queries");
    expect(within(block).getByRole("heading", { name: "Search queries" })).toBeInTheDocument();
    const table = within(block).getByRole("table");
    expect(within(table).getByRole("rowheader", { name: "OpenAlex" })).toBeInTheDocument();
    expect(within(table).getAllByTestId("query-results-pulse")).toHaveLength(1);
    expect(within(table).getByText("1,184")).toBeInTheDocument();
    // A citation pass reads in grey; a topic query in navy.
    expect(within(table).getByText("Following citations from 50 sources")).toHaveClass("text-grey");
    expect(within(table).getByText("primary school food environment obesity")).toHaveClass("text-navy");
    // No empty card and no count line while the search runs with nothing in.
    expect(screen.queryByText(/No sources yet/)).toBeNull();
    expect(screen.queryByText(/^\d+ sources$/)).toBeNull();
  });

  it("folds the live queries once the search has ended, before the committed coverage lands", () => {
    vi.mocked(queries.useCoverage).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.useCoverage>);
    streamState = searching(
      [
        { backend: "openalex", query: "a", kind: "topic", results: 34 },
        { backend: "openalex", query: "b", kind: "topic", results: 1 },
      ],
      "completed",
    );
    renderSources();
    expect(screen.getByRole("button", { name: "2 search queries · 35 results · Show" })).toBeInTheDocument();
  });

  it("fades in a source that lands while a stage runs, and holds the page it opened on still", () => {
    vi.mocked(queries.useCoverage).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.useCoverage>);
    streamState = searching([{ backend: "openalex", query: "a", kind: "topic", results: 2 }]);
    const first = { ...mockEvidence[0], source_id: "a", title: "First source" };
    const second = { ...mockEvidence[0], source_id: "b", title: "Second source" };
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: evidencePage([first]),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useEvidence>);
    const view = renderSources();
    const rowOf = (title: string) => screen.getAllByRole("row").find((r) => r.textContent?.includes(title)) as HTMLElement;
    expect(rowOf("First source")).not.toHaveClass("anim-swap-in");
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: evidencePage([first, second]),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useEvidence>);
    view.rerender(sourcesTree());
    expect(rowOf("Second source")).toHaveClass("anim-swap-in");
    expect(rowOf("First source")).not.toHaveClass("anim-swap-in");
  });
});

describe("SourcesView — fixture-driven render (mock mode)", () => {
  it("renders the real mock/fixtures.ts evidence rows without breaking on the new columns", () => {
    renderSources();
    // Row for a source carrying both an evidence type and an appraisal
    // tier renders them as two distinct chips, not one merged cell.
    expect(screen.getByText("Cohort study")).toBeInTheDocument();
    expect(screen.getByText("Moderate confidence")).toBeInTheDocument();
    const sourcesTable = screen.getAllByRole("table")[0];
    expect(sourcesTable).toBeTruthy();
    expect(within(sourcesTable).getAllByRole("row")).toHaveLength(mockEvidence.length + 1);
  });
});

describe("SourcesView — refinement batch (owner live-demo list, 2026-08-05)", { timeout: 20_000 }, () => {
  it("defaults to Included on the relevance spectrum, Relevant header marked descending", () => {
    renderSources();
    expect(lastEvidenceQuery()).toMatchObject({
      status: ["Included"],
      sort: "relevance",
      order: "desc",
    });
    expect(screen.getByRole("button", { name: "Included" })).toHaveAttribute("aria-pressed", "true");
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

  it("binds the filter row's Year control to the query, its name carrying the range", async () => {
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: "Filter by year: any" }));
    const fromInput = screen.getByLabelText("From");
    // Four-digit text fields, not number spinners.
    expect(fromInput).toHaveAttribute("type", "text");
    expect(fromInput).toHaveAttribute("inputmode", "numeric");
    expect(fromInput).toHaveAttribute("maxlength", "4");
    await user.type(fromInput, "2021");
    await user.tab();
    expect(screen.getByTestId("location")).toHaveTextContent("year_from=2021");
    expect(lastEvidenceQuery()).toMatchObject({ year_from: 2021 });
    expect(screen.getByRole("button", { name: "Filter by year: 2021 to any" })).toBeInTheDocument();
  });

  it("binds the filter row's origin, evidence type and strength selects to the query", async () => {
    const user = userEvent.setup();
    renderSources();
    // No native selects are left anywhere on the page (round 10).
    expect(screen.queryAllByRole("combobox")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: /^Origin/ }));
    const origins = await screen.findByRole("listbox", { name: "Origin" });
    // Uploaded is not offered — document upload isn't a live feature. The
    // provider names stay as they are (owner, 2026-11-06).
    expect(within(origins).getAllByRole("option").map((option) => option.textContent)).toEqual(["All", "OpenAlex", "Overton"]);
    await user.click(within(origins).getByRole("option", { name: "Overton" }));
    expect(screen.getByTestId("location")).toHaveTextContent("origin=Overton");
    expect(lastEvidenceQuery()).toMatchObject({ origin: "Overton" });

    // Evidence-type options come from the landscape distribution, in
    // sentence case; the query keeps the classifier's value.
    await user.click(screen.getByRole("button", { name: /^Evidence type/ }));
    const types = await screen.findByRole("listbox", { name: "Evidence type" });
    expect(within(types).getByRole("option", { name: "Observational research studies" })).toBeInTheDocument();
    await user.click(within(types).getByRole("option", { name: "Systematic review and meta-analysis" }));
    expect(lastEvidenceQuery()).toMatchObject({ evidence_type: "Systematic Review and Meta-Analysis" });

    await user.click(screen.getByRole("button", { name: /^Strength/ }));
    const strengths = await screen.findByRole("listbox", { name: "Strength" });
    // Task 056: Unrated is its own band, offered last.
    expect(within(strengths).getAllByRole("option").at(-1)).toHaveTextContent("Unrated");
    await user.click(within(strengths).getByRole("option", { name: "Moderate" }));
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
    // The name carries the figure (round 10).
    expect(screen.getByRole("button", { name: "Relevant, 91% confidence: screening details" })).toBeInTheDocument();
    expect(screen.getByText("91%")).toHaveClass("tabular-nums");
    // The retracted row keeps its honest verdict.
    expect(screen.getByRole("button", { name: "Excluded — retracted: screening details" })).toBeInTheDocument();
  });

  it("shows read depth in the Status column and drops the cited-redundant ladder label", () => {
    renderSources();
    expect(screen.getAllByText("Full text").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Abstract only").length).toBeGreaterThan(0);
    expect(screen.queryByText("Cited in the evidence base")).toBeNull();
  });
});

describe("SourceDossierBody authorships (042)", () => {
  const authored = mockSourceDossiers[mockEvidence[2].source_id];
  const corporate = mockSourceDossiers[mockEvidence[7].source_id];

  it("renders authors with superscript markers and numbered, deduped institutions", () => {
    const { container } = render(
      <SourceDossierBody source={authored} findings={[]} findingsPending={false} />,
    );
    expect(screen.getAllByText(/Alex Sampleton/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Casey Mockford/).length).toBeGreaterThan(0);
    // The sheet header owns the title (042 item 4): the body never repeats it.
    expect(screen.queryByText(authored.title)).toBeNull();
    expect(screen.getAllByText(/Institute of Fictional Studies/).length).toBeGreaterThan(0);
    // Marker sequence proves the shared institution deduped to number 1 and
    // listed once: two author markers, then the two numbered institution rows.
    const markers = [...container.querySelectorAll("sup")].map((sup) => sup.textContent);
    expect(markers).toEqual(["1", "1,2", "1", "2"]);
  });

  it("renders a corporate author with no markers and no institutions line", () => {
    const { container } = render(
      <SourceDossierBody source={corporate} findings={[]} findingsPending={false} />,
    );
    expect(screen.getAllByText(/Example Policy Institute/).length).toBeGreaterThan(0);
    expect(container.querySelector("sup")).toBeNull();
  });

  it("renders no authors line at all when the source carries none", () => {
    const { container } = render(
      <SourceDossierBody
        source={{ ...authored, authorships: [] }}
        findings={[]}
        findingsPending={false}
      />,
    );
    expect(screen.queryByText(/Sampleton/)).toBeNull();
    expect(container.querySelector("sup")).toBeNull();
  });
});

describe("SourcesView — Download CSV", () => {
  it("fetches every page unfiltered and builds an escaped CSV", async () => {
    const rowA = { ...mockEvidence[0], title: 'A "quoted", title', url: "https://a.example" };
    const rowB = { ...mockEvidence[0], source_id: "22222222-2222-2222-2222-222222222222", title: "\t=SUM(1)" };
    const get = vi.fn()
      .mockResolvedValueOnce({ data: { data: [rowA], pagination: { page: 1, page_size: 1, total_items: 2 } } })
      .mockResolvedValueOnce({ data: { data: [rowB], pagination: { page: 2, page_size: 1, total_items: 2 } } });
    vi.mocked(queries.useApiClient).mockReturnValue({ GET: get } as never);
    let blob: Blob | undefined;
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn((value: Blob) => { blob = value; return "blob:mock"; }),
      revokeObjectURL: vi.fn(),
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderSources();
    await userEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    expect(get).toHaveBeenCalledTimes(2);
    expect(get.mock.calls[0][1].params.query).toEqual({ page: 1, page_size: 200 });
    const csv = await blob!.text();
    expect(csv).toContain("Screening reason");
    expect(csv).toContain("Description");
    expect(csv).toContain('"A ""quoted"", title"');
    expect(csv).toContain("\"'\t=SUM(1)\"");
    expect(click).toHaveBeenCalled();
    expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe("Tower Hamlets task - sources.csv");
    click.mockRestore();
    vi.unstubAllGlobals();
  });
});

// Task 046, amendment 3 (R67): on an options-scoping task the dossier's
// findings slot shows the document's intervention profile records.
describe("SourcesView — the dossier's records on a scoping task", () => {
  const dossier = mockSourceDossiers[mockEvidence[2].source_id];
  const SOURCE_ID = dossier.source_id;
  const OPTION_A = "a0000000-0000-4000-8000-00000000000a";
  const OPTION_B = "a0000000-0000-4000-8000-00000000000b";
  const record = (optionId: string, optionName: string, intervention: string) => ({
    option_id: optionId,
    option_name: optionName,
    record_id: `${optionId}-record`,
    intervention,
    setting: "Jobcentres",
    unit: "16 to 24 year olds",
    outcome: "employment",
    study_geography: "England",
    role: "evaluated" as const,
  });
  const finding = {
    finding_id: "f-1",
    source_id: SOURCE_ID,
    profile: "iof",
    statement: "A finding statement from this source.",
  };

  function withTask(capability: "options_scoping" | "evidence_search") {
    vi.mocked(queries.useTask).mockReturnValue(
      { data: { name: "Tower Hamlets task", capability } } as unknown as ReturnType<typeof queries.useTask>,
    );
    vi.mocked(queries.useSourceDossier).mockReturnValue(
      { data: dossier, isPending: false, isError: false } as unknown as ReturnType<typeof queries.useSourceDossier>,
    );
    vi.mocked(queries.useFindings).mockReturnValue(
      { data: { data: [finding] }, isPending: false } as unknown as ReturnType<typeof queries.useFindings>,
    );
  }

  function withRecords(records: ReturnType<typeof record>[]) {
    vi.mocked(queries.useSourceRecords).mockReturnValue({
      data: { task_source_snapshot_id: SOURCE_ID, records },
      isPending: false,
    } as unknown as ReturnType<typeof queries.useSourceRecords>);
  }

  function renderAt(search: string) {
    return render(
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources${search}`]}>
          <Routes>
            <Route path="/tasks/:taskId/sources" element={<SourcesView />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );
  }

  it("from an option card: \"In this option\", the record in its own words", () => {
    withTask("options_scoping");
    withRecords([record(OPTION_A, "Youth guarantee", "youth guarantee")]);
    renderAt(`?source=${SOURCE_ID}&option=${OPTION_A}`);
    expect(vi.mocked(queries.useSourceRecords)).toHaveBeenLastCalledWith(
      TASK_ID, SOURCE_ID, OPTION_A, { enabled: true },
    );
    expect(screen.getByText("In this option")).toBeInTheDocument();
    expect(screen.queryByText("Findings from this source")).toBeNull();
    for (const [label, value] of [
      ["Intervention", "youth guarantee"],
      ["Setting", "Jobcentres"],
      ["Tried on", "16 to 24 year olds"],
      ["Outcomes measured", "employment"],
      ["Where", "England"],
      ["Role", "evaluated"],
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
      expect(screen.getByText(value)).toBeInTheDocument();
    }
    // The option is the card's own: its name is not repeated.
    expect(screen.queryByText("Youth guarantee")).toBeNull();
    expect(screen.queryByText(finding.statement)).toBeNull();
  });

  it("from the Sources tab: \"Records\", one per option with the option's name", () => {
    withTask("options_scoping");
    withRecords([
      record(OPTION_B, "Guarantee package", "guarantee package"),
      record(OPTION_A, "Youth guarantee", "youth guarantee"),
    ]);
    renderAt(`?source=${SOURCE_ID}`);
    expect(vi.mocked(queries.useSourceRecords)).toHaveBeenLastCalledWith(
      TASK_ID, SOURCE_ID, null, { enabled: true },
    );
    expect(screen.getByText("Records")).toBeInTheDocument();
    expect(screen.getByText("Guarantee package")).toBeInTheDocument();
    expect(screen.getByText("Youth guarantee")).toBeInTheDocument();
    expect(screen.getByText("guarantee package")).toBeInTheDocument();
    expect(screen.getByText("youth guarantee")).toBeInTheDocument();
    expect(screen.queryByText("In this option")).toBeNull();
  });

  it("a document with no record under the option shows its findings", () => {
    withTask("options_scoping");
    withRecords([]);
    renderAt(`?source=${SOURCE_ID}&option=${OPTION_A}`);
    expect(screen.getByText("Findings from this source")).toBeInTheDocument();
    expect(screen.getByText(finding.statement)).toBeInTheDocument();
    expect(screen.queryByText("In this option")).toBeNull();
  });

  it("an Evidence search task is unchanged: no records read, the findings shown", () => {
    withTask("evidence_search");
    withRecords([record(OPTION_A, "Youth guarantee", "youth guarantee")]);
    renderAt(`?source=${SOURCE_ID}`);
    expect(vi.mocked(queries.useSourceRecords)).toHaveBeenLastCalledWith(
      TASK_ID, SOURCE_ID, null, { enabled: false },
    );
    expect(screen.getByText("Findings from this source")).toBeInTheDocument();
    expect(screen.getByText(finding.statement)).toBeInTheDocument();
    expect(screen.queryByText("Records")).toBeNull();
    expect(screen.queryByText("youth guarantee")).toBeNull();
  });
});

describe("SourcesView — one header line (owner, round 10)", () => {
  it("keeps every header on one line at the Caption label size, each sort mark's slot reserved", () => {
    renderSources();
    const table = screen.getAllByRole("table")[0];
    for (const th of within(table).getAllByRole("columnheader")) {
      expect(th).toHaveClass("sources-th");
      const button = within(th).getByRole("button");
      expect(button).toHaveClass("whitespace-nowrap", "text-caption", "uppercase", "min-h-6");
      // The arrow is always there (hidden until hover or focus when the
      // column is not the sort), so every label sits at the same height.
      expect(button.querySelector("[data-testid='sort-arrow']")).not.toBeNull();
    }
    // The header filters moved to the filter row: none left in the header.
    expect(within(table).queryByRole("button", { name: /^Filter/ })).toBeNull();
  });
});

// Several clicks through popovers each: a longer budget for a loaded machine.
describe("SourcesView — the filter row (round 10)", { timeout: 20_000 }, () => {
  it("groups the exclusive screening toggles and puts every filter in one row as a visible control", () => {
    renderSources();
    const row = screen.getByRole("group", { name: "Filter sources" });
    const screening = within(row).getByRole("group", { name: "Screening" });
    expect(within(screening).getAllByRole("button").map((button) => button.textContent)).toEqual(["All", "Included", "Screened out"]);
    expect(within(screening).queryByRole("button", { name: "Cited" })).toBeNull();
    // Each select is a visible bordered control at least 24 px tall.
    for (const name of [/^Key theme/, /^Origin/, /^Evidence type/, /^Strength/, /^Filter by year/]) {
      const trigger = within(row).getByRole("button", { name });
      expect(trigger).toHaveClass("border", "min-h-[34px]");
      expect(trigger).not.toHaveClass("opacity-0");
    }
  });

  it("filters by publisher country, the Landscape's names offered and the query carrying it", async () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: { ...mockLandscape, geographies: { GB: 30, US: 8, "Not reported": 5 } } } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: /^Country/ }));
    const countries = await screen.findByRole("listbox", { name: "Country" });
    expect(within(countries).getAllByRole("option").map((option) => option.textContent)).toEqual(["All", "United Kingdom", "United States"]);
    await user.click(within(countries).getByRole("option", { name: "United Kingdom" }));
    expect(screen.getByTestId("location")).toHaveTextContent("country=United+Kingdom");
    expect(lastEvidenceQuery()).toMatchObject({ country: "United Kingdom" });
  });

  it("shows Clear filters once a filter narrows the view, and clears every filter but the screening choice", async () => {
    const user = userEvent.setup();
    renderSources();
    expect(screen.queryByRole("button", { name: "Clear filters" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Included" }));
    expect(screen.queryByRole("button", { name: "Clear filters" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Cited" }));
    await user.click(screen.getByRole("button", { name: /^Origin/ }));
    await user.click(screen.getByRole("option", { name: "Overton" }));
    expect(screen.getByTestId("location")).toHaveTextContent("cited=true");
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByTestId("location")).toHaveTextContent("?status=Included");
    expect(screen.getByTestId("location")).not.toHaveTextContent(/cited|origin/);
  });

  it("offers a Sort select for phones, in column order with the direction named", async () => {
    const user = userEvent.setup();
    renderSources();
    const trigger = screen.getByRole("button", { name: /^Sort Relevant/ });
    expect(trigger.closest(".lg\\:hidden")).not.toBeNull();
    expect(trigger).toHaveTextContent("Relevant, most likely first");
    await user.click(trigger);
    const options = within(await screen.findByRole("listbox", { name: "Sort" })).getAllByRole("option");
    expect(options[0]).toHaveTextContent("Source, A to Z");
    expect(options.map((option) => option.textContent)).toContain("Year, newest first");
    await user.click(screen.getByRole("option", { name: "Year, newest first" }));
    expect(screen.getByTestId("location")).toHaveTextContent("sort=year&order=desc");
    expect(lastEvidenceQuery()).toMatchObject({ sort: "year", order: "desc" });
  });
});

describe("SourcesView — the rows (round 10)", () => {
  it("leaves one tab stop per row, the title: the cells' reasons are hover only", () => {
    renderSources();
    const table = screen.getAllByRole("table")[0];
    const body = within(table).getAllByRole("rowgroup")[1];
    for (const row of within(body).getAllByRole("row")) {
      const tabbable = within(row).getAllByRole("button").filter((button) => button.tabIndex >= 0);
      expect(tabbable).toHaveLength(1);
    }
    // The hover reasons are still there for a pointer.
    expect(screen.getAllByRole("button", { name: "Abstract only: why" })[0]).toHaveAttribute("tabindex", "-1");
  });

  it("sets the values as plain text: the evidence type in sentence case, the one chip the green Cited", () => {
    renderSources([{ ...mockEvidence[2], evidence_type: "RCTs and Quasi-Experimental Studies", cited: true }]);
    const table = screen.getAllByRole("table")[0];
    expect(within(table).getByText("RCTs and quasi-experimental studies")).not.toHaveClass("text-[11.5px]");
    const chips = table.querySelectorAll(".text-\\[11\\.5px\\]");
    expect([...chips].map((chip) => chip.textContent)).toEqual(["Cited"]);
  });

  it("stacks a row below lg with the values in column order (the markup the phone row restyles)", () => {
    renderSources([{ ...mockEvidence[2] }]);
    const table = screen.getAllByRole("table")[0];
    const row = within(table).getAllByRole("row")[1];
    const cells = within(row).getAllByRole("cell");
    expect(cells.map((cell) => cell.className.split(" ").filter((name) => name.startsWith("sources-cell") || name === "sources-value"))).toEqual([
      ["sources-cell", "sources-cell-source"],
      ["sources-cell", "sources-cell-year"],
      ["sources-cell", "sources-value"],
      ["sources-cell", "sources-value"],
      ["sources-cell", "sources-value", "sources-cell-relevant"],
      ["sources-cell", "sources-value"],
    ]);
    expect(cells.slice(2).map((cell) => cell.textContent)).toEqual(["Cohort study", "Moderate confidence", "91%", "Abstract only"]);
  });
});

describe("SourcesView — states in the table's frame (round 10)", { timeout: 20_000 }, () => {
  const evidence = (value: Partial<ReturnType<typeof queries.useEvidence>>) =>
    vi.mocked(queries.useEvidence).mockReturnValue({ refetch: vi.fn(), ...value } as unknown as ReturnType<typeof queries.useEvidence>);

  it("loads inside the frame: the real header row and six placeholder rows", () => {
    evidence({ data: undefined, isPending: true, isError: false } as never);
    renderSources();
    const loading = screen.getByLabelText("Loading sources");
    expect(loading).toHaveClass("sources-frame");
    expect(loading).toHaveAttribute("aria-busy", "true");
    expect(within(loading).getByRole("button", { name: "Sort by source" })).toBeInTheDocument();
    expect(loading.querySelectorAll(".sources-row-skeleton")).toHaveLength(6);
  });

  it("fails inside the frame with the sentence and a 40 px ghost Try again", async () => {
    const refetch = vi.fn();
    evidence({ data: undefined, isPending: false, isError: true, error: new Error("boom"), refetch } as never);
    renderSources();
    const alert = screen.getByRole("alert");
    expect(alert).toHaveClass("sources-frame");
    expect(alert).toHaveTextContent("Sources couldn't be loaded.");
    const retry = within(alert).getByRole("button", { name: "Try again" });
    expect(retry).toHaveClass("h-10");
    await userEvent.click(retry);
    expect(refetch).toHaveBeenCalled();
  });

  it("says no sources yet, with one sentence, when nothing has been found", () => {
    evidence({ data: evidencePage([]), isPending: false, isError: false } as never);
    streamState = { ...createInitialRunStreamState(), run: { id: "r", status: "running", startedAt: "2026-11-05T10:00:00Z" }, stages: [] } as RunStreamState;
    renderSources();
    const empty = screen.getAllByRole("status").find((node) => node.classList.contains("sources-frame")) as HTMLElement;
    expect(empty).toHaveTextContent("No sources yet");
    expect(empty).toHaveTextContent("They appear here as the search finds them.");
    expect(empty).not.toHaveTextContent("—");
  });

  it("offers to clear the filters when nothing matches, saying how many there are without them", async () => {
    vi.mocked(queries.useEvidence).mockImplementation((_task, query) => ({
      data: query?.page_size === 1 ? evidencePage(mockEvidence.slice(0, 7)) : evidencePage([]),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    }) as unknown as ReturnType<typeof queries.useEvidence>);
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: "Cited" }));
    const empty = screen.getAllByRole("status").find((node) => node.classList.contains("sources-frame")) as HTMLElement;
    expect(empty).toHaveTextContent("No sources match");
    expect(empty).toHaveTextContent("Clear the filters to see all 7.");
    await user.click(within(empty).getByRole("button", { name: "Clear filters" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("cited");
  });

  it("names the rows a page shows, and starts the next page at its top", async () => {
    const scroll = vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(() => {});
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: { data: mockEvidence, pagination: { page: 1, page_size: 50, total_items: 52 } },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useEvidence>);
    renderSources();
    expect(screen.getAllByRole("status").some((node) => node.textContent === `1–${mockEvidence.length} of 52 sources`)).toBe(true);
    const pages = screen.getByRole("navigation", { name: "Pages" });
    expect(pages).toHaveTextContent("Page 1 of 2");
    const next = within(pages).getByRole("button", { name: "Next" });
    expect(next).toHaveClass("h-10");
    await userEvent.click(next);
    expect(screen.getByTestId("location")).toHaveTextContent("page=2");
    expect(scroll).toHaveBeenCalledWith({ block: "start" });
    scroll.mockRestore();
  });
});

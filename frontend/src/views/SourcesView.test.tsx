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
  useLonglist: vi.fn(() => ({ data: undefined, isPending: false, isError: false })),
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

/** The fixture rows with an abstract each, as real rows carry one (the
 *  provider's abstract or a description), so "Abstract only" reads as it
 *  does live; a test that needs "Title only" drops it. */
const ABSTRACTED = mockEvidence.map((item) => ({ ...item, abstract: `About ${item.title}.` }));

function evidencePage(rows: typeof mockEvidence = ABSTRACTED) {
  return { data: rows, pagination: { page: 1, page_size: 50, total_items: rows.length } };
}

/** Surfaces the current URL search string so tests can assert on it
 *  without reaching into router internals. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.search}</div>;
}

function renderSources(rows?: typeof mockEvidence, search = "") {
  if (rows !== undefined) {
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: evidencePage(rows),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useEvidence>);
  }
  return render(sourcesTree(search));
}

function sourcesTree(search = "") {
  return (
    <TooltipProvider>
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources${search}`]}>
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

describe("SourcesView — the default filter during a run (task 058, N16)", { timeout: 20_000 }, () => {
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
    expect(screen.getByRole("button", { name: "Relevant" })).toHaveAttribute("aria-pressed", "true");
    expect(lastEvidenceQuery()).toMatchObject({ status: ["Included"] });
  });

  it("keeps Included for a task with no live stream and no run in flight", () => {
    renderSources();
    expect(screen.getByRole("button", { name: "Relevant" })).toHaveAttribute("aria-pressed", "true");
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

  it("says Collecting… on a source queued for its full text while the full texts are collected, in place of its label (round 14)", () => {
    streamState = running("ingest");
    rows([
      row({ source_id: "a", title: "Unread source", screen_status: "relevant", read_in_full: false, status: "relevant", full_text_status: "queued" }),
      row({ source_id: "b", title: "Read source", screen_status: "relevant", read_in_full: true, status: "read_in_full" }),
    ]);
    renderSources();
    const collecting = screen.getByTestId("status-collecting");
    expect(collecting).toHaveTextContent("Collecting…");
    expect(collecting).toHaveClass("anim-breathe-soft", "text-grey");
    expect(screen.getByText("Unread source").closest("tr")).toContainElement(collecting);
    expect(screen.queryByText("Abstract only")).toBeNull();
    expect(screen.getAllByTestId("status-collecting")).toHaveLength(1);
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
    expect(line.textContent).toBe(`${cited.venue} · ${cited.year} · ${cited.origin}`);
    expect(within(line).getByText(String(cited.year))).toHaveClass("@min-[54rem]/sources:hidden");
    // Round 12: "Cited" sits under the Status with a green tick, no chip.
    const status = row.querySelector(".sources-cell-status") as HTMLElement;
    expect(within(status).getByText("Cited")).toHaveClass("sources-cited");
    expect(status.querySelector(".sources-cited svg")).toHaveClass("text-green");
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
    // Idle, the control names its facet; its name carries the value.
    const trigger = screen.getByRole("button", { name: "Key theme: All themes" });
    expect(trigger).toHaveTextContent("Key theme");
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

  it("counts the sources under the table, Download CSV at that line's end, the filter bar filters only (round 12)", () => {
    renderSources();
    const count = screen.getAllByRole("status").find((node) => node.textContent === `${mockEvidence.length} sources`) as HTMLElement;
    expect(count).toHaveClass("text-meta", "text-grey");
    const frame = document.querySelector(".sources-frame") as HTMLElement;
    expect(frame.compareDocumentPosition(count) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Round 12 (lead): Download CSV is the quiet control with the download
    // glyph at the right end of the line under the table, 24 px after the
    // page controls; the filter bar holds filters only.
    const download = screen.getByRole("button", { name: "Download CSV" });
    expect(download).toHaveClass("text-grey", "h-8");
    expect(download).not.toHaveClass("border");
    expect(download.querySelector("svg")).not.toBeNull();
    expect(screen.getByRole("group", { name: "Filter sources" })).not.toContainElement(download);
    const foot = screen.getByTestId("sources-foot");
    expect(foot).toContainElement(download);
    expect(foot).toContainElement(count);
    expect(download.closest("div")).toBe(foot);
  });

  it("shows the finished search as a one-line section above the filter bar, a Body sentence whose Show opens one table", async () => {
    const user = userEvent.setup();
    renderSources();
    const block = screen.getByTestId("search-queries-summary");
    // Round 12 (owner): above the filter bar, 24 px clear of it, so the bar
    // reads as the table's own head.
    const bar = screen.getByRole("group", { name: "Filter sources" });
    expect(block.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(block.parentElement).toHaveClass("mb-6");
    // One line: the Label heading at the left, the Body Ink sentence at the
    // right, the hairline under them.
    // One region by that name: the folded live block no longer names itself.
    expect(screen.getAllByRole("region", { name: "Search queries" })).toHaveLength(1);
    // Round 14 (owner): the whole line is the one button, inside the
    // heading: the Label at the left, the Body Ink sentence and Show at the
    // right, the hairline under them.
    const line = within(block).getByRole("button", { name: /^Search queries: Found with/ });
    expect(line.closest("h2")).not.toBeNull();
    expect(line).toHaveClass("w-full", "justify-between", "flex-wrap", "border-b");
    expect(within(line).getByText("Search queries")).toBeInTheDocument();
    expect(within(line).getByText(/^Found with/).closest(".text-body")).toHaveClass("text-ink");
    expect(within(block).getAllByRole("button")).toHaveLength(1);
    const toggle = within(block).getByRole("button", { name: "Search queries: Found with 5 queries and 1 citation pass · Show" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(toggle).getByText("Show")).toHaveClass("font-semibold", "text-grey", "underline");
    expect(within(block).queryByRole("table")).toBeNull();
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveTextContent(/Hide$/);
    const table = within(block).getByRole("table");
    // Ruled rows: the query, the database in Grey, the count; no row-group
    // labels.
    expect(within(table).queryByRole("rowheader")).toBeNull();
    // Round 14 (owner): visible column headings in the Sources table's
    // header style, once, Results over the counts at the right.
    const head = within(table).getByRole("columnheader", { name: "Query" }).closest("thead") as HTMLElement;
    expect(head).not.toHaveClass("sr-only");
    expect(head).toHaveClass("border-b");
    expect(within(table).getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Query", "Database", "Results"]);
    expect(within(table).getByRole("columnheader", { name: "Results" })).toHaveClass("text-right");
    expect(table.querySelectorAll("thead")).toHaveLength(1);
    expect(within(table).getAllByText("Overton")[0]).toHaveClass("text-grey");
    expect(table).toHaveClass("text-meta");
    // The saved pass is its own Grey row, worded by the server.
    expect(within(table).getByText("Followed citations from 50 sources").closest("td")).toHaveClass("text-grey");
    expect(within(table).getByText("184")).toHaveClass("tabular-nums");
    const query = within(table).getByText("childhood obesity school intervention UK");
    // Queries wrap on words.
    expect(query.closest("td")).toHaveClass("break-words");
    expect(within(table).getByText("34")).toHaveClass("tabular-nums");
  });
});

// Round 12 (owner go): each query and pass is a link that filters the table
// to the records it returned.
describe("SourcesView — a query's results (round 12)", { timeout: 20_000 }, () => {
  const coverage = {
    data: {
      sentence: "",
      backends_detail: [
        {
          backend: "OpenAlex",
          relevant: 1,
          results: 40,
          queries: [{ query: "primary school food environment and childhood obesity in England", results: 34, query_id: 11 }],
          passes: [{ pass: "citations", query: "Followed citations from 20 sources", results: 6, query_id: 12 }],
        },
      ],
    },
  } as unknown as ReturnType<typeof queries.useCoverage>;
  beforeEach(() => {
    vi.mocked(queries.useCoverage).mockReturnValue(coverage);
  });

  it("links each query and pass to the table filtered on it, every screening choice shown", async () => {
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: /^Search queries: Found with 1 query and 1 citation pass/ }));
    const link = screen.getByRole("link", { name: "primary school food environment and childhood obesity in England" });
    expect(link.getAttribute("href")).toContain("query=11");
    expect(screen.getByRole("link", { name: "Followed citations from 20 sources" }).getAttribute("href")).toContain("query=12");
    await user.click(link);
    expect(screen.getByTestId("location")).toHaveTextContent("query=11");
    expect(screen.getByTestId("location")).toHaveTextContent("status=all");
    expect(lastEvidenceQuery()).toMatchObject({ query: 11, status: undefined });
  });

  it("shows the applied query as a Navy chip, its first 40 characters, the × clearing it", async () => {
    const user = userEvent.setup();
    renderSources(ABSTRACTED.slice(0, 2), "?query=11&status=all");
    const bar = screen.getByRole("group", { name: "Filter sources" });
    const chip = within(bar).getByText("Query: primary school food environment and chil…");
    expect(chip.closest("span.bg-navy")).not.toBeNull();
    // The count line reads for the filtered set (the read's own total).
    expect(screen.getAllByRole("status").some((node) => node.textContent === "2 sources")).toBe(true);
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
    await user.click(within(bar).getByRole("button", { name: "Clear the query filter" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("query=");
  });

  it("says why a search from before the change finds nothing", () => {
    // The server keeps no records for a search run before the ids were
    // kept: the query returned 34, the filter on it alone returns none.
    renderSources([], "?query=11&status=all");
    expect(screen.getByText("This search ran before queries were linked to their results.")).toBeInTheDocument();
    expect(screen.queryByText(/Clear the filters to see all/)).toBeNull();
  });

  it("keeps the ordinary no-match state when another filter narrows the query's results", () => {
    renderSources([], "?query=11&status=all&strength=Weak");
    expect(screen.queryByText("This search ran before queries were linked to their results.")).toBeNull();
    expect(screen.getByText("No sources match")).toBeInTheDocument();
  });

  it("reads a live query without a key as plain words", () => {
    vi.mocked(queries.useCoverage).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.useCoverage>);
    streamState = {
      ...createInitialRunStreamState(),
      run: { id: "run-1", status: "running", startedAt: "2026-11-05T10:00:00Z" },
      stages: [{ stage: "acquire", label: "Searching", status: "started", startedAt: "2026-11-05T10:00:00Z", counts: [] }],
      liveSearchQueries: [
        { backend: "openalex", query: "school meals uptake", kind: "topic", results: 3 },
        { backend: "openalex", query: "breakfast clubs", kind: "topic", results: 4, query_id: 21 } as NonNullable<RunStreamState["liveSearchQueries"]>[number],
      ],
    } as RunStreamState;
    renderSources();
    const block = screen.getByTestId("search-queries");
    expect(within(block).queryByRole("link", { name: "school meals uptake" })).toBeNull();
    expect(within(block).getByRole("link", { name: "breakfast clubs" }).getAttribute("href")).toContain("query=21");
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
    expect(within(table).getByText("Following citations from 50 sources").closest("td")).toHaveClass("text-grey");
    expect(within(table).getByText("primary school food environment obesity").closest("td")).toHaveClass("text-navy");
    // No empty card and no count line while the search runs with nothing in,
    // and the filter bar waits with the table (round 12).
    expect(screen.queryByText(/No sources yet/)).toBeNull();
    expect(screen.queryByText(/^\d+ sources$/)).toBeNull();
    expect(screen.queryByRole("group", { name: "Filter sources" })).toBeNull();
    // The finished search's section waits for the search to end.
    expect(screen.queryByTestId("search-queries-summary")).toBeNull();
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
    expect(screen.getByRole("button", { name: "Search queries: Found with 2 queries · Show" })).toBeInTheDocument();
  });

  it("words a live pass in the past tense once the search ends, before the saved coverage lands", async () => {
    const user = userEvent.setup();
    vi.mocked(queries.useCoverage).mockReturnValue({ data: null } as unknown as ReturnType<typeof queries.useCoverage>);
    streamState = searching(
      [
        { backend: "openalex", query: "school meals uptake", kind: "topic", results: 34 },
        { backend: "openalex", query: "Following citations from 40 sources", kind: "citations", results: 212 },
      ],
      "completed",
    );
    renderSources();
    const toggle = screen.getByRole("button", { name: "Search queries: Found with 1 query and 1 citation pass · Show" });
    await user.click(toggle);
    const table = within(screen.getByTestId("search-queries-summary")).getByRole("table");
    expect(within(table).getByText("Followed citations from 40 sources").closest("td")).toHaveClass("text-grey");
    expect(within(table).getByText("212")).toHaveClass("tabular-nums");
  });

  it("takes the saved passes over the stream's once the coverage lands", () => {
    vi.mocked(queries.useCoverage).mockReturnValue({
      data: {
        sentence: "",
        backends_detail: [
          {
            backend: "OpenAlex",
            relevant: 1,
            results: 40,
            queries: [{ query: "school meals uptake", results: 34 }],
            passes: [
              { pass: "citations", query: "Followed citations from 20 sources", results: 6 },
              { pass: "lookup", query: "Looked up 200 cited works", results: 200 },
            ],
          },
        ],
      },
    } as unknown as ReturnType<typeof queries.useCoverage>);
    streamState = searching(
      [{ backend: "openalex", query: "Following citations from 20 sources", kind: "citations", results: 6 }],
      "completed",
    );
    renderSources();
    expect(screen.getByRole("button", { name: "Search queries: Found with 1 query and 2 citation passes · Show" })).toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: "Relevant" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("columnheader", { name: /Relevant/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
  });

  it("Included narrows via the status param", async () => {
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: "Relevant" }));
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

describe("SourceDossierBody, one type scale (round 12)", () => {
  const cited = mockSourceDossiers[mockEvidence[7].source_id];
  const breakfast = mockSourceDossiers[mockEvidence[2].source_id];

  it("opens on the reference line as the report's, then the facts as a ruled list", () => {
    render(
      <TooltipProvider>
        <SourceDossierBody source={{ ...breakfast, url: "https://doi.org/10.1000/example.1" }} findings={[]} findingsPending={false} />
      </TooltipProvider>,
    );
    const reference = screen.getByTestId("dossier-reference");
    expect(reference).toHaveClass("text-body");
    expect(reference.textContent).toMatch(/^Sampleton A, Mockford C \(2022\)\. BMJ Open\. doi\.org\/10\.1000\/example\.1$/);
    const facts = document.querySelector('dl[aria-label="About this source"]') as HTMLElement;
    expect(facts).not.toBeNull();
    const labels = within(facts).getAllByRole("term").map((term) => term.textContent);
    expect(labels).toEqual(["Evidence type", "Why this type", "Strength", "Status", "Year", "Origin"]);
    for (const term of within(facts).getAllByRole("term")) expect(term).toHaveClass("text-grey");
    // The actions at the foot.
    const open = screen.getByRole("link", { name: "Open original" });
    expect(open.closest("footer")).not.toBeNull();
    expect(open).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("carries no chips and no bold, its labels at Meta Grey", () => {
    const { container } = render(
      <TooltipProvider>
        <SourceDossierBody source={cited} findings={[]} findingsPending={false} />
      </TooltipProvider>,
    );
    expect(container.querySelectorAll(".text-\\[11\\.5px\\]")).toHaveLength(0);
    expect(container.querySelectorAll(".font-semibold, .font-bold, .font-extrabold")).toHaveLength(0);
    for (const heading of screen.getAllByRole("heading")) expect(heading).toHaveClass("text-meta", "text-grey");
    // An AI description says so in its label, not in a chip.
    expect(screen.getByRole("heading", { name: "About · AI description" })).toBeInTheDocument();
    // Cited sits with the Status, as in the table.
    const status = screen.getByText("Status").parentElement as HTMLElement;
    expect(within(status).getByText("Cited")).toHaveClass("sources-cited");
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
    expect(within(screening).getAllByRole("button").map((button) => button.textContent)).toEqual(["All", "Relevant", "Screened out"]);
    expect(within(screening).queryByRole("button", { name: "Cited" })).toBeNull();
    // Each select is a visible bordered control at least 24 px tall.
    // Every control is a 32 px outline box on the bar's one baseline (round 11).
    for (const name of [/^Key theme/, /^Origin/, /^Evidence type/, /^Strength/, /^Filter by year/]) {
      const trigger = within(row).getByRole("button", { name });
      expect(trigger).toHaveClass("border", "h-8", "text-meta");
      expect(trigger).not.toHaveClass("opacity-0");
    }
    // Round 12: 12 px between controls.
    // Round 12: the screening switch alone on the first row, the facets on
    // a second with 12 px gaps, 8 px between the rows.
    expect(row).toHaveClass("flex-col", "gap-2");
    expect(row.firstElementChild).toBe(screening);
    const facets = within(row).getByTestId("sources-facets");
    expect(facets).toHaveClass("flex-wrap", "gap-3");
    expect(facets).not.toContainElement(screening);
    // The screening switch: the chosen choice has a Navy border and words.
    expect(within(screening).getByRole("button", { name: "Relevant" })).toHaveClass("border-navy", "text-navy", "h-8");
    expect(within(screening).getByRole("button", { name: "All" })).toHaveClass("border-line-2", "text-grey");
  });

  it("shows an applied filter as a filled Navy chip whose × clears it", async () => {
    const user = userEvent.setup();
    renderSources(undefined, "?strength=Moderate&cited=true");
    const chip = screen.getByRole("button", { name: "Strength: Moderate" });
    expect(chip).toHaveTextContent("Strength: Moderate");
    expect(chip.parentElement).toHaveClass("bg-navy", "text-paper", "h-8");
    const cited = screen.getByRole("button", { name: "Cited" });
    expect(cited).toHaveAttribute("aria-pressed", "true");
    expect(cited.parentElement).toHaveClass("bg-navy");
    await user.click(screen.getByRole("button", { name: "Clear the strength filter" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("strength=");
    expect(screen.getByTestId("location")).toHaveTextContent("cited=true");
    // An idle facet stays the outline box.
    expect(screen.getByRole("button", { name: "Strength: All" })).toHaveClass("border-line-2", "bg-paper");
  });

  it("filters by publisher country, the Landscape's names offered and the query carrying it", async () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: { ...mockLandscape, geographies: { GB: 30, US: 8, "Not reported": 5 } } } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    const user = userEvent.setup();
    renderSources();
    await user.click(screen.getByRole("button", { name: /^Country/ }));
    const countries = await screen.findByRole("listbox", { name: "Country" });
    // Round 14: the sources without one, last, as the Landscape pins them.
    expect(within(countries).getAllByRole("option").map((option) => option.textContent)).toEqual(["All", "United Kingdom", "United States", "Not reported"]);
    await user.click(within(countries).getByRole("option", { name: "United Kingdom" }));
    expect(screen.getByTestId("location")).toHaveTextContent("country=United+Kingdom");
    expect(lastEvidenceQuery()).toMatchObject({ country: "United Kingdom" });
  });

  it("names a scoping task's theme filter Theme, its choices the longlist's themes (round 14)", () => {
    vi.mocked(queries.useTask).mockReturnValue(
      { data: { name: "NEET task", capability: "options_scoping" } } as unknown as ReturnType<typeof queries.useTask>,
    );
    vi.mocked(queries.useLonglist).mockReturnValue({
      data: { themes: [{ theme_id: "lt-1", name: "Earlier support", description: "", option_ids: [] }], options: [] },
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof queries.useLonglist>);
    renderSources(undefined, "?theme=lt-1");
    expect(vi.mocked(queries.useLonglist)).toHaveBeenLastCalledWith(TASK_ID);
    expect(lastEvidenceQuery()).toMatchObject({ theme: "lt-1" });
    expect(screen.getByRole("group", { name: "Filter sources" })).toHaveTextContent("Theme: Earlier support");
  });

  it("names the sources with no country Not reported when the Landscape's row opens them (round 14)", () => {
    vi.mocked(queries.useLandscape).mockReturnValue(
      { data: { ...mockLandscape, geographies: { GB: 30, "Not reported": 5 } } } as unknown as ReturnType<typeof queries.useLandscape>,
    );
    renderSources(undefined, "?country=none");
    expect(lastEvidenceQuery()).toMatchObject({ country: "none" });
    expect(screen.getByRole("group", { name: "Filter sources" })).toHaveTextContent("Country: Not reported");
  });

  it("shows Clear filters once a filter narrows the view, and clears every filter but the screening choice", async () => {
    const user = userEvent.setup();
    renderSources();
    expect(screen.queryByRole("button", { name: "Clear filters" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Relevant" }));
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
    const trigger = screen.getByRole("button", { name: /^Sort: Relevant/ });
    // Shown while the table stacks, by the column's width (round 12).
    expect(trigger).toHaveClass("@min-[54rem]/sources:hidden");
    expect(trigger).toHaveTextContent("Sort: Relevant, most likely first");
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

  it("marks the values with a reason by the dotted underline, and the strength by its tone", () => {
    renderSources([
      { ...mockEvidence[2], source_id: "s1", title: "Strong one", appraisal_tier: "Very strong", classification_reason: "Why" },
      { ...mockEvidence[2], source_id: "s2", title: "Middle one", appraisal_tier: "Moderate" },
      { ...mockEvidence[2], source_id: "s3", title: "Weak one", appraisal_tier: "Weak" },
      { ...mockEvidence[2], source_id: "s4", title: "Unrated one", appraisal_tier: "Unrated" },
    ]);
    const table = screen.getAllByRole("table")[0];
    // The standard affordance: the value's word carries the dotted underline.
    expect(within(table).getAllByText("Cohort study")[0]).toHaveClass("reason-word");
    expect(within(table).getByText("Very strong")).toHaveClass("reason-word");
    expect(within(table).getAllByText("91%")[0]).toHaveClass("reason-word");
    // The tone square before the strength (round 12): green, yellow, red, red.
    const tones = within(table).getAllByTestId("strength-mark").map((mark) => mark.getAttribute("data-tone"));
    expect(tones).toEqual(["green", "yellow", "red", "red"]);
  });

  it("sets the values as plain text: the evidence type in sentence case, and no chips (round 12)", () => {
    renderSources([{ ...mockEvidence[2], evidence_type: "RCTs and Quasi-Experimental Studies", cited: true }]);
    const table = screen.getAllByRole("table")[0];
    expect(within(table).getByText("RCTs and quasi-experimental studies")).not.toHaveClass("text-[11.5px]");
    expect(table.querySelectorAll(".text-\\[11\\.5px\\]")).toHaveLength(0);
  });

  it("shows the strength's tones as a legend on its header", async () => {
    renderSources();
    const header = screen.getByRole("button", { name: "Sort by evidence strength" });
    await userEvent.hover(header);
    const legend = (await screen.findAllByRole("list", { name: "Evidence strength tones" }))[0];
    expect(within(legend).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Very strong, Strong", "Moderate, Limited", "Weak, Unrated",
    ]);
  });

  it("tones the Status: green full text, yellow abstract, red neither; Full text links to the document", () => {
    renderSources([
      { ...mockEvidence[5], source_id: "f1", title: "Read one", abstract: "A.", full_text_url: "https://example.org/read.pdf" },
      { ...mockEvidence[6], source_id: "f2", title: "Read, no address", abstract: "A.", full_text_url: null },
      { ...mockEvidence[2], source_id: "a1", title: "Abstract one", abstract: "An abstract." },
      { ...mockEvidence[2], source_id: "t1", title: "Title one", abstract: null },
    ]);
    const table = screen.getAllByRole("table")[0];
    const marks = within(table).getAllByTestId("status-mark").map((mark) => mark.getAttribute("data-tone"));
    expect(marks).toEqual(["green", "green", "yellow", "red"]);
    const link = within(table).getByRole("link", { name: "Full text (opens the document in a new tab)" });
    expect(link).toHaveAttribute("href", "https://example.org/read.pdf");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    // Without the address the word stays plain.
    expect(within(table).getAllByRole("link", { name: /Full text/ })).toHaveLength(1);
    expect(within(table).getByRole("button", { name: "Title only: why" })).toHaveAttribute("tabindex", "-1");
  });

  it("stacks a row below lg with the values in column order (the markup the phone row restyles)", () => {
    renderSources([{ ...mockEvidence[2], abstract: "An abstract." }]);
    const table = screen.getAllByRole("table")[0];
    const row = within(table).getAllByRole("row")[1];
    const cells = within(row).getAllByRole("cell");
    expect(cells.map((cell) => cell.className.split(" ").filter((name) => name.startsWith("sources-cell") || name === "sources-value"))).toEqual([
      ["sources-cell", "sources-cell-source"],
      ["sources-cell", "sources-cell-year"],
      ["sources-cell", "sources-value", "sources-cell-type"],
      ["sources-cell", "sources-value"],
      ["sources-cell", "sources-value", "sources-cell-relevant"],
      ["sources-cell", "sources-value", "sources-cell-status"],
    ]);
    expect(cells.slice(2).map((cell) => cell.textContent)).toEqual(["Cohort study", "Moderate confidence", "91%", "Abstract only"]);
  });
});

// Round 13 (owner): the funnel's Appraised and Full text accessed rows open
// the table on their sets through the evidence read's filters.
describe("SourcesView — the funnel's sets (round 13)", { timeout: 20_000 }, () => {
  it("filters on appraised and full text, each shown as a chip whose × clears it", async () => {
    const user = userEvent.setup();
    renderSources(undefined, "?appraised=true&depth=full_text");
    expect(lastEvidenceQuery()).toMatchObject({ appraised: true, depth: "full_text" });
    const bar = screen.getByRole("group", { name: "Filter sources" });
    expect(within(bar).getByRole("button", { name: "Appraised" }).closest("span")).toHaveClass("bg-navy");
    expect(within(bar).getByRole("button", { name: "Full text accessed" }).closest("span")).toHaveClass("bg-navy");
    await user.click(within(bar).getByRole("button", { name: "Appraised" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("appraised");
    expect(screen.getByTestId("location")).toHaveTextContent("depth=full_text");
    // Clear filters takes the rest.
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("depth");
  });

  it("names the screened-in set Relevant, as the funnel does, the API's value unchanged", async () => {
    const user = userEvent.setup();
    renderSources(undefined, "?status=all");
    await user.click(screen.getByRole("button", { name: "Relevant" }));
    expect(screen.getByTestId("location")).toHaveTextContent("status=Included");
    expect(screen.queryByRole("button", { name: "Included" })).toBeNull();
  });
});

// Round 12 (owner): 25 a page by default, 50 or 100 by choice, remembered
// per task; the URL names the size only when it is not 25.
describe("SourcesView — sources per page (round 12)", { timeout: 20_000 }, () => {
  // A storage of our own: the Node and jsdom storages behave differently
  // locally and on CI (docs/knowledge).
  beforeEach(() => {
    const values = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      get length() {
        return values.size;
      },
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      key: (index: number) => [...values.keys()][index] ?? null,
      removeItem: (key: string) => void values.delete(key),
      setItem: (key: string, value: string) => void values.set(key, String(value)),
    } satisfies Storage);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });
  const paged = (pageSize: number) =>
    vi.mocked(queries.useEvidence).mockReturnValue({
      data: { data: ABSTRACTED, pagination: { page: 1, page_size: pageSize, total_items: 207 } },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useEvidence>);

  it("asks for 25 a page by default and names the range for it", () => {
    paged(25);
    renderSources();
    expect(lastEvidenceQuery()).toMatchObject({ page_size: 25 });
    expect(screen.getAllByRole("status").some((node) => node.textContent === `1–${ABSTRACTED.length} of 207 sources`)).toBe(true);
    const select = screen.getByRole("combobox", { name: "Sources per page" });
    expect(select).toHaveTextContent("25 per page");
    expect(select).toHaveClass("h-8");
  });

  it("puts a chosen size in the URL and remembers it for the task; 25 leaves the URL", async () => {
    const user = userEvent.setup();
    paged(25);
    const { unmount } = renderSources(undefined, "?page=3");
    await user.click(screen.getByRole("combobox", { name: "Sources per page" }));
    await user.click(screen.getByRole("option", { name: "100 per page" }));
    expect(screen.getByTestId("location")).toHaveTextContent("page_size=100");
    expect(screen.getByTestId("location")).not.toHaveTextContent("page=3");
    expect(lastEvidenceQuery()).toMatchObject({ page_size: 100 });
    unmount();
    // A fresh visit to the task opens on the remembered size, URL or not.
    renderSources();
    expect(lastEvidenceQuery()).toMatchObject({ page_size: 100 });
    paged(100);
    await user.click(screen.getByRole("combobox", { name: "Sources per page" }));
    await user.click(screen.getByRole("option", { name: "25 per page" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("page_size");
    expect(lastEvidenceQuery()).toMatchObject({ page_size: 25 });
  });

  it("names the size it asked for even when the server answers with another", () => {
    paged(207);
    renderSources();
    expect(screen.getByRole("combobox", { name: "Sources per page" })).toHaveTextContent("25 per page");
  });

  it("offers no size when every source fits on the smallest page", () => {
    renderSources(ABSTRACTED.slice(0, 3));
    expect(screen.queryByRole("combobox", { name: "Sources per page" })).toBeNull();
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
    // Round 13 (owner): a bar in every column of every row, each sized to
    // its column, the source's two lines included; Relevant's at the right.
    for (const row of loading.querySelectorAll(".sources-row-skeleton")) {
      const cells = [...row.querySelectorAll("td")];
      expect(cells).toHaveLength(6);
      for (const cell of cells) expect(cell.querySelector(".placeholder-bar")).not.toBeNull();
      expect(cells[0].querySelectorAll(".placeholder-bar")).toHaveLength(2);
      expect(cells[4].querySelector(".placeholder-bar")).toHaveClass("ml-auto");
    }
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
    const range = screen.getAllByRole("status").find((node) => node.textContent === `1–${mockEvidence.length} of 52 sources`) as HTMLElement;
    const pages = screen.getByRole("navigation", { name: "Pages" });
    expect(pages).toHaveTextContent("Page 1 of 2");
    // Round 12 (owner): Download CSV at the left; at the right the page
    // size, the range, then the page controls.
    const foot = screen.getByTestId("sources-foot");
    expect(foot.firstElementChild).toContainElement(screen.getByRole("button", { name: "Download CSV" }));
    const right = foot.lastElementChild as HTMLElement;
    expect(right).toContainElement(screen.getByRole("combobox", { name: "Sources per page" }));
    expect([...right.children].indexOf(range)).toBeLessThan([...right.children].indexOf(pages));
    const next = within(pages).getByRole("button", { name: "Next" });
    expect(next).toHaveClass("h-10");
    await userEvent.click(next);
    expect(screen.getByTestId("location")).toHaveTextContent("page=2");
    expect(scroll).toHaveBeenCalledWith({ block: "start" });
    scroll.mockRestore();
  });
});

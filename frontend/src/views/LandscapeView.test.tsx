import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState, type RunStreamState } from "../store";

import { mockFunnel, mockGroups, mockLandscape } from "../mock/fixtures";
import { LandscapeView } from "./LandscapeView";
import * as queries from "../api/queries";

vi.mock("../api/queries", () => ({
  useTask: vi.fn(),
  useLandscape: vi.fn(),
  useFunnel: vi.fn(),
  useGroups: vi.fn(),
}));

let streamState: RunStreamState = createInitialRunStreamState();
vi.mock("../store", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../store")>()),
  useRunStream: () => streamState,
}));

afterEach(() => {
  streamState = createInitialRunStreamState();
});

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function renderLandscape() {
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/sources/landscape`]}>
      <Routes>
        <Route path="/tasks/:taskId/sources/landscape" element={<LandscapeView />} />
      </Routes>
    </MemoryRouter>,
  );
}

type Landscape = NonNullable<ReturnType<typeof queries.useLandscape>["data"]>;
type Funnel = NonNullable<ReturnType<typeof queries.useFunnel>["data"]>;

function reads({
  landscape = mockLandscape,
  funnel = mockFunnel,
  groups = mockGroups,
  pending = false,
}: {
  landscape?: Landscape;
  funnel?: Funnel;
  groups?: typeof mockGroups | undefined;
  pending?: boolean;
} = {}) {
  vi.mocked(queries.useLandscape).mockReturnValue({
    data: pending ? undefined : landscape,
    isPending: pending,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof queries.useLandscape>);
  vi.mocked(queries.useFunnel).mockReturnValue({
    data: pending ? undefined : funnel,
    isPending: pending,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof queries.useFunnel>);
  vi.mocked(queries.useGroups).mockReturnValue({
    data: groups,
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof queries.useGroups>);
}

const REALISTIC_TYPES = {
  "Observational Research Studies": 31,
  "Policy Syntheses & Guidance Documents": 24,
  "RCTs and Quasi-Experimental Studies": 14,
  "Systematic Review and Meta-Analysis": 11,
  "Unknown / Insufficient information": 5,
};

beforeEach(() => {
  vi.mocked(queries.useTask).mockReturnValue(
    { data: { name: "Tower Hamlets task" } } as unknown as ReturnType<typeof queries.useTask>,
  );
});

describe("LandscapeView — finished", () => {
  it("sets each chart as an uncarded section in one centred column, named by an h2", () => {
    reads();
    const { container } = renderLandscape();
    for (const name of ["From search to citation", "Evidence types", "Publication years", "Where sources were published", "Finding groups"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
    expect(screen.getByRole("region", { name: "Evidence types" }).parentElement).toHaveClass("max-w-3xl");
    // No card inside the Sources panel.
    expect(container.querySelector(".shadow-\\[0_1px_3px_rgba\\(15\\,41\\,74\\,0\\.05\\)\\,0_8px_24px_rgba\\(15\\,41\\,74\\,0\\.04\\)\\]")).toBeNull();
    // The one bordered thing is the List / Map switch's outline (round 11).
    for (const bordered of container.querySelectorAll(".border-line-2")) {
      expect(bordered.closest('[role="group"][aria-label="Show as"]')).not.toBeNull();
    }
  });

  it("draws the funnel as a table of sources only, values in cells, no Findings row", () => {
    reads();
    renderLandscape();
    const table = screen.getByRole("table", { name: "From search to citation" });
    const rows = within(table).getAllByRole("row");
    expect(rows.map((row) => within(row).getByRole("rowheader").textContent)).toEqual([
      "Found",
      "Relevant",
      "Quality-checked",
      "Full text",
      "Shortlisted",
      "Cited",
    ]);
    expect(within(rows[0]).getByRole("cell")).toHaveTextContent("128");
    expect(within(table).queryByText("Findings")).toBeNull();
  });

  it("links each funnel row the table can filter to, and only those (round 11)", () => {
    reads();
    renderLandscape();
    const table = screen.getByRole("table", { name: "From search to citation" });
    const base = `/tasks/${TASK_ID}/sources/all`;
    expect(within(table).getByRole("link", { name: "Found" })).toHaveAttribute("href", `${base}?status=all`);
    expect(within(table).getByRole("link", { name: "Relevant" })).toHaveAttribute("href", `${base}?status=Included`);
    expect(within(table).getByRole("link", { name: "Cited" })).toHaveAttribute("href", `${base}?cited=true`);
    for (const name of ["Quality-checked", "Full text", "Shortlisted"]) {
      expect(within(table).queryByRole("link", { name })).toBeNull();
    }
  });

  it("switches the publisher countries between the list (the default) and the map", { timeout: 20_000 }, async () => {
    reads();
    renderLandscape();
    const region = screen.getByRole("region", { name: "Where sources were published" });
    const list = within(region).getByRole("button", { name: "List" });
    expect(list).toHaveAttribute("aria-pressed", "true");
    expect(within(region).getByRole("table", { name: "Where sources were published" })).toBeInTheDocument();
    within(region).getByRole("button", { name: "Map" }).click();
    // The map's module (and the atlas) loads lazily: allow for a busy runner.
    expect(
      await within(region).findByRole("img", { name: "Where sources were published" }, { timeout: 15_000 }),
    ).toBeInTheDocument();
    expect(within(region).queryByRole("table", { name: "Where sources were published" })).toBeNull();
  });

  it("puts no population line at the top (round 11); a heading counts only what differs", () => {
    reads({ landscape: { ...mockLandscape, years: { "2021": 20, "2022": 20 } as Record<string, number> } });
    renderLandscape();
    expect(screen.queryByText("46 relevant sources")).toBeNull();
    expect(screen.queryByTestId("landscape-population")).toBeNull();
    const within_ = (name: string) => within(screen.getByRole("region", { name }));
    expect(within_("Evidence types").queryByText(/relevant source/)).toBeNull();
    expect(within_("Publication years").getByText("40 with a year")).toBeInTheDocument();
    expect(within_("Where sources were published").queryByText(/relevant source/)).toBeNull();
    expect(within_("Finding groups").getByText("34 findings")).toBeInTheDocument();
  });

  it("puts no count on the years heading when every source has a year", () => {
    reads();
    renderLandscape();
    expect(within(screen.getByRole("region", { name: "Publication years" })).queryByText(/relevant source|with a year/)).toBeNull();
  });

  it("makes each evidence type with sources a link to All sources filtered to it; zero rows lead nowhere", () => {
    reads({ landscape: { ...mockLandscape, evidence_types: REALISTIC_TYPES } });
    renderLandscape();
    const table = screen.getByRole("table", { name: "Evidence types" });
    // Sentence case on the page (the report's formatter); the link keeps the
    // classifier's value.
    const review = within(table).getByRole("link", { name: "Systematic review and meta-analysis" });
    expect(review.getAttribute("href")).toBe(
      `/tasks/${TASK_ID}/sources/all?type=Systematic+Review+and+Meta-Analysis`,
    );
    expect(review.closest("tr")).toHaveAttribute("data-link");
    const modelling = within(table).getByRole("rowheader", { name: "Modelling & simulation" });
    expect(within(modelling).queryByRole("link")).toBeNull();
    expect(modelling.closest("tr")).not.toHaveAttribute("data-link");
  });

  it("makes each country a link to All sources filtered to it; Not reported and the folded tail lead nowhere", () => {
    reads({ landscape: { ...mockLandscape, geographies: { "Not reported": 49, GB: 37, US: 12 } } });
    renderLandscape();
    const table = screen.getByRole("table", { name: "Where sources were published" });
    expect(within(table).getByRole("link", { name: "United Kingdom" })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all?country=United+Kingdom`,
    );
    expect(within(table).getAllByRole("link")).toHaveLength(2);
    expect(within(within(table).getByRole("rowheader", { name: "Not reported" })).queryByRole("link")).toBeNull();
  });

  it("orders evidence types by the classifier's vocabulary, zeros shown, Unknown last", () => {
    reads({ landscape: { ...mockLandscape, evidence_types: REALISTIC_TYPES } });
    renderLandscape();
    const table = screen.getByRole("table", { name: "Evidence types" });
    const headers = within(table).getAllByRole("rowheader").map((cell) => cell.textContent);
    expect(headers[0]).toBe("Systematic review and meta-analysis");
    expect(headers.at(-1)).toBe("Unknown / insufficient information");
    expect(headers).toContain("Modelling & simulation");
    const modelling = within(table).getByRole("rowheader", { name: "Modelling & simulation" }).closest("tr");
    expect(modelling).toHaveTextContent("0");
    expect(screen.queryByTestId("classified-so-far")).toBeNull();
  });

  it("pins Not reported last in the geography table", () => {
    reads({ landscape: { ...mockLandscape, geographies: { "Not reported": 49, GB: 37, US: 12 } } });
    renderLandscape();
    const table = screen.getByRole("table", { name: "Where sources were published" });
    expect(within(table).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual([
      "United Kingdom",
      "United States",
      "Not reported",
    ]);
  });

  it("draws each finding facet as a ranked table under a Caption-size facet label", () => {
    reads();
    renderLandscape();
    const facet = screen.getByRole("heading", { level: 3, name: "Intervention type" });
    expect(facet).toHaveClass("text-caption");
    const table = screen.getByRole("table", { name: "Intervention type" });
    expect(within(table).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual([
      "Universal breakfast provision",
      "Active-travel offers",
      "Family support programmes",
      "Ungrouped",
    ]);
  });

  it("makes the years chart a listbox of years, with a hidden table beside it", () => {
    reads();
    renderLandscape();
    const years = screen.getByRole("listbox", { name: "Publication years" });
    expect(within(years).getAllByRole("option")).toHaveLength(6);
    const table = screen.getByRole("table", { name: "Publication years" });
    expect(within(table).getAllByRole("row")).toHaveLength(7);
  });

  it("shows the section frame with placeholder rows while loading, never animate-pulse", () => {
    reads({ pending: true });
    const { container } = renderLandscape();
    expect(screen.getByLabelText("Loading the landscape")).toHaveAttribute("aria-busy", "true");
    expect(container.querySelector(".animate-pulse")).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("LandscapeView — small counts become sentences", () => {
  it("one relevant source: a type sentence, a year sentence, the no-country sentence", () => {
    reads({
      landscape: {
        evidence_types: { "Systematic Review and Meta-Analysis": 1 },
        years: { "2024": 1 },
        themes: [],
        geographies: { "Not reported": 1 },
      },
      funnel: { found: 1, relevant: 1 },
      groups: undefined,
    });
    renderLandscape();
    expect(screen.getByText("1 source: Systematic review and meta-analysis.")).toBeInTheDocument();
    expect(screen.getByText("All from 2024.")).toBeInTheDocument();
    expect(screen.getByText("No publisher country was reported for these sources.")).toBeInTheDocument();
    expect(screen.queryByText(/The country of the publishing venue/)).toBeNull();
    expect(screen.queryByRole("table", { name: "Evidence types" })).toBeNull();
    expect(screen.queryByTestId("years-chart")).toBeNull();
    expect(screen.queryByTestId("landscape-population")).toBeNull();
    expect(within(screen.getByRole("region", { name: "Evidence types" })).queryByText("1 relevant source")).toBeNull();
  });
});

// Owner, round 8, and the landscape-polish rulings: while Classifying runs
// the evidence-type rows stand in their fixed order and fill in place.
describe("LandscapeView — while a run is live", () => {
  const live = (stage: "classify" | "acquire", status: "started" | "completed" = "started", run: "running" | "paused" = "running"): RunStreamState => ({
    ...createInitialRunStreamState(),
    run: { id: "r1", status: run, startedAt: "2026-11-05T10:00:00Z" },
    stages: [{ stage, label: "Classifying", status, startedAt: "2026-11-05T10:05:00Z", counts: [] }],
  });

  it("pulses a placeholder in every evidence-type row with no value, inside the chart's own rows", () => {
    streamState = live("classify");
    reads({ landscape: { ...mockLandscape, evidence_types: {} }, funnel: { found: 312, relevant: 118 } });
    renderLandscape();
    const table = screen.getByRole("table", { name: "Evidence types" });
    expect(table).toHaveAttribute("aria-busy", "true");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(9);
    expect(within(rows[0]).getByRole("rowheader")).toHaveTextContent("Systematic review and meta-analysis");
    expect(table.querySelectorAll(".placeholder-bar")).toHaveLength(9);
    expect(screen.getByTestId("classified-so-far")).toHaveTextContent("Classified so far: 0 of 118 relevant sources");
  });

  it("fills a landed type in place and keeps the other rows pending, in the same order", () => {
    streamState = live("classify");
    reads({
      landscape: { ...mockLandscape, evidence_types: { "Observational Research Studies": 12, "Qualitative & Contextual Evidence": 6 } },
      funnel: { found: 312, relevant: 118 },
    });
    renderLandscape();
    const table = screen.getByRole("table", { name: "Evidence types" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(9);
    expect(within(rows[2]).getByRole("rowheader")).toHaveTextContent("Observational research studies");
    expect(within(rows[2]).getByRole("cell")).toHaveTextContent("12");
    expect(table.querySelectorAll(".placeholder-bar")).toHaveLength(7);
    expect(screen.getByTestId("classified-so-far")).toHaveTextContent("Classified so far: 18 of 118 relevant sources");
  });

  it("drops the placeholders and the so-far line once Classifying has ended", () => {
    streamState = live("classify", "completed");
    reads({ landscape: { ...mockLandscape, evidence_types: REALISTIC_TYPES }, funnel: { found: 312, relevant: 118 } });
    renderLandscape();
    const table = screen.getByRole("table", { name: "Evidence types" });
    expect(table.querySelectorAll(".placeholder-bar")).toHaveLength(0);
    expect(table).not.toHaveAttribute("aria-busy");
    expect(screen.queryByTestId("classified-so-far")).toBeNull();
  });

  it("stands the funnel's six stages: done, the running one pulsing, the rest Grey", () => {
    streamState = live("classify");
    reads({ landscape: { ...mockLandscape, evidence_types: {} }, funnel: { found: 312, relevant: 118 } });
    renderLandscape();
    const table = screen.getByRole("table", { name: "From search to citation" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(6);
    expect(rows[2].querySelector(".placeholder-bar")).not.toBeNull();
    expect(rows[3]).toHaveAttribute("data-muted");
    expect(rows[3].querySelector(".placeholder-bar")).toBeNull();
  });

  it("pulses nothing while the run is paused, though the whole funnel stands", () => {
    streamState = live("classify", "started", "paused");
    reads({ landscape: { ...mockLandscape, evidence_types: {} }, funnel: { found: 312, relevant: 118 } });
    renderLandscape();
    expect(within(screen.getByRole("table", { name: "From search to citation" })).getAllByRole("row")).toHaveLength(6);
    expect(document.querySelectorAll(".placeholder-bar")).toHaveLength(0);
  });
});

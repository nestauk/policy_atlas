import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { beforeAll, describe, expect, it, vi } from "vitest";

import {
  EVIDENCE_TYPE_ORDER,
  evidenceTypeRows,
  facetRows,
  fewYearsSentence,
  funnelRows,
  geographyRows,
  LandscapeSection,
  onlyNotReported,
  population,
  PublicationYears,
  RankedBars,
  singleTypeSentence,
  yearAxis,
  yearTicks,
} from "./LandscapeViewCharts";
import { LandscapeSkeleton } from "./LandscapeViewSkeleton";

const labels = (rows: Array<{ label: string }>) => rows.map((row) => row.label);

describe("RankedBars — an accessible table", () => {
  it("is a named table with a row header and a value cell per row", () => {
    render(
      <RankedBars
        caption="Evidence types"
        rows={[
          { key: "a", label: "Observational Research Studies", count: 31 },
          { key: "b", label: "Modelling & Simulation", count: 0 },
        ]}
      />,
    );
    const table = screen.getByRole("table", { name: "Evidence types" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByRole("rowheader")).toHaveTextContent("Observational Research Studies");
    expect(within(rows[0]).getByRole("cell")).toHaveTextContent("31");
    // A zero reads "0" and draws no bar.
    expect(within(rows[1]).getByRole("cell")).toHaveTextContent("0");
    expect(within(rows[1]).queryByTestId("ranked-bar")).toBeNull();
  });

  it("sizes each bar against the largest value and keeps the bar out of the accessibility tree", () => {
    render(
      <RankedBars
        caption="Funnel"
        rows={[
          { key: "a", label: "Found", count: 312 },
          { key: "b", label: "Relevant", count: 78 },
        ]}
      />,
    );
    const bars = screen.getAllByTestId("ranked-bar");
    expect(bars[0]).toHaveAttribute("aria-hidden", "true");
    expect(bars[0].style.getPropertyValue("--share")).toBe("1");
    expect(bars[1].style.getPropertyValue("--share")).toBe("0.25");
  });

  it("breathes a placeholder in a pending row's bar cell and marks the table busy", () => {
    render(
      <RankedBars
        caption="Evidence types"
        busy
        rows={[
          { key: "a", label: "Systematic Review and Meta-Analysis", count: null, pending: true },
          { key: "b", label: "Observational Research Studies", count: 4 },
        ]}
      />,
    );
    const table = screen.getByRole("table", { name: "Evidence types" });
    expect(table).toHaveAttribute("aria-busy", "true");
    const [pendingRow] = within(table).getAllByRole("row");
    expect(within(pendingRow).getByRole("rowheader")).toHaveTextContent("Systematic Review and Meta-Analysis");
    expect(pendingRow.querySelector(".placeholder-bar")).toHaveAttribute("aria-hidden", "true");
  });

  it("fades in a value that replaces its breathing placeholder, and only that value", () => {
    const pendingRows = [
      { key: "a", label: "Systematic Review and Meta-Analysis", count: null, pending: true },
      { key: "b", label: "Observational Research Studies", count: 4 },
    ];
    const { rerender } = render(<RankedBars caption="Evidence types" busy rows={pendingRows} />);
    // At first paint nothing fades: the value already there holds still.
    expect(document.querySelectorAll(".anim-swap-in")).toHaveLength(0);
    rerender(
      <RankedBars
        caption="Evidence types"
        rows={[
          { key: "a", label: "Systematic Review and Meta-Analysis", count: 3, pending: false },
          { key: "b", label: "Observational Research Studies", count: 5 },
        ]}
      />,
    );
    const [landedRow, steadyRow] = screen.getAllByRole("row");
    expect(landedRow.querySelector(".ranked-bars__bar")).toHaveClass("anim-swap-in");
    expect(landedRow.querySelector(".ranked-bars__value")).toHaveClass("anim-swap-in");
    // A value that changed without a placeholder does not fade.
    expect(steadyRow.querySelector(".anim-swap-in")).toBeNull();
    // Nothing breathes with Tailwind's pulse.
    expect(document.querySelector(".animate-pulse")).toBeNull();
  });

  it("marks Grey rows and muted labels for the stylesheet", () => {
    render(
      <RankedBars
        caption="Geography"
        rows={[
          { key: "a", label: "Not reported", count: 3, tone: "grey" },
          { key: "b", label: "Cited", count: null, muted: true },
        ]}
      />,
    );
    const [grey, muted] = screen.getAllByRole("row");
    expect(grey).toHaveAttribute("data-tone", "grey");
    expect(muted).toHaveAttribute("data-muted");
  });
});

describe("funnelRows", () => {
  const funnel = { found: 312, relevant: 118, quality_checked: 90, read_in_full: 38, selected: 24, cited: 19 };

  it("counts sources only: Findings is not a funnel row", () => {
    const rows = funnelRows({ ...funnel, findings: 71 } as never, false, new Set());
    expect(labels(rows)).toEqual(["Found", "Relevant", "Quality-checked", "Full text", "Shortlisted", "Cited"]);
    expect(rows.map((row) => row.count)).toEqual([312, 118, 90, 38, 24, 19]);
  });

  it("leaves a stage with no count out when no run is live", () => {
    expect(labels(funnelRows({ found: 1, relevant: 1 }, false, new Set()))).toEqual(["Found", "Relevant"]);
  });

  it("stands all six stages while a run is live: done, running (pulsing) and to come (Grey)", () => {
    const rows = funnelRows({ found: 312, relevant: 118 }, true, new Set(["classify"]));
    expect(rows).toHaveLength(6);
    expect(rows[0]).toMatchObject({ label: "Found", count: 312 });
    expect(rows[2]).toMatchObject({ label: "Quality-checked", count: null, pending: true, muted: false });
    expect(rows[3]).toMatchObject({ label: "Full text", count: null, pending: false, muted: true });
  });

  it("pulses Full text while the run fetches the full texts and Shortlisted while it shortlists", () => {
    const fetching = funnelRows({ found: 312, relevant: 118, quality_checked: 90 }, true, new Set(["ingest"]));
    expect(fetching[3]).toMatchObject({ label: "Full text", pending: true });
    expect(fetching[4]).toMatchObject({ label: "Shortlisted", pending: false, muted: true });
    const shortlisting = funnelRows({ found: 312, relevant: 118, quality_checked: 90, read_in_full: 38 }, true, new Set(["select"]));
    expect(shortlisting[3]).toMatchObject({ label: "Full text", count: 38 });
    expect(shortlisting[4]).toMatchObject({ label: "Shortlisted", pending: true });
  });

  it("pulses nothing while the run is paused (no stage is running)", () => {
    const rows = funnelRows({ found: 312 }, true, new Set());
    expect(rows.filter((row) => row.pending)).toHaveLength(0);
  });
});

describe("evidenceTypeRows", () => {
  it("keeps the classifier's fixed order and shows the seven substantive types at zero", () => {
    const rows = evidenceTypeRows(
      { "Observational Research Studies": 31, "Systematic Review and Meta-Analysis": 4 },
      false,
    );
    // Shown in sentence case; the keys keep the classifier's labels.
    expect(rows.map((row) => row.key)).toEqual([...EVIDENCE_TYPE_ORDER]);
    expect(labels(rows)[0]).toBe("Systematic review and meta-analysis");
    expect(rows[0].count).toBe(4);
    expect(rows[1].count).toBe(0);
    expect(rows[2].count).toBe(31);
  });

  it("pins Other and Unknown last in Grey, only when non-zero", () => {
    const rows = evidenceTypeRows(
      { "Unknown / Insufficient information": 5, "Other (Non-evidence documents)": 0, "Modelling & Simulation": 9 },
      false,
    );
    expect(rows.at(-1)).toMatchObject({ label: "Unknown / insufficient information", count: 5, tone: "grey" });
    expect(labels(rows)).not.toContain("Other (non-evidence documents)");
  });

  it("puts a label outside the vocabulary after the substantive types, largest first", () => {
    const rows = evidenceTypeRows({ "local evaluation": 3, "Policy analysis": 12 }, false);
    expect(labels(rows).slice(7)).toEqual(["Policy analysis", "Local evaluation"]);
  });

  it("while classifying: every row stands, unclassified ones pending, a value in place", () => {
    const rows = evidenceTypeRows({ "RCTs and Quasi-Experimental Studies": 6 }, true);
    expect(rows).toHaveLength(9);
    expect(rows[0]).toMatchObject({ count: null, pending: true });
    expect(rows[1]).toMatchObject({ label: "RCTs and quasi-experimental studies", count: 6, pending: false });
    expect(rows.at(-1)).toMatchObject({ count: null, pending: true, tone: "grey" });
  });

  it("does not reorder rows as counts change", () => {
    const before = labels(evidenceTypeRows({ "Observational Research Studies": 2, "Modelling & Simulation": 9 }, true));
    const after = labels(evidenceTypeRows({ "Observational Research Studies": 20, "Modelling & Simulation": 9 }, true));
    expect(after).toEqual(before);
  });
});

describe("geographyRows", () => {
  it("pins Not reported last in Grey however large it is", () => {
    const rows = geographyRows({ "Not reported": 49, GB: 37, US: 12 });
    expect(labels(rows)).toEqual(["United Kingdom", "United States", "Not reported"]);
    expect(rows.at(-1)?.tone).toBe("grey");
  });

  it("folds the tail past twelve rows into one Grey 'Other countries (N)' row and keeps the sum", () => {
    const data: Record<string, number> = { "Not reported": 10 };
    for (let index = 0; index < 15; index += 1) data[`Country ${String(index).padStart(2, "0")}`] = 20 - index;
    const rows = geographyRows(data);
    expect(rows).toHaveLength(12);
    expect(rows.at(-2)).toMatchObject({ label: "Other countries (5)", tone: "grey" });
    expect(rows.at(-1)?.label).toBe("Not reported");
    const total = rows.reduce((sum, row) => sum + (row.count ?? 0), 0);
    expect(total).toBe(Object.values(data).reduce((sum, count) => sum + count, 0));
  });

  it("knows when no publisher country was reported at all", () => {
    expect(onlyNotReported({ "Not reported": 1 })).toBe(true);
    expect(onlyNotReported({ "Not reported": 1, GB: 1 })).toBe(false);
  });
});

describe("facetRows", () => {
  it("ranks the groups largest first and pins Ungrouped last in Grey", () => {
    const rows = facetRows(
      [
        { label: "Breakfast clubs", size: 9 },
        { label: "Universal free school meals", size: 14 },
      ],
      7,
    );
    expect(labels(rows)).toEqual(["Universal free school meals", "Breakfast clubs", "Ungrouped"]);
    expect(rows.at(-1)).toMatchObject({ count: 7, tone: "grey" });
  });
});

describe("small counts: a sentence in place of a one-bar chart", () => {
  it("names the one evidence type there is", () => {
    const rows = evidenceTypeRows({ "Systematic Review and Meta-Analysis": 1 }, false);
    expect(singleTypeSentence(rows)).toBe("1 source: Systematic review and meta-analysis.");
    expect(singleTypeSentence(evidenceTypeRows({ "Modelling & Simulation": 1, "Observational Research Studies": 2 }, false))).toBeNull();
  });

  it("says the year or the two years instead of drawing them", () => {
    expect(fewYearsSentence({ "2024": 1 })).toBe("All from 2024.");
    expect(fewYearsSentence({ "2023": 2, "2024": 1 })).toBe("From 2023 and 2024.");
    expect(fewYearsSentence({ "2022": 1, "2023": 2, "2024": 1 })).toBeNull();
  });

  it("words the headings' populations", () => {
    expect(population.withYear(112)).toBe("112 with a year");
    expect(population.findings(71)).toBe("71 findings");
    expect(population.classifiedSoFar(18, 118)).toBe("Classified so far: 18 of 118 relevant sources");
  });
});

describe("yearAxis", () => {
  it("steps the value axis in at most four round steps, the top at or above the largest year", () => {
    expect(yearAxis(1)).toEqual([0, 1]);
    expect(yearAxis(6)).toEqual([0, 2, 4, 6]);
    expect(yearAxis(10)).toEqual([0, 5, 10]);
    expect(yearAxis(37)).toEqual([0, 10, 20, 30, 40]);
    expect(yearAxis(90)).toEqual([0, 25, 50, 75, 100]);
  });
});

describe("yearTicks", () => {
  const range = (first: number, last: number) => Array.from({ length: last - first + 1 }, (_, i) => first + i);

  it("labels every year of a short span, 2024 included", () => {
    expect(yearTicks(range(2015, 2024), false)).toEqual(range(2015, 2024));
  });

  it("labels the multiples of 5 on a long span, plus a first year that stands clear", () => {
    expect(yearTicks(range(2006, 2025), false)).toEqual([2006, 2010, 2015, 2020, 2025]);
    expect(yearTicks(range(2009, 2025), false)).toEqual([2010, 2015, 2020, 2025]);
  });

  it("uses the multiples of 5 on a phone once the span passes six years", () => {
    expect(yearTicks(range(2015, 2024), true)).toEqual([2015, 2020]);
    expect(yearTicks(range(2020, 2024), true)).toEqual(range(2020, 2024));
  });
});

describe("PublicationYears", { timeout: 20_000 }, () => {
  // jsdom has no PointerEvent; a MouseEvent carries clientX and button.
  beforeAll(() => {
    if (typeof window.PointerEvent === "undefined") {
      class PointerEventPolyfill extends MouseEvent {
        pointerId: number;
        pointerType: string;
        constructor(type: string, init: PointerEventInit = {}) {
          super(type, init);
          this.pointerId = init.pointerId ?? 1;
          this.pointerType = init.pointerType ?? "mouse";
        }
      }
      (window as unknown as { PointerEvent: unknown }).PointerEvent = PointerEventPolyfill;
    }
  });

  const DATA = { "2015": 2, "2016": 0, "2017": 3, "2018": 4, "2019": 6, "2020": 1 };

  function renderYears(rangeHref?: (from: string, to: string) => string) {
    function Where() {
      return <p data-testid="where">{useLocation().pathname + useLocation().search}</p>;
    }
    render(
      <MemoryRouter initialEntries={["/landscape"]}>
        <PublicationYears data={DATA} caption="Publication years" rangeHref={rangeHref} />
        <Where />
      </MemoryRouter>,
    );
    const list = screen.queryByRole("listbox", { name: "Publication years" });
    if (list !== null) {
      // Six columns over 600 px: column i spans [100i, 100i + 100).
      vi.spyOn(list, "getBoundingClientRect").mockReturnValue({ left: 0, width: 600, top: 0, height: 200, right: 600, bottom: 200, x: 0, y: 0, toJSON: () => ({}) });
    }
    return list;
  }
  const href = (from: string, to: string) => `/all?year_from=${from}&year_to=${to}`;

  it("carries every year, zeros included, in a hidden table", () => {
    renderYears(href);
    const table = screen.getByRole("table", { name: "Publication years" });
    expect(table).toHaveClass("sr-only");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((row) => row.textContent)).toEqual(["20152", "20160", "20173", "20184", "20196", "20201"]);
  });

  it("is a horizontal listbox of the years, each named with its count, when it can choose", () => {
    const list = renderYears(href) as HTMLElement;
    expect(list).toHaveAttribute("aria-orientation", "horizontal");
    expect(list).toHaveAttribute("aria-multiselectable", "true");
    expect(list).toHaveAttribute("tabindex", "0");
    expect(within(list).getByRole("option", { name: "2019: 6 sources" })).toBeInTheDocument();
  });

  it("is a still picture, out of the accessibility tree, when it leads nowhere", () => {
    renderYears();
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("table", { name: "Publication years" })).toBeInTheDocument();
  });

  it("drags a range: the covered columns turn blue, the label says the range, release opens it", () => {
    const list = renderYears(href) as HTMLElement;
    fireEvent.pointerDown(list, { clientX: 150, button: 0, pointerId: 1 });
    fireEvent.pointerMove(list, { clientX: 350, pointerId: 1 });
    fireEvent.pointerMove(list, { clientX: 450, pointerId: 1 });
    const options = within(list).getAllByRole("option");
    expect(options.map((option) => option.hasAttribute("data-blue"))).toEqual([false, true, true, true, true, false]);
    expect(options.map((option) => option.getAttribute("aria-selected"))).toEqual(["false", "true", "true", "true", "true", "false"]);
    expect(screen.getByTestId("years-range-label")).toHaveTextContent("2016 to 2019");
    fireEvent.pointerUp(list, { clientX: 450, pointerId: 1 });
    expect(screen.getByTestId("where")).toHaveTextContent("/all?year_from=2016&year_to=2019");
  });

  it("drags right to left as well, and a click on one column opens that year", () => {
    const list = renderYears(href) as HTMLElement;
    fireEvent.pointerDown(list, { clientX: 450, button: 0 });
    fireEvent.pointerMove(list, { clientX: 250 });
    expect(screen.getByTestId("years-range-label")).toHaveTextContent("2017 to 2019");
    fireEvent.pointerCancel(list);
    expect(screen.queryByTestId("years-range-label")).toBeNull();
    fireEvent.pointerDown(list, { clientX: 520, button: 0 });
    fireEvent.pointerUp(list, { clientX: 520 });
    expect(screen.getByTestId("where")).toHaveTextContent("/all?year_from=2020&year_to=2020");
  });

  it("does not open a year, or a range, with no sources in it", () => {
    const list = renderYears(href) as HTMLElement;
    fireEvent.pointerDown(list, { clientX: 150, button: 0 });
    fireEvent.pointerUp(list, { clientX: 150 });
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/landscape$/);
  });

  it("from the keyboard: arrows move, Shift extends the range, Enter opens it, Escape drops it", async () => {
    const user = userEvent.setup();
    const list = renderYears(href) as HTMLElement;
    await user.tab();
    expect(list).toHaveFocus();
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(list.getAttribute("aria-activedescendant")).toBe(within(list).getAllByRole("option")[2].id);
    await user.keyboard("{Shift>}{ArrowRight}{ArrowRight}{/Shift}");
    expect(screen.getByTestId("years-range-label")).toHaveTextContent("2017 to 2019");
    const options = within(list).getAllByRole("option");
    expect(options[2]).toHaveAttribute("aria-selected", "true");
    expect(options[4]).toHaveAttribute("aria-selected", "true");
    expect(options[4]).toHaveAttribute("data-active");
    await user.keyboard("{Escape}");
    expect(screen.queryByTestId("years-range-label")).toBeNull();
    await user.keyboard("{Shift>}{ArrowLeft}{/Shift}{Enter}");
    expect(screen.getByTestId("where")).toHaveTextContent("/all?year_from=2018&year_to=2019");
  });

  it("opens the focused year alone with Enter when no range is held", async () => {
    const user = userEvent.setup();
    renderYears(href);
    await user.tab();
    await user.keyboard("{End}{Enter}");
    expect(screen.getByTestId("where")).toHaveTextContent("/all?year_from=2020&year_to=2020");
  });
});

describe("LandscapeSection", () => {
  it("is a region named by a real h2, with its population figure", () => {
    render(
      <LandscapeSection title="Evidence types" figure="118 relevant sources">
        <p>body</p>
      </LandscapeSection>,
    );
    const heading = screen.getByRole("heading", { level: 2, name: "Evidence types" });
    expect(screen.getByRole("region", { name: "Evidence types" })).toContainElement(heading);
    expect(screen.getByText("118 relevant sources")).toBeInTheDocument();
  });
});

describe("LandscapeSkeleton", () => {
  it("is busy, named, and holds the ranked-bar geometry with still-under-reduced-motion bars", () => {
    render(<LandscapeSkeleton />);
    const skeleton = screen.getByLabelText("Loading the landscape");
    expect(skeleton).toHaveAttribute("aria-busy", "true");
    expect(skeleton.querySelectorAll(".ranked-bars__row")).toHaveLength(8);
    expect(skeleton.querySelector(".animate-pulse")).toBeNull();
    expect(skeleton.querySelectorAll(".placeholder-bar").length).toBe(16);
  });
});

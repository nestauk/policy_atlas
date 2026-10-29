import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../../api/queries";
import { REPORT_BODY_CLASS, REPORT_LABEL_CLASS, REPORT_PART_HEADING_CLASS, REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import { FigureList } from "./Documents";
import { boxId, linkId, SHARED_DOC_TITLE, TASK_ID, tocEvidenceFixture, tocGraphFixture } from "./fixture";
import { TocResult } from "./TocResult";
import type { TocGraph } from "./types";

vi.mock("../../api/queries", () => ({ useTask: vi.fn(), useToc: vi.fn(), useTocEvidence: vi.fn(), useTocDocumentContext: vi.fn() }));

function renderResult(graph: TocGraph = tocGraphFixture()) {
  vi.mocked(queries.useTask).mockReturnValue({ data: { name: "Ads and obesity" } } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useToc).mockReturnValue({ data: graph, isPending: false } as unknown as ReturnType<typeof queries.useToc>);
  vi.mocked(queries.useTocEvidence).mockReturnValue({ data: tocEvidenceFixture() } as unknown as ReturnType<typeof queries.useTocEvidence>);
  vi.mocked(queries.useTocDocumentContext).mockReturnValue({
    isPending: false,
    isError: false,
    data: { context: "Before. Exposure fell by about half. After.", clamped: false, span_start: 0, span_end: 10 },
  } as unknown as ReturnType<typeof queries.useTocDocumentContext>);
  return render(
    <MemoryRouter>
      <TocResult taskId={TASK_ID} />
    </MemoryRouter>,
  );
}

const node = (n: number) => document.querySelector(`[data-id="${boxId(n)}"]`) as HTMLElement;
const edge = (n: number) => document.querySelector(`[data-testid="rf__edge-${linkId(n)}"]`);

beforeEach(() => vi.clearAllMocks());

describe("canvas", () => {
  it("renders neutral boxes with no grade colour", () => {
    renderResult();
    expect(screen.getAllByText(/Ban on less healthy food ads/).length).toBeGreaterThan(0);
    const box = node(1).firstElementChild as HTMLElement;
    expect(box.className).toContain("border-grey/40");
    expect(box.className).not.toMatch(/grade/);
  });

  it("styles each edge by its verdict: solid, two-tone, dashed, dotted", () => {
    renderResult();
    expect(edge(1)?.querySelector(".toc-edge--confident")).not.toBeNull();
    // Mixed is two-tone: the amber underlay and the green dash on top.
    expect(edge(5)?.querySelector(".toc-edge--not_sure_mixed")).not.toBeNull();
    expect(edge(5)?.querySelector(".toc-edge-under")).not.toBeNull();
    expect(edge(1)?.querySelector(".toc-edge-under")).toBeNull();
    expect(edge(2)?.querySelector(".toc-edge--not_sure_insufficient")).not.toBeNull();
    expect(edge(7)?.querySelector(".toc-edge--not_confident")).not.toBeNull();
    expect(edge(9)?.querySelector(".toc-edge--pending")).not.toBeNull(); // still checking
  });

  it("marks the critical connection with a warning triangle, not a thicker line", () => {
    renderResult();
    // The mark is the edge's only <g transform>: one on the critical edge, none elsewhere.
    expect(document.querySelectorAll(".react-flow__edge g[transform]")).toHaveLength(1);
    expect(edge(3)?.querySelector("g[transform]")).not.toBeNull();
    expect(document.querySelector(".toc-edge--critical")).toBeNull();
  });

  it("keys the four line styles and the critical connection's mark", () => {
    renderResult();
    const key = screen.getByRole("list", { name: "Line key" });
    for (const label of ["Confident", "Not sure: mixed", "Not sure: too little evidence", "Not confident: evidence against"]) {
      expect(within(key).getByText(label)).toBeInTheDocument();
    }
    expect(within(key).getByText(/Critical connection/)).toBeInTheDocument();
  });

  it("shows each box's code and the accountability ceiling", () => {
    renderResult();
    expect(within(node(7)).getByText("L1")).toBeInTheDocument();
    expect(screen.getByText("Directly influenced")).toBeInTheDocument();
    expect(screen.getByText("Contributes to")).toBeInTheDocument();
    // Both dividers run edge to edge of the view and never take a click meant for a box or a connection.
    expect(screen.getByTestId("toc-line")).toHaveClass("inset-x-0", "pointer-events-none");
    expect(screen.getByTestId("toc-ceiling")).toHaveClass("inset-y-0", "pointer-events-none");
  });

  it("hover text gives the verdict", () => {
    renderResult();
    expect(edge(4)?.querySelector("title")?.textContent).toBe("Confident");
    expect(edge(3)?.querySelector("title")?.textContent).toBe("Critical connection · test this first. Not sure: mixed");
  });
});

describe("reading guide", () => {
  it("opens and closes", async () => {
    const user = userEvent.setup();
    renderResult();
    expect(screen.queryByLabelText("How to read this")).toBeNull();
    await user.click(screen.getByRole("button", { name: "How to read this" }));
    const guide = screen.getByLabelText("How to read this");
    expect(within(guide).getByText(/neither clearly supports nor refutes/)).toBeInTheDocument();
    expect(within(guide).getByText(/Rules in force since January 2026/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "How to read this" }));
    expect(screen.queryByLabelText("How to read this")).toBeNull();
  });
});

describe("detail panel", () => {
  const openLink = (n: number) => {
    fireEvent.click((edge(n) as Element).querySelector("path") as Element); // d3-zoom needs a real window for mouse-down
    return screen.getByRole("complementary", { name: "Details" });
  };

  it("leads with the title and its verdict, then how it works, then the evidence in order", () => {
    renderResult();
    const panel = openLink(3);
    const heading = (text: string) => (_: string, el: Element | null) => el?.tagName === "P" && el.textContent === text;
    expect(within(panel).getByText(heading("Critical connection #3 · P1 → S1 · test this first"))).toBeInTheDocument();
    const title = within(panel).getByRole("heading", { level: 3 });
    expect(title.textContent).toBe("Link 3 title");
    // The verdict right under the title: the dot and the label.
    const verdict = within(panel).getByTestId("link-verdict");
    expect(title.nextElementSibling).toBe(verdict);
    expect(verdict.textContent).toBe("Not sure: mixed");
    // Section order: How this works (clauses, then Conditions); Evidence (size, balance, sentence, documents).
    const text = panel.textContent ?? "";
    const order = [
      "How this works",
      "because",
      "Conditions",
      "Evidence",
      "Size of change",
      "Evidence balance: Not sure: mixed",
      "brands moved to brand-only adverts",
      "Documents (3)",
    ].map((part) => text.indexOf(part, text.indexOf("How this works")));
    expect(order.every((index) => index >= 0)).toBe(true);
    expect([...order].sort((x, y) => x - y)).toEqual(order);
    expect(within(panel).queryByText(/Worked elsewhere|Holds here/)).toBeNull();
  });

  it("shows each figure's statement, quote and source, and groups same-measure figures as a range", () => {
    renderResult();
    const panel = openLink(3);
    expect(within(panel).getAllByTestId("figure-group")).toHaveLength(2);
    expect(within(panel).getByText("Evidence suggests 44 to 58% fewer adverts for less healthy food seen by children (2 studies)")).toBeInTheDocument();
    expect(within(panel).getByText("Children saw 44% fewer adverts for less healthy food after the rules.").className).toContain("font-semibold");
    expect(within(panel).getByText("odds ratio 1·05 (0·99 to 1·12)")).toBeInTheDocument();
    expect(within(panel).getAllByText(/^Smith et al\. · Obesity Reviews · 2020 · quasi-experiment/).length).toBe(3);
    expect(within(panel).queryByText("Figures come from the documents' abstracts.")).toBeNull();
  });

  it("numbers the sentence's citations as the document list does, and opens them in the citation sidebar", async () => {
    const user = userEvent.setup();
    renderResult();
    const panel = openLink(3);
    // The list, heaviest first: [1] the London study, [2] the brand study, [3] Chile.
    const listed = within(panel)
      .getAllByRole("listitem")
      .map((item) => item.textContent ?? "")
      .filter((item) => item.includes("quality"));
    expect(listed[0]).toContain(`[1]${SHARED_DOC_TITLE}`);
    expect(listed[2]).toContain("[3]Children's exposure after Chile's Law 20.606");
    const marker = within(panel).getByRole("button", { name: "Citations 1, 3" });
    expect(marker.className).toContain("citation-marker");
    await user.click(marker);
    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("Where this comes from")).toBeInTheDocument();
    expect(within(sheet).getByText(/brands moved to brand-only adverts/)).toBeInTheDocument();
    expect(within(sheet).getByText(SHARED_DOC_TITLE)).toBeInTheDocument();
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, expect.stringContaining("0000e0002"), null);
  });

  it("gives each figure a marker that opens its own quote in context", async () => {
    const user = userEvent.setup();
    renderResult();
    const panel = openLink(3);
    // Figure 2 comes from the London study, number 1.
    const [marker] = within(panel).getAllByRole("button", { name: "Citations 1" });
    await user.click(marker as HTMLElement);
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, expect.stringContaining("0000e0002"), "Exposure fell 58% after the rules.");
  });

  it("opens for a box: description, how we'd know, then one Evidence section: seen-in note, size of change, case studies", async () => {
    const user = userEvent.setup();
    renderResult();
    fireEvent.click(node(7));
    const panel = screen.getByRole("complementary", { name: "Details" });
    expect(within(panel).getByText((_, el) => el?.tagName === "P" && el.textContent === "Long-term outcome L1")).toBeInTheDocument();
    const text = panel.textContent ?? "";
    const order = ["described in a short paragraph", "How we'd know it happened", "Definition", "Indicator", "Timing", "Evidence", "Seen on London transport", "Size of change", "Case studies (1)", "[1]Transport for London advertising restriction"].map((part) =>
      text.indexOf(part),
    );
    expect(order.every((index) => index >= 0)).toBe(true);
    expect([...order].sort((x, y) => x - y)).toEqual(order);
    expect(within(panel).queryByText("Result criteria")).toBeNull();
    expect(within(panel).queryByText("Indicators used")).toBeNull();
    // A case study's source names its authors or publisher and year, not "Academic".
    expect(within(panel).getByText((_, el) => el?.tagName === "P" && (el.textContent ?? "").startsWith("Transport for London · 2022 · "))).toBeInTheDocument();
    expect(within(panel).queryByText(/^Academic/)).toBeNull();
    // The seen-in note's citation opens the case study's quote in context.
    const seenIn = within(panel).getByText(/Seen on London transport/);
    await user.click(within(seenIn).getByRole("button", { name: "Citations 1" }));
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, "00000000-0000-4000-8000-0000000e0009", "Calories bought fell by about 7%.");
  });
});

describe("detailed information", () => {
  const SECTIONS = ["Summary", "How change happens", "Assumptions and evidence", "What to test and measure", "Sources"];

  it("is the five-section report, in the report's four text styles only", () => {
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    expect(within(info).getByRole("heading", { level: 2 }).className).toBe(REPORT_PART_HEADING_CLASS);
    const sections = within(info).getAllByRole("heading", { level: 3 });
    expect(sections.map((h) => h.textContent)).toEqual(SECTIONS);
    for (const heading of sections) expect(heading.className).toContain(REPORT_SECTION_HEADING_CLASS);
    // Every text element uses one of the four styles (body, label, part or section heading);
    // metadata lines (the scope) are the body style in grey.
    const greyBody = REPORT_BODY_CLASS.replace("text-ink", "text-grey");
    const styles = [REPORT_BODY_CLASS, greyBody, REPORT_LABEL_CLASS, REPORT_PART_HEADING_CLASS, REPORT_SECTION_HEADING_CLASS];
    for (const el of info.querySelectorAll("p, ul, table, th, h2, h3")) {
      const own = el.className;
      const inherited = (el.closest("table") as HTMLElement | null)?.className ?? "";
      expect(styles.some((style) => own.includes(style) || inherited.includes(style))).toBe(true);
    }
    expect(within(info).getByText("Goal:")).toBeInTheDocument();
    expect([...info.querySelectorAll("i")].map((el) => el.textContent)).toEqual(["If", "then", "because"]);
    expect(within(info).getByText(/Population: children under 18 in England · Time horizon: five years · Directly influenced: up to outputs/)).toBeInTheDocument();
    expect(within(info).getByText("Weakest critical links.")).toBeInTheDocument();
    expect(within(info).getByText("Fewer adverts, less snacking.")).toBeInTheDocument();
    // Tables scroll sideways on a narrow screen.
    expect(info.querySelectorAll(".overflow-x-auto table")).toHaveLength(2);
    // No method paragraph under the sources.
    expect(within(info).queryByText(/'Too little evidence' means none was found/)).toBeNull();
  });

  it("selects a link or box on the canvas from a code in the text", async () => {
    const user = userEvent.setup();
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    await user.click(within(info).getAllByRole("button", { name: "Show #3 on the canvas" })[0] as HTMLElement);
    const panel = screen.getByRole("complementary", { name: "Details" });
    expect(within(panel).getByText(/Critical connection/)).toBeInTheDocument();
    await user.click(within(info).getAllByRole("button", { name: "Show S1 on the canvas" })[0] as HTMLElement);
    expect(within(screen.getByRole("complementary", { name: "Details" })).getByText("Children see fewer ads for less healthy food")).toBeInTheDocument();
  });

  it("opens each [n] in the citation sidebar, as the Evidence search does", async () => {
    const user = userEvent.setup();
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    const [marker] = within(info).getAllByRole("button", { name: "Citations 3" });
    expect(marker?.className).toContain("citation-marker");
    await user.click(marker as HTMLElement);
    expect(within(screen.getByRole("dialog")).getByText("Where this comes from")).toBeInTheDocument();
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, "00000000-0000-4000-8000-0000000e0003", null);
    // The source list reads as the Evidence search's references: number, title, then authors, year and venue.
    expect(info.querySelector("#toc-source-3")?.textContent).toBe("[3]Source 3 — Ann Smith, Bo Lee (2020) · Obesity Reviews");
  });

  it("lists the set-aside pathways in one line each, at the end of How change happens", () => {
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    const label = within(info).getByText("Considered and set aside");
    expect(label.className).toBe(`mt-4 ${REPORT_LABEL_CLASS}`);
    expect(within(info).getByText(/Merged into pathway 1/)).toBeInTheDocument();
  });

  it("prints whole: nothing is collapsed, and the button prints", async () => {
    const user = userEvent.setup();
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    expect(info.querySelectorAll('details, [aria-expanded="false"]')).toHaveLength(0);
    await user.click(within(info).getByRole("button", { name: "Download as PDF" }));
    expect(print).toHaveBeenCalled();
  });

  it("says when the report is not written yet", () => {
    renderResult(tocGraphFixture({ report: null }));
    expect(screen.getByText("The report is written when the evidence check finishes.")).toBeInTheDocument();
  });
});

describe("detail panel documents", () => {
  it("shows authors and opens the quote in context from a document title", async () => {
    const user = userEvent.setup();
    renderResult();
    fireEvent.click((edge(3) as Element).querySelector("path") as Element);
    const panel = screen.getByRole("complementary", { name: "Details" });
    expect(within(panel).getAllByText(/^Smith et al\. · 20\d\d · quasi-experiment/).length).toBeGreaterThan(0);
    await user.click(within(panel).getByRole("button", { name: "Children's exposure after Chile's Law 20.606" }));
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, expect.stringContaining("0000e"), null);
    expect(screen.getByText("Where this comes from")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the source" })).toHaveAttribute("href", expect.stringContaining("example.org"));
  });
});

describe("header", () => {
  it("says the check is running while it runs", () => {
    renderResult(tocGraphFixture({ check_status: "checking" }));
    expect(screen.getByText(/checking each step against the evidence/)).toBeInTheDocument();
  });

  it("shows the report's title and summary, or the task's name before a report", () => {
    const { unmount } = renderResult();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Food advert limits and childhood obesity");
    expect(screen.getByText(/whether children see fewer adverts overall is the weakest step/).className).toContain(REPORT_BODY_CLASS);
    expect(screen.queryByText("About this theory")).toBeNull();
    unmount();
    renderResult(tocGraphFixture({ report: null }));
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Ads and obesity");
  });
});

describe("figures", () => {
  it("shows three groups, then offers all the figures", async () => {
    const user = userEvent.setup();
    const [base] = tocEvidenceFixture().links[0]?.figures ?? [];
    const figures = ["a", "b", "c", "d"].map((measure, i) => ({ ...base!, figure_id: `f${i}`, measure }));
    render(<FigureList taskId={TASK_ID} figures={figures} citationOf={() => null} />);
    expect(screen.getAllByTestId("figure-group")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "Show all 4 figures" }));
    expect(screen.getAllByTestId("figure-group")).toHaveLength(4);
    expect(screen.queryByRole("button", { name: /Show all/ })).toBeNull();
  });
});

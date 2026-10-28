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

vi.mock("../../api/queries", () => ({ useToc: vi.fn(), useTocEvidence: vi.fn(), useTocDocumentContext: vi.fn() }));

function renderResult(graph: TocGraph = tocGraphFixture()) {
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

  it("draws the critical connection thicker, and nothing else", () => {
    renderResult();
    expect(document.querySelectorAll(".toc-edge--critical")).toHaveLength(1);
    expect(edge(3)?.querySelector(".toc-edge--critical")).not.toBeNull();
    expect(edge(3)?.querySelector(".toc-edge-under--critical")).not.toBeNull();
  });

  it("keys the four line styles and the thicker critical line", () => {
    renderResult();
    const key = screen.getByRole("list", { name: "Line key" });
    for (const label of ["Confident", "Not sure: mixed", "Not sure: too little evidence", "Not confident: evidence against"]) {
      expect(within(key).getByText(label)).toBeInTheDocument();
    }
    expect(within(key).getByText(/critical connection/)).toBeInTheDocument();
  });

  it("shows each box's code and the accountability ceiling", () => {
    renderResult();
    expect(within(node(7)).getByText("L1")).toBeInTheDocument();
    expect(screen.getByText("Directly influenced")).toBeInTheDocument();
    expect(screen.getByText("Contributes to")).toBeInTheDocument();
    // Display only: the ceiling never takes a click meant for a box or a connection.
    const ceiling = document.querySelector('[data-id="ceiling"]') as HTMLElement;
    expect(ceiling.style.pointerEvents).toBe("none");
  });

  it("hover text gives the verdict", () => {
    renderResult();
    expect(edge(4)?.querySelector("title")?.textContent).toBe("Confident");
    expect(edge(3)?.querySelector("title")?.textContent).toBe("Critical connection · test this first. Not sure: mixed · close to the threshold");
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
  it("shows the verdict, the balance and each document's support, quality and relevance", () => {
    renderResult();
    // Open the critical link from the panel: click its edge.
    const target = edge(3) as Element;
    fireEvent.click(target.querySelector("path") as Element); // d3-zoom needs a real window for mouse-down
    const panel = screen.getByRole("complementary", { name: "Details" });
    const heading = (text: string) => (_: string, el: Element | null) => el?.tagName === "P" && el.textContent === text;
    expect(within(panel).getByText(heading("Critical connection #3 · P1 → S1 · test this first"))).toBeInTheDocument();
    expect(within(panel).getByText("Not sure: mixed")).toBeInTheDocument();
    expect(within(panel).getByText(/brands moved to brand-only adverts/)).toBeInTheDocument();
    expect(within(panel).getByText("Close to the threshold: one more study could change this verdict.")).toBeInTheDocument();
    // The balance: one refuting block, two strongly supporting ones, heights by weight.
    const blocks = (support: string) => within(within(panel).getByTestId(`balance-${support}`)).queryAllByTestId("balance-block");
    expect(blocks("refutes")).toHaveLength(1);
    expect(blocks("mixed")).toHaveLength(0);
    expect(blocks("weak")).toHaveLength(0);
    expect(blocks("strong").map((block) => block.style.height)).toEqual(["27px", "9px"]); // weights 0.667 and 0.222
    // Documents, heaviest first, with their chips.
    expect(within(panel).getByText("Documents (3)")).toBeInTheDocument();
    const titles = within(panel).getAllByRole("button", { name: /Chile|Transport for London/ }).map((b) => b.textContent);
    expect(titles[0]).toBe(SHARED_DOC_TITLE);
    expect(within(panel).getByText("Strongly supports · quality 2 · relevance 3 · London, so it applies in England")).toBeInTheDocument();
    expect(within(panel).queryByText(/Worked elsewhere|Holds here/)).toBeNull();
    // Size of change: the grouped range, each quote and its source line, and the note.
    expect(within(panel).getByText("Size of change")).toBeInTheDocument();
    expect(within(panel).getAllByTestId("figure-group")).toHaveLength(2);
    expect(within(panel).getByText("Evidence suggests 44 to 58% fewer adverts for less healthy food seen by children (2 studies)")).toBeInTheDocument();
    expect(within(panel).getByText("odds ratio 1·05 (0·99 to 1·12)")).toBeInTheDocument();
    expect(within(panel).getAllByText("Smith, Jones · Obesity Reviews · 2020 · quasi-experiment").length).toBe(3);
    expect(within(panel).getByText("Figures come from the documents' abstracts.")).toBeInTheDocument();
  });

  it("opens for a box", () => {
    renderResult();
    fireEvent.click(node(7));
    const panel = screen.getByRole("complementary", { name: "Details" });
    expect(within(panel).getByText("Definition of: Households buy fewer calories from less healthy food")).toBeInTheDocument();
    expect(within(panel).getByText(/Case studies \(1\)/)).toBeInTheDocument();
    expect(within(panel).getByText((_, el) => el?.tagName === "P" && el.textContent === "Long-term outcome L1")).toBeInTheDocument();
    // Figures: a level of this box, reported by one of its links' documents.
    expect(within(panel).getByText("Figures")).toBeInTheDocument();
    expect(within(panel).getByText("140 kcal excess calories a day eaten by children")).toBeInTheDocument();
    expect(within(panel).getByText("children overall eat 140 excess kcal per day")).toBeInTheDocument();
    expect(within(panel).getByText(/Public Health England · 2020 · government evidence review/)).toBeInTheDocument();
  });
});

describe("detailed information", () => {
  const SECTIONS = ["Summary", "How change happens", "Assumptions and evidence", "What to test and measure", "Sources and method"];

  it("is the five-section report, in the report's four text styles only", () => {
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    expect(within(info).getByRole("heading", { level: 2 }).className).toBe(REPORT_PART_HEADING_CLASS);
    const sections = within(info).getAllByRole("heading", { level: 3 });
    expect(sections.map((h) => h.textContent)).toEqual(SECTIONS);
    for (const heading of sections) expect(heading.className).toContain(REPORT_SECTION_HEADING_CLASS);
    // Every text element uses one of the four styles (body, label, part or section heading);
    // metadata lines (the scope, the method) are the body style in grey.
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
    expect(within(info).getByText(/'Too little evidence' means none was found/)).toBeInTheDocument();
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

  it("links each [n] to its source in the list", () => {
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    const [marker] = within(info).getAllByRole("link", { name: "[3]" });
    expect(marker).toHaveAttribute("href", "#toc-source-3");
    expect(info.querySelector("#toc-source-3")?.textContent).toContain("Food brand advertising after Chile's restrictions");
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
    expect(within(panel).getAllByText(/Smith, Jones · 20\d\d · quasi-experiment/).length).toBeGreaterThan(0);
    await user.click(within(panel).getByRole("button", { name: "Children's exposure after Chile's Law 20.606" }));
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, expect.stringContaining("0000e"));
    expect(screen.getByText("Where this comes from")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the source" })).toHaveAttribute("href", expect.stringContaining("example.org"));
  });
});

describe("header", () => {
  it("says the check is running while it runs", () => {
    renderResult(tocGraphFixture({ check_status: "checking" }));
    expect(screen.getByText(/checking each step against the evidence/)).toBeInTheDocument();
  });

  it("leaves the summary paragraphs to the report", () => {
    renderResult();
    expect(screen.queryByText("About this theory")).toBeNull();
    expect(screen.queryByText("What the evidence says")).toBeNull();
  });
});

describe("figures", () => {
  it("shows three groups, then offers all the figures", async () => {
    const user = userEvent.setup();
    const [base] = tocEvidenceFixture().links[0]?.figures ?? [];
    const figures = ["a", "b", "c", "d"].map((measure, i) => ({ ...base!, figure_id: `f${i}`, measure }));
    render(<FigureList figures={figures} />);
    expect(screen.getAllByTestId("figure-group")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "Show all 4 figures" }));
    expect(screen.getAllByTestId("figure-group")).toHaveLength(4);
    expect(screen.queryByRole("button", { name: /Show all/ })).toBeNull();
  });
});

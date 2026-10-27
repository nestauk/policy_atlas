import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../../api/queries";
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

  it("colours each edge by its lower grade and dashes weak ones", () => {
    renderResult();
    expect(edge(1)?.querySelector(".toc-edge--medium")).not.toBeNull(); // strong / medium
    expect(edge(3)?.querySelector(".toc-edge--weak")).not.toBeNull(); // medium / weak
    expect(edge(2)?.querySelector(".toc-edge--none")).not.toBeNull(); // weak / none
    expect(edge(9)?.querySelector(".toc-edge--pending")).not.toBeNull(); // still checking
  });

  it("carries exactly one critical dot", () => {
    renderResult();
    expect(screen.getAllByTestId("toc-critical-dot")).toHaveLength(1);
  });

  it("hover text gives both grades", () => {
    renderResult();
    expect(edge(4)?.querySelector("title")?.textContent).toBe("Strong evidence it worked elsewhere · Weak evidence it holds here");
  });
});

describe("reading guide", () => {
  it("opens and closes", async () => {
    const user = userEvent.setup();
    renderResult();
    expect(screen.queryByLabelText("How to read this")).toBeNull();
    await user.click(screen.getByRole("button", { name: "How to read this" }));
    const guide = screen.getByLabelText("How to read this");
    expect(within(guide).getByText(/Two or more good studies|two or more good studies/)).toBeInTheDocument();
    expect(within(guide).getByText(/Rules in force since January 2026/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "How to read this" }));
    expect(screen.queryByLabelText("How to read this")).toBeNull();
  });
});

describe("detail panel", () => {
  it("shows both questions and lists a shared document once", () => {
    renderResult();
    // Open the critical link from the panel: click its edge.
    const target = edge(3) as Element;
    fireEvent.click(target.querySelector("path") as Element); // d3-zoom needs a real window for mouse-down
    const panel = screen.getByRole("complementary", { name: "Details" });
    expect(within(panel).getByText("Critical connection · test this first")).toBeInTheDocument();
    expect(within(panel).getByLabelText("Worked elsewhere")).toBeInTheDocument();
    expect(within(panel).getByLabelText("Holds here")).toBeInTheDocument();
    // Listed in full once, plus the one-line "Also counts here" reference.
    expect(within(panel).getAllByRole("button", { name: SHARED_DOC_TITLE })).toHaveLength(2);
    expect(within(panel).getAllByText(/Also counts here:/)).toHaveLength(1);
    expect(within(panel).getByText("This is England, so it counts here.")).toBeInTheDocument();
  });

  it("opens for a box", () => {
    renderResult();
    fireEvent.click(node(7));
    const panel = screen.getByRole("complementary", { name: "Details" });
    expect(within(panel).getByText("Definition of: Households buy fewer calories from less healthy food")).toBeInTheDocument();
    expect(within(panel).getByText(/Case studies \(1\)/)).toBeInTheDocument();
  });
});

describe("detailed information", () => {
  it("expands a pathway, writes one paragraph for a merged link and opens documents from +", async () => {
    const user = userEvent.setup();
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    // Pathway 1 starts open; pathway 2 (with the merged link) starts closed.
    expect(within(info).getByText("Link 3 says the step works.")).toBeInTheDocument();
    expect(within(info).queryByText("Link 6 says the step works.")).toBeNull();
    await user.click(within(info).getByRole("button", { name: /Pathway 2/ }));
    expect(within(info).getByText("Link 6 says the step works.")).toBeInTheDocument();
    expect(within(info).getAllByText("Medium evidence, including here.")).toHaveLength(1);
    // The "+" after the elsewhere sentence of the critical link lists its documents.
    expect(within(info).queryByText("Exposure fell by about half.")).toBeNull();
    await user.click(within(info).getAllByRole("button", { name: /Show the 2 documents/ })[0] as HTMLElement);
    expect(within(info).getByText("Exposure fell by about half.")).toBeInTheDocument();
    expect(within(info).getAllByText("Critical connection · test this first").length).toBeGreaterThan(0);
  });

  it("shows authors and opens the quote in context from a document title", async () => {
    const user = userEvent.setup();
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    await user.click(within(info).getAllByRole("button", { name: /Show the 2 documents/ })[0] as HTMLElement);
    expect(within(info).getAllByText(/Smith, Jones · 20\d\d · quasi-experiment/).length).toBeGreaterThan(0);
    await user.click(within(info).getByRole("button", { name: "Children's exposure after Chile's Law 20.606" }));
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, expect.stringContaining("0000e"), "elsewhere");
    expect(screen.getByText("Where this comes from")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the source" })).toHaveAttribute("href", expect.stringContaining("example.org"));
  });

  it("lists every condition under Assumptions in its type group", async () => {
    const user = userEvent.setup();
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    await user.click(within(info).getByRole("button", { name: /Assumptions/ }));
    const labels = ["Delivery", "Take-up", "Behaviour change", "Benefits and side effects", "If it goes wrong"];
    for (const label of labels) expect(within(info).getByText(label)).toBeInTheDocument();
    for (let n = 1; n <= 9; n += 1) {
      if (n === 3 || n === 4) continue; // these two carry their own wording
      expect(within(info).getByText(`Condition for link ${n}`)).toBeInTheDocument();
    }
    expect(within(info).getByText("Brands do not move their spend to brand-only ads, sponsorship and influencers")).toBeInTheDocument();
    // Take-up holds link 3 (critical) and link 6.
    const takeUp = within(info).getByText("Take-up").parentElement as HTMLElement;
    expect(within(takeUp).getByText("Condition for link 6")).toBeInTheDocument();
    expect(within(takeUp).getByText(/Critical connection · test this first/)).toBeInTheDocument();
  });

  it("lists the set-aside pathways and the evaluation questions", async () => {
    const user = userEvent.setup();
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    await user.click(within(info).getByRole("button", { name: /Considered and set aside/ }));
    expect(within(info).getByText(/Merged into pathway 1/)).toBeInTheDocument();
    await user.click(within(info).getByRole("button", { name: /Questions for an evaluation/ }));
    expect(within(info).getByText("Are the calories cut made up from other food?")).toBeInTheDocument();
  });
});

describe("header", () => {
  it("says the check is running while it runs", () => {
    renderResult(tocGraphFixture({ check_status: "checking" }));
    expect(screen.getByText(/checking each step against the evidence/)).toBeInTheDocument();
    expect(screen.queryByText("About this theory")).toBeNull();
  });

  it("shows both summary paragraphs once checked", () => {
    renderResult();
    expect(screen.getByText("About this theory")).toBeInTheDocument();
    expect(screen.getByText("What the evidence says")).toBeInTheDocument();
  });
});

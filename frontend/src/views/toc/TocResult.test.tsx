import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../../api/queries";
import { ToastProvider } from "../../ui/radix/Toast";
import { TooltipProvider } from "../../ui/radix/Tooltip";
import { REPORT_BODY_CLASS, REPORT_LABEL_CLASS, REPORT_PART_HEADING_CLASS, REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import { forgetReportExpand } from "../ArtefactOutline";
import { setAsideLine } from "./DetailedInformation";
import { FigureList } from "./Documents";
import { boxId, link, linkId, SHARED_DOC_TITLE, TASK_ID, tocEvidenceFixture, tocGraphFixture } from "./fixture";
import { TocResult } from "./TocResult";
import type { TocGraph } from "./types";

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(),
  useToc: vi.fn(),
  useTocEvidence: vi.fn(),
  useTocDocumentContext: vi.fn(),
  useTocHistory: vi.fn(() => ({ data: [{ event_id: "e1", at: "2026-10-30T11:20:00Z", who: "Ada", what: "Edited S1: text", undoable: true }] })),
  useTocProposals: vi.fn(() => ({ data: [], refetch: vi.fn() })),
  // Task 054's 058 alignment: the facts line counts what was found; a
  // citation's marks and a source's dossier read the shared dossier.
  useFunnel: vi.fn(() => ({ data: { found: 412 } })),
  useSourceDossier: vi.fn(() => ({ data: undefined, isPending: false, isLoading: false, isError: false })),
  useEvidence: vi.fn(() => ({ data: undefined, isPending: false })),
  useFindings: vi.fn(() => ({ data: undefined, isPending: false })),
  useSourceRecords: vi.fn(() => ({ data: undefined, isPending: false })),
}));
const mutate = vi.fn();
// The canvas picture cannot be made in jsdom: a download of it fails.
vi.mock("html-to-image", () => ({
  toPng: vi.fn(() => Promise.reject(new Error("no canvas"))),
  toSvg: vi.fn(() => Promise.reject(new Error("no canvas"))),
}));
vi.mock("../../api/mutations", () => ({ useTocEdit: vi.fn(() => ({ mutate, isPending: false })) }));

function renderResult(graph: TocGraph = tocGraphFixture(), evidence = tocEvidenceFixture()) {
  vi.mocked(queries.useTask).mockReturnValue({ data: { name: "Ads and obesity" } } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(queries.useToc).mockReturnValue({ data: graph, isPending: false } as unknown as ReturnType<typeof queries.useToc>);
  vi.mocked(queries.useTocEvidence).mockReturnValue({ data: evidence } as unknown as ReturnType<typeof queries.useTocEvidence>);
  vi.mocked(queries.useTocDocumentContext).mockReturnValue({
    isPending: false,
    isError: false,
    data: { context: "Before. Exposure fell by about half. After.", clamped: false, span_start: 0, span_end: 10 },
  } as unknown as ReturnType<typeof queries.useTocDocumentContext>);
  return render(
    <MemoryRouter>
      <ToastProvider>
        <TooltipProvider delayDuration={0}>
          <TocResult taskId={TASK_ID} />
        </TooltipProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

const node = (n: number) => document.querySelector(`[data-id="${boxId(n)}"]`) as HTMLElement;
const edge = (n: number) => document.querySelector(`[data-testid="rf__edge-${linkId(n)}"]`);

beforeEach(() => {
  vi.clearAllMocks();
  // The report's expand state is remembered per task: each test opens it fresh.
  forgetReportExpand(TASK_ID);
});

describe("canvas", () => {
  it("renders neutral boxes with no grade colour", () => {
    renderResult();
    expect(screen.getAllByText(/Ban on less healthy food ads/).length).toBeGreaterThan(0);
    const box = node(1).firstElementChild as HTMLElement;
    // The cards' hairline and paper weight; the rounded corners stay (owner).
    expect(box.className).toContain("border-line-2");
    expect(box.className).toContain("shadow-paper");
    expect(box.className).toContain("rounded-lg");
    expect(box.className).not.toMatch(/grade/);
  });

  it("styles each edge by its verdict: solid, dashed, dotted", () => {
    renderResult();
    expect(edge(1)?.querySelector(".toc-edge--supported")).not.toBeNull();
    // Mixed is one solid amber line (owner, 2026-11-04).
    expect(edge(5)?.querySelector(".toc-edge--not_sure_mixed")).not.toBeNull();
    expect(edge(5)?.querySelectorAll("path")).toHaveLength(edge(1)?.querySelectorAll("path").length ?? 0);
    expect(edge(2)?.querySelector(".toc-edge--not_sure_insufficient")).not.toBeNull();
    expect(edge(7)?.querySelector(".toc-edge--against")).not.toBeNull();
    expect(edge(9)?.querySelector(".toc-edge--pending")).not.toBeNull(); // still checking
  });

  it("draws a connection being checked in the unchecked grey, its arrowhead too, with a travelling dot (owner, 2026-11-10)", () => {
    renderResult();
    const pending = edge(9)?.querySelector(".toc-edge--pending");
    expect(pending?.getAttribute("marker-end")).toContain("color-line-2");
    expect(pending?.getAttribute("marker-end")).not.toContain("color-blue");
    expect(edge(9)?.querySelector('[data-testid="toc-edge-dot"]')).not.toBeNull();
    expect(edge(1)?.querySelector('[data-testid="toc-edge-dot"]')).toBeNull();
  });

  it("marks the critical connection with a warning triangle, not a thicker line", () => {
    renderResult();
    // The mark is the edge's only <g transform>: one on the critical edge, none elsewhere.
    expect(document.querySelectorAll(".react-flow__edge g[transform]")).toHaveLength(1);
    expect(edge(3)?.querySelector("g[transform]")).not.toBeNull();
    expect(document.querySelector(".toc-edge--critical")).toBeNull();
  });

  it("keys the six line styles and the critical connection's mark", () => {
    renderResult();
    const key = screen.getByRole("list", { name: "Line key" });
    for (const label of ["Supported", "Leaning supports", "Mixed", "Leaning against", "Evidence against", "Not enough evidence"]) {
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

  it("puts a blue halo under the selected connection only", () => {
    renderResult();
    expect(document.querySelector('[data-testid="toc-edge-halo"]')).toBeNull();
    fireEvent.click((edge(3) as Element).querySelector("path") as Element);
    expect(document.querySelectorAll('[data-testid="toc-edge-halo"]')).toHaveLength(1);
    expect(edge(3)?.querySelector('[data-testid="toc-edge-halo"]')).not.toBeNull();
  });

  it("hover text gives the verdict", () => {
    renderResult();
    expect(edge(4)?.querySelector("title")?.textContent).toBe("Supported");
    expect(edge(3)?.querySelector("title")?.textContent).toBe("Critical connection. Mixed");
  });
});

describe("reading guide", () => {
  it("opens and closes", async () => {
    const user = userEvent.setup();
    renderResult();
    expect(screen.queryByLabelText("How to read this")).toBeNull();
    // It lives in the canvas bar's "…" menu (round 5).
    await user.click(screen.getByLabelText("More actions"));
    await user.click(screen.getByRole("menuitem", { name: "How to read this" }));
    const guide = screen.getByLabelText("How to read this");
    expect(within(guide).getByText(/neither clearly supports nor refutes/)).toBeInTheDocument();
    // Context and supporting activities are in the report, not here (owner, 2026-11-04).
    expect(within(guide).queryByText(/Rules in force since January 2026/)).toBeNull();
    await user.click(screen.getByLabelText("More actions"));
    await user.click(screen.getByRole("menuitem", { name: "Hide how to read this" }));
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
    expect(within(panel).getByText(heading("Critical connection #3 · P1 → S1"))).toBeInTheDocument();
    const title = within(panel).getByRole("heading", { level: 3 });
    expect(title.textContent).toBe("Link 3 title");
    // The verdict right under the title: the dot and the label.
    const verdict = within(panel).getByTestId("link-verdict");
    expect(title.nextElementSibling).toBe(verdict);
    expect(verdict.textContent).toBe("Mixed");
    // Section order: How this works (clauses, then Conditions); Evidence (balance, sentence, size, documents).
    const text = panel.textContent ?? "";
    const order = [
      "How this works",
      "because",
      "Conditions",
      "Evidence",
      "Evidence balance: Mixed",
      "brands moved to brand-only adverts",
      "Size of change",
      "Documents (3)",
    ].map((part) => text.indexOf(part, text.indexOf("How this works")));
    expect(order.every((index) => index >= 0)).toBe(true);
    expect([...order].sort((x, y) => x - y)).toEqual(order);
    expect(within(panel).queryByText(/Worked elsewhere|Holds here/)).toBeNull();
  });

  it("shows a balance block's document on hover, as the document list shows it", async () => {
    const user = userEvent.setup();
    renderResult();
    const panel = openLink(3);
    const [block] = within(panel).getAllByTestId("balance-block");
    await user.hover(block as HTMLElement);
    expect((await screen.findByRole("tooltip")).textContent).toContain("quality");
  });

  it("opens a balance block's document in the citation sidebar on click", async () => {
    const user = userEvent.setup();
    renderResult();
    const panel = openLink(3);
    await user.click(within(panel).getAllByTestId("balance-block")[0] as HTMLElement);
    expect(within(screen.getByRole("dialog")).getByText("Evidence for this claim")).toBeInTheDocument();
  });

  it("says what makes a connection critical on hover", async () => {
    const user = userEvent.setup();
    renderResult();
    const panel = openLink(3);
    await user.hover(within(panel).getByText("Critical connection"));
    expect((await screen.findByRole("tooltip")).textContent).toContain("weakest evidence");
  });

  it("shows each figure's statement, quote and source, and groups same-measure figures as a range", () => {
    renderResult();
    const panel = openLink(3);
    expect(within(panel).getAllByTestId("figure-group")).toHaveLength(2);
    expect(within(panel).getByText("Evidence suggests 44 to 58% fewer adverts for less healthy food seen by children (2 studies)")).toBeInTheDocument();
    expect(within(panel).getByText("Children saw 44% fewer adverts for less healthy food after the rules.").className).toContain("font-semibold");
    expect(within(panel).getByText("odds ratio 1·05 (0·99 to 1·12)")).toBeInTheDocument();
    expect(within(panel).getAllByText(/^Smith, Jones · Obesity Reviews · 2020 · Quasi-experiment/).length).toBe(3);
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
    expect(within(sheet).getByText("Evidence for this claim")).toBeInTheDocument();
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
  const SECTIONS = ["Summary", "Pathways", "How it could fail", "What to test first", "How it could be expanded", "Supporting activities", "Assumptions", "References"];
  /** A reader opening a finished report finds its sections shut (058's expand state). */
  const openAll = async (user: ReturnType<typeof userEvent.setup>) => user.click(screen.getByRole("button", { name: "Show all" }));

  it("bullets its lists with the report's square, as the other capabilities do (owner, 2026-11-10)", async () => {
    const user = userEvent.setup();
    renderResult();
    await user.click(screen.getByRole("button", { name: "Show all" }));
    const info = screen.getByLabelText("Detailed information");
    expect(info.querySelector(".list-disc")).toBeNull();
    const supporting = within(info).getByText(/Ofcom monitors compliance/).closest("li") as HTMLElement;
    expect(supporting.querySelector("[data-bullet]")).not.toBeNull();
    const expansion = within(info).getByText("Brands move spend to influencers.").closest("li") as HTMLElement;
    expect(expansion.querySelector("[data-bullet]")).not.toBeNull();
    const condition = within(info).getByText("Brands do not move their spend to brand-only ads").closest("li") as HTMLElement;
    expect(condition.querySelector("[data-bullet]")).not.toBeNull();
  });

  it("sets the contents inside the paper beside the narrative; the canvas and the Assumptions table keep the full width (owner, 2026-11-10)", () => {
    renderResult();
    const paper = screen.getByRole("main");
    // Not beside the paper, as the Evidence search's are: inside it.
    for (const nav of screen.getAllByRole("navigation", { name: "Contents" })) expect(paper).toContainElement(nav);
    const beside = screen
      .getAllByRole("navigation", { name: "Contents" })
      .map((nav) => nav.parentElement as HTMLElement)
      .find((el) => el.querySelector("#toc-summary") !== null) as HTMLElement;
    expect(beside.querySelector("#toc-routes")).not.toBeNull();
    expect(beside.querySelector("#toc-assumptions")).toBeNull();
    expect(beside.querySelector("#references")).toBeNull();
    expect(beside).not.toContainElement(document.getElementById("toc-canvas"));
  });

  it("is the report in the shared page: h2 sections in today's order, the contents, the report's text styles (A14)", async () => {
    const user = userEvent.setup();
    renderResult();
    const info = screen.getByLabelText("Detailed information");
    // The sections are the page's h2s, each a disclosure, shut for a fresh reader.
    const sections = within(info).getAllByRole("heading", { level: 2 });
    expect(sections.map((h) => h.textContent?.replace(/(Show|Hide)$/, ""))).toEqual(SECTIONS);
    for (const heading of sections) expect(heading.className).toContain(REPORT_SECTION_HEADING_CLASS);
    expect(within(info).queryByText(/This report asks whether the ban/)).toBeNull();
    // The contents list the same sections (inside the paper from md up, a disclosure on a phone).
    const contents = screen.getAllByRole("navigation", { name: "Contents" });
    expect(contents.length).toBeGreaterThan(0);
    expect(within(contents[0] as HTMLElement).getByText("Assumptions")).toBeInTheDocument();
    await openAll(user);
    // Every text element uses the report's styles; metadata lines are the body style in grey.
    const greyBody = REPORT_BODY_CLASS.replace("text-ink", "text-grey");
    const styles = [REPORT_BODY_CLASS, greyBody, REPORT_LABEL_CLASS, REPORT_PART_HEADING_CLASS, REPORT_SECTION_HEADING_CLASS];
    for (const el of info.querySelectorAll("p, ul, table, th, h2")) {
      // The contents beside the narrative are the page's chrome, not its text.
      if (el.closest("nav") !== null) continue;
      const own = el.className;
      const inherited = (el.closest("table") as HTMLElement | null)?.className ?? "";
      expect(styles.some((style) => own.includes(style) || inherited.includes(style))).toBe(true);
    }
    // The Summary: context, question, claim (If / then / because in bold), then the verdict and why.
    expect(within(info).queryByText("Goal:")).toBeNull();
    expect(within(info).getByText(/This report asks whether the ban/)).toBeInTheDocument();
    expect([...info.querySelectorAll("p > b")].map((el) => el.textContent)).toEqual(expect.arrayContaining(["If", "then", "because", "Verdict: Too little evidence."]));
    // Above the canvas: the verdict, the goal (the report's question), then the evidence in brief.
    expect(screen.queryByText("children under 18 in England · five years")).toBeNull();
    expect(screen.getAllByText(/This report asks whether the ban/)).toHaveLength(2);
    expect(within(info).getByText(/Find out whether children see fewer/)).toBeInTheDocument();
    // The table scrolls sideways on a narrow screen; What to test is a list, not a table.
    expect(info.querySelectorAll(".overflow-x-auto table")).toHaveLength(1);
    // The table keeps all its columns, Sources included (§ 8).
    expect(within(info).getAllByRole("columnheader").map((th) => th.textContent?.replace(/[↕▲▼]/g, "").trim())).toEqual([
      "Code",
      "Assumption (connection)",
      "Conditions",
      "Importance",
      "Evidence",
      "Why",
      "Sources",
    ]);
    // No method paragraph under the sources; the References footer stays (§ 8).
    expect(within(info).queryByText(/'Too little evidence' means none was found/)).toBeNull();
    expect(within(info).getByText(/These are the documents the report cites/)).toBeInTheDocument();
  });

  it("heads the page with the kind row, the title, the date and the facts line (A14)", () => {
    renderResult();
    expect(screen.getByText("Report")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Food advert limits and childhood obesity");
    // Sources cited out of those found, and the years they were published.
    const facts = screen.getAllByText("Sources").map((el) => el.closest("dl")).find((dl) => dl !== null) as HTMLElement;
    expect(facts).toHaveTextContent("Sources3 cited out of 412 found");
    expect(facts).toHaveTextContent("Published2020");
    expect(within(facts).getByRole("link", { name: "3 cited out of 412 found" })).toHaveAttribute("href", "#references");
  });

  it("selects a link or box on the canvas from a code in the text", async () => {
    const user = userEvent.setup();
    renderResult();
    await openAll(user);
    const info = screen.getByLabelText("Detailed information");
    await user.click(within(info).getAllByRole("button", { name: "Show #3 on the canvas" })[0] as HTMLElement);
    const panel = screen.getByRole("complementary", { name: "Details" });
    expect(within(panel).getByText(/Critical connection/)).toBeInTheDocument();
    await user.click(within(info).getAllByRole("button", { name: "Show S1 on the canvas" })[0] as HTMLElement);
    expect(within(screen.getByRole("complementary", { name: "Details" })).getByText("Children see fewer ads for less healthy food")).toBeInTheDocument();
  });

  it("opens each [n] in the shared citation sheet, and lists the shared References (A15)", async () => {
    const user = userEvent.setup();
    renderResult();
    await openAll(user);
    const info = screen.getByLabelText("Detailed information");
    const [marker] = within(info).getAllByRole("button", { name: "Citations 3" });
    expect(marker?.className).toContain("citation-marker");
    await user.click(marker as HTMLElement);
    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("Evidence for this claim")).toBeInTheDocument();
    expect(within(sheet).queryByRole("link", { name: "Open the source" })).toBeNull();
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, "00000000-0000-4000-8000-0000000e0003", null);
    // The source's marks come from its dossier, by its document row.
    expect(queries.useSourceDossier).toHaveBeenCalledWith(TASK_ID, expect.stringMatching(/^[0-9a-f-]{36}$/));
    await user.keyboard("{Escape}");
    // The References read as the Evidence search's: number, then the citation form.
    const references = screen.getByRole("region", { name: "References" });
    expect(within(references).getByRole("button", { name: "Source 3: Source 3" })).toBeInTheDocument();
    expect(references).toHaveTextContent("Smith A, Lee B (2020).");
  });

  it("opens a source's dossier from the sheet, with Back to the claim (A15)", async () => {
    const user = userEvent.setup();
    renderResult();
    fireEvent.click((edge(3) as Element).querySelector("path") as Element);
    const panel = screen.getByRole("complementary", { name: "Details" });
    await user.click(within(panel).getByRole("button", { name: "Children's exposure after Chile's Law 20.606" }));
    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("Evidence for this claim")).toBeInTheDocument();
    expect(within(sheet).queryByRole("link", { name: "Open the source" })).toBeNull();
    await user.click(within(sheet).getByRole("button", { name: "Children's exposure after Chile's Law 20.606" }));
    await user.click(screen.getByRole("button", { name: "Back to the claim" }));
    expect(screen.getByText("Evidence for this claim")).toBeInTheDocument();
  });

  it("names each set-aside pathway, then who set it aside and why (§ 8), with no control", async () => {
    const user = userEvent.setup();
    renderResult();
    await openAll(user);
    const info = screen.getByLabelText("Detailed information");
    const [item] = within(info).getAllByTestId("set-aside-pathway");
    expect(within(item as HTMLElement).getByRole("heading", { level: 3 }).textContent).toBe("Children ask parents less");
    expect(within(item as HTMLElement).getByText("Set aside by Policy Atlas · Merged into pathway 1, because it is the same step as healthier choices.")).toBeInTheDocument();
    expect(within(item as HTMLElement).queryByRole("button")).toBeNull();
    expect(within(info).queryByText("Considered and set aside:")).toBeNull();
  });

  it("counts a set-aside pathway's thin connections in its line (§ 8)", () => {
    const links = [
      { link_id: "a", verdict: "not_sure_insufficient", state: "checked" },
      { link_id: "b", verdict: "supported", state: "checked" },
      { link_id: "c", verdict: "not_sure_insufficient", state: "checked" },
      { link_id: "d", verdict: "not_sure_mixed", state: "checked" },
    ] as const;
    expect(setAsideLine({ link_ids: ["a", "b", "c", "d"], reason: "Over the limit." }, links)).toBe(
      "Set aside by Policy Atlas · Too little evidence for 2 of its 4 connections.",
    );
    expect(setAsideLine({ link_ids: ["b", "d"], reason: "Over the limit of 4 success pathways." }, links)).toBe(
      "Set aside by Policy Atlas · Over the limit of 4 success pathways.",
    );
    expect(setAsideLine({ link_ids: ["a"], reason: null }, links)).toBe("Set aside by Policy Atlas · Too little evidence for 1 of its 1 connection.");
    expect(setAsideLine({ link_ids: [], reason: null }, links)).toBe("Set aside by Policy Atlas.");
  });

  it("selects a pathway on the canvas from its name, with its strength", async () => {
    const user = userEvent.setup();
    renderResult();
    await openAll(user);
    const info = screen.getByLabelText("Detailed information");
    const item = within(info).getByRole("button", { name: "Show the pathway Fewer adverts, less snacking on the canvas" }).closest("h3") as HTMLElement;
    expect(item).toHaveTextContent("Mixed");
    await user.click(within(item).getByRole("button", { name: /Show the pathway/ }));
    expect(screen.getByRole("combobox", { name: /pathway/i })).toHaveTextContent(/^Pathway 1 ·/);
  });

  it("shows the first five rows, the rest on a click, and collapses again", async () => {
    const user = userEvent.setup();
    const fixture = tocGraphFixture();
    const report = fixture.report as NonNullable<TocGraph["report"]>;
    const base = report.assumptions[0] as (typeof report.assumptions)[number];
    const more = [4, 6, 7, 8].map((n) => ({ ...base, code: `#${n}`, flag: false }));
    renderResult({ ...fixture, report: { ...report, assumptions: [...report.assumptions, ...more] } });
    await openAll(user);
    const row = screen.getAllByRole("row", { hidden: true }).find((item) => item.textContent?.startsWith("#8")) as HTMLElement;
    expect(row).toHaveClass("hidden");
    await user.click(screen.getByRole("button", { name: "Show all 6 connections" }));
    expect(row).not.toHaveClass("hidden");
    // "Show all 6 connections" / "Hide": the one disclosure vocabulary.
    await user.click(within(screen.getByRole("table").parentElement as HTMLElement).getByRole("button", { name: "Hide" }));
    expect(row).toHaveClass("hidden");
  });

  it("sorts the assumptions table and flags central, weak rows", async () => {
    const user = userEvent.setup();
    renderResult();
    await openAll(user);
    const table = screen.getByRole("table");
    const codes = () => [...table.querySelectorAll("tbody tr td:first-child")].map((cell) => cell.textContent?.replace("⚠", ""));
    expect(codes()).toEqual(["#3", "#5"]);
    expect(within(table).getByRole("img", { name: "Central and weakly evidenced" })).toBeInTheDocument();
    // The shared sortable header (moved from the Sources view): its arrow, no ▲▼↕ glyphs.
    expect(table.textContent).not.toMatch(/[▲▼↕⚠]/);
    expect(within(table).getAllByTestId("sort-arrow")).toHaveLength(3);
    await user.click(within(table).getByRole("button", { name: "Sort by evidence" }));
    expect(codes()).toEqual(["#3", "#5"]);
    await user.click(within(table).getByRole("button", { name: "Sort by evidence" }));
    expect(codes()).toEqual(["#5", "#3"]);
  });

  it("opens whole with Show all, and Download sits in the kind row and prints (A14)", async () => {
    const user = userEvent.setup();
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    renderResult();
    await openAll(user);
    const info = screen.getByLabelText("Detailed information");
    expect(info.querySelectorAll('details, [aria-expanded="false"]')).toHaveLength(0);
    // Not in the canvas bar any more.
    expect(within(document.getElementById("toc-canvas") as HTMLElement).queryByRole("button", { name: "Download" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Download" }));
    expect(within(screen.getAllByRole("menu").at(-1) as HTMLElement).getAllByRole("menuitem").map((item) => item.firstChild?.textContent)).toEqual(["Report (PDF)", "Image (PNG)", "Image (SVG)", "Diagram file (draw.io)", "References (CSV)", "Theory (JSON)"]);
    await user.click(screen.getByRole("menuitem", { name: /Report \(PDF\)/ }));
    await waitFor(() => expect(print).toHaveBeenCalled());
  });

  it("says so in an error toast when a download cannot be made", async () => {
    const user = userEvent.setup();
    const alert = vi.spyOn(window, "alert").mockImplementation(() => undefined);
    renderResult();
    await user.click(screen.getByRole("button", { name: "Download" }));
    await user.click(screen.getByRole("menuitem", { name: /Image \(PNG\)/ }));
    expect(await screen.findByText("The download could not be made. Try again.")).toBeInTheDocument();
    expect(alert).not.toHaveBeenCalled();
  });

  it("links back to the plan on the report's action line, as Evidence search does", async () => {
    const user = userEvent.setup();
    renderResult();
    const header = screen.getByRole("heading", { level: 1 }).closest("header") as HTMLElement;
    await user.click(within(header).getByRole("button", { name: "See the plan" }));
  });

  it("offers no Download before the report is committed", () => {
    renderResult(tocGraphFixture({ report: null }));
    expect(screen.queryByRole("button", { name: "Download" })).toBeNull();
  });

  it("leads with the overall verdict and its headline, beside a rule in its tone", () => {
    const fixture = tocGraphFixture();
    const report = fixture.report as NonNullable<TocGraph["report"]>;
    renderResult({ ...fixture, report: { ...report, verdict: { ...(report.verdict as NonNullable<typeof report.verdict>), mechanism: "implausible", label: "Implausible", headline: "Implausible: blue doors would not credibly reduce diabetes." } } });
    const line = screen.getByText("Implausible.").closest("p") as HTMLElement;
    expect(line).toHaveTextContent("Implausible. Blue doors would not credibly reduce diabetes.");
    expect(within(line).getByTestId("verdict-rule")).toHaveAttribute("data-tone", "red");
    // The rule replaces the square (owner, 2026-11-10).
    expect(within(line).queryByTestId("verdict-mark")).toBeNull();
  });

  it("asks the user to review an uploaded theory, with its suggested connections dashed", async () => {
    const user = userEvent.setup();
    const base = tocGraphFixture({ can_edit: true, check_status: "drafted" });
    renderResult({ ...base, links: base.links.map((item, i) => ({ ...item, origin: i === 0 ? "drafted" : "imported" })) });
    expect(screen.getByText(/This is how Policy Atlas read your diagram/)).toBeInTheDocument();
    expect((edge(1) as Element).querySelector(".toc-edge--suggested")).not.toBeNull();
    expect((edge(2) as Element).querySelector(".toc-edge--suggested")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Check the evidence" }));
    expect(mutate.mock.calls.at(-1)?.[0]).toEqual({ kind: "checkFull" });
  });

  it("shows nothing under the canvas before writing starts (§ 8)", () => {
    renderResult(tocGraphFixture({ report: null, check_status: "checking" }));
    expect(screen.queryByLabelText("Detailed information")).toBeNull();
    expect(screen.queryByText(/The report is written when/)).toBeNull();
    expect(screen.queryByText(/The report's sections are set out/)).toBeNull();
  });
});

describe("detail panel documents", () => {
  it("shows authors and opens the quote in context from a document title", async () => {
    const user = userEvent.setup();
    renderResult();
    fireEvent.click((edge(3) as Element).querySelector("path") as Element);
    const panel = screen.getByRole("complementary", { name: "Details" });
    expect(within(panel).getAllByText(/^Smith, Jones · 20\d\d · Quasi-experiment/).length).toBeGreaterThan(0);
    await user.click(within(panel).getByRole("button", { name: "Children's exposure after Chile's Law 20.606" }));
    expect(queries.useTocDocumentContext).toHaveBeenCalledWith(TASK_ID, expect.stringContaining("0000e"), null);
    expect(screen.getByText("Evidence for this claim")).toBeInTheDocument();
  });
});

describe("header", () => {
  it("says nothing of its own while the check runs: the run status bar says it (§ 8)", () => {
    renderResult(tocGraphFixture({ check_status: "checking" }));
    expect(screen.queryByText(/checking each step against the evidence/)).toBeNull();
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
    const toggle = screen.getByRole("button", { name: "Show all 4 figures" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(screen.getAllByTestId("figure-group")).toHaveLength(4);
    expect(screen.queryByRole("button", { name: /Show all/ })).toBeNull();
    // The one disclosure vocabulary: "Show all N figures" / "Hide".
    await user.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.getAllByTestId("figure-group")).toHaveLength(3);
  });
});

describe("editing (C41, C47, C40)", () => {
  const editable = (extra: Partial<TocGraph> = {}) => tocGraphFixture({ can_edit: true, ...extra });
  const panel = () => screen.getByRole("complementary", { name: "Details" });
  const lastEdit = () => mutate.mock.calls.at(-1)?.[0];

  it("shows no editing controls to a reader", () => {
    renderResult();
    expect(screen.queryByRole("button", { name: /Add box/ })).toBeNull();
    fireEvent.click(node(1));
    expect(within(panel()).queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByText(/^History/)).toBeNull();
  });

  it("adds a box from the toolbar", async () => {
    const user = userEvent.setup();
    renderResult(editable());
    await user.click(screen.getByRole("button", { name: /Add box/ }));
    const form = screen.getByRole("form", { name: "Add a box" });
    await user.type(within(form).getByLabelText("What changes"), "Parents set limits on screen time");
    await user.click(within(form).getByRole("button", { name: "Add" }));
    expect(lastEdit()).toEqual({ kind: "createBox", body: { layer: "outcome_short", text: "Parents set limits on screen time" } });
  });

  it("edits a box in its sidebar with the revision it showed", async () => {
    const user = userEvent.setup();
    renderResult(editable());
    fireEvent.click(node(5));
    await user.click(within(panel()).getByRole("button", { name: "Edit" }));
    const text = within(panel()).getByLabelText("Text");
    await user.clear(text);
    await user.type(text, "Children see fewer adverts overall");
    // A text change warns that its connections' evidence was for the earlier wording.
    expect(within(panel()).getByText(/evidence from the earlier wording/)).toBeInTheDocument();
    await user.click(within(panel()).getByRole("button", { name: "Save" }));
    expect(lastEdit()).toMatchObject({ kind: "patchBox", boxId: boxId(5), body: { expected_revision: 1, text: "Children see fewer adverts overall" } });
  });

  it("asks before deleting a box, naming its connections", async () => {
    const user = userEvent.setup();
    renderResult(editable());
    fireEvent.click(node(5));
    await user.click(within(panel()).getByRole("button", { name: "Edit" }));
    await user.click(within(panel()).getByRole("button", { name: "Delete box" }));
    expect(within(panel()).getByText(/Also deletes its \d+ connections/)).toBeInTheDocument();
    await user.click(within(panel()).getByRole("button", { name: "Delete" }));
    expect(lastEdit()).toEqual({ kind: "deleteBox", boxId: boxId(5), revision: 1 });
  });

  it("connects two boxes in Connect mode", async () => {
    const user = userEvent.setup();
    renderResult(editable());
    await user.click(screen.getByRole("button", { name: "Connect" }));
    expect(screen.getByText(/Click the box the connection starts from/)).toBeInTheDocument();
    fireEvent.click(node(3));
    expect(screen.getByText(/Click the box it leads to/)).toBeInTheDocument();
    fireEvent.click(node(8));
    expect(lastEdit()).toEqual({ kind: "createLink", body: { source_box_id: boxId(3), target_box_id: boxId(8) } });
  });

  it("offers Find evidence for a connection no check has judged, alone or with the others", async () => {
    const user = userEvent.setup();
    const added = link(20, 3, 8, "Short-term to impact", "not_sure_insufficient", { state: "unchecked", origin: "user", title: null, sentence: "If a, then b." });
    renderResult(editable({ links: [...tocGraphFixture().links, added] }));
    await user.click(screen.getByLabelText("More actions"));
    expect(screen.getByRole("menuitem", { name: "Find evidence for new connections (1)" })).toBeInTheDocument();
    fireEvent.click((edge(20) as Element).querySelector("path") as Element);
    expect(within(panel()).getByText("Needs evidence")).toBeInTheDocument();
    await user.click(within(panel()).getByRole("button", { name: "Find evidence" }));
    expect(lastEdit()).toEqual({ kind: "check", body: { link_ids: [linkId(20)], mode: "new_items" } });
  });

  it("marks a connection critical; History lives in the History tab", async () => {
    const user = userEvent.setup();
    renderResult(editable());
    fireEvent.click((edge(4) as Element).querySelector("path") as Element);
    await user.click(within(panel()).getByRole("button", { name: "Mark as critical" }));
    expect(lastEdit()).toEqual({ kind: "patchLink", linkId: linkId(4), body: { expected_revision: 1, critical: true } });
    expect(screen.queryByText(/^History/)).toBeNull();
  });
});


describe("editing the evidence (C42, C43)", () => {
  const editable = (extra: Partial<TocGraph> = {}) => tocGraphFixture({ can_edit: true, ...extra });
  const panel = () => screen.getByRole("complementary", { name: "Details" });
  const lastEdit = () => mutate.mock.calls.at(-1)?.[0];
  const openLink = (n: number) => fireEvent.click((edge(n) as Element).querySelector("path") as Element);

  it("sets the user's scores on a document, keeping the judge's in view", async () => {
    const user = userEvent.setup();
    renderResult(editable());
    openLink(3);
    await user.click(within(panel()).getAllByRole("button", { name: "Change" })[0] as HTMLElement);
    const menu = within(panel()).getByRole("group", { name: "Change this document" });
    expect(within(menu).getByText(/^Judge said:/)).toBeInTheDocument();
    await user.click(within(menu).getByRole("combobox", { name: "Support" }));
    await user.click(screen.getByRole("option", { name: "Refutes" }));
    await user.click(within(within(menu).getByRole("group", { name: "Relevance" })).getByRole("button", { name: "3" }));
    await user.click(within(menu).getByRole("button", { name: "Save" }));
    expect(lastEdit()).toMatchObject({ kind: "evidence", body: { action: "score", support: "refutes", relevance: 3, expected_revision: 1 } });
  });

  it("removes a document, and lists a removed one greyed with Restore", async () => {
    const user = userEvent.setup();
    const evidence = tocEvidenceFixture();
    const onLink3 = evidence.links.find((entry) => entry.link_id === linkId(3));
    if (onLink3?.documents[0] !== undefined) onLink3.documents[0] = { ...onLink3.documents[0], removed_by: "Ada" };
    renderResult(editable(), evidence);
    openLink(3);
    expect(within(panel()).getByText("Removed (1)")).toBeInTheDocument();
    await user.click(within(panel()).getByRole("button", { name: "Restore" }));
    expect(lastEdit()).toMatchObject({ kind: "evidence", body: { action: "restore" } });
    await user.click(within(panel()).getAllByRole("button", { name: "Change" })[0] as HTMLElement);
    // The colleague's words, in the quiet control (owner, 2026-11-09).
    await user.click(within(panel()).getByRole("button", { name: "Remove" }));
    expect(lastEdit()).toMatchObject({ kind: "evidence", body: { action: "remove" } });
  });

  it("adds a study by its DOI", async () => {
    const user = userEvent.setup();
    renderResult(editable());
    openLink(3);
    await user.type(within(panel()).getByLabelText("DOI"), "10.1016/j.appet.2016.02.017");
    await user.click(within(panel()).getByRole("button", { name: "Add" }));
    expect(lastEdit()).toEqual({ kind: "addStudy", linkId: linkId(3), body: { identifier: "10.1016/j.appet.2016.02.017" } });
  });

  it("offers Keep the evidence or Check again after an edit", async () => {
    const user = userEvent.setup();
    const links = tocGraphFixture().links.map((item) => (item.link_id === linkId(3) ? { ...item, state: "pending" as const } : item));
    renderResult(editable({ links }));
    openLink(3);
    expect(within(panel()).getByText("Evidence from the earlier wording")).toBeInTheDocument();
    await user.click(within(panel()).getByRole("button", { name: "Keep the evidence" }));
    expect(lastEdit()).toEqual({ kind: "keep", body: { link_ids: [linkId(3)] } });
    await user.click(within(panel()).getByRole("button", { name: "Check again" }));
    expect(lastEdit()).toEqual({ kind: "check", body: { link_ids: [linkId(3)], mode: "check_again" } });
  });
});

describe("finding more and stopping (C44, C48)", () => {
  const editable = (extra: Partial<TocGraph> = {}) => tocGraphFixture({ can_edit: true, ...extra });
  const panel = () => screen.getByRole("complementary", { name: "Details" });
  const lastEdit = () => mutate.mock.calls.at(-1)?.[0];
  const openLink = (n: number) => fireEvent.click((edge(n) as Element).querySelector("path") as Element);

  it("shows new evidence waiting for Accept, with the verdict if accepted, and a dot on the canvas", async () => {
    const user = userEvent.setup();
    const links = tocGraphFixture().links.map((item) =>
      item.link_id === linkId(3) ? { ...item, pending_count: 2, verdict_if_accepted: "supported" as const } : item,
    );
    const evidence = tocEvidenceFixture();
    const onLink3 = evidence.links.find((entry) => entry.link_id === linkId(3));
    if (onLink3 !== undefined) onLink3.documents = onLink3.documents.map((doc, index) => (index < 2 ? { ...doc, status: "pending" as const } : doc));
    renderResult(editable({ links }), evidence);
    expect(edge(3)?.querySelector('[data-testid="toc-edge-attention"]')).not.toBeNull();
    expect(edge(4)?.querySelector('[data-testid="toc-edge-attention"]')).toBeNull();
    openLink(3);
    expect(within(panel()).getByText("New evidence found: 2 documents")).toBeInTheDocument();
    expect(within(panel()).getByText(/if accepted:/)).toBeInTheDocument();
    // Pending documents are not in the counted list.
    expect(within(panel()).getByText("Documents (1)")).toBeInTheDocument();
    await user.click(within(panel()).getByRole("button", { name: "Accept all" }));
    expect(lastEdit()).toEqual({ kind: "decide", linkId: linkId(3), accept: true });
    await user.click(within(panel()).getAllByRole("button", { name: "Reject" })[0] as HTMLElement);
    expect(lastEdit()).toMatchObject({ kind: "evidence", body: { action: "reject" } });
  });

  it("finds more evidence for a connection, and for a box's connections", async () => {
    const user = userEvent.setup();
    renderResult(editable());
    openLink(3);
    await user.click(within(panel()).getByRole("button", { name: "Find more evidence" }));
    expect(lastEdit()).toEqual({ kind: "check", body: { link_ids: [linkId(3)], mode: "find_more" } });
    fireEvent.click(node(5));
    await user.click(within(panel()).getByRole("button", { name: "Find more evidence" }));
    expect(lastEdit()).toMatchObject({ kind: "check", body: { mode: "find_more" } });
    expect((lastEdit() as { body: { link_ids: string[] } }).body.link_ids.length).toBeGreaterThan(1);
  });

  it("says it is finding evidence, and is inactive, while the check runs on that connection", () => {
    const links = tocGraphFixture().links.map((link) => (link.link_id === linkId(3) ? { ...link, state: "checking" as const } : link));
    renderResult(editable({ check_status: "checking", links }));
    openLink(3);
    expect(within(panel()).getByRole("button", { name: "Finding evidence…" })).toBeDisabled();
    expect(within(panel()).queryByRole("button", { name: "Find more evidence" })).toBeNull();
  });

  it("stops a running check, and says when one was stopped", async () => {
    const user = userEvent.setup();
    const { unmount } = renderResult(editable({ check_status: "checking" }));
    await user.click(screen.getByRole("button", { name: "Stop the check" }));
    expect(lastEdit()).toEqual({ kind: "stop" });
    unmount();
    renderResult(editable({ check_status: "stopped" }));
    expect(screen.getByText(/The check was stopped/)).toBeInTheDocument();
  });
});


describe("review and suggestions (C45, C46)", () => {
  const editable = (extra: Partial<TocGraph> = {}) => tocGraphFixture({ can_edit: true, ...extra });
  const lastEdit = () => mutate.mock.calls.at(-1)?.[0];
  const proposal = {
    proposal_id: "p1",
    source: "review" as const,
    summary: "S5 leads nowhere.",
    created_at: "2026-10-30T12:00:00Z",
    edits: [
      { index: 0, op: "add_link", line: "Connect S5 → L1", reason: "S5 reaches no impact.", status: "pending" as const },
      { index: 1, op: "merge_boxes", line: "Merge S4 into S2", reason: "They say the same thing.", status: "pending" as const },
    ],
    report_findings: [{ section: "how_change_happens", why: "A step changed." }],
  };

  it("offers to check the evidence again after a failed check", async () => {
    const user = userEvent.setup();
    renderResult(editable({ check_status: "failed" }));
    expect(screen.getByRole("alert")).toHaveTextContent("The evidence check stopped with an error.");
    await user.click(screen.getByRole("button", { name: "Check the evidence" }));
    expect(lastEdit()).toEqual({ kind: "checkFull" });
  });

  it("asks for a review, counting the changes since the last one", async () => {
    const user = userEvent.setup();
    renderResult(editable({ edits_since_review: 6 }));
    await user.click(screen.getByLabelText("More actions"));
    await user.click(screen.getByRole("menuitem", { name: "Review the theory (6 changes)" }));
    expect(lastEdit()).toEqual({ kind: "review" });
  });

  it("offers a found route as one suggestion, previewed faded on the canvas", async () => {
    const user = userEvent.setup();
    const route = {
      proposal_id: "p2",
      source: "draft" as const,
      summary: "To complete your theory: 1 more route to the goal",
      created_at: "2026-11-04T12:00:00Z",
      edits: [
        { index: 0, op: "add_box", line: "Add box", reason: "r", status: "pending" as const, group: "r1", key: "n1", layer: "outcome_short", text: "Families cook at home" },
        { index: 1, op: "add_link", line: "Connect", reason: "r", status: "pending" as const, group: "r1", key: "l9", source: "P1", dest: "n1" },
        { index: 2, op: "add_pathway", line: "Add pathway", reason: "r", status: "pending" as const, group: "r1", links: ["l9"], kind: "success", label: "Cooking at home" },
      ],
      report_findings: [],
    };
    vi.mocked(queries.useTocProposals).mockReturnValue({ data: [route], refetch: vi.fn() } as unknown as ReturnType<typeof queries.useTocProposals>);
    renderResult(editable());
    const panel = screen.getByRole("region", { name: "Suggestions" });
    // One suggestion for the route, not one per box and link.
    expect(within(panel).getByText("Cooking at home")).toBeInTheDocument();
    expect(within(panel).getAllByRole("button", { name: "Accept" })).toHaveLength(1);
    await user.hover(within(panel).getByText("Cooking at home"));
    expect(screen.getByText("Families cook at home").closest(".border-dashed")).not.toBeNull();
    await user.click(within(panel).getByRole("button", { name: "Accept" }));
    expect(lastEdit()).toEqual({ kind: "proposal", proposalId: "p2", body: { index: null, accept: true, group: "r1" } });
    vi.mocked(queries.useTocProposals).mockReturnValue({ data: [], refetch: vi.fn() } as unknown as ReturnType<typeof queries.useTocProposals>);
  });

  it("lists suggestions with Accept, Reject, Accept all, Update the report and Dismiss", async () => {
    const user = userEvent.setup();
    vi.mocked(queries.useTocProposals).mockReturnValue({ data: [proposal], refetch: vi.fn() } as unknown as ReturnType<typeof queries.useTocProposals>);
    renderResult(editable());
    const card = screen.getByRole("region", { name: "Suggestions" });
    expect(within(card).getByText("Connect S5 → L1")).toBeInTheDocument();
    expect(within(card).getByText(/How change happens/)).toBeInTheDocument();
    await user.click(within(card).getAllByRole("button", { name: "Accept" })[0] as HTMLElement);
    expect(lastEdit()).toEqual({ kind: "proposal", proposalId: "p1", body: { index: 0, accept: true } });
    await user.click(within(card).getAllByRole("button", { name: "Reject" })[1] as HTMLElement);
    expect(lastEdit()).toEqual({ kind: "proposal", proposalId: "p1", body: { index: 1, accept: false } });
    await user.click(within(card).getByRole("button", { name: "Accept all" }));
    expect(lastEdit()).toEqual({ kind: "proposal", proposalId: "p1", body: { index: null, accept: true } });
    await user.click(within(card).getByRole("button", { name: "Update the report" }));
    expect(lastEdit()).toEqual({ kind: "updateReport", proposalId: "p1" });
    await user.click(within(card).getByRole("button", { name: "Dismiss" }));
    expect(lastEdit()).toEqual({ kind: "dismiss", proposalId: "p1" });
    // The panel closes, and the canvas bar's Suggestions button opens it again.
    await user.click(within(screen.getByRole("complementary", { name: "Suggestions" })).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("region", { name: "Suggestions" })).toBeNull();
    await user.click(screen.getByRole("button", { name: /^Suggestions \(/ }));
    expect(screen.getByRole("region", { name: "Suggestions" })).toBeInTheDocument();
    vi.mocked(queries.useTocProposals).mockReturnValue({ data: [], refetch: vi.fn() } as unknown as ReturnType<typeof queries.useTocProposals>);
  });
});

describe("before any draft", () => {
  it("lets the owner draw their own theory on an empty canvas, with no check or review yet", async () => {
    renderResult(tocGraphFixture({ boxes: [], links: [], pathways: [], report: null, check_status: "none", can_edit: true }));
    expect(screen.getByText(/Draw your own theory here/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add box" })).toBeInTheDocument();
    expect(screen.queryByText(/Review the theory/)).not.toBeInTheDocument();
  });

  it("tells a reader there is no theory yet", () => {
    renderResult(tocGraphFixture({ boxes: [], links: [], pathways: [], report: null, check_status: "none", can_edit: false }));
    expect(screen.getByText("There is no theory of change yet.")).toBeInTheDocument();
  });
});

describe("the shared tones, links and disclosures (phase 7, § 4 E)", () => {
  const openLink = (n: number) => {
    fireEvent.click((edge(n) as Element).querySelector("path") as Element);
    return screen.getByRole("complementary", { name: "Details" });
  };

  it("writes a connection's verdict as the shared tone square and the word in ink; not enough evidence is grey", () => {
    renderResult();
    const mixed = within(openLink(3)).getByTestId("link-verdict");
    expect(within(mixed).getByTestId("verdict-mark")).toHaveAttribute("data-tone", "yellow");
    expect(mixed.innerHTML).not.toMatch(/toc-verdict-|rounded-full/);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    const thin = within(openLink(2)).getByTestId("link-verdict");
    expect(thin.textContent).toBe("Not enough evidence");
    expect(within(thin).getByTestId("verdict-mark")).toHaveAttribute("data-tone", "grey");
    expect(within(thin).getByTestId("verdict-mark").className).toContain("bg-line-2");
  });

  it("gives each document's support its tone square, and its title the shared source link", () => {
    renderResult();
    const panel = openLink(3);
    const title = within(panel).getByRole("button", { name: "Children's exposure after Chile's Law 20.606" });
    expect(title.className).toContain("decoration-line-2");
    expect(title.className).not.toContain("text-blue");
    const item = title.closest("li") as HTMLElement;
    expect(within(item).getByTestId("verdict-mark")).toBeInTheDocument();
  });

  it("heads the panel's sections plainly, closes with the shared button, and opens its notes with the shared disclosure", async () => {
    const user = userEvent.setup();
    renderResult();
    const panel = openLink(3);
    const head = within(panel).getByRole("heading", { level: 4, name: "How this works" });
    expect(head.className).not.toMatch(/uppercase|tracking/);
    const close = within(panel).getByRole("button", { name: "Close" });
    expect(close.textContent).toBe("");
    expect(close.querySelector("svg")).not.toBeNull();
    expect(panel.querySelector("details")).toBeNull();
    const origin = within(panel).getByRole("button", { name: "Where this came from" });
    expect(origin).toHaveAttribute("aria-expanded", "false");
    await user.click(origin);
    expect(origin).toHaveAttribute("aria-expanded", "true");
  });

  it("leads the header with the verdict's tone rule and its word in ink, not uppercase", () => {
    renderResult();
    const label = screen.getAllByText("Too little evidence.").find((el) => el.closest("header") !== null) as HTMLElement;
    expect(label.className).not.toMatch(/uppercase|tracking/);
    const line = label.closest("p") as HTMLElement;
    expect(within(line).getByTestId("verdict-rule")).toHaveAttribute("data-tone", "grey");
  });

  it("links a report's codes in the Link style and keeps an old report's numbers as markers", async () => {
    const user = userEvent.setup();
    const fixture = tocGraphFixture();
    const report = fixture.report as NonNullable<TocGraph["report"]>;
    // A report written before sources carried their judgement.
    const old = { ...report, sources: report.sources.map((source) => ({ ...source, evidence_id: null, quote: null })) };
    renderResult({ ...fixture, report: old });
    await user.click(screen.getByRole("button", { name: "Show all" }));
    const info = screen.getByLabelText("Detailed information");
    const code = within(info).getAllByRole("button", { name: "Show #3 on the canvas" })[0] as HTMLElement;
    expect(code.className).toContain("font-semibold");
    expect(code.className).not.toContain("font-bold");
    const marker = within(info).getAllByRole("button", { name: /^Source 1: / })[0] as HTMLElement;
    expect(marker.className).toContain("citation-marker");
  });
});

import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useSyncExternalStore } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../../api/queries";
import { createInitialRunStreamState, type LiveSection, type RunStreamState, type StageEntry } from "../../store";
import { TooltipProvider } from "../../ui/radix/Tooltip";
import { forgetReportExpand } from "../ArtefactOutline";
import * as taskLive from "../taskLive";
import { TASK_ID, tocEvidenceFixture, tocGraphFixture } from "./fixture";
import { pendingCitations, tocParts } from "./liveReport";
import { TocResult } from "./TocResult";
import type { TocGraph } from "./types";

/*
 * The theory of change's report while it is written, the swap to the
 * committed report, and the report written before the reader's changes
 * (task 054's 058 alignment: A13, A17, A22).
 */

/** What the mocked reads return, kept outside React and read through
 *  `useSyncExternalStore`, so a change re-renders the page as a real read
 *  would (the React Compiler skips a re-render with unchanged props). */
const reads = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  return {
    toc: null as unknown,
    live: null as unknown,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    notify: () => listeners.forEach((listener) => listener()),
  };
});

vi.mock("../../api/queries", () => ({
  useTask: vi.fn(() => ({ data: { name: "Ads and obesity" } })),
  useToc: () => useSyncExternalStore(reads.subscribe, () => reads.toc),
  useTocEvidence: vi.fn(),
  useTocDocumentContext: vi.fn(() => ({ isPending: false, isError: false, data: undefined })),
  useTocHistory: vi.fn(() => ({ data: [] })),
  useTocProposals: vi.fn(() => ({ data: [], refetch: vi.fn() })),
  useFunnel: vi.fn(() => ({ data: { found: 412 } })),
  useSourceDossier: vi.fn(() => ({ data: undefined, isPending: false, isLoading: false, isError: false })),
  useEvidence: vi.fn(() => ({ data: undefined, isPending: false })),
  useFindings: vi.fn(() => ({ data: undefined, isPending: false })),
  useSourceRecords: vi.fn(() => ({ data: undefined, isPending: false })),
}));
const mutate = vi.fn();
vi.mock("../../api/mutations", () => ({ useTocEdit: vi.fn(() => ({ mutate, isPending: false })) }));
vi.mock("../taskLive", async (importOriginal) => {
  const actual = await importOriginal<typeof taskLive>();
  return { ...actual, useTaskLive: () => useSyncExternalStore(reads.subscribe, () => reads.live) };
});

const T0 = "2026-11-09T10:00:00Z";

function part(index: number, title: string, overrides: Partial<LiveSection> = {}): LiveSection {
  return { index, title, focus: "", role: "body", state: "planned", ...overrides };
}

/** The skeleton as the server sends it (`report_stream.PAGE_PARTS`), with no
 *  routes found and one supporting activity. */
function skeleton(overrides: Record<number, Partial<LiveSection>> = {}): Record<number, LiveSection> {
  const titles = ["", "Too little evidence", "", "", "Summary", "Pathways", "How it could fail", "What to test first", "Supporting activities", "Assumptions", "References"];
  return Object.fromEntries(titles.map((title, index) => [index, part(index, title, overrides[index])]));
}

function stream(liveSections: Record<number, LiveSection>, status: "running" | "succeeded" = "running", stages: StageEntry[] = []): RunStreamState {
  return {
    ...createInitialRunStreamState(),
    connectionStatus: "connected",
    run: { id: "check", status, startedAt: T0 },
    stages,
    liveSections,
  };
}

function live(state: RunStreamState | null) {
  reads.live =
    state === null ? null : { taskId: TASK_ID, tab: "result", stream: state, marks: taskLive.NO_MARKS, capability: "theory_of_change", isOwner: true, ownerName: null };
}

/** Change what the reads return after the first render, as a refetch or a frame would. */
function update(state: RunStreamState | null, theory: TocGraph) {
  act(() => {
    live(state);
    reads.toc = { data: theory, isPending: false };
    reads.notify();
  });
}

function graph(overrides: Partial<TocGraph> = {}): TocGraph {
  return tocGraphFixture({ check_status: "checking", ...overrides });
}

function page(theory: TocGraph) {
  reads.toc = { data: theory, isPending: false };
  vi.mocked(queries.useTocEvidence).mockReturnValue({ data: tocEvidenceFixture() } as unknown as ReturnType<typeof queries.useTocEvidence>);
  return (
    <MemoryRouter>
      <TooltipProvider delayDuration={0}>
        <TocResult taskId={TASK_ID} />
      </TooltipProvider>
    </MemoryRouter>
  );
}

const sources = [
  { sourceId: "1", title: "Smith 2020" },
  { sourceId: "3", title: "Lee 2023" },
];

beforeEach(() => {
  vi.clearAllMocks();
  forgetReportExpand(TASK_ID);
  live(null);
});

describe("the report's parts", () => {
  it("reads the header's parts by their place and the sections by their heading", () => {
    const parts = tocParts(skeleton());
    expect(parts.get("title")?.index).toBe(0);
    expect(parts.get("verdict")?.title).toBe("Too little evidence");
    expect(parts.get("in_brief")?.index).toBe(3);
    expect(parts.get("supporting_activities")?.index).toBe(8);
    expect(parts.get("references")?.index).toBe(10);
    // A verdict that closed empty leaves the store, not its place.
    const noVerdict = skeleton();
    delete noVerdict[1];
    expect(tocParts(noVerdict).get("question")?.index).toBe(2);
  });

  it("turns the writer's numbers into pending chips on the word before them (S5)", () => {
    const names = new Map([["3", "Lee 2023"]]);
    const marked = pendingCitations("Exposure fell [3]. Spend moved [3, 5].", names);
    expect(marked.text).toBe("Exposure fell. Spend moved.");
    expect(marked.claims.map((claim) => [claim.end, claim.sources.map((source) => source.title)])).toEqual([
      [13, ["Lee 2023"]],
      [26, ["Lee 2023", "Source 5"]],
    ]);
  });
});

describe("the live report (A13)", () => {
  it("fills each part in its page place, with placeholder lines until its words arrive and [·] chips", () => {
    live(
      stream(
        skeleton({
          0: { state: "writing", draft: "Food ad limits and obesity" },
          1: { state: "filled", prose: "Too little evidence: the evidence is thin." },
          4: { state: "writing", draft: "Chile restricted adverts [1]. England follows.", sources },
        }),
      ),
    );
    render(page(graph({ report: null })));
    // The report's own title streams into the h1.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Food ad limits and obesity");
    // The verdict's words show at once; its tone square comes with the committed report.
    const verdict = screen.getByText("Too little evidence.").closest("p") as HTMLElement;
    expect(verdict).toHaveTextContent("Too little evidence. The evidence is thin.");
    expect(verdict.querySelector("[data-tone]")).toBeNull();
    const info = screen.getByLabelText("Detailed information");
    // Today's section order, h2s, not collapsible while written.
    expect(within(info).getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "Summary",
      "Pathways",
      "How it could fail",
      "What to test first",
      "Supporting activities",
      "Assumptions",
      "References",
    ]);
    expect(within(info).queryByRole("button", { name: /Show/ })).toBeNull();
    // The Summary's words, its source number a muted chip naming the source.
    expect(within(info).getByText(/Chile restricted adverts/)).toBeInTheDocument();
    const chip = within(info).getByTestId("provisional-mark");
    expect(chip).toHaveTextContent("[·]");
    expect(chip).toHaveAttribute("title", "Smith 2020");
    expect(info).not.toHaveTextContent("[1]");
    // The parts not yet written hold their place with breathing lines.
    expect(within(info).getAllByTestId("placeholder-lines").length).toBeGreaterThan(3);
    // No Download until the report is committed; the contents list the sections.
    expect(screen.queryByRole("button", { name: "Download" })).toBeNull();
    expect(within(screen.getAllByRole("navigation", { name: "Contents" })[0] as HTMLElement).getByText("Assumptions")).toBeInTheDocument();
  });

  it("fills in the order written: a list part's items arrive before a section above it", () => {
    live(
      stream(
        skeleton({
          9: { state: "writing", cards: [{ title: "#3", prose: "Seen after Chile's rules [3]." }], sources },
        }),
      ),
    );
    render(page(graph({ report: null })));
    const assumptions = document.getElementById("toc-assumptions") as HTMLElement;
    expect(within(assumptions).getByText("#3")).toBeInTheDocument();
    expect(assumptions).toHaveTextContent("Seen after Chile's rules");
    // What to test first, above it on the page, still waits.
    expect(within(document.getElementById("toc-tests") as HTMLElement).getByTestId("placeholder-lines")).toBeInTheDocument();
  });

  it("marks the part being written with ◆ Writing", () => {
    const first = stream(skeleton({ 6: { state: "writing", draft: "Brands" } }));
    live(first);
    render(page(graph({ report: null })));
    update(stream(skeleton({ 6: { state: "writing", draft: "Brands moved their spend" } })), graph({ report: null }));
    const fail = document.getElementById("toc-fail") as HTMLElement;
    expect(fail).toHaveAttribute("aria-busy", "true");
    expect(within(fail).getByTestId("action-line")).toHaveTextContent("Writing");
    expect(within(fail).getByTestId("section-mark")).toBeInTheDocument();
  });

  it("swaps in place to the committed report, its sections open for the reader who watched", () => {
    live(stream(skeleton({ 4: { state: "filled", prose: "Chile restricted adverts [1]." } })));
    render(page(graph({ report: null })));
    update(stream(skeleton({ 4: { state: "filled", prose: "Chile restricted adverts [1]." } }), "succeeded"), graph({ check_status: "checked" }));
    const info = screen.getByLabelText("Detailed information");
    // The committed report: numbered markers, the committed details fading in.
    expect(within(info).queryByTestId("provisional-mark")).toBeNull();
    expect(screen.getByRole("button", { name: "Hide all" })).toBeInTheDocument();
    expect(within(info).getByText(/This report asks whether the ban/)).toBeInTheDocument();
    expect(info.querySelector(".anim-swap-in")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });
});

describe("a report written before the reader's changes (A17, A22)", () => {
  it("says so under the title block, and Update the report is the reader's", async () => {
    const user = userEvent.setup();
    const fixture = graph({ check_status: "checked", can_edit: true });
    const report = fixture.report as NonNullable<TocGraph["report"]>;
    render(page({ ...fixture, report: { ...report, stale: true } }));
    expect(screen.getByText("Written before your latest changes.")).toHaveClass("text-meta", "text-grey");
    await user.click(screen.getByRole("button", { name: "Update the report" }));
    expect(mutate.mock.calls.at(-1)?.[0]).toEqual({ kind: "updateReport" });
    // While it runs, the working line stands in its place; the old report stays.
    update(null, { ...fixture, check_status: "checking", report: { ...report, stale: true } });
    expect(screen.getByRole("status")).toHaveTextContent("Updating the report");
    expect(screen.queryByText("Written before your latest changes.")).toBeNull();
    expect(screen.getByLabelText("Detailed information")).toBeInTheDocument();
  });

  it("knows an update from its steps after a reload, and shows no live sections over the old report", () => {
    const fixture = graph({ check_status: "checking", can_edit: true });
    const report = fixture.report as NonNullable<TocGraph["report"]>;
    const steps: StageEntry[] = [{ stage: "toc_summarise", label: "Titles", status: "completed", startedAt: T0 }];
    // Even a stray skeleton never takes the page from a report (S7b).
    live(stream(skeleton({ 4: { state: "writing", draft: "New words" } }), "running", steps));
    render(page({ ...fixture, report: { ...report, stale: true } }));
    expect(screen.getByRole("status")).toHaveTextContent("Updating the report");
    expect(screen.queryByText(/New words/)).toBeNull();
    expect(screen.queryByTestId("placeholder-lines")).toBeNull();
  });

  it("offers no update to a reader who cannot edit", () => {
    const fixture = graph({ check_status: "checked" });
    const report = fixture.report as NonNullable<TocGraph["report"]>;
    render(page({ ...fixture, report: { ...report, stale: true } }));
    expect(screen.getByText("Written before your latest changes.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Update the report" })).toBeNull();
  });
});

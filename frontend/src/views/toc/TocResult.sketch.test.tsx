import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useSyncExternalStore } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../../api/queries";
import { createInitialRunStreamState, type LiveSection, type LiveSketch, type RunStreamState, type StageEntry } from "../../store";
import { ToastProvider } from "../../ui/radix/Toast";
import { TooltipProvider } from "../../ui/radix/Tooltip";
import { forgetReportExpand } from "../ArtefactOutline";
import * as taskLive from "../taskLive";
import { TASK_ID, tocEvidenceFixture, tocGraphFixture } from "./fixture";
import { TocResult } from "./TocResult";
import type { TocGraph } from "./types";

/*
 * The theory of change's first draft drawn on the canvas while it is written
 * (task 054, S12), the swap to the stored graph, a connection being
 * checked (its travelling dot and its key), and the live "What to test
 * first" numbered as the committed one.
 */

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
vi.mock("../../api/mutations", () => ({ useTocEdit: vi.fn(() => ({ mutate: vi.fn(), isPending: false })) }));
vi.mock("../taskLive", async (importOriginal) => {
  const actual = await importOriginal<typeof taskLive>();
  return { ...actual, useTaskLive: () => useSyncExternalStore(reads.subscribe, () => reads.live) };
});

const T0 = "2026-11-10T11:00:00Z";

const BOXES: LiveSketch["boxes"] = [
  { key: "b1", layer: "input", text: "Ban on less healthy food ads" },
  { key: "b2", layer: "output", text: "Fewer less healthy food ads shown" },
  { key: "b3", layer: "outcome_short", text: "Children see fewer ads for less healthy food" },
];

function draftStage(status: StageEntry["status"]): StageEntry {
  return { stage: "toc_draft", label: "Drafting the theory", status, startedAt: T0 };
}

function stream({
  sketch,
  stage = "started",
  status = "running",
  runId = "draft",
  liveSections = {},
}: {
  sketch?: LiveSketch;
  stage?: StageEntry["status"] | null;
  status?: "running" | "succeeded" | "failed";
  runId?: string;
  liveSections?: Record<number, LiveSection>;
}): RunStreamState {
  const state: RunStreamState = {
    ...createInitialRunStreamState(),
    connectionStatus: "connected",
    run: { id: runId, status, startedAt: T0 },
    stages: stage === null ? [] : [draftStage(stage)],
    liveSections,
  };
  if (sketch !== undefined) state.liveSketch = sketch;
  return state;
}

function live(state: RunStreamState | null) {
  reads.live =
    state === null ? null : { taskId: TASK_ID, tab: "result", stream: state, marks: taskLive.NO_MARKS, capability: "theory_of_change", isOwner: true, ownerName: null };
}

/** The stored graph while the draft runs: no boxes yet. */
function drafting(): TocGraph {
  return tocGraphFixture({ check_status: "drafting", boxes: [], links: [], pathways: [], report: null, can_edit: true });
}

function update(state: RunStreamState | null, theory: TocGraph) {
  act(() => {
    live(state);
    reads.toc = { data: theory, isPending: false };
    reads.notify();
  });
}

function page(theory: TocGraph) {
  reads.toc = { data: theory, isPending: false };
  vi.mocked(queries.useTocEvidence).mockReturnValue({ data: tocEvidenceFixture() } as unknown as ReturnType<typeof queries.useTocEvidence>);
  return (
    <MemoryRouter>
      <ToastProvider>
        <TooltipProvider delayDuration={0}>
          <TocResult taskId={TASK_ID} />
        </TooltipProvider>
      </ToastProvider>
    </MemoryRouter>
  );
}

const boxNodes = () => [...document.querySelectorAll<HTMLElement>(".react-flow__node-box")];
const EMPTY_STATE = "The theory of change is being drafted.";

beforeEach(() => {
  vi.clearAllMocks();
  forgetReportExpand(TASK_ID);
  live(null);
});

describe("the live draft on the canvas (S12)", () => {
  it("keeps today's empty state until the first box arrives", () => {
    live(stream({}));
    render(page(drafting()));
    expect(screen.getByText(EMPTY_STATE)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Theory of change canvas" })).toBeNull();
  });

  it("draws the sketch's boxes and connections on the canvas, the newest being written", () => {
    live(stream({ sketch: { boxes: BOXES, links: [{ key: "l1", source: "b1", target: "b2" }] } }));
    render(page(drafting()));
    expect(screen.queryByText(EMPTY_STATE)).toBeNull();
    const canvas = screen.getByRole("group", { name: "Theory of change canvas" });
    expect(canvas).toHaveAttribute("aria-busy", "true");
    expect(boxNodes().map((node) => node.textContent)).toEqual(BOXES.map((box) => box.text));
    // In the stored graph's columns, under their headings.
    expect(within(canvas).getByText("Short-term outcomes")).toBeInTheDocument();
    // The connection is drawn plain grey: no verdict, and it is not being checked.
    expect(document.querySelectorAll(".react-flow__edge")).toHaveLength(1);
    expect(document.querySelector(".toc-edge--unchecked")).not.toBeNull();
    expect(document.querySelector(".toc-edge--pending")).toBeNull();
    expect(screen.queryByTestId("toc-edge-dot")).toBeNull();
    // The boxes are written; no box is marked while the connections are.
    expect(screen.queryByTestId("toc-box-writing")).toBeNull();
  });

  it("marks the newest box while the boxes are written", () => {
    live(stream({ sketch: { boxes: BOXES, links: [] } }));
    render(page(drafting()));
    const writing = screen.getByTestId("toc-box-writing");
    expect(boxNodes().at(-1)).toContainElement(writing);
    expect(writing).toHaveClass("anim-breathe");
  });

  it("is not a control: no codes, no focus, no details, no edits", () => {
    live(stream({ sketch: { boxes: BOXES, links: [{ key: "l1", source: "b1", target: "b2" }] } }));
    render(page(drafting()));
    for (const node of boxNodes()) {
      expect(node).not.toHaveAttribute("tabindex");
      fireEvent.click(node);
    }
    // No details panel opens, and the editor's tools wait for the stored graph.
    expect(screen.queryByRole("complementary")).toBeNull();
    expect(screen.queryByRole("button", { name: "Add box" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Connect" })).toBeNull();
    expect(document.querySelector(".react-flow__edge")).not.toHaveAttribute("tabindex");
  });

  it("empties the canvas when the draft is written again, then draws the retry", () => {
    live(stream({ sketch: { boxes: BOXES, links: [] } }));
    render(page(drafting()));
    // An empty frame removes the stream's sketch while the draft still runs.
    update(stream({}), drafting());
    expect(boxNodes()).toHaveLength(0);
    expect(screen.getByRole("group", { name: "Theory of change canvas" })).toBeInTheDocument();
    expect(screen.queryByText(EMPTY_STATE)).toBeNull();
    update(stream({ sketch: { boxes: BOXES.slice(0, 1), links: [] } }), drafting());
    expect(boxNodes()).toHaveLength(1);
  });

  it("holds the sketch after the draft's stage ends, until the stored graph replaces it with no empty frame", () => {
    const sketch = { boxes: BOXES, links: [] };
    live(stream({ sketch }));
    render(page(drafting()));
    // The stage ends; `GET /toc` has not returned the graph yet.
    update(stream({ sketch, stage: "completed", status: "succeeded" }), drafting());
    expect(boxNodes()).toHaveLength(3);
    // The check's walk starts and the stream drops the sketch: still held.
    update(stream({ stage: null, runId: "check" }), drafting());
    expect(boxNodes()).toHaveLength(3);
    expect(screen.queryByText(EMPTY_STATE)).toBeNull();
    // The stored graph lands: its boxes, with their codes, in place of the sketch.
    update(stream({ stage: null, runId: "check" }), tocGraphFixture({ check_status: "checking" }));
    expect(screen.getByRole("group", { name: "Theory of change canvas" })).not.toHaveAttribute("aria-busy");
    expect(boxNodes().length).toBeGreaterThan(3);
    expect(screen.getByText("A1")).toBeInTheDocument();
    expect(boxNodes().every((node) => node.getAttribute("data-id")?.startsWith("sketch:") !== true)).toBe(true);
  });

  it("drops the sketch when the draft fails", () => {
    const sketch = { boxes: BOXES, links: [] };
    live(stream({ sketch }));
    render(page(drafting()));
    update(stream({ sketch, stage: "failed", status: "failed" }), drafting());
    expect(boxNodes()).toHaveLength(0);
    expect(screen.queryByRole("group", { name: "Theory of change canvas" })).toBeNull();
  });
});

describe("a connection being checked (owner, 2026-11-10)", () => {
  const checking = () => tocGraphFixture({ check_status: "checking" });
  const pendingEdge = () => document.querySelector(".toc-edge--pending")?.closest("g") as SVGGElement;

  it("keeps the grey line, with an ink dot travelling its path on the 1.6 s loop", () => {
    expect(checking().links.some((link) => link.state === "checking")).toBe(true);
    render(page(checking()));
    const edge = pendingEdge();
    const line = edge.querySelector(".toc-edge--pending") as SVGPathElement;
    expect(line.getAttribute("style") ?? "").not.toContain("stroke");
    const dot = within(edge as unknown as HTMLElement).getByTestId("toc-edge-dot");
    expect(dot).toHaveClass("fill-ink");
    const motion = dot.querySelector("animateMotion") as SVGElement;
    expect(motion).toHaveAttribute("path", line.getAttribute("d"));
    expect(motion).toHaveAttribute("dur", "1.6s");
    expect(motion).toHaveAttribute("repeatCount", "indefinite");
    // No blue anywhere on the connections, arrowheads included.
    expect(document.querySelector(".react-flow__edges")?.innerHTML ?? "").not.toContain("--color-blue");
    expect(document.querySelector(".react-flow")?.querySelector("defs")?.innerHTML ?? "").not.toContain("--color-blue");
  });

  it("holds the dot still at the middle under reduced motion", () => {
    const original = window.matchMedia;
    window.matchMedia = ((query: string) => ({ matches: query.includes("reduce"), media: query, addEventListener: () => {}, removeEventListener: () => {} })) as unknown as typeof window.matchMedia;
    try {
      render(page(checking()));
      const motion = within(pendingEdge() as unknown as HTMLElement).getByTestId("toc-edge-dot").querySelector("animateMotion") as SVGElement;
      expect(motion).toHaveAttribute("keyPoints", "0.5;0.5");
      expect(motion).toHaveAttribute("fill", "freeze");
      expect(motion).not.toHaveAttribute("repeatCount");
    } finally {
      window.matchMedia = original;
    }
  });

  it("keys the dot only while a connection is being checked", () => {
    const { unmount } = render(page(checking()));
    const entry = within(screen.getByRole("list", { name: "Line key" })).getByText("Being checked").closest("li") as HTMLElement;
    expect(entry.querySelector("line")).toHaveAttribute("stroke", "var(--color-line-2)");
    expect(within(entry).getByTestId("toc-edge-dot")).toBeInTheDocument();
    unmount();
    const checked = tocGraphFixture({ check_status: "checked" });
    render(page({ ...checked, links: checked.links.map((link) => ({ ...link, state: "checked" as const })) }));
    expect(within(screen.getByRole("list", { name: "Line key" })).queryByText("Being checked")).toBeNull();
    expect(screen.queryByTestId("toc-edge-dot")).toBeNull();
  });
});

describe("What to test first while it is written (owner, 2026-11-10)", () => {
  it("is numbered as the committed list is; the other lists keep the square bullets", () => {
    const titles = ["", "Too little evidence", "", "", "Summary", "Pathways", "How it could fail", "What to test first", "Supporting activities", "Assumptions", "References"];
    const sections: Record<number, LiveSection> = Object.fromEntries(
      titles.map((title, index) => [index, { index, title, focus: "", role: "body", state: "planned" } as LiveSection]),
    );
    sections[5] = { ...sections[5], state: "writing", cards: [{ title: "Fewer ads", prose: "Children see fewer ads." }] } as LiveSection;
    sections[7] = { ...sections[7], state: "writing", cards: [{ title: "#3", prose: "Test the ad count." }, { title: "#5", prose: "Test the spend." }] } as LiveSection;
    live({ ...stream({ stage: null, runId: "check", liveSections: sections }) });
    render(page(tocGraphFixture({ check_status: "checking", report: null })));
    const tests = document.getElementById("toc-tests") as HTMLElement;
    const list = tests.querySelector("ol") as HTMLElement;
    expect(list).toHaveClass("list-decimal");
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(tests.querySelector("[data-bullet]")).toBeNull();
    const pathways = document.getElementById("toc-routes") as HTMLElement;
    expect(pathways.querySelector("ol")).toBeNull();
    expect(pathways.querySelector("[data-bullet]")).not.toBeNull();
  });
});

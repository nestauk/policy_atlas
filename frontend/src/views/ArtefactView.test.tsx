import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createInitialRunStreamState } from "../store";
import type { LiveSection, RunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import {
  AnnotatedProse,
  CitationProvenanceBlock,
  draftParagraphs,
  highlightParts,
  LiveArtefactBody,
  liveCaseStudyCards,
  liveReferences,
  minutesSince,
  orderSections,
  ProvenanceSheet,
  ReferencesSection,
  ReportToBe,
  settlePlan,
  settleStep,
  showLiveArtefact,
} from "./ArtefactView";
import { drawingOnLine, liveSourceName } from "./artefactPresentation";

describe("highlightParts", () => {
  it("finds an exact quote", () => {
    const parts = highlightParts("before the exact quote after", "the exact quote");
    expect(parts).toEqual({
      kind: "highlight",
      before: "before ",
      match: "the exact quote",
      after: " after",
    });
  });

  it("remaps a whitespace-normalised quote", () => {
    const parts = highlightParts("text with  odd\n spacing here", "with odd spacing");
    expect(parts.kind).toBe("highlight");
    if (parts.kind === "highlight") {
      expect(parts.match).toContain("with");
    }
  });

  it("starts the remapped match on the word, not inside a collapsed whitespace run", () => {
    const parts = highlightParts("abc  def ghi", "def ghi");
    expect(parts.kind).toBe("highlight");
    if (parts.kind === "highlight") {
      expect(parts.match.startsWith("def")).toBe(true);
    }
  });

  it("degrades to quote-above-text when nothing matches — never a broken panel", () => {
    const parts = highlightParts("completely different content", "an absent quote");
    expect(parts).toEqual({
      kind: "degrade",
      quote: "an absent quote",
      text: "completely different content",
    });
  });
});

describe("orderSections", () => {
  it("presents key findings first and conclusions last", () => {
    const ordered = orderSections([
      { title: "Middle", role: "standard" as const },
      { title: "End", role: "conclusions" as const },
      { title: "First", role: "key_findings" as const },
    ]);
    expect(ordered.map((section) => section.title)).toEqual(["First", "Middle", "End"]);
  });

  it("places case_studies after key_findings and before standard", () => {
    const ordered = orderSections([
      { title: "Body", role: "standard" as const },
      { title: "Cases", role: "case_studies" as const },
      { title: "KF", role: "key_findings" as const },
      { title: "End", role: "conclusions" as const },
    ]);
    expect(ordered.map((section) => section.title)).toEqual(["KF", "Cases", "Body", "End"]);
  });
});

function streamWith(
  sections: LiveSection[],
  runStatus: "running" | "failed" | "aborted" | "interrupted",
): RunStreamState {
  const state = createInitialRunStreamState();
  return {
    ...state,
    run: { id: "r1", status: runStatus, startedAt: "2026-07-21T10:00:00Z" },
    liveSections: Object.fromEntries(sections.map((section) => [section.index, section])),
  };
}

const LIVE_SECTIONS: LiveSection[] = [
  { index: 0, title: "Key findings", focus: "Headline claims.", state: "planned" },
  { index: 1, title: "Costs", focus: "What it costs.", state: "writing" },
  {
    index: 2,
    title: "Effects <script>alert(1)</script>",
    focus: "",
    state: "filled",
    prose: "Prose arrived <img src=x onerror=alert(1)> safely.",
  },
];

const FAILED = "Two studies found no effect.";
const REPAIRED = "One study found no effect.";
const LEAD = "Cost is the barrier families name most often.";

/** A writing stream: key findings waits, "Costs" is being written with the
 *  writer's tick naming it, "Outreach" is still to come. */
function writingStream(
  costs: Partial<LiveSection> = {},
  activity = "Looking for: evidence on subsidy uptake",
  status: "running" | "succeeded" | "degraded" | "failed" = "running",
): RunStreamState {
  const stream = streamWith(
    [
      { index: 0, title: "Key findings", focus: "Headline claims.", state: "planned" },
      { index: 1, title: "Costs", focus: "What it costs.", state: "writing", ...costs },
      { index: 2, title: "Outreach", focus: "What reached families.", state: "planned" },
    ],
    status === "succeeded" || status === "degraded" ? "running" : status,
  );
  return {
    ...stream,
    run: { id: "r1", status, startedAt: "2026-07-21T10:00:00Z" },
    liveness: {
      synthesise: {
        activity,
        section: "Section 1 of 2 · Costs",
        heartbeat: false,
        dropped: 0,
        occurredAt: "2026-07-21T10:05:00Z",
      },
    },
  };
}

function mockReducedMotion(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

describe("LiveArtefactBody", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("titles the page with the question and keeps proposed sections as pulsing lines", () => {
    render(<LiveArtefactBody stream={writingStream()} question="What raises take-up?" />);
    expect(screen.getByRole("heading", { level: 1, name: "What raises take-up?" })).toBeInTheDocument();
    // Key findings and Outreach wait with placeholder lines; Costs has its own.
    const placeholders = screen.getAllByTestId("placeholder-lines");
    expect(placeholders).toHaveLength(3);
    for (const lines of placeholders) {
      expect(lines.className).toContain("anim-breathe");
      expect(lines.children.length).toBeGreaterThanOrEqual(2);
      expect(lines.children.length).toBeLessThanOrEqual(3);
    }
    expect(screen.getByText("Written last, after the sections are checked.")).toBeInTheDocument();
    // No pills, no old status copy.
    expect(screen.queryByText(/Being written now/)).toBeNull();
    expect(screen.queryByText(/Writing this section now/)).toBeNull();
  });

  it("shows the writer's action line under the active heading, its words beside the mark for the whole write", () => {
    const { rerender } = render(<LiveArtefactBody stream={writingStream()} />);
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section");
    expect(costs).not.toBeNull();
    const action = within(costs as HTMLElement).getByTestId("action-line");
    expect(action).toHaveTextContent("Looking for: evidence on subsidy uptake");
    expect(action).not.toHaveAttribute("aria-hidden");
    // The section's mark is the run's live mark, the fold mark turning, at
    // the start of the action line, not beside the heading (owner, 2026-11-05).
    const mark = within(action).getByTestId("section-mark");
    expect(mark).toHaveAttribute("data-live-mark");
    expect(mark.nextElementSibling).toHaveTextContent("Looking for: evidence on subsidy uptake");
    expect(within(screen.getByRole("heading", { name: "Costs" })).queryByTestId("section-mark")).toBeNull();

    rerender(<LiveArtefactBody stream={writingStream({ draft: "Cost is the" }, "Writing")} />);
    const after = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    // While the draft streams the line reads "◆ Writing" (lead, 2026-11-05).
    const line = within(after).getByTestId("action-line");
    expect(line).not.toHaveAttribute("aria-hidden");
    expect(line).toHaveTextContent(/^Writing$/);
    expect(within(line).getByTestId("section-mark").nextElementSibling).toHaveTextContent("Writing");
    expect(within(after).queryByTestId("placeholder-lines")).toBeNull();
    expect(within(after).getByText("Cost is the")).toBeInTheDocument();
  });

  it("appends drafted prose as plain text with paragraph breaks and no claim marker", () => {
    vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "setTimeout", "clearTimeout", "performance"] });
    const { rerender, container } = render(
      <LiveArtefactBody stream={writingStream({ draft: "Cost is" }, "Writing")} />,
    );
    rerender(
      <LiveArtefactBody
        stream={writingStream({ draft: `${LEAD} **Bold?** [1]\n\nSubsidy design matters.` }, "Writing")}
      />,
    );
    // Paced in the browser: the text is revealed over a few frames.
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    // Laid out as the committed prose is: one paragraph element, a blank
    // line between paragraphs (owner, round 7: nothing moves at the swap).
    const paragraphs = costs.querySelectorAll("p.whitespace-pre-line");
    expect(paragraphs).toHaveLength(1);
    expect(paragraphs[0].textContent).toBe(`${LEAD} **Bold?** [1]\n\nSubsidy design matters.`);
    // Plain text: Markdown is not interpreted, and nothing is a marker.
    expect(container.querySelector(".citation-marker")).toBeNull();
    expect(within(costs).queryByRole("button")).toBeNull();
  });

  it("returns the action line for the check, and blurs a span under repair in place", () => {
    const draft = `${LEAD} ${FAILED}`;
    const start = draft.indexOf(FAILED);
    render(
      <LiveArtefactBody
        stream={writingStream({ draft, revising: [{ start, end: start + FAILED.length }] }, "Revising 1 claim")}
      />,
    );
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    expect(within(costs).getByTestId("action-line")).toHaveTextContent("Revising 1 claim");
    const revising = costs.querySelector("[data-revising='true']");
    expect(revising).toHaveTextContent(FAILED);
    expect(revising).toHaveClass("draft-revising");
    // Only the failed sentence: the rest of the draft is untouched.
    expect(costs.querySelectorAll("[data-revising='true']")).toHaveLength(1);
  });

  it("settles the draft into the final prose with a settling layer, then marks nothing", () => {
    mockReducedMotion(false);
    vi.useFakeTimers();
    const draft = `${LEAD} ${FAILED}`;
    const start = draft.indexOf(FAILED);
    const { rerender } = render(
      <LiveArtefactBody
        stream={writingStream({ draft, revising: [{ start, end: start + FAILED.length }] }, "Revising 1 claim")}
      />,
    );
    rerender(
      <LiveArtefactBody
        stream={writingStream({ state: "filled", prose: `${LEAD} ${REPAIRED}`, draft: undefined, revising: undefined })}
      />,
    );
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    // The settling layer holds the blurred sentence, in the flow, the
    // checked prose waiting unseen under it (round 8).
    const layer = within(costs).getByTestId("draft-prose");
    expect(layer).toHaveAttribute("aria-hidden", "true");
    expect(layer.querySelector(".draft-revised-held")).toHaveTextContent(FAILED);
    // Then the sentence takes its new words, resolving out of the blur.
    act(() => {
      vi.advanceTimersByTime(0);
    });
    expect(layer.querySelector(".draft-settle-in")).toHaveTextContent(REPAIRED);
    expect(layer).not.toHaveTextContent(FAILED);
    // Then the layer fades off the checked prose.
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(costs.querySelector(".anim-settle-out")).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(costs.querySelector(".anim-settle-out")).toBeNull();
    expect(costs).toHaveTextContent(REPAIRED);
    expect(costs).not.toHaveTextContent(FAILED);
    // A done section carries no marker of any kind.
    expect(costs.querySelector("[data-revising]")).toBeNull();
    expect(within(costs).queryByTestId("section-mark")).toBeNull();
    expect(within(costs).getByTestId("action-line")).toHaveAttribute("aria-hidden", "true");
    expect(costs.querySelector(".underline, .border-dotted")).toBeNull();
  });

  it("under reduced motion swaps at once, keeps the lines still and only dims the repair", () => {
    mockReducedMotion(true);
    const draft = `${LEAD} ${FAILED}`;
    const { rerender } = render(<LiveArtefactBody stream={writingStream({ draft }, "Writing")} />);
    for (const lines of screen.getAllByTestId("placeholder-lines")) {
      expect(lines.className).not.toContain("anim-breathe");
    }
    rerender(
      <LiveArtefactBody stream={writingStream({ state: "filled", prose: `${LEAD} ${REPAIRED}`, draft: undefined })} />,
    );
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    expect(costs.querySelector(".anim-settle-out")).toBeNull();
    expect(costs).toHaveTextContent(REPAIRED);
  });

  it("announces the section being written in a polite live region", () => {
    render(<LiveArtefactBody stream={writingStream()} />);
    const region = screen.getByText("Costs is being written");
    expect(region).toHaveAttribute("aria-live", "polite");
  });

  it("keeps the key-findings note until their words arrive, with no footer under the sections", () => {
    const sections: LiveSection[] = [
      { index: 0, title: "Key findings", focus: "", state: "writing" },
      { index: 1, title: "Costs", focus: "", state: "filled", prose: "Costs prose." },
      { index: 2, title: "Outreach", focus: "", state: "filled", prose: "Outreach prose." },
    ];
    const stream = streamWith(sections, "running");
    const { rerender } = render(<LiveArtefactBody stream={stream} />);
    // Owner, round 8: the note stays until the key findings' deltas start.
    expect(screen.getByText("Written last, after the sections are checked.")).toBeInTheDocument();
    rerender(
      <LiveArtefactBody
        stream={streamWith([{ ...sections[0], draft: "- Cost" }, sections[1], sections[2]], "running")}
      />,
    );
    expect(screen.queryByText("Written last, after the sections are checked.")).toBeNull();
    const keyFindings = screen.getByRole("heading", { name: "Key findings" }).closest("section") as HTMLElement;
    expect(within(keyFindings).getByTestId("section-mark")).toBeInTheDocument();
    // Owner, 2026-11-05: no "Checking claims and attaching citations" line;
    // the key-findings section's live mark is the one signal.
    expect(screen.queryByText(/attaching citations/)).toBeNull();
    expect(screen.queryByText("Report ready")).toBeNull();
  });

  it.each(["succeeded", "degraded"] as const)(
    "marks nothing once the run is %s (the committed report takes over)",
    (status) => {
      const stream = streamWith(
        [
          { index: 0, title: "Key findings", focus: "", state: "filled", prose: "Headline." },
          { index: 1, title: "Costs", focus: "", state: "filled", prose: "Costs prose." },
        ],
        "running",
      );
      render(
        <LiveArtefactBody stream={{ ...stream, run: { id: "r1", status, startedAt: "2026-07-21T10:00:00Z" } }} />,
      );
      expect(screen.queryByText("Report ready")).toBeNull();
      expect(screen.queryByRole("button", { name: "Read the full report" })).toBeNull();
      expect(screen.queryByTestId("section-mark")).toBeNull();
    },
  );

  it("streamed strings render scrubbed (adversarial fixture strings)", () => {
    const withControlChars: LiveSection[] = [
      ...LIVE_SECTIONS,
      {
        index: 3,
        title: "Controls",
        focus: "",
        state: "filled",
        prose: "clean\u202Ereversed\u0007bell",
      },
    ];
    const { container } = render(
      <LiveArtefactBody stream={streamWith(withControlChars, "running")} />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    // scrub() strips control/format characters — React escaping alone would
    // keep them, so this proves the prose actually passes through scrub.
    expect(container.textContent).not.toContain("\u202E");
    expect(container.textContent).not.toContain("\u0007");
    expect(screen.getByText(/cleanreversedbell/)).toBeInTheDocument();
  });

  it.each(["failed", "aborted", "interrupted"] as const)(
    "keeps the drafted-not-final banner over streamed sections after a %s ending",
    (runStatus) => {
      render(<LiveArtefactBody stream={streamWith(LIVE_SECTIONS, runStatus)} />);
      expect(screen.getByRole("alert")).toHaveTextContent(
        "This run ended before the write-up completed.",
      );
      // Sections stay visible; nothing pulses or claims to be in progress.
      expect(screen.getByText(/Prose arrived/)).toBeInTheDocument();
      expect(screen.queryByTestId("placeholder-lines")).toBeNull();
      expect(screen.queryByTestId("section-mark")).toBeNull();
    },
  );

  it("drops a closed-empty section slot (hide, never fake)", () => {
    const withEmpty: LiveSection[] = [
      ...LIVE_SECTIONS,
      { index: 3, title: "Empty key findings", focus: "", state: "filled", prose: "" },
    ];
    render(<LiveArtefactBody stream={streamWith(withEmpty, "running")} />);
    expect(screen.queryByText("Empty key findings")).toBeNull();
  });
});

describe("draftParagraphs", () => {
  it("splits on blank lines and marks spans by code point", () => {
    const draft = "A \u{1F600} b.\n\nC d.";
    // The emoji is one code point: the span [2, 3) is the emoji alone.
    const paragraphs = draftParagraphs(draft, [{ start: 2, end: 3 }]);
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0]).toEqual([
      { text: "A ", start: 0, revising: false },
      { text: "\u{1F600}", start: 2, revising: true, reviseAt: 0 },
      { text: " b.", start: 3, revising: false },
    ]);
    expect(paragraphs[1]).toEqual([{ text: "C d.", start: 8, revising: false }]);
  });
});

describe("evidence shown live (task 058, owner 2026-11-05)", () => {
  const SOURCES = [
    { sourceId: "a", title: "Smith 2023" },
    { sourceId: "b", title: "DfE 2022" },
    { sourceId: "c", title: "Walking school buses and active travel to school: a mixed-methods evaluation" },
    { sourceId: "d", title: "Sustrans 2020" },
  ];

  it("names up to three sources under the heading, then 'and N more'", () => {
    expect(drawingOnLine(undefined)).toBeNull();
    expect(drawingOnLine([])).toBeNull();
    expect(drawingOnLine(SOURCES.slice(0, 1))).toBe("Drawing on 1 source · Smith 2023");
    expect(drawingOnLine(SOURCES)).toBe(
      "Drawing on 4 sources · Smith 2023 · DfE 2022 · Walking school buses and active travel… · and 1 more",
    );
    expect(liveSourceName("Short title")).toBe("Short title");
    expect(liveSourceName("x".repeat(60))).toBe(`${"x".repeat(40)}…`);
  });

  it("shows the line from the first read, above the action line and the prose, until the section settles", () => {
    const { rerender } = render(<LiveArtefactBody stream={writingStream({ sources: SOURCES.slice(0, 2) })} />);
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    const line = within(costs).getByTestId("drawing-on");
    expect(line).toHaveTextContent("Drawing on 2 sources · Smith 2023 · DfE 2022");
    expect(line.className).toContain("text-meta");
    expect(line.className).toContain("text-grey");
    // Under the heading, before the action line; nothing in it is a link.
    expect(costs.querySelector("h3")?.nextElementSibling).toBe(line);
    expect(line.compareDocumentPosition(within(costs).getByTestId("action-line"))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(within(line).queryByRole("link")).toBeNull();
    expect(within(line).queryByRole("button")).toBeNull();

    rerender(
      <LiveArtefactBody stream={writingStream({ sources: SOURCES, draft: "Cost is the" }, "Checking claims")} />,
    );
    expect(screen.getByTestId("drawing-on")).toHaveTextContent("and 1 more");

    rerender(
      <LiveArtefactBody
        stream={writingStream({ state: "filled", prose: "Cost is the barrier.", draft: undefined, sources: undefined })}
      />,
    );
    expect(screen.queryByTestId("drawing-on")).toBeNull();
  });

  it("puts a muted marker chip after each cited span, named for its sources, under the revising blur too", () => {
    const draft = `${LEAD} ${FAILED}`;
    const failedAt = draft.indexOf(FAILED);
    const claims = [
      { start: 0, end: LEAD.length, sources: [SOURCES[0], SOURCES[1]] },
      { start: failedAt, end: failedAt + FAILED.length, sources: [SOURCES[3]] },
    ];
    render(
      <LiveArtefactBody
        stream={writingStream(
          { draft, claims, revising: [{ start: failedAt, end: failedAt + FAILED.length }] },
          "Checking claims",
        )}
      />,
    );
    const marks = screen.getAllByRole("img", { name: /^Cited, being checked: / });
    expect(marks).toHaveLength(2);
    expect(marks[0]).toHaveAccessibleName("Cited, being checked: Smith 2023; DfE 2022");
    expect(marks[0]).toHaveAttribute("title", "Smith 2023; DfE 2022");
    expect(marks[1]).toHaveAccessibleName("Cited, being checked: Sustrans 2020");
    for (const mark of marks) {
      // The final marker's chip in its muted look, a dot for the number
      // (owner, round 7); not blue, not a control.
      expect(mark).toHaveTextContent("[·]");
      expect(mark.className).toContain("citation-marker");
      expect(mark.className).toContain("border-line");
      expect(mark.className).toContain("bg-ground");
      expect(mark.className).toContain("text-grey");
      expect(mark.className).toContain("text-caption");
      expect(mark.className).not.toMatch(/blue/);
      expect(mark.tagName).toBe("SPAN");
    }
    // The first mark follows the lead sentence; the second the blurred one.
    expect(marks[0].previousSibling?.textContent).toBe(LEAD);
    expect(marks[1].previousElementSibling).toHaveAttribute("data-revising", "true");
    expect(screen.queryAllByRole("button", { name: /Cited/ })).toHaveLength(0);
  });

  it("the settled section carries no provisional marks", () => {
    render(
      <LiveArtefactBody
        stream={writingStream({ state: "filled", prose: LEAD, draft: undefined, claims: undefined })}
      />,
    );
    expect(screen.queryAllByTestId("provisional-mark")).toHaveLength(0);
  });

  it("draftParagraphs ends a run where a citation ends, across paragraphs and code points", () => {
    const draft = "A \u{1F600} b.\n\nC d.";
    const claim = { start: 0, end: 3, sources: [SOURCES[0]] };
    const tail = { start: 10, end: 12, sources: [SOURCES[1]] };
    const paragraphs = draftParagraphs(draft, [], [claim, tail, { start: 0, end: 99, sources: [] }]);
    expect(paragraphs).toEqual([
      [
        { text: "A \u{1F600}", start: 0, revising: false, marks: [claim], markAt: 0 },
        { text: " b.", start: 3, revising: false },
      ],
      [{ text: "C d.", start: 8, revising: false, marks: [tail], markAt: 1 }],
    ]);
  });
});

describe("the live page looks like the final page (task 058, owner round 7)", () => {
  const SMITH = "Smith 2023";
  const DFE = "DfE 2022";
  // The pre-round-8 frame: no ids, no quote, so the markers are inert.
  const citation = (start: number, end: number, n: number, title: string, tier: string | null = "tier_2") => ({
    start,
    end,
    n,
    sourceId: `s${n}`,
    title,
    tier,
    citationId: null,
    claimId: null,
    quote: "",
  });

  it("gives a checked section the report's numbered markers after the cited words, not controls yet", () => {
    const prose = `${LEAD} Subsidy design matters.`;
    render(
      <LiveArtefactBody
        stream={writingStream({
          state: "filled",
          prose,
          draft: undefined,
          citations: [citation(0, LEAD.length, 3, SMITH), citation(0, LEAD.length, 5, DFE), citation(LEAD.length + 1, prose.length, 3, SMITH)],
        })}
      />,
    );
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    const markers = within(costs).getAllByRole("img", { name: /details when the report is ready$/ });
    expect(markers).toHaveLength(2);
    expect(markers[0]).toHaveTextContent("[3,5]");
    expect(markers[0]).toHaveAccessibleName("Citations 3, 5, Smith 2023; DfE 2022; details when the report is ready");
    expect(markers[1]).toHaveAccessibleName("Citation 3, Smith 2023; details when the report is ready");
    expect(markers[1]).toHaveAttribute("title", SMITH);
    // The final marker's look, without the control's cursor.
    expect(markers[0].className).toContain("bg-blue-tint-2");
    expect(markers[0].className).not.toContain("cursor-pointer");
    expect(markers[0].previousElementSibling).toHaveTextContent(LEAD);
    expect(within(costs).queryByRole("button")).toBeNull();
    // The report's own prose component sets it.
    expect(costs.querySelectorAll("p.whitespace-pre-line")).toHaveLength(1);
  });

  it("keeps the pending markers on the draft layer as it fades, and the numbered ones under it", () => {
    mockReducedMotion(false);
    const claims = [{ start: 0, end: LEAD.length, sources: [{ sourceId: "s3", title: SMITH }] }];
    const { rerender } = render(
      <LiveArtefactBody stream={writingStream({ draft: LEAD, claims }, "Checking claims")} />,
    );
    rerender(
      <LiveArtefactBody
        stream={writingStream({
          state: "filled",
          prose: LEAD,
          draft: undefined,
          claims: undefined,
          citations: [citation(0, LEAD.length, 1, SMITH)],
        })}
      />,
    );
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    const ghost = costs.querySelector(".anim-settle-out") as HTMLElement;
    expect(within(ghost).getByTestId("provisional-mark")).toHaveTextContent("[·]");
    expect(within(costs).getByRole("img", { name: /^Citation 1, Smith 2023/ })).toHaveTextContent("[1]");
  });

  it("orders the sections as the report does and heads the parts, with contents beside the page", () => {
    const stream = streamWith(
      [
        { index: 0, title: "Key findings", focus: "", state: "planned", role: "key_findings" },
        { index: 1, title: "Costs", focus: "", state: "writing", role: "body" },
        { index: 2, title: "Conclusions", focus: "", state: "planned", role: "body" },
        { index: 3, title: "Case studies", focus: "", state: "planned", role: "case_studies" },
      ],
      "running",
    );
    render(<LiveArtefactBody stream={stream} question="What raises take-up?" />);
    const page = screen.getByRole("main");
    expect(within(page).getByText("Report")).toBeInTheDocument();
    // The parts are h2 and the sections inside them h3 (round 10, finding 5).
    const outline = within(page)
      .getAllByRole("heading")
      .map((heading) => `${heading.tagName} ${heading.textContent}`);
    expect(outline).toEqual([
      "H1 What raises take-up?",
      "H2 Executive summary",
      "H3 Key findings",
      "H3 Case studies",
      "H2 Full report",
      "H3 Costs",
      "H3 Conclusions",
    ]);
    // Anchored as the committed report anchors them, so the contents work live.
    const nav = screen.getByRole("navigation");
    // Anchored by the committed order (case studies second on the page).
    expect(within(nav).getByRole("link", { name: "Costs" })).toHaveAttribute("href", "#section-2-costs");
    expect(document.getElementById("section-2-costs")).not.toBeNull();
    // No download, facts strip, ask link or most relevant sources while live.
    expect(screen.queryByText("Most relevant sources")).toBeNull();
    expect(screen.queryByText("Ask about this analysis")).toBeNull();
  });

  it("orders by the skeleton's own roles: case studies last in the skeleton, second on the page", () => {
    const stream = streamWith(
      [
        { index: 0, title: "Key findings", focus: "", state: "planned", role: "key_findings" },
        { index: 1, title: "Costs", focus: "", state: "planned", role: "body" },
        { index: 2, title: "Conclusions", focus: "", state: "planned", role: "body" },
        { index: 3, title: "Examples", focus: "", state: "planned", role: "case_studies" },
      ] as unknown as LiveSection[],
      "running",
    );
    render(<LiveArtefactBody stream={stream} />);
    const headings = within(screen.getByRole("main"))
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);
    expect(headings).toEqual(["Key findings", "Examples", "Costs", "Conclusions"]);
  });

  it("lays the case-study cards out as the report does, one by one as each closes", () => {
    const stream = streamWith(
      [
        { index: 0, title: "Key findings", focus: "", state: "planned" },
        {
          index: 1,
          title: "Case studies",
          focus: "",
          state: "writing",
          role: "case_studies",
          cards: [{ title: "Leeds pilot", prose: "Take-up rose after direct payment." }],
        },
      ],
      "running",
    );
    render(<LiveArtefactBody stream={stream} />);
    const section = screen.getByRole("heading", { name: "Case studies" }).closest("section") as HTMLElement;
    expect(within(section).getByText("Relevant examples from the cited evidence.")).toBeInTheDocument();
    const cards = within(section).getAllByRole("listitem");
    expect(cards).toHaveLength(1);
    // Each case study in its ruled card (owner, round 11); the title an h4
    // under the section's h3 (round 10, finding 5).
    expect(cards[0].parentElement).toHaveClass("grid", "gap-3");
    expect(cards[0].parentElement).not.toHaveClass("divide-y");
    expect(cards[0]).toHaveClass("border", "border-line", "p-4");
    expect(within(cards[0]).getByRole("heading", { level: 4, name: "Leeds pilot" })).toHaveClass("font-bold");
    expect(cards[0]).toHaveTextContent("Take-up rose after direct payment.");
    expect(within(section).queryByTestId("placeholder-lines")).toBeNull();
  });

  it("renders a completed case-studies slot as its cards with their markers, never as bold markup", () => {
    const prose = "**Leeds pilot**\nTake-up rose.\n\n**Bristol letters**\nLetters helped.";
    const stream = streamWith(
      [
        { index: 0, title: "Key findings", focus: "", state: "planned", role: "key_findings" },
        {
          index: 1,
          title: "Case studies",
          focus: "",
          state: "filled",
          role: "case_studies",
          prose,
          citations: [citation(16, 29, 2, SMITH)],
        },
      ],
      "running",
    );
    render(<LiveArtefactBody stream={stream} />);
    const section = screen.getByRole("heading", { name: "Case studies" }).closest("section") as HTMLElement;
    expect(section).not.toHaveTextContent("**");
    const cards = within(section).getAllByRole("listitem");
    expect(cards.map((card) => within(card).getByText(/Leeds pilot|Bristol letters/).textContent)).toEqual([
      "Leeds pilot",
      "Bristol letters",
    ]);
    expect(within(cards[0]).getByRole("img", { name: /^Citation 2, Smith 2023/ })).toHaveTextContent("[2]");
  });

  it("reads a completed case-studies slot back into its cards, each with its own markers", () => {
    const prose = "**Leeds pilot**\nTake-up rose.\n\n**Bristol letters**\nLetters helped.";
    const bristolAt = Array.from(prose).length - "Letters helped.".length;
    const cards = liveCaseStudyCards(prose, [citation(16, 29, 2, SMITH), citation(bristolAt, bristolAt + 15, 4, DFE)]);
    expect(cards.map((card) => [card.title, card.prose])).toEqual([
      ["Leeds pilot", "Take-up rose."],
      ["Bristol letters", "Letters helped."],
    ]);
    expect(cards[0].claims?.[0].span).toEqual([0, 13]);
    expect(cards[1].claims?.[0].span).toEqual([0, 15]);
    expect(cards[1].claims?.[0].citations?.[0].n).toBe(4);
  });

  it("grows a numbered references list as sections are checked: titles only, no links", () => {
    const stream = streamWith(
      [
        { index: 0, title: "Key findings", focus: "", state: "planned" },
        { index: 1, title: "Costs", focus: "", state: "filled", prose: LEAD, citations: [citation(0, 10, 2, DFE), citation(0, 10, 1, SMITH)] },
        { index: 2, title: "Outreach", focus: "", state: "filled", prose: LEAD, citations: [citation(0, 10, 1, SMITH)] },
      ],
      "running",
    );
    render(<LiveArtefactBody stream={stream} />);
    const references = screen.getByRole("region", { name: "References" });
    const items = within(references).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([`[1]${SMITH}`, `[2]${DFE}`]);
    for (const item of items) expect(within(item).queryByRole("button")).toBeNull();
    expect(within(references).queryByRole("link")).toBeNull();
    expect(liveReferences(Object.values(stream.liveSections))).toEqual([
      { n: 1, title: SMITH },
      { n: 2, title: DFE },
    ]);
  });
});

describe("round 8: the Result tab while it is written (task 058, owner notes 2026-11-05)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });
  const SMITH = { sourceId: "s1", title: "Smith 2023" };
  const DFE = { sourceId: "s2", title: "DfE 2022" };
  const SECOND = "Subsidy design matters more than its size.";

  it("breathes the muted chips in turn while the claims are checked, and only then", () => {
    const draft = `${LEAD} ${SECOND}`;
    const claims = [
      { start: 0, end: LEAD.length, sources: [SMITH] },
      { start: LEAD.length + 1, end: draft.length, sources: [DFE] },
    ];
    const { rerender } = render(<LiveArtefactBody stream={writingStream({ draft, claims }, "Writing")} />);
    const costs = () => screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    expect(within(costs()).getByTestId("draft-prose")).not.toHaveClass("draft-checking");
    rerender(<LiveArtefactBody stream={writingStream({ draft, claims }, "Checking claims")} />);
    expect(within(costs()).getByTestId("draft-prose")).toHaveClass("draft-checking");
    // Each chip knows its turn in the section, in document order (the
    // stylesheet offsets each by 150 ms).
    const chips = within(costs()).getAllByTestId("provisional-mark");
    expect(chips.map((chip) => chip.style.getPropertyValue("--mark-at"))).toEqual(["0", "1"]);
    expect(chips[0]).toHaveClass("pending-mark");
    // A repair is not a check: the chips are still.
    rerender(<LiveArtefactBody stream={writingStream({ draft, claims }, "Revising 1 claim")} />);
    expect(within(costs()).getByTestId("draft-prose")).not.toHaveClass("draft-checking");
  });

  it("reads the key findings' and the introduction's own section lines as theirs", () => {
    const stream = streamWith(
      [
        { index: 0, title: "What appears to help", focus: "", state: "writing", role: "key_findings", draft: "Breakfast" },
        { index: 1, title: "Costs", focus: "", state: "filled", role: "body", prose: "Costs prose." },
      ],
      "running",
    );
    render(
      <LiveArtefactBody
        stream={{
          ...stream,
          liveness: {
            synthesise: {
              activity: "Checking claims",
              section: "Key findings",
              heartbeat: false,
              dropped: 0,
              occurredAt: "2026-07-21T10:05:00Z",
            },
          },
        }}
      />,
    );
    const findings = screen.getByRole("heading", { name: "What appears to help" }).closest("section") as HTMLElement;
    expect(within(findings).getByTestId("action-line")).toHaveTextContent("Checking claims");
    // A plain sentence stays prose: only "- " lines make the list.
    expect(within(findings).queryByRole("listitem")).toBeNull();
  });

  it("staggers the revising blur by 120 ms per span, in document order", () => {
    const draft = `${LEAD} ${FAILED} ${SECOND}`;
    const failedAt = draft.indexOf(FAILED);
    const secondAt = draft.indexOf(SECOND);
    render(
      <LiveArtefactBody
        stream={writingStream(
          {
            draft,
            revising: [
              { start: secondAt, end: secondAt + SECOND.length },
              { start: failedAt, end: failedAt + FAILED.length },
            ],
          },
          "Revising 2 claims",
        )}
      />,
    );
    const spans = [...document.querySelectorAll<HTMLElement>("[data-revising='true']")];
    expect(spans.map((span) => span.textContent)).toEqual([FAILED, SECOND]);
    expect(spans[0].style.animationDelay).toBe("");
    expect(spans[1].style.animationDelay).toBe("120ms");
  });

  it("settles several repairs one by one, 120 ms apart, then fades the layer off the checked prose", () => {
    mockReducedMotion(false);
    vi.useFakeTimers();
    const NEW_SECOND = "Subsidy design matters more than how large it is, in three studies.";
    const draft = `${LEAD} ${FAILED} ${SECOND}`;
    const failedAt = draft.indexOf(FAILED);
    const secondAt = draft.indexOf(SECOND);
    const revising = [
      { start: failedAt, end: failedAt + FAILED.length },
      { start: secondAt, end: secondAt + SECOND.length },
    ];
    const { rerender } = render(
      <LiveArtefactBody stream={writingStream({ draft, revising }, "Revising 2 claims")} />,
    );
    rerender(
      <LiveArtefactBody
        stream={writingStream({
          state: "filled",
          prose: `${LEAD} ${REPAIRED} ${NEW_SECOND}`,
          draft: undefined,
          revising: undefined,
        })}
      />,
    );
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    const layer = within(costs).getByTestId("draft-prose");
    act(() => {
      vi.advanceTimersByTime(0);
    });
    // The first repair has its new words; the second still waits, blurred.
    expect([...layer.querySelectorAll(".draft-settle-in")].map((span) => span.textContent)).toEqual([REPAIRED]);
    expect(layer.querySelector(".draft-revised-held")).toHaveTextContent(SECOND);
    act(() => {
      vi.advanceTimersByTime(120);
    });
    expect([...layer.querySelectorAll(".draft-settle-in")].map((span) => span.textContent)).toEqual([
      REPAIRED,
      NEW_SECOND,
    ]);
    expect(layer.querySelector(".draft-revised-held")).toBeNull();
    // The checked prose waited under the layer, unseen, and takes over.
    expect(costs.querySelector(".opacity-0")).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(costs.querySelector(".anim-settle-out")).not.toBeNull();
    expect(costs.querySelector(".opacity-0")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(within(costs).queryByTestId("draft-prose")).toBeNull();
    expect(costs).toHaveTextContent(`${LEAD} ${REPAIRED} ${NEW_SECOND}`);
  });

  it("lines the repaired spans up with the checked prose, or settles at once when they do not line up", () => {
    const draft = `${LEAD} ${FAILED} ${SECOND}`;
    const failedAt = draft.indexOf(FAILED);
    const secondAt = draft.indexOf(SECOND);
    const revising = [
      { start: failedAt, end: failedAt + FAILED.length },
      { start: secondAt, end: secondAt + SECOND.length },
    ];
    // Two failed sentences one space apart: the shared " " is placed after
    // the full stop nearest where the new text's length puts it.
    const plan = settlePlan(draft, `${LEAD} ${REPAIRED} Shorter. Two sentences now.`, revising);
    expect(plan).toEqual([
      { kind: "same", text: `${LEAD} `, from: 0 },
      { kind: "repaired", old: FAILED, text: REPAIRED, from: failedAt, at: 0 },
      { kind: "same", text: " ", from: failedAt + FAILED.length },
      { kind: "repaired", old: SECOND, text: "Shorter. Two sentences now.", from: secondAt, at: 1 },
    ]);
    expect(settlePlan(draft, "Something else entirely.", revising)).toBeNull();
    expect(settlePlan(draft, draft, [])).toBeNull();
    // A citation that ends in a settled span follows its new words.
    const single = settlePlan(`${LEAD} ${FAILED}`, `${LEAD} ${REPAIRED}`, [revising[0]]) ?? [];
    const step = settleStep(single, 1, [{ start: failedAt, end: failedAt + FAILED.length, sources: [SMITH] }]);
    expect(step.text).toBe(`${LEAD} ${REPAIRED}`);
    expect(step.settling).toEqual([{ start: failedAt, end: failedAt + REPAIRED.length }]);
    expect(step.claims[0].end).toBe(failedAt + REPAIRED.length);
  });

  it("writes the key findings as the report's list: items, bold leads, muted chips", () => {
    const draft = "- Cost decides take-up: more than the subsidy's size.\n- Outreach works when";
    const claims = [{ start: 2, end: 53, sources: [SMITH] }];
    const stream = streamWith(
      [
        { index: 0, title: "Key findings", focus: "", state: "writing", role: "key_findings", draft, claims },
        { index: 1, title: "Costs", focus: "", state: "filled", prose: "Costs prose." },
      ],
      "running",
    );
    render(<LiveArtefactBody stream={stream} />);
    const findings = screen.getByRole("heading", { name: "Key findings" }).closest("section") as HTMLElement;
    const items = within(findings).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0].querySelector("strong")).toHaveTextContent("Cost decides take-up:");
    expect(items[0]).toHaveTextContent("Cost decides take-up: more than the subsidy's size.[·]");
    expect(items[0]).not.toHaveTextContent("- Cost");
    expect(within(items[0]).getByTestId("provisional-mark")).toBeInTheDocument();
    expect(items[1]).toHaveTextContent("Outreach works when");
    expect(within(findings).queryByText("Written last, after the sections are checked.")).toBeNull();
  });

  it("writes the introduction under the Full report heading, with no heading of its own", () => {
    const sections: LiveSection[] = [
      { index: 0, title: "Key findings", focus: "", state: "filled", role: "key_findings", prose: "- Headline." },
      { index: 1, title: "Costs", focus: "", state: "filled", role: "body", prose: "Costs prose." },
      { index: 2, title: "Full report", focus: "", state: "planned", role: "intro" },
    ];
    const { rerender } = render(<LiveArtefactBody stream={streamWith(sections, "running")} />);
    const headings = () =>
      within(screen.getByRole("main"))
        .getAllByRole("heading")
        .filter((heading) => heading.tagName !== "H1")
        .map((heading) => heading.textContent);
    // Not a section: the page's order and contents are as before.
    expect(headings()).toEqual(["Executive summary", "Key findings", "Full report", "Costs"]);
    expect(screen.queryByTestId("intro-draft")).toBeNull();
    expect(within(screen.getByRole("navigation")).queryAllByRole("link", { name: "Full report" })).toHaveLength(1);

    const writing = { ...sections[2], state: "writing" as const, draft: "This report sets out" };
    rerender(
      <LiveArtefactBody
        stream={{
          ...streamWith([sections[0], sections[1], writing], "running"),
          liveness: {
            synthesise: {
              activity: "Writing the introduction",
              section: "Full report",
              heartbeat: false,
              dropped: 0,
              occurredAt: "2026-07-21T10:05:00Z",
            },
          },
        }}
      />,
    );
    const part = document.getElementById("full-report") as HTMLElement;
    expect(within(part).getByTestId("intro-draft")).toHaveTextContent("This report sets out");
    expect(within(part).getByTestId("action-line")).toHaveTextContent("Writing the introduction");
    expect(within(part).queryByTestId("drawing-on")).toBeNull();
    expect(headings()).toEqual(["Executive summary", "Key findings", "Full report", "Costs"]);

    rerender(
      <LiveArtefactBody
        stream={streamWith(
          [sections[0], sections[1], { ...sections[2], state: "filled", prose: "This report sets out what works." }],
          "running",
        )}
      />,
    );
    const intro = within(document.getElementById("full-report") as HTMLElement).getByText(
      "This report sets out what works.",
    );
    expect(intro.tagName).toBe("P");
    expect(intro).toHaveClass("max-w-prose-measure");
  });

  it("shows the most relevant sources as each note is written, in the final layout", () => {
    const stream = streamWith(
      [
        { index: 0, title: "Key findings", focus: "", state: "filled", role: "key_findings", prose: "- Headline." },
        { index: 1, title: "Costs", focus: "", state: "filled", role: "body", prose: "Costs prose." },
      ],
      "running",
    );
    const { rerender } = render(<LiveArtefactBody stream={stream} />);
    expect(screen.queryByRole("heading", { name: "Most relevant sources" })).toBeNull();
    const notes = [{ sourceId: "s1", title: "Smith 2023", note: "The largest trial of direct payment." }];
    rerender(<LiveArtefactBody stream={{ ...stream, liveSourceNotes: notes } as RunStreamState} />);
    const block = screen.getByRole("heading", { name: "Most relevant sources" }).closest("section") as HTMLElement;
    expect(within(block).getByText("Sources cited most often in this report.")).toBeInTheDocument();
    const items = within(block).getAllByRole("listitem");
    expect(items).toHaveLength(1);
    // In the case studies' ruled card (owner, round 11).
    expect(items[0]).toHaveClass("border", "border-line", "p-4", "anim-rise");
    expect(within(items[0]).getByText("Smith 2023")).toHaveClass("font-bold");
    expect(within(items[0]).getByText("The largest trial of direct payment.")).toBeInTheDocument();
    // Not links yet, no chips yet.
    expect(within(block).queryByRole("button")).toBeNull();
    expect(within(block).queryByText(/Cited by/)).toBeNull();
    // The executive summary's last part, before the full report's sections,
    // as the report sets it (owner, round 11).
    expect(
      block.compareDocumentPosition(screen.getByRole("heading", { name: "Costs" })) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      block.compareDocumentPosition(screen.getByRole("heading", { name: "Key findings" })) &
        Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
    expect(within(screen.getByRole("navigation")).getByRole("link", { name: "Most relevant sources" })).toHaveAttribute(
      "href",
      "#sources",
    );
    rerender(
      <LiveArtefactBody
        stream={
          {
            ...stream,
            liveSourceNotes: [...notes, { sourceId: "s2", title: "DfE 2022", note: "The national survey." }],
          } as RunStreamState
        }
      />,
    );
    expect(within(block).getAllByRole("listitem")).toHaveLength(2);
  });
});

describe("ReportToBe", () => {
  it("is the question and one sentence, nothing else", () => {
    const { container } = render(<ReportToBe question="What raises take-up?" />);
    expect(screen.getByRole("heading", { level: 1, name: "What raises take-up?" })).toBeInTheDocument();
    expect(screen.getByText("The report's sections are set out when writing begins.")).toBeInTheDocument();
    expect(container.querySelectorAll("p")).toHaveLength(1);
    expect(screen.queryByText(/Preparing your results/)).toBeNull();
  });
});

describe("re-run notice wording", () => {
  it("counts whole minutes, zero under a minute", () => {
    const now = new Date("2026-11-05T10:00:00Z");
    expect(minutesSince("2026-11-05T09:57:40Z", now.getTime())).toBe(2);
    // Task 058 polish ruling: under one minute the line reads "just now", so the count may be 0.
    expect(minutesSince("2026-11-05T09:59:50Z", now.getTime())).toBe(0);
  });
});

describe("AnnotatedProse", () => {
  const claim = (id: string, span: number[] | null, text = "") => ({
    claim_id: id,
    claim_type: "citation" as const,
    text,
    span,
    citations: [],
  });
  const noop = () => undefined;

  it("wraps exactly the spanned prose in the claim affordance", () => {
    render(
      <TooltipProvider>
        <AnnotatedProse
          block={{ block_id: "b1", prose: "Money talks loudly.", claims: [claim("c1", [6, 11])] }}
          onOpenClaim={noop}
        />
      </TooltipProvider>,
    );
    // The words are a pointer target, not a button or a tab stop (round 10,
    // finding 4): the marker after them is the control.
    const span = screen.getByText("talks");
    expect(span).toHaveClass("citation-marker", "cursor-pointer");
    expect(span).not.toHaveAttribute("role");
    expect(span).not.toHaveAttribute("tabindex");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("slices spans by code points so astral characters never shift offsets", () => {
    // "🌍🌍 policy works": in code points "policy" is [3, 9]; in UTF-16 code
    // units it would be [5, 11] — the Python annotator counts code points.
    render(
      <TooltipProvider>
        <AnnotatedProse
          block={{ block_id: "b1", prose: "🌍🌍 policy works", claims: [claim("c1", [3, 9])] }}
          onOpenClaim={noop}
        />
      </TooltipProvider>,
    );
    expect(screen.getByText("policy")).toHaveClass("citation-marker");
  });

  it("skips overlapping spans (first wins) and drops invalid spans cleanly", () => {
    render(
      <TooltipProvider>
        <AnnotatedProse
          block={{
            block_id: "b1",
            prose: "Plain prose stays whole.",
            claims: [
              claim("c1", [0, 5]),
              claim("c2", [3, 8]), // overlaps c1 — skipped
              claim("c3", [10, 999]), // oversize — dropped
              claim("c4", [-2, 4]), // negative — dropped
              claim("c5", [7, 7]), // empty — dropped
            ],
          }}
          onOpenClaim={noop}
        />
      </TooltipProvider>,
    );
    const spans = document.querySelectorAll("span.citation-marker");
    expect(spans).toHaveLength(1);
    expect(spans[0]).toHaveTextContent("Plain");
    // The prose renders complete despite the dropped spans.
    expect(screen.getByText(/stays whole/)).toBeInTheDocument();
  });
});

describe("renderLeadColonBullet double-citation suppression", () => {
  it("shows exactly one [n] marker when a citation span crosses the colon", () => {
    // "- Universal breakfast: helped eleven evaluations." — the claim covers
    // the entire text; it spans the colon, so both the lead half (before `:`)
    // and the rest half (after `: `) would independently try to render [n].
    // The fix suppresses [n] on the lead half so it appears exactly once.
    const prose = "- Universal breakfast: helped eleven evaluations.";
    const blockText = "Universal breakfast: helped eleven evaluations.";
    const spanStart = prose.indexOf("Universal");
    const block = {
      block_id: "b-cross",
      prose,
      claims: [
        {
          claim_id: "c-cross",
          claim_type: "citation" as const,
          text: blockText,
          span: [spanStart, spanStart + blockText.length] as [number, number],
          citations: [
            {
              citation_id: "cit-1",
              n: 7,
              source_title: "A study",
              quote: "",
              appraisal_label: null,
              source_id: null,
              evidence_type: null,
            },
          ],
        },
      ],
    };
    render(
      <TooltipProvider>
        <AnnotatedProse block={block} onOpenClaim={() => undefined} />
      </TooltipProvider>,
    );
    const markerButtons = screen
      .getAllByRole("button")
      .filter((btn) => /\[7\]/.test(btn.textContent ?? ""));
    expect(markerButtons).toHaveLength(1);
  });
});

describe("showLiveArtefact", () => {
  const latest = {
    capability_run_id: "r1",
    status: "succeeded" as const,
    started_at: "2026-07-21T10:00:00Z",
    ended_at: "2026-07-21T10:12:00Z",
  };

  it("does not swap to LiveArtefactBody while replaying a succeeded run", () => {
    const stream = streamWith(LIVE_SECTIONS, "running");
    expect(showLiveArtefact(stream, latest)).toBe(false);
  });

  it("still shows the live body for an in-flight run", () => {
    const stream = streamWith(LIVE_SECTIONS, "running");
    expect(
      showLiveArtefact(stream, {
        ...latest,
        status: "running",
        ended_at: null,
      }),
    ).toBe(true);
  });

  it("still shows the live body when a new run id is streaming", () => {
    const stream = streamWith(LIVE_SECTIONS, "running");
    expect(
      showLiveArtefact(stream, { ...latest, capability_run_id: "r-previous" }),
    ).toBe(true);
  });

  it("keeps the terminal-partial view after a failed run", () => {
    const stream = streamWith(LIVE_SECTIONS, "failed");
    expect(
      showLiveArtefact(stream, {
        ...latest,
        status: "failed",
        ended_at: "2026-07-21T10:12:00Z",
      }),
    ).toBe(true);
  });
});

describe("CitationProvenanceBlock authorships (042)", () => {
  const baseContext = {
    isPending: false,
    isError: false,
    data: {
      context: "The quoted passage sits here.",
      span_start: 0,
      span_end: 10,
      clamped: false,
      year: 2022,
      venue: "BMJ Open",
      authorships: [
        { name: "Alex Sampleton", institutions: ["University of Exampleshire"] },
        { name: "Casey Mockford", institutions: ["University of Exampleshire", "Institute of Fictional Studies"] },
      ],
    },
  };

  it("bounds a citation in its own box: the judge's callout, then the References-form source line, then the quote (round 13)", () => {
    const { container } = render(
      <CitationProvenanceBlock
        n={1}
        sourceTitle="A study"
        sourceRef={null}
        onOpenDossier={() => {}}
        context={baseContext}
        quote="The quoted"
        judgement={{ label: "Tier 2 · grounded", words: "The passage says so." }}
      />,
    );
    const block = container.querySelector("[data-citation-block]") as HTMLElement;
    // Its own box, a hairline all round: the coloured rule is the Claim's.
    expect(block).toHaveClass("border", "border-line", "p-4");
    expect(block.className).not.toMatch(/border-l-/);
    // Judge and Quote labelled in the dossier's style; the source line not.
    const labels = [...block.querySelectorAll("[data-provenance-label]")].map((label) => label.textContent);
    expect(labels).toEqual(["Judge", "Quote"]);
    // The AI's judgement carries the blue diamond; the other labels do not.
    const marks = block.querySelectorAll("[data-testid='ai-mark']");
    expect(marks).toHaveLength(1);
    expect(marks[0].closest("[data-provenance-label]")).toHaveTextContent("Judge");
    // The judge in a tinted callout: the tier in Navy Semibold, its words at Body Grey.
    const verdict = screen.getByText("Tier 2 · grounded");
    expect(verdict).toHaveClass("font-semibold", "text-navy");
    expect(verdict.parentElement).toHaveClass("bg-blue-tint-2");
    expect(screen.getByText("The passage says so.")).toHaveClass("text-body", "text-grey");
    // The source, title first: "[1] Title" in Navy Semibold, then the byline in Grey.
    const name = screen.getByText("A study");
    expect(name.closest("p")).toHaveTextContent(/^\[1\]\s*A study$/);
    expect(name.closest("p")).toHaveClass("font-semibold", "text-navy");
    const byline = screen.getByText("Sampleton A, Mockford C · 2022 · BMJ Open");
    expect(byline).toHaveClass("text-body", "text-grey");
    expect(name.compareDocumentPosition(byline) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The source line has its own room: 12 px above and below.
    expect(name.closest("p")?.parentElement).toHaveClass("my-3");
    expect(verdict.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The quote, highlighted in its passage, last.
    const quote = screen.getByText("The quoted");
    expect(quote.tagName).toBe("MARK");
    expect(name.compareDocumentPosition(quote) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Names only, as the References: the institutions are the dossier's.
    expect(container.querySelector("sup")).toBeNull();
    expect(screen.queryByText(/University of Exampleshire/)).toBeNull();
  });

  it("tints an unsupported verdict's callout red and an unchecked one grey", () => {
    const tint = (label: string) => {
      const { unmount } = render(
        <CitationProvenanceBlock
          n={1}
          sourceTitle="A study"
          sourceRef={null}
          onOpenDossier={() => {}}
          context={baseContext}
          quote="The quoted"
          judgement={{ label, words: "Words." }}
        />,
      );
      const classes = screen.getByText(label).parentElement?.className ?? "";
      unmount();
      return classes;
    };
    expect(tint("Unsupported")).toContain("bg-red-tint");
    expect(tint("Unchecked")).toContain("bg-ground");
  });

  it("starts the source line at the number and title when the context carries no authors", () => {
    render(
      <CitationProvenanceBlock
        n={1}
        sourceTitle="A study"
        sourceRef={null}
        onOpenDossier={() => {}}
        context={{ ...baseContext, data: { ...baseContext.data, authorships: [] } }}
        quote="The quoted"
      />,
    );
    expect(screen.getByText("A study").closest("p")).toHaveTextContent(/^\[1\]\s*A study$/);
    expect(screen.getByText("2022 · BMJ Open")).toHaveClass("text-grey");
  });
});

describe("ReferencesSection (042 item 1; round 10, C5)", () => {
  const references = [
    {
      n: 1,
      title: "Universal breakfast clubs and diet quality",
      year: 2022,
      venue: "BMJ Open",
      url: "https://doi.org/10.1000/example.1",
      authorships: [
        { name: "Alex Sampleton", institutions: ["University of Exampleshire"] },
        { name: "Casey Mockford", institutions: [] },
      ],
    },
    // Corporate author (D2): the issuing organisation in the author slot, as written.
    { n: 2, title: "School food policy brief", year: 2023, venue: null, authorships: [{ name: "Example Policy Institute", institutions: [] }] },
    // Honest absence (D1): no authors, so the entry starts at its title.
    { n: 12, title: "Uploaded evidence note", year: null, venue: null, authorships: [] },
  ];

  it("opens a reference's source from its number, and leaves the number plain while the report is written (round 14)", async () => {
    const user = userEvent.setup();
    const open = vi.fn();
    const view = render(<ReferencesSection references={references} onOpenReference={open} />);
    await user.click(screen.getByRole("button", { name: "References" }));
    await user.click(screen.getByRole("button", { name: "Source 12: Uploaded evidence note" }));
    expect(open).toHaveBeenCalledWith("Uploaded evidence note");
    view.unmount();
    render(<ReferencesSection references={references} defaultOpen />);
    expect(screen.queryByRole("button", { name: /^Source 1:/ })).toBeNull();
    expect(screen.getByText("[1]")).toHaveClass("text-grey");
  });

  it("sets each reference in the citation form, authors and year first, nothing invented when absent", async () => {
    const user = userEvent.setup();
    render(<ReferencesSection references={references} onOpenReference={() => {}} />);
    await user.click(screen.getByRole("button", { name: "References" }));
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent(
      "[1]Sampleton A, Mockford C (2022). Universal breakfast clubs and diet quality. BMJ Open. doi.org/10.1000/example.1",
    );
    expect(items[1]).toHaveTextContent("[2]Example Policy Institute (2023). School food policy brief.");
    expect(items[2]).toHaveTextContent("[12]Uploaded evidence note.");
    expect(items[2].textContent).not.toContain("()");
    // Names only in the list (D4) — superscript markers belong to the sheets.
    expect(items[0].querySelector("sup")).toBeNull();
    // The number sits in its own column in Electric Blue and opens the
    // source's sheet (owner, round 14).
    const number = within(items[0]).getByRole("button", { name: "Source 1: Universal breakfast clubs and diet quality" });
    expect(number).toHaveTextContent("[1]");
    expect(number).toHaveClass("w-9", "text-right", "tabular-nums", "text-blue");
  });

  it("links the title to its dossier and the address out, the scheme only in print", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<ReferencesSection references={references} onOpenReference={onOpen} defaultOpen />);
    const title = screen.getByRole("link", { name: "Universal breakfast clubs and diet quality" });
    expect(title).toHaveAttribute("href", expect.stringContaining("source=Universal+breakfast+clubs+and+diet+quality"));
    await user.click(title);
    expect(onOpen).toHaveBeenCalledWith("Universal breakfast clubs and diet quality");
    const address = screen.getByRole("link", { name: /doi\.org\/10\.1000\/example\.1/ });
    expect(address).toHaveAttribute("href", "https://doi.org/10.1000/example.1");
    expect(address).toHaveAttribute("target", "_blank");
    expect(within(address).getByText("doi.org/10.1000/example.1")).toHaveClass("print:hidden");
    expect(within(address).getByText("https://doi.org/10.1000/example.1")).toHaveClass("hidden", "print:inline");
    // The heading stays a heading with the button inside it (GOV.UK pattern).
    expect(screen.getByRole("heading", { level: 2, name: "References" }).querySelector("button")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("shows only the titles, not links, while the report is live", () => {
    render(<ReferencesSection references={[{ n: 1, title: "Smith 2023" }]} defaultOpen />);
    expect(screen.getByRole("listitem")).toHaveTextContent(/^\[1\]Smith 2023$/);
    expect(screen.queryByRole("link")).toBeNull();
  });
});

describe("ProvenanceSheet footer (042 item 5)", () => {
  it("renders the claim without the removed tagline", () => {
    render(
      <ProvenanceSheet claimTexts={["A claim."]} onClose={() => {}}>
        {null}
      </ProvenanceSheet>,
    );
    expect(screen.getByText("A claim.")).toBeInTheDocument();
    expect(screen.queryByText(/Every claim links to the exact passage/)).toBeNull();
  });
});

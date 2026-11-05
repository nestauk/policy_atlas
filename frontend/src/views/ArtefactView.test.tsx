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
  minutesSince,
  orderSections,
  ProvenanceSheet,
  ReferencesSection,
  reportDateLabel,
  ReportToBe,
  showLiveArtefact,
} from "./ArtefactView";

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

  it("shows the writer's action line under the active heading until the first delta", () => {
    const { rerender } = render(<LiveArtefactBody stream={writingStream()} />);
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section");
    expect(costs).not.toBeNull();
    const action = within(costs as HTMLElement).getByTestId("action-line");
    expect(action).toHaveTextContent("Looking for: evidence on subsidy uptake");
    expect(action).not.toHaveAttribute("aria-hidden");
    // The section's mark is the run's blue 6 px square (task 058, owner 2026-11-05).
    const mark = within(costs as HTMLElement).getByTestId("section-dot");
    expect(mark).toHaveClass("bg-blue", "size-1.5");
    expect(mark.className).not.toMatch(/rounded|bg-yellow/);

    rerender(<LiveArtefactBody stream={writingStream({ draft: "Cost is the" }, "Writing")} />);
    const after = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    expect(within(after).getByTestId("action-line")).toHaveAttribute("aria-hidden", "true");
    expect(within(after).queryByTestId("placeholder-lines")).toBeNull();
    expect(within(after).getByText("Cost is the")).toBeInTheDocument();
  });

  it("appends drafted prose as plain text with paragraph breaks and no claim marker", () => {
    const { rerender, container } = render(
      <LiveArtefactBody stream={writingStream({ draft: "Cost is" }, "Writing")} />,
    );
    rerender(
      <LiveArtefactBody
        stream={writingStream({ draft: `${LEAD} **Bold?** [1]\n\nSubsidy design matters.` }, "Writing")}
      />,
    );
    const costs = screen.getByRole("heading", { name: "Costs" }).closest("section") as HTMLElement;
    const paragraphs = costs.querySelectorAll("p.whitespace-pre-line");
    expect(paragraphs).toHaveLength(2);
    // Plain text: Markdown is not interpreted, and nothing is a marker.
    expect(paragraphs[0]).toHaveTextContent(`${LEAD} **Bold?** [1]`);
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

  it("settles the draft into the final prose with a fading layer, then marks nothing", () => {
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
    // The draft layer sits over the settled prose while it fades.
    const ghost = costs.querySelector(".anim-settle-out");
    expect(ghost).not.toBeNull();
    expect(ghost).toHaveTextContent(FAILED);
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(costs.querySelector(".anim-settle-out")).toBeNull();
    expect(costs).toHaveTextContent(REPAIRED);
    expect(costs).not.toHaveTextContent(FAILED);
    // A done section carries no marker of any kind.
    expect(costs.querySelector("[data-revising]")).toBeNull();
    expect(within(costs).queryByTestId("section-dot")).toBeNull();
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

  it("drops the key-findings note when its turn comes, with no footer under the sections", () => {
    const stream = streamWith(
      [
        { index: 0, title: "Key findings", focus: "", state: "writing" },
        { index: 1, title: "Costs", focus: "", state: "filled", prose: "Costs prose." },
        { index: 2, title: "Outreach", focus: "", state: "filled", prose: "Outreach prose." },
      ],
      "running",
    );
    render(<LiveArtefactBody stream={stream} />);
    expect(screen.queryByText("Written last, after the sections are checked.")).toBeNull();
    const keyFindings = screen.getByRole("heading", { name: "Key findings" }).closest("section") as HTMLElement;
    expect(within(keyFindings).getByTestId("section-dot")).toBeInTheDocument();
    // Owner, 2026-11-05: no "Checking claims and attaching citations" line;
    // the key-findings heading's dot is the one signal.
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
      expect(screen.queryByTestId("section-dot")).toBeNull();
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
      expect(screen.queryByTestId("section-dot")).toBeNull();
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
      { text: "A ", revising: false },
      { text: "\u{1F600}", revising: true },
      { text: " b.", revising: false },
    ]);
    expect(paragraphs[1]).toEqual([{ text: "C d.", revising: false }]);
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
  it("dates the report and counts whole minutes, zero under a minute", () => {
    const now = new Date("2026-11-05T10:00:00Z");
    expect(reportDateLabel("2026-11-03T15:00:00Z", now)).toBe("3 November");
    expect(reportDateLabel("2025-11-03T15:00:00Z", now)).toBe("3 November 2025");
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
    expect(screen.getByRole("button", { name: /talks/ })).toHaveTextContent("talks");
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
    expect(screen.getByRole("button", { name: /policy/ })).toHaveTextContent("policy");
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
    const spans = screen.getAllByRole("button");
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
              grounding_tier: null,
              appraisal_label: null,
              source_id: null,
              grounding_rationale: null,
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

  it("renders authors with markers between the title and the year line, institutions below", () => {
    const { container } = render(
      <CitationProvenanceBlock
        n={1}
        sourceTitle="A study"
        sourceRef={null}
        onOpenDossier={() => {}}
        context={baseContext}
        quote="The quoted"
      />,
    );
    expect(screen.getAllByText(/Alex Sampleton/).length).toBeGreaterThan(0);
    expect(screen.getByText("2022 · BMJ Open")).toBeInTheDocument();
    expect(screen.getAllByText(/University of Exampleshire/).length).toBeGreaterThan(0);
    const markers = [...container.querySelectorAll("sup")].map((sup) => sup.textContent);
    expect(markers).toEqual(["1", "1,2", "1", "2"]);
  });

  it("renders no author or institution lines when the context carries none", () => {
    const { container } = render(
      <CitationProvenanceBlock
        n={1}
        sourceTitle="A study"
        sourceRef={null}
        onOpenDossier={() => {}}
        context={{ ...baseContext, data: { ...baseContext.data, authorships: [] } }}
        quote="The quoted"
      />,
    );
    expect(container.querySelector("sup")).toBeNull();
    expect(screen.getByText("2022 · BMJ Open")).toBeInTheDocument();
  });
});

describe("ReferencesSection authors (042 item 1)", () => {
  const references = [
    {
      n: 1,
      title: "Universal breakfast clubs and diet quality",
      year: 2022,
      venue: "BMJ Open",
      authorships: [
        { name: "Alex Sampleton", institutions: ["University of Exampleshire"] },
        { name: "Casey Mockford", institutions: [] },
      ],
    },
    // Corporate author (D2): the issuing organisation in the author slot.
    { n: 2, title: "School food policy brief", year: 2023, venue: null, authorships: [{ name: "Example Policy Institute", institutions: [] }] },
    // Honest absence (D1): no authors line, no separator.
    { n: 3, title: "Uploaded evidence note", year: null, venue: null, authorships: [] },
  ];

  it("renders names-only author lines between title and year, nothing when absent", async () => {
    const user = userEvent.setup();
    render(<ReferencesSection references={references} onOpenReference={() => {}} />);
    await user.click(screen.getByRole("button", { name: /References/ }));
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Universal breakfast clubs and diet quality — Alex Sampleton, Casey Mockford (2022) · BMJ Open");
    expect(items[1]).toHaveTextContent("School food policy brief — Example Policy Institute (2023)");
    expect(items[2]).toHaveTextContent("Uploaded evidence note");
    expect(items[2].textContent).not.toContain("—");
    // Names only in the list (D4) — superscript markers belong to the sheets.
    expect(items[0].querySelector("sup")).toBeNull();
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

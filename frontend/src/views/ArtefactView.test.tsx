import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createInitialRunStreamState } from "../store";
import type { LiveSection, RunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { AnnotatedProse, highlightParts, LiveArtefactBody, orderSections, showLiveArtefact } from "./ArtefactView";

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

describe("LiveArtefactBody", () => {
  const sections = LIVE_SECTIONS;

  it("renders planned/writing/filled states in place while running", () => {
    render(<LiveArtefactBody stream={streamWith(sections, "running")} />);
    expect(screen.getByText("Headline claims.")).toBeInTheDocument();
    expect(screen.getByText("Writing this section now…")).toBeInTheDocument();
    expect(screen.getByText(/Prose arrived/)).toBeInTheDocument();
    expect(screen.getByText(/sections appear as they are drafted/)).toBeInTheDocument();
    // The attach-at-commit footer only renders while it is still true.
    expect(screen.getByText(/attached when the write-up completes/)).toBeInTheDocument();
  });

  it("streamed strings render scrubbed (adversarial fixture strings)", () => {
    const withControlChars: LiveSection[] = [
      ...sections,
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
    "shows the terminal banner over streamed sections after a %s ending",
    (runStatus) => {
      render(<LiveArtefactBody stream={streamWith(sections, runStatus)} />);
      expect(screen.getByRole("alert")).toHaveTextContent(
        "This run ended before the write-up completed.",
      );
      // Sections stay visible; the now-false footer and the writing pulse do not.
      expect(screen.getByText(/Prose arrived/)).toBeInTheDocument();
      expect(screen.queryByText(/attached when the write-up completes/)).toBeNull();
      expect(screen.queryByText("Writing this section now…")).toBeNull();
    },
  );

  it("drops a closed-empty section slot (hide, never fake)", () => {
    const withEmpty: LiveSection[] = [
      ...sections,
      { index: 3, title: "Empty key findings", focus: "", state: "filled", prose: "" },
    ];
    render(<LiveArtefactBody stream={streamWith(withEmpty, "running")} />);
    expect(screen.queryByText("Empty key findings")).toBeNull();
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

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createInitialRunStreamState } from "../store";
import type { LiveSection, RunStreamState } from "../store";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { AnnotatedProse, highlightParts, LiveArtefactBody, orderSections } from "./ArtefactView";

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
});

function streamWith(
  sections: LiveSection[],
  runStatus: "running" | "failed" | "aborted" | "interrupted",
): RunStreamState {
  const state = createInitialRunStreamState();
  return {
    ...state,
    run: { id: "r1", status: runStatus },
    liveSections: Object.fromEntries(sections.map((section) => [section.index, section])),
  };
}

describe("LiveArtefactBody", () => {
  const sections: LiveSection[] = [
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

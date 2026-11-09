import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  ABSTRACT_ONLY,
  citationJudgement,
  evidenceTypeLabel,
  FULL_TEXT,
  humanReason,
  readDepthColour,
  readDepthHint,
  readDepthLabel,
  STRENGTH_FALLBACK_HINT,
  STRENGTH_LEGEND,
  STRENGTH_TIERS,
  strengthColour,
  strengthHint,
  strengthRank,
  strengthTierColour,
  strengthTierName,
  strengthTone,
  TIER_LABEL,
  TIER_TEXT,
  TITLE_ONLY,
  toneSquareClass,
  uncheckedLabel,
  uncheckedWords,
} from "./evidence";
import { DepthMark, StrengthMark, ToneSquare } from "./EvidenceMarks";

describe("evidence strength", () => {
  it("gives every strength a colour: green strong, yellow moderate and limited, red weak and unrated", () => {
    expect(STRENGTH_TIERS.map((tier) => strengthColour(strengthTone(tier) ?? "weak"))).toEqual([
      "green", "green", "yellow", "yellow", "red", "red",
    ]);
    expect(STRENGTH_TIERS.map(strengthTierColour)).toEqual(["green", "green", "yellow", "yellow", "red", "red"]);
    expect(strengthTone("Moderate confidence")).toBeNull();
    // Round 14: matched whatever its case or surrounding space (chat sends
    // "moderate"), so the word always gets its square.
    expect(strengthTierColour("moderate")).toBe("yellow");
    expect(strengthTierColour(" very STRONG ")).toBe("green");
    expect(strengthTone("unrated")).toBe("weak");
    expect(strengthTone("")).toBeNull();
    expect(strengthTierColour(null)).toBeNull();
  });

  it("ranks strengths strongest first, case aside, unknown and missing last", () => {
    expect(STRENGTH_TIERS.map(strengthRank)).toEqual([0, 1, 2, 3, 4, 5]);
    expect(strengthRank("very strong")).toBe(0);
    expect(strengthRank("Moderate confidence")).toBe(STRENGTH_TIERS.length);
    expect(strengthRank(null)).toBe(STRENGTH_TIERS.length);
  });

  it("reads the legend from the tones, in the sort's order", () => {
    expect(STRENGTH_LEGEND).toEqual([
      { colour: "green", tiers: "Very strong, Strong" },
      { colour: "yellow", tiers: "Moderate, Limited" },
      { colour: "red", tiers: "Weak, Unrated" },
    ]);
  });

  it("explains a strength from its type, in sentence case, or why Unrated is not scored", () => {
    expect(strengthHint("Strong", "Systematic Review")).toBe(
      "Strong evidence strength — appraised from the document type: Systematic review.",
    );
    expect(strengthHint("Unrated", "Other (Non-evidence documents)")).toBe(
      "Unrated — the document type (Other (non-evidence documents)) is not scored; the source can be cited but counts below the evidence bar.",
    );
    expect(strengthHint("Strong", null)).toBe(STRENGTH_FALLBACK_HINT);
    expect(strengthHint(null, "Cohort study")).toBe(STRENGTH_FALLBACK_HINT);
  });
});

describe("read depth", () => {
  it("names the read depth by what the analysis had: full text, an abstract, or the title alone", () => {
    const relevant = { status: "relevant", screen_status: "relevant", read_in_full: false } as const;
    expect(readDepthLabel({ ...relevant, read_in_full: true })).toBe(FULL_TEXT);
    expect(readDepthLabel({ ...relevant, abstract: "An abstract." })).toBe(ABSTRACT_ONLY);
    expect(readDepthLabel({ ...relevant, abstract: null })).toBe(TITLE_ONLY);
    expect(readDepthLabel({ status: "unavailable", screen_status: "relevant", read_in_full: false, abstract: " " })).toBe(TITLE_ONLY);
    expect(readDepthLabel({ status: "screened_out", screen_status: "not_relevant", read_in_full: false })).toBeNull();
    expect([FULL_TEXT, ABSTRACT_ONLY, TITLE_ONLY]).toEqual(["Full text", "Abstract only", "Title only"]);
    expect(([FULL_TEXT, ABSTRACT_ONLY, TITLE_ONLY] as const).map(readDepthColour)).toEqual(["green", "yellow", "red"]);
  });

  it("says why the full text was not read, in plain words", () => {
    expect(readDepthHint({ read_in_full: true, status: "read_in_full" })).toBeNull();
    expect(readDepthHint({ read_in_full: false, status: "unavailable", status_reason: "paywall", abstract: "An abstract." })).toBe(
      "The full text is behind a paywall — only the abstract was read.",
    );
    expect(readDepthHint({ read_in_full: false, status: "relevant", abstract: null })).toBe(
      "The full text hasn't been collected and there is no abstract — screening and appraisal used the title.",
    );
  });

  it("never renders a raw reason code", () => {
    expect(humanReason("no_url")).toBe("No full-text link was available");
    expect(humanReason("some_new_code")).toBe("Some new code");
    expect(humanReason("Already a sentence.")).toBe("Already a sentence.");
  });
});

describe("evidenceTypeLabel", () => {
  it("writes the classifier's labels in sentence case, acronyms kept", () => {
    expect(evidenceTypeLabel("Systematic Review and Meta-Analysis")).toBe("Systematic review and meta-analysis");
    expect(evidenceTypeLabel("RCTs and Quasi-Experimental Studies")).toBe("RCTs and quasi-experimental studies");
    expect(evidenceTypeLabel("Other (Non-evidence documents)")).toBe("Other (non-evidence documents)");
    expect(evidenceTypeLabel("Unknown / Insufficient information")).toBe("Unknown / insufficient information");
    expect(evidenceTypeLabel("Cohort study")).toBe("Cohort study");
  });
});

describe("the judge's verdict", () => {
  it("words the unchecked judgement, the tier's meaning when the judge gave none, and nothing for an unknown tier", () => {
    expect(citationJudgement(null, null, true)).toEqual({
      label: "Unchecked",
      words: "The evidence check could not run for this answer",
    });
    expect(citationJudgement(undefined, null)).toEqual({ label: "Unchecked", words: "Awaiting evidence check" });
    expect(citationJudgement("not_a_tier", null)).toBeNull();
    expect(citationJudgement("tier_2", "Matches the source.")).toEqual({ label: TIER_LABEL.tier_2, words: "Matches the source." });
    expect(citationJudgement("tier_1", "  ")).toEqual({ label: TIER_LABEL.tier_1, words: TIER_TEXT.tier_1 });
  });

  it("says an unchecked citation on one line, awaiting or unavailable", () => {
    expect(uncheckedLabel(false)).toBe("Unchecked · awaiting evidence check");
    expect(uncheckedLabel(true)).toBe("Unchecked · check unavailable");
    expect(uncheckedWords(false)).toBe("Awaiting evidence check");
  });
});

describe("the tone square and the marks", () => {
  it("draws the 6 px square from the palette, decorative, its colour named", () => {
    expect(toneSquareClass("yellow")).toContain("bg-yellow");
    expect(toneSquareClass("red")).toContain("size-1.5");
    const { container } = render(<ToneSquare colour="green" testId="status-mark" className="extra" />);
    const square = container.firstElementChild as HTMLElement;
    expect(square).toHaveAttribute("aria-hidden", "true");
    expect(square).toHaveAttribute("data-tone", "green");
    expect(square).toHaveClass("size-1.5", "bg-green", "extra");
  });

  it("writes a strength as its square then its word; an unknown tier keeps the word, no square", () => {
    const { rerender } = render(<p><StrengthMark tier="Limited" wordClassName="dotted" /></p>);
    const mark = screen.getByTestId("strength-mark");
    expect(mark).toHaveAttribute("data-tone", "yellow");
    expect(screen.getByText("Limited")).toHaveClass("dotted");
    expect(mark.compareDocumentPosition(screen.getByText("Limited")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    rerender(<p><StrengthMark tier="Moderate confidence" /></p>);
    expect(screen.getByText("Moderate confidence")).toBeInTheDocument();
    expect(screen.queryByTestId("strength-mark")).toBeNull();
  });

  it("prints the vocabulary's word whatever case the server sends, and keeps an unknown word as it came", () => {
    expect(strengthTierName("moderate")).toBe("Moderate");
    expect(strengthTierName(" very STRONG ")).toBe("Very strong");
    expect(strengthTierName("Moderate confidence")).toBe("Moderate confidence");
    render(<p><StrengthMark tier="limited" /></p>);
    expect(screen.getByText("Limited")).toBeInTheDocument();
    expect(screen.queryByText("limited")).toBeNull();
  });

  it("writes a read depth as its square then its word", () => {
    render(<p><DepthMark depth={ABSTRACT_ONLY} /></p>);
    expect(screen.getByTestId("status-mark")).toHaveAttribute("data-tone", "yellow");
    expect(screen.getByText("Abstract only")).toBeInTheDocument();
  });
});

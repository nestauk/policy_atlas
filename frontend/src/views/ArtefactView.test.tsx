import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createInitialRunStreamState } from "../store";
import type { LiveSection, RunStreamState } from "../store";
import { highlightParts, LiveArtefactBody, orderSections } from "./ArtefactView";

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
  runStatus: "running" | "failed" | "interrupted",
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
    const { container } = render(<LiveArtefactBody stream={streamWith(sections, "running")} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("shows the terminal banner over streamed sections after a bad ending", () => {
    render(<LiveArtefactBody stream={streamWith(sections, "interrupted")} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This run ended before the write-up completed.",
    );
    // Sections stay visible; the now-false footer and the writing pulse do not.
    expect(screen.getByText(/Prose arrived/)).toBeInTheDocument();
    expect(screen.queryByText(/attached when the write-up completes/)).toBeNull();
    expect(screen.queryByText("Writing this section now…")).toBeNull();
  });

  it("drops a closed-empty section slot (hide, never fake)", () => {
    const withEmpty: LiveSection[] = [
      ...sections,
      { index: 3, title: "Empty key findings", focus: "", state: "filled", prose: "" },
    ];
    render(<LiveArtefactBody stream={streamWith(withEmpty, "running")} />);
    expect(screen.queryByText("Empty key findings")).toBeNull();
  });
});

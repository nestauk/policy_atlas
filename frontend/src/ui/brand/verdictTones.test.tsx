import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SUPPORT_COLOUR, theoryVerdictColour, VERDICT_COLOUR, VerdictMark, VerdictSquare } from "./verdictTones";

describe("the theory of change's verdict tones", () => {
  it("gives each verdict a palette tone, and not enough evidence the Line 2 grey (§ 8)", () => {
    expect(VERDICT_COLOUR).toEqual({
      supported: "green",
      leaning_supports: "green",
      not_sure_mixed: "yellow",
      not_sure_insufficient: "grey",
      leaning_against: "red",
      against: "red",
    });
    expect(SUPPORT_COLOUR.not_about).toBeNull();
    expect(SUPPORT_COLOUR.refutes).toBe("red");
  });

  it("reads the theory's verdict from what it says, never its words", () => {
    expect(theoryVerdictColour({ mechanism: "implausible", evidence: "supports" })).toBe("red");
    expect(theoryVerdictColour({ mechanism: "plausible", evidence: "against" })).toBe("red");
    expect(theoryVerdictColour({ mechanism: "plausible", evidence: "mixed" })).toBe("yellow");
    expect(theoryVerdictColour({ mechanism: "plausible", evidence: "supports" })).toBe("green");
    expect(theoryVerdictColour({ mechanism: "plausible", evidence: "too_little" })).toBe("grey");
  });

  it("draws the grey square as the shared 6 px square in Line 2, and the others as ToneSquare", () => {
    const { rerender } = render(<VerdictSquare colour="grey" />);
    const grey = screen.getByTestId("verdict-mark");
    expect(grey).toHaveAttribute("data-tone", "grey");
    expect(grey).toHaveAttribute("aria-hidden", "true");
    expect(grey.className).toContain("size-1.5");
    expect(grey.className).toContain("bg-line-2");
    expect(grey.className).not.toContain("bg-green");
    rerender(<VerdictSquare colour="red" />);
    expect(screen.getByTestId("verdict-mark").className).toContain("bg-red");
  });

  it("writes the word beside its square, and a word with no tone alone", () => {
    const { rerender } = render(<VerdictMark colour="yellow" word="Mixed" />);
    expect(screen.getByText("Mixed")).toBeInTheDocument();
    expect(screen.getByTestId("verdict-mark")).toHaveAttribute("data-tone", "yellow");
    rerender(<VerdictMark colour={null} word="Unknown" />);
    expect(screen.queryByTestId("verdict-mark")).toBeNull();
  });
});

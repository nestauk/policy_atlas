import { describe, expect, it } from "vitest";

import { boxId, linkId, tocGraphFixture } from "./fixture";
import { BOX_W, COL_GAP, groupAssumptions, gradeSentence, layoutToc, linkTip, tocTitle } from "./tocModel";

const COL_STEP = BOX_W + COL_GAP;

describe("layoutToc", () => {
  const layout = layoutToc(tocGraphFixture());
  const at = (n: number) => layout.boxes.find((b) => b.id === boxId(n));

  it("puts each layer in its own column", () => {
    expect([1, 2, 3, 4, 5, 8].map((n) => at(n)?.column)).toEqual([0, 0, 1, 1, 2, 3]);
    expect(at(5)?.x).toBe(2 * COL_STEP);
  });

  it("orders rows by first appearance along the kept pathways", () => {
    expect(at(1)?.row).toBe(0);
    expect(at(2)?.row).toBe(1);
    expect(at(6)?.row).toBe(1); // second outcome met on pathway 1, after C1
    expect(at(5)?.row).toBe(0);
  });

  it("places failure-only boxes under the line, a failure outcome after its source", () => {
    const line = layout.lineY ?? -1;
    expect(line).toBeGreaterThan(0);
    for (const n of [9, 10]) {
      expect(at(n)?.failure).toBe(true);
      expect(at(n)?.y).toBeGreaterThan(line);
    }
    for (const n of [1, 3, 5, 8]) expect(at(n)?.y).toBeLessThan(line);
    expect(at(9)?.column).toBe(2); // source (output, column 1) + 1
    expect(at(10)?.column).toBe(3);
  });

  it("is deterministic and leaves out set-aside pathways", () => {
    expect(layoutToc(tocGraphFixture())).toEqual(layout);
    expect(layout.boxes).toHaveLength(10);
  });
});

describe("wording and grouping", () => {
  it("writes the grade sentences", () => {
    expect(gradeSentence("medium", "elsewhere")).toBe("Medium evidence it worked elsewhere.");
    expect(gradeSentence("weak", "here")).toBe("Weak evidence it holds here.");
    expect(gradeSentence("strong", "merged")).toBe("Strong evidence, including here.");
    expect(gradeSentence("none", "here")).toBe("No evidence found on whether it holds here.");
  });

  it("shows both grades on a link's hover text", () => {
    const link = tocGraphFixture().links.find((l) => l.link_id === linkId(4));
    expect(link && linkTip(link)).toBe("Strong evidence it worked elsewhere · Weak evidence it holds here");
  });

  it("groups every condition of every kept link by type, in order", () => {
    const groups = groupAssumptions(tocGraphFixture());
    expect(groups.map((g) => g.key)).toEqual(["delivery", "take-up", "behaviour change", "benefits and side effects", "if it goes wrong"]);
    expect(groups.flatMap((g) => g.items)).toHaveLength(9);
  });

  it("titles the page from the first input and the impact", () => {
    expect(tocTitle(tocGraphFixture())).toBe("Ban on less healthy food ads → Fewer children living with obesity at age 10 to 11");
  });
});

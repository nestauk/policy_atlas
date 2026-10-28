import { describe, expect, it } from "vitest";

import { boxId, linkId, tocEvidenceFixture, tocGraphFixture } from "./fixture";
import { BOX_H, BOX_W, COL_GAP, ROW_GAP, evidenceBalance, figureGroups, figureHeadline, groupAssumptions, layoutToc, linkTip, routeEdge, tocTitle } from "./tocModel";

const COL_STEP = BOX_W + COL_GAP;

describe("layoutToc", () => {
  const layout = layoutToc(tocGraphFixture());
  const at = (n: number) => layout.boxes.find((b) => b.id === boxId(n));

  it("gives each layer its columns, outcomes one column per step of their chain", () => {
    // Short-term S1 → S2 take columns 2 and 3, long-term L1 column 4; the impact comes after them.
    expect([1, 2, 3, 4, 5, 6, 7, 8].map((n) => at(n)?.column)).toEqual([0, 0, 1, 1, 2, 3, 4, 5]);
    expect(at(5)?.x).toBe(2 * COL_STEP);
    expect(layout.headings.map((h) => [h.label, h.x])).toEqual([
      ["Inputs and activities", 0],
      ["Outputs", COL_STEP],
      ["Short-term outcomes", 2 * COL_STEP],
      ["Long-term outcomes", 4 * COL_STEP],
      ["Impact", 5 * COL_STEP],
    ]);
  });

  it("puts the accountability ceiling in the gap after the outputs, down past the lowest box", () => {
    expect(layout.ceilingX).toBe(COL_STEP + BOX_W + COL_GAP / 2);
    expect(layout.height).toBe(Math.max(...layout.boxes.map((b) => b.y + BOX_H)));
  });

  it("keeps a chain on one row: each box takes the average row of its sources", () => {
    for (const n of [1, 3, 5]) expect(at(n)?.row).toBe(0);
    expect(at(2)?.row).toBe(1);
    expect(at(4)?.row).toBe(1);
    // S2 has sources on rows 0 (S1) and 1 (P2): the average, 0.5, rounds to row 1.
    expect(at(6)?.row).toBe(1);
    expect(at(7)?.row).toBe(1);
    expect(at(8)?.row).toBe(1);
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

describe("routeEdge", () => {
  it("turns once in the gap between neighbouring columns", () => {
    const route = routeEdge(200, 40, 280, 140, 1);
    expect(route.path).toMatch(/^M 200,40 L 230,40 Q 240,40 240,50 L 240,130 Q 240,140 250,140 L 280,140$/);
    expect([route.labelX, route.labelY]).toEqual([260, 140]);
  });

  it("runs a longer connection along the lane above the target's row, never through a box", () => {
    const route = routeEdge(200, 40, 3 * COL_STEP, 140, 3);
    const lane = 140 - BOX_H / 2 - ROW_GAP / 2;
    expect(route.path).toContain(`${COL_STEP - COL_GAP / 2},${lane}`);
    expect(route.path).toContain(`${3 * COL_STEP - COL_GAP / 2}`);
    expect(route.path.endsWith(`L ${3 * COL_STEP},140`)).toBe(true);
  });
});

describe("wording and grouping", () => {
  it("puts each document in its support column, heaviest first, leaving out not-about ones", () => {
    const columns = evidenceBalance([
      { support: "weak", weight: 0.2 },
      { support: "refutes", weight: 0.4 },
      { support: "weak", weight: 0.6 },
      { support: "not_about", weight: 0 },
    ]);
    expect(columns).toEqual([
      { support: "refutes", weights: [0.4] },
      { support: "mixed", weights: [] },
      { support: "weak", weights: [0.6, 0.2] },
      { support: "strong", weights: [] },
    ]);
  });

  it("groups figures by measure, unit and type, and words a range across studies, never an average", () => {
    const figures = tocEvidenceFixture().links[0]?.figures ?? [];
    const groups = figureGroups(figures);
    // The first two differ only in case and punctuation: one group.
    expect(groups.map((group) => group.figures.length)).toEqual([2, 1]);
    expect(figureHeadline(groups[0]!)).toBe("Evidence suggests 44 to 58% fewer adverts for less healthy food seen by children (2 studies)");
    // A single number keeps its reported text and range.
    expect(figureHeadline(groups[1]!)).toBe("1·05 odds of children's exposure, no change (range 0·99 to 1·12)");
  });

  it("says one study when two figures come from the same document, and one value when they agree", () => {
    const [first] = tocEvidenceFixture().links[0]?.figures ?? [];
    const same = { ...first!, figure_id: "x", value: 44, value_text: "44" };
    expect(figureHeadline({ key: "k", figures: [first!, same] })).toBe(
      "Evidence suggests 44% fewer adverts for less healthy food seen by children (1 study)",
    );
  });

  it("gives the verdict on a link's hover text", () => {
    const link = tocGraphFixture().links.find((l) => l.link_id === linkId(4));
    expect(link && linkTip(link)).toBe("Confident");
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

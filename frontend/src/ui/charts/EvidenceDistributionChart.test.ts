import { describe, expect, it } from "vitest";

import { fillYearRange, humaniseLabel, orderThemes } from "./EvidenceDistributionChart";

describe("fillYearRange", () => {
  it("fills every year from the earliest to the latest evidence year", () => {
    expect(fillYearRange({ "2019": 6, "2021": 3 })).toEqual([
      { label: "2019", count: 6 },
      { label: "2020", count: 0 },
      { label: "2021", count: 3 },
    ]);
  });
});


describe("orderThemes", () => {
  it("orders themes by descending count", () => {
    expect(
      orderThemes([
        { size: 2, name: "b" },
        { size: 9, name: "a" },
        { size: 4, name: "c" },
      ]).map((theme) => theme.name),
    ).toEqual(["a", "c", "b"]);
  });
});

describe("humaniseLabel", () => {
  it("presents snake_cased data values without leaking underscores", () => {
    expect(humaniseLabel("systematic_review")).toBe("Systematic review");
    expect(humaniseLabel("Guidance")).toBe("Guidance");
  });
});

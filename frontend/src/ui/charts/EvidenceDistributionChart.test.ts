import { describe, expect, it } from "vitest";

import {
  fillYearRange,
  humaniseLabel,
  normaliseGeographies,
  orderThemes,
} from "./EvidenceDistributionChart";

describe("normaliseGeographies", () => {
  it("keeps the 'Not reported' residual intact so the bars still sum to the population", () => {
    // Task 031 defect 3: the backend counts sources with no publisher country
    // into this bucket rather than dropping them. A country alias that
    // swallowed or renamed it would silently break the sum again.
    const normalised = normaliseGeographies({ GB: 4, "Not reported": 7 });
    expect(normalised).toEqual({ "United Kingdom": 4, "Not reported": 7 });
    expect(Object.values(normalised).reduce((sum, count) => sum + count, 0)).toBe(11);
  });
});

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

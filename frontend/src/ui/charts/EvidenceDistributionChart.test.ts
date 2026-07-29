import { describe, expect, it } from "vitest";

import { fillYearRange } from "./EvidenceDistributionChart";

describe("fillYearRange", () => {
  it("fills every year from the earliest to the latest evidence year", () => {
    expect(fillYearRange({ "2019": 6, "2021": 3 })).toEqual([
      { label: "2019", count: 6 },
      { label: "2020", count: 0 },
      { label: "2021", count: 3 },
    ]);
  });
});

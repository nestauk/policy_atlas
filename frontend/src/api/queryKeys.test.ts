import { describe, expect, it } from "vitest";

import { queryKeys, type EvidenceQuery } from "./queries";

describe("queryKeys.evidence", () => {
  it("keys every server filter — a param missing from the key silently serves cached rows", () => {
    const base = queryKeys.evidence("p", {});
    const variants: EvidenceQuery[] = [
      { page: 2 },
      { page_size: 100 },
      { status: ["Included"] },
      { cited: true },
      { sort: "year" },
      { order: "desc" },
      { theme: "t" },
      { origin: "Overton" },
      { evidence_type: "Systematic review" },
      { strength: "Weak" },
      { year_from: 2019 },
      { year_to: 2024 },
    ];
    for (const query of variants) {
      expect(queryKeys.evidence("p", query)).not.toEqual(base);
    }
  });
});

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

// Task 033 phase 10a: `scope` (and, for projects, `portfolio_id`) must be
// part of the list-query key — otherwise a switcher toggling scope (10b)
// would silently serve another scope's cached rows.
describe("queryKeys.projects", () => {
  it("keys scope and portfolio_id", () => {
    const base = queryKeys.projects({});
    expect(queryKeys.projects({ scope: "mine" })).not.toEqual(base);
    expect(queryKeys.projects({ scope: "all" })).not.toEqual(base);
    expect(queryKeys.projects({ scope: "mine" })).not.toEqual(queryKeys.projects({ scope: "all" }));
    expect(queryKeys.projects({ portfolio_id: "p1" })).not.toEqual(base);
    expect(queryKeys.projects({ portfolio_id: "p1" })).not.toEqual(queryKeys.projects({ portfolio_id: "p2" }));
  });
});

describe("queryKeys.portfolios", () => {
  it("keys scope", () => {
    const base = queryKeys.portfolios({});
    expect(queryKeys.portfolios({ scope: "mine" })).not.toEqual(base);
    expect(queryKeys.portfolios({ scope: "mine" })).not.toEqual(queryKeys.portfolios({ scope: "all" }));
  });
});

describe("queryKeys.me", () => {
  it("is a stable, parameterless key", () => {
    expect(queryKeys.me()).toEqual(["me"]);
    expect(queryKeys.me()).toEqual(queryKeys.me());
  });
});

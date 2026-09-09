import { describe, expect, it } from "vitest";

import { scopingWalkStatus } from "./workspace/planStart";
import {
  artefactDepthLabel,
  baselineBand,
  isBaselineArtefact,
} from "./baselineBand";

const PAUSED_AT_GATE = {
  status: "paused",
  started_at: "2026-09-09T10:00:00Z",
  plan_version: 1,
};
const FINISHED = {
  status: "succeeded",
  started_at: "2026-09-09T10:00:00Z",
  plan_version: 1,
};

function band(
  runs: Array<{ status: string; started_at: string; plan_version: number }>,
  currentVersion: number | null,
  baselineConfirmed: { plan_version: number } | null = null,
) {
  return baselineBand(scopingWalkStatus({ runs, currentVersion, baselineConfirmed }));
}

describe("isBaselineArtefact", () => {
  it("reads the roll-up's template word, not the sections", () => {
    expect(isBaselineArtefact({ template: "baseline" })).toBe(true);
    expect(isBaselineArtefact({ template: null })).toBe(false);
    expect(isBaselineArtefact({})).toBe(false);
    expect(isBaselineArtefact(null)).toBe(false);
    expect(isBaselineArtefact(undefined)).toBe(false);
  });
});

describe("artefactDepthLabel", () => {
  it("passes the roll-up's own words through, and reports absence honestly", () => {
    expect(artefactDepthLabel({ depth_label: "scoping pass" })).toBe("scoping pass");
    expect(artefactDepthLabel({ depth_label: "" })).toBeNull();
    expect(artefactDepthLabel(undefined)).toBeNull();
  });
});

describe("baselineBand", () => {
  it("says the baseline is ready and awaiting confirmation while the walk sits on the gate", () => {
    expect(band([PAUSED_AT_GATE], 1)).toEqual({
      line: "Baseline · the situation these options would change · ready · awaiting your confirmation",
      planVersionMark: null,
    });
  });

  it("says the plan is confirmed once the record names the current plan version", () => {
    expect(band([PAUSED_AT_GATE], 1, { plan_version: 1 })).toEqual({
      line: "Baseline · the situation these options would change · plan confirmed · the longlist arrives with the next stage",
      planVersionMark: null,
    });
  });

  it("keeps the plan-version mark when a newer plan was confirmed off an older baseline", () => {
    // "Confirm plan and build longlist" after a plan edit: the plan is
    // settled, but the profile on screen is still the one v1 produced.
    const both = band([PAUSED_AT_GATE], 2, { plan_version: 2 });
    expect(both.line).toContain("plan confirmed");
    expect(both.planVersionMark).toBe("built from plan version 1");
  });

  it("says the plan is confirmed when a finished walk ran on the version on screen", () => {
    // A walk can only reach `succeeded` through the gate's Confirm option or
    // the standing default — the same rule the plan document's start area uses.
    expect(band([FINISHED], 1).line).toContain("plan confirmed");
  });

  it("marks the plan version only after the plan has moved on", () => {
    expect(band([FINISHED], 1).planVersionMark).toBeNull();
    expect(band([FINISHED], 3).planVersionMark).toBe("built from plan version 1");
    // A newer plan version is no longer confirmed by the older walk.
    expect(band([FINISHED], 3).line).toContain("ready · awaiting your confirmation");
  });

  it("reads the most recently started walk when several exist", () => {
    const older = { status: "aborted", started_at: "2026-09-08T09:00:00Z", plan_version: 1 };
    const newer = { status: "succeeded", started_at: "2026-09-09T09:00:00Z", plan_version: 2 };
    expect(band([older, newer], 2).line).toContain("plan confirmed");
  });

  it("holds the awaiting wording with no walk loaded rather than claiming confirmation", () => {
    expect(band([], null).line).toContain("ready · awaiting your confirmation");
    expect(band([], null).planVersionMark).toBeNull();
  });
});

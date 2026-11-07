import { describe, expect, it } from "vitest";

import { cellPulses } from "./sourcesPresentation";

describe("the cells that pulse while a stage runs (owner, round 13)", () => {
  const row = { evidence_type: "Cohort study", appraisal_tier: "Moderate" } as const;

  it("pulses Relevant while screening runs, only where the verdict is absent", () => {
    const screen = new Set(["screen"]);
    expect(cellPulses({ ...row, screen_status: null, read_in_full: false, status: "found" }, screen).relevant).toBe(true);
    expect(cellPulses({ ...row, screen_status: "relevant", read_in_full: false, status: "relevant" }, screen).relevant).toBe(false);
    expect(cellPulses({ ...row, screen_status: null, read_in_full: false, status: "found" }, new Set()).relevant).toBe(false);
  });

  it("pulses Status while the full texts are fetched until the depth is full text, whatever it reads now", () => {
    const ingest = new Set(["ingest"]);
    const relevant = { ...row, screen_status: "relevant", read_in_full: false } as const;
    expect(cellPulses({ ...relevant, status: "relevant" }, ingest).status).toBe(true);
    expect(cellPulses({ ...relevant, status: "unavailable" }, ingest).status).toBe(true);
    expect(cellPulses({ ...relevant, status: "read_in_full", read_in_full: true }, ingest).status).toBe(false);
    expect(cellPulses({ ...row, screen_status: "not_relevant", read_in_full: false, status: "screened_out" }, ingest).status).toBe(false);
    expect(cellPulses({ ...relevant, status: "relevant" }, new Set()).status).toBe(false);
  });
});

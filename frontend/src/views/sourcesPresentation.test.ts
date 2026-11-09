import { describe, expect, it } from "vitest";

import { cellPulses } from "./sourcesPresentation";

describe("the cells that wait on a running stage (rounds 13 and 14)", () => {
  const row = { evidence_type: "Cohort study", appraisal_tier: "Moderate", full_text_status: "not_attempted" } as const;

  it("pulses Relevant while screening runs, only where the verdict is absent", () => {
    const screen = new Set(["screen"]);
    expect(cellPulses({ ...row, screen_status: null, read_in_full: false, status: "found" }, screen).relevant).toBe(true);
    expect(cellPulses({ ...row, screen_status: "relevant", read_in_full: false, status: "relevant" }, screen).relevant).toBe(false);
    expect(cellPulses({ ...row, screen_status: null, read_in_full: false, status: "found" }, new Set()).relevant).toBe(false);
  });

  it("collects a source whose full text is queued, only while the full texts are collected", () => {
    const ingest = new Set(["ingest"]);
    const relevant = { ...row, screen_status: "relevant", read_in_full: false, status: "relevant" } as const;
    expect(cellPulses({ ...relevant, full_text_status: "queued" }, ingest).status).toBe(true);
    // Not queued, already collected, or failed: its depth stands.
    expect(cellPulses({ ...relevant, full_text_status: "not_attempted" }, ingest).status).toBe(false);
    expect(cellPulses({ ...relevant, full_text_status: "ingested", read_in_full: true, status: "read_in_full" }, ingest).status).toBe(false);
    expect(cellPulses({ ...relevant, full_text_status: "fetch_failed", status: "unavailable" }, ingest).status).toBe(false);
    // The stage is the guard: a queued source outside the stage waits quietly.
    expect(cellPulses({ ...relevant, full_text_status: "queued" }, new Set()).status).toBe(false);
  });
});

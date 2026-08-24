import { describe, expect, it } from "vitest";

import { isStale, runPresentation, taskStatus } from "./landingPresentation";

const NOW = new Date("2026-08-17T00:00:00.000Z");

function run(status: string | undefined, ended_at: string | null = null) {
  if (status === undefined) return undefined;
  return { capability_run_id: "r1", started_at: "2026-01-01T00:00:00Z", status, ended_at } as never;
}

describe("runPresentation", () => {
  it("maps each of the seven run statuses to its label and tone", () => {
    expect(runPresentation(run("running"))).toEqual({ dot: "running", label: "Analysing the evidence…", tone: "yellow" });
    expect(runPresentation(run("paused"))).toEqual({ dot: "paused", label: "Paused — waiting on your input", tone: "yellow" });
    expect(runPresentation(run("succeeded"))).toEqual({ dot: "complete", label: "Complete", tone: "green" });
    expect(runPresentation(run("degraded"))).toEqual({ dot: "complete", label: "Complete — with gaps", tone: "yellow" });
    expect(runPresentation(run("failed"))).toEqual({ dot: "failed", label: "Failed", tone: "red" });
    expect(runPresentation(run("interrupted"))).toEqual({ dot: "failed", label: "Interrupted", tone: "red" });
    expect(runPresentation(run("aborted"))).toEqual({ dot: "idle", label: "Stopped", tone: "soft" });
  });

  it("maps null and undefined to Not started", () => {
    expect(runPresentation(null)).toEqual({ dot: "idle", label: "Not started", tone: "soft" });
    expect(runPresentation(undefined)).toEqual({ dot: "idle", label: "Not started", tone: "soft" });
  });
});

describe("isStale", () => {
  it("is true only for a succeeded run with ended_at older than 12 months", () => {
    expect(isStale(run("succeeded", "2025-01-01T00:00:00Z"), NOW)).toBe(true);
  });

  it("is false for a succeeded run 11 months old", () => {
    expect(isStale(run("succeeded", "2025-09-17T00:00:00.000Z"), NOW)).toBe(false);
  });

  it("is false for a failed run however old", () => {
    expect(isStale(run("failed", "2020-01-01T00:00:00Z"), NOW)).toBe(false);
  });

  it("is false when ended_at is null", () => {
    expect(isStale(run("succeeded", null), NOW)).toBe(false);
  });

  it("is exactly false at the 12-month boundary, true one day older, false one day younger", () => {
    expect(isStale(run("succeeded", "2025-08-17T00:00:00.000Z"), NOW)).toBe(false);
    expect(isStale(run("succeeded", "2025-08-16T00:00:00.000Z"), NOW)).toBe(true);
    expect(isStale(run("succeeded", "2025-08-18T00:00:00.000Z"), NOW)).toBe(false);
  });
});

describe("taskStatus", () => {
  it("returns Stale with soft tone for a stale task", () => {
    expect(taskStatus(run("succeeded", "2020-01-01T00:00:00Z"), NOW)).toEqual({
      dot: "complete",
      label: "Stale",
      tone: "soft",
    });
  });

  it("returns the plain runPresentation label otherwise", () => {
    expect(taskStatus(run("running"), NOW)).toEqual({ dot: "running", label: "Analysing the evidence…", tone: "yellow" });
    expect(taskStatus(run("succeeded", "2026-08-01T00:00:00Z"), NOW)).toEqual({ dot: "complete", label: "Complete", tone: "green" });
  });
});

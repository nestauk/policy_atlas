import { describe, expect, it } from "vitest";

import { isStale, READY_WORDS, taskStatusTone, taskStatusWord } from "./taskStatus";

const NOW = new Date("2026-08-17T00:00:00.000Z");

function run(status: string | undefined, ended_at: string | null = null) {
  if (status === undefined) return undefined;
  return { capability_run_id: "r1", started_at: "2026-01-01T00:00:00Z", status, ended_at } as never;
}

describe("taskStatusWord", () => {
  it("names each of the seven run statuses", () => {
    expect(taskStatusWord("running")).toBe("Running");
    expect(taskStatusWord("paused")).toBe("Paused · waiting on you");
    expect(taskStatusWord("succeeded")).toBe("Complete");
    expect(taskStatusWord("degraded")).toBe("Complete · with gaps");
    expect(taskStatusWord("failed")).toBe("Failed");
    expect(taskStatusWord("interrupted")).toBe("Stopped");
    expect(taskStatusWord("aborted")).toBe("Stopped");
  });

  it("reads Not started for a task with no run", () => {
    expect(taskStatusWord(null)).toBe("Not started");
    expect(taskStatusWord(undefined)).toBe("Not started");
  });

  // Round 10 (lead rulings P2 and 4): who a paused task waits on, one
  // separator, and the archived word.
  it("names who a paused task waits on", () => {
    expect(taskStatusWord("paused", { isOwner: true })).toBe("Paused · waiting on you");
    expect(taskStatusWord("paused", { isOwner: false, ownerName: "Grace Hopper" })).toBe("Paused · waiting on Grace");
    expect(taskStatusWord("paused", { isOwner: false, ownerName: null })).toBe("Paused");
  });

  it("reads Archived for an archived task, whatever its last run, and never Stale", () => {
    expect(taskStatusWord("succeeded", { archived: true })).toBe("Archived");
    expect(taskStatusWord("succeeded", { archived: true, stale: true })).toBe("Archived");
  });

  it("reads Stale for a stale finished task", () => {
    expect(taskStatusWord("succeeded", { stale: true })).toBe("Stale");
  });
});

describe("taskStatusTone", () => {
  it("gives the row's mark its colour", () => {
    expect(taskStatusTone("running")).toBe("running");
    expect(taskStatusTone("paused")).toBe("paused");
    expect(taskStatusTone("succeeded")).toBe("complete");
    expect(taskStatusTone("degraded")).toBe("complete");
    expect(taskStatusTone("failed")).toBe("failed");
    expect(taskStatusTone("interrupted")).toBe("failed");
    expect(taskStatusTone("aborted")).toBe("idle");
    expect(taskStatusTone(undefined)).toBe("idle");
    expect(taskStatusTone("succeeded", true)).toBe("idle");
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

describe("READY_WORDS", () => {
  it("names the finish per walk", () => {
    expect(READY_WORDS.evidence_search).toBe("Report ready");
    expect(READY_WORDS.longlist).toBe("The longlist is ready");
  });
});

import { describe, expect, it } from "vitest";

import { LIFECYCLE_TABS, isTabOpen, lifecycleTabs, taskDestination } from "./lifecycle";
import type { LifecycleTab } from "./lifecycle";

/** The contract's locking table, transcribed independently of the source. */
const LOCKING_TABLE: ReadonlyArray<{
  state: string;
  status: Parameters<typeof isTabOpen>[1];
  open: readonly LifecycleTab[];
}> = [
  { state: "no run yet", status: null, open: ["plan"] },
  { state: "running", status: "running", open: ["plan", "sources", "history"] },
  { state: "paused", status: "paused", open: ["plan", "sources", "history"] },
  { state: "succeeded", status: "succeeded", open: [...LIFECYCLE_TABS] },
  { state: "degraded", status: "degraded", open: [...LIFECYCLE_TABS] },
  { state: "failed", status: "failed", open: ["plan", "sources", "history"] },
  { state: "aborted", status: "aborted", open: ["plan", "sources", "history"] },
  { state: "interrupted", status: "interrupted", open: ["plan", "sources", "history"] },
];

describe("lifecycle tab locking", () => {
  for (const { state, status, open } of LOCKING_TABLE) {
    it(`matches the contract's row for ${state}`, () => {
      for (const tab of LIFECYCLE_TABS) {
        expect(isTabOpen(tab, status), `${tab} at ${state}`).toBe(open.includes(tab));
      }
    });
  }

  it("treats an absent latest_run the same as an explicit null", () => {
    for (const tab of LIFECYCLE_TABS) {
      expect(isTabOpen(tab, undefined)).toBe(isTabOpen(tab, null));
    }
  });

  it("keeps Sources open after a failed run, because the corpus is real", () => {
    expect(isTabOpen("sources", "failed")).toBe(true);
    expect(isTabOpen("results", "failed")).toBe(false);
  });

  it("never locks Plan, at any state", () => {
    for (const { status } of LOCKING_TABLE) {
      expect(isTabOpen("plan", status)).toBe(true);
    }
  });
});

describe("lifecycleTabs", () => {
  it("returns all five tabs in order with their paths, whatever the state", () => {
    const tabs = lifecycleTabs("/projects/p1", null);
    expect(tabs.map((entry) => entry.tab)).toEqual([...LIFECYCLE_TABS]);
    expect(tabs.map((entry) => entry.to)).toEqual([
      "/projects/p1",
      "/projects/p1/results",
      "/projects/p1/sources",
      "/projects/p1/share",
      "/projects/p1/history",
    ]);
  });

  it("marks the locked ones rather than dropping them", () => {
    const locked = lifecycleTabs("/projects/p1", "running")
      .filter((entry) => entry.locked)
      .map((entry) => entry.tab);
    expect(locked).toEqual(["results", "share"]);
  });
});

describe("taskDestination", () => {
  it("opens Results for a succeeded task", () => {
    expect(taskDestination("p1", "succeeded")).toBe("/projects/p1/results");
  });

  it("opens Plan for every other state", () => {
    for (const status of ["running", "paused", "degraded", "failed", "aborted", "interrupted"] as const) {
      expect(taskDestination("p1", status)).toBe("/projects/p1");
    }
    expect(taskDestination("p1", null)).toBe("/projects/p1");
  });
});

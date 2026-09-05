import { describe, expect, it } from "vitest";

import { LIFECYCLE_TABS, isTabOpen, lifecycleTabs, taskDestination } from "./lifecycle";
import type { LifecycleTab } from "./lifecycle";

/** The locking table after the 2026-08-25 steer: Result opens while a run
 *  is executing so the in-progress write-up is reachable. Failed runs still
 *  lock Result. */
const LOCKING_TABLE: ReadonlyArray<{
  state: string;
  status: Parameters<typeof isTabOpen>[1];
  open: readonly LifecycleTab[];
}> = [
  { state: "no run yet", status: null, open: ["agent", "share"] },
  { state: "running", status: "running", open: [...LIFECYCLE_TABS] },
  { state: "paused", status: "paused", open: [...LIFECYCLE_TABS] },
  { state: "succeeded", status: "succeeded", open: [...LIFECYCLE_TABS] },
  { state: "degraded", status: "degraded", open: [...LIFECYCLE_TABS] },
  { state: "failed", status: "failed", open: ["agent", "sources", "share", "history"] },
  { state: "aborted", status: "aborted", open: ["agent", "sources", "share", "history"] },
  { state: "interrupted", status: "interrupted", open: ["agent", "sources", "share", "history"] },
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
    expect(isTabOpen("result", "failed")).toBe(false);
  });

  it("never locks Agent, at any state", () => {
    for (const { status } of LOCKING_TABLE) {
      expect(isTabOpen("agent", status)).toBe(true);
    }
  });
});

describe("lifecycleTabs", () => {
  it("returns all five tabs in order with their paths, whatever the state", () => {
    const tabs = lifecycleTabs("/tasks/p1", null);
    expect(tabs.map((entry) => entry.tab)).toEqual([...LIFECYCLE_TABS]);
    expect(tabs.map((entry) => entry.to)).toEqual([
      "/tasks/p1",
      "/tasks/p1/result",
      "/tasks/p1/sources",
      "/tasks/p1/share",
      "/tasks/p1/history",
    ]);
  });

  it("marks the locked ones rather than dropping them", () => {
    const locked = lifecycleTabs("/tasks/p1", "failed")
      .filter((entry) => entry.locked)
      .map((entry) => entry.tab);
    expect(locked).toEqual(["result"]);
  });

  it("opens Result while a run is executing", () => {
    expect(
      lifecycleTabs("/tasks/p1", "running").filter((entry) => entry.locked),
    ).toEqual([]);
  });
});

describe("taskDestination", () => {
  it("opens Result for a succeeded task", () => {
    expect(taskDestination("p1", "succeeded")).toBe("/tasks/p1/result");
  });

  it("opens Agent for every other state", () => {
    for (const status of ["running", "paused", "degraded", "failed", "aborted", "interrupted"] as const) {
      expect(taskDestination("p1", status)).toBe("/tasks/p1");
    }
    expect(taskDestination("p1", null)).toBe("/tasks/p1");
  });
});

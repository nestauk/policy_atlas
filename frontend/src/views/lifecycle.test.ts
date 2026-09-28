import { describe, expect, it } from "vitest";

import {
  LIFECYCLE_TABS,
  isTabOpen,
  lifecycleTabs,
  resultView,
  resultViews,
  taskDestination,
  withChat,
} from "./lifecycle";
import type { LifecycleTab } from "./lifecycle";
import {
  activeRun,
  hasLonglist,
  hasTaskResult,
  isRunActive,
  isScoping,
  statusRun,
  tabRunStatus,
  type TaskActivity,
} from "./scopingActivity";

describe("withChat", () => {
  it("carries the open chat onto every tab link but the Agent tab's", () => {
    const tabs = lifecycleTabs("/tasks/t1", "succeeded");
    const carried = withChat(tabs, "c 1");
    expect(carried.find((item) => item.tab === "sources")?.to).toBe("/tasks/t1/sources?chat=c%201");
    expect(carried.find((item) => item.tab === "agent")?.to).toBe("/tasks/t1");
    expect(withChat(tabs, null)).toBe(tabs);
  });
});

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

  // Task 044 (A17): a scoping baseline outlives the walk that wrote it, so
  // Result opens on the baseline whatever the walk's ending.
  it("opens Result on a scoping baseline at every run state, and locks nothing else open", () => {
    for (const { status } of LOCKING_TABLE) {
      expect(isTabOpen("result", status, { hasBaseline: true })).toBe(true);
    }
    expect(isTabOpen("result", null, { hasBaseline: true })).toBe(true);
    // The baseline unlocks Result and nothing more: Sources and History stay
    // shut on a task that has never run.
    expect(isTabOpen("sources", null, { hasBaseline: true })).toBe(false);
    expect(isTabOpen("history", null, { hasBaseline: true })).toBe(false);
  });

  it("keeps the tab order when the baseline unlocks Result", () => {
    expect(
      lifecycleTabs("/tasks/p1", "failed", { hasBaseline: true })
        .filter((entry) => !entry.locked)
        .map((entry) => entry.tab),
    ).toEqual(["agent", "result", "sources", "share", "history"]);
  });

  it("leaves an Evidence search untouched — no baseline, no extra tab", () => {
    expect(isTabOpen("result", "failed", { hasBaseline: false })).toBe(false);
    expect(isTabOpen("result", "failed")).toBe(false);
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

// Task 045 (deliverable 9, S13/S15): the longlist opens Result the way the
// baseline does, the Result opens on it, and what drives the tabs is the
// scoping task's `latest_run` — never an option search.
describe("the longlist and the scoping readers (task 045)", () => {
  const LATEST = {
    capability_run_id: "run-longlist",
    status: "succeeded" as const,
    started_at: "2026-09-02T00:00:00Z",
    ended_at: "2026-09-02T00:20:00Z",
  };
  const CHILD = {
    capability_run_id: "run-child",
    status: "running" as const,
    started_at: "2026-09-03T00:00:00Z",
    ended_at: null,
  };

  it("a longlist opens Result whatever the walk's ending, like a baseline", () => {
    expect(isTabOpen("result", null, { hasLonglist: true })).toBe(true);
    expect(isTabOpen("result", "failed", { hasLonglist: true })).toBe(true);
    expect(isTabOpen("result", "aborted", { hasLonglist: false })).toBe(false);
  });

  it("Result opens on the longlist once one exists, and on the baseline before", () => {
    expect(resultView(null, { hasBaseline: true })).toBe("baseline");
    expect(resultView(null, { hasBaseline: true, hasLonglist: true })).toBe("longlist");
    expect(resultView("baseline", { hasLonglist: true })).toBe("baseline");
    // A view the switch does not offer, or cannot open, falls back.
    expect(resultView("report", { hasLonglist: true })).toBe("longlist");
    expect(resultView("longlist", { hasLonglist: false })).toBe("baseline");
  });

  it("the view switch: Baseline · Longlist · Report, Report available after assessment", () => {
    expect(resultViews({ hasBaseline: true })).toBeNull();
    expect(resultViews({ hasLonglist: true })).toEqual([
      { key: "baseline", label: "Baseline", available: true },
      { key: "longlist", label: "Longlist", available: true },
      { key: "report", label: "Report", available: false, note: "available after assessment" },
    ]);
  });

  it("a running child shows as activity but never opens or locks a tab", () => {
    const withChild = {
      capability: "options_scoping",
      latest_run: LATEST,
      active_run: CHILD,
      has_longlist: true,
    };
    const without = { ...withChild, active_run: null };
    expect(isRunActive(withChild)).toBe(true);
    expect(activeRun(withChild)?.capability_run_id).toBe("run-child");
    expect(tabRunStatus(withChild)).toBe("succeeded");
    const tabs = (task: TaskActivity) =>
      lifecycleTabs("/tasks/t1", tabRunStatus(task), { hasLonglist: hasLonglist(task) }).map(
        (item) => [item.tab, item.locked],
      );
    expect(tabs(withChild)).toEqual(tabs(without));

    // Before any longlist: a child cannot exist without its parent, but an
    // aborted latest walk with a live child still locks exactly as without.
    const aborted = { ...withChild, latest_run: { ...LATEST, status: "aborted" as const }, has_longlist: false };
    expect(tabs(aborted)).toEqual(tabs({ ...aborted, active_run: null }));
  });

  it("a scoping task's status word reads the active walk, then its latest", () => {
    const task = { capability: "options_scoping", latest_run: LATEST, active_run: CHILD };
    expect(statusRun(task)?.status).toBe("running");
    expect(statusRun({ ...task, active_run: null })?.status).toBe("succeeded");
  });

  it("an Evidence search's readers are unchanged: latest_run only", () => {
    const es = {
      capability: "evidence_search",
      latest_run: { ...LATEST, status: "succeeded" as const },
      // The server fills active_run for every task; an ES reader ignores it.
      active_run: CHILD,
      has_longlist: false,
    };
    expect(isScoping(es)).toBe(false);
    expect(activeRun(es)).toBeNull();
    expect(statusRun(es)?.status).toBe("succeeded");
    expect(tabRunStatus(es)).toBe("succeeded");
    expect(hasLonglist({ ...es, has_longlist: true })).toBe(false);
    expect(hasTaskResult(es)).toBe(true);
    expect(hasTaskResult({ ...es, latest_run: { ...LATEST, status: "running" as const } })).toBe(false);
    expect(activeRun({ ...es, latest_run: { ...LATEST, status: "paused" as const } })?.status).toBe("paused");
  });

  it("a scoping task has a result once a baseline or a longlist exists", () => {
    const task = { capability: "options_scoping", latest_run: { ...LATEST, status: "running" as const } };
    expect(hasTaskResult(task)).toBe(false);
    expect(hasTaskResult(task, { hasBaseline: true })).toBe(true);
    expect(hasTaskResult({ ...task, has_longlist: true })).toBe(true);
  });

  it("a task row with a longlist lands on Result", () => {
    expect(taskDestination("t1", "running", { hasLonglist: true })).toBe("/tasks/t1/result");
    expect(taskDestination("t1", "running")).toBe("/tasks/t1");
  });
});

import { LIFECYCLE_LABELS } from "../lib/vocabulary";
import type { components } from "../api/gen/types";

/** The generated contract inlines the run-status union rather than naming it. */
type RunStatus = components["schemas"]["LatestRun"]["status"];

/** The five task-level stages, in the order a task runs through them. */
export const LIFECYCLE_TABS = ["agent", "result", "sources", "share", "history"] as const;

export type LifecycleTab = (typeof LIFECYCLE_TABS)[number];

/** Path suffix for each tab, relative to `/tasks/:taskId`. */
const TAB_PATHS: Record<LifecycleTab, string> = {
  agent: "",
  result: "/result",
  sources: "/sources",
  share: "/share",
  history: "/history",
};

/**
 * The set of tabs a task at this run state can open.
 *
 * Task 032 locked Results until the run succeeded. Owner steer 2026-08-25
 * reopens it while a run is executing or paused so the in-progress write-up
 * is reachable (LiveArtefactBody already streams sections as they fill).
 * Availability is still computed from run state, never from whether a page
 * would happen to render empty.
 *
 * Sources stays open after a failed run on purpose: the corpus that was
 * gathered is real and readable, and dropping it would hide work that exists.
 * That is the flag-don't-drop discipline, not a special case. Results stays
 * locked after a failed run — a partial write-up is still on Plan.
 */
function openTabs(status: RunStatus | null | undefined): readonly LifecycleTab[] {
  if (status === null || status === undefined) return ["agent", "share"];
  switch (status) {
    case "running":
    case "paused":
    case "succeeded":
    case "degraded":
      return LIFECYCLE_TABS;
    case "failed":
    case "aborted":
    case "interrupted":
      return ["agent", "sources", "share", "history"];
  }
}

/** Whether the task has a result to ask about: the run finished with a
 *  report (038 V8 — chats are offered only then; a run still writing is not
 *  a result yet, even though the Result tab already opens for it). */
export function hasResult(status: RunStatus | null | undefined): boolean {
  return status === "succeeded" || status === "degraded";
}

/** Whether one lifecycle tab can be opened at this run state. */
export function isTabOpen(tab: LifecycleTab, status: RunStatus | null | undefined): boolean {
  return openTabs(status).includes(tab);
}

/** The five tabs with their label, path and availability at this run state. */
export function lifecycleTabs(base: string, status: RunStatus | null | undefined) {
  const open = openTabs(status);
  return LIFECYCLE_TABS.map((tab) => ({
    tab,
    label: LIFECYCLE_LABELS[tab],
    to: `${base}${TAB_PATHS[tab]}`,
    locked: !open.includes(tab),
  }));
}

/**
 * The two tabs the public (link-shared) task view exposes — task 037.
 * One list, shared with `LifecycleRoute`'s public gate so the nav and the
 * gate cannot drift apart.
 */
export const PUBLIC_TABS: readonly LifecycleTab[] = ["result", "sources"];

/**
 * The public tab set as nav items. Both stay open regardless of run state:
 * the backend's public read leg is the gate, and an empty Results page
 * renders its shaped absence.
 */
export function publicLifecycleTabs(base: string) {
  return PUBLIC_TABS.map((tab) => ({
    tab,
    label: LIFECYCLE_LABELS[tab],
    to: `${base}${TAB_PATHS[tab]}`,
    locked: false,
  }));
}

/**
 * Where a task row in the tasks list should land.
 *
 * One destination per state, never a generic detail page: a finished task
 * opens what the reader came for, and everything else opens the plan, which
 * is the only stage guaranteed to have something in it.
 */
export function taskDestination(taskId: string, status: RunStatus | null | undefined): string {
  const base = `/tasks/${taskId}`;
  return status === "succeeded" ? `${base}/result` : base;
}

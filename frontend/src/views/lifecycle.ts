import { LIFECYCLE_LABELS } from "../lib/vocabulary";
import type { components } from "../api/gen/types";

/** The generated contract inlines the run-status union rather than naming it. */
type RunStatus = components["schemas"]["LatestRun"]["status"];

/** The five task-level stages, in the order a task runs through them. */
export const LIFECYCLE_TABS = ["plan", "results", "sources", "share", "history"] as const;

export type LifecycleTab = (typeof LIFECYCLE_TABS)[number];

/** Path suffix for each tab, relative to `/projects/:projectId`. */
const TAB_PATHS: Record<LifecycleTab, string> = {
  plan: "",
  results: "/results",
  sources: "/sources",
  share: "/share",
  history: "/history",
};

/**
 * The set of tabs a task at this run state can open.
 *
 * A direct transcription of the contract's locking table (task 032 § Behaviour
 * rules). Availability is computed from run state, never from whether a page
 * would happen to render empty — that is the difference between an honest
 * locked tab and a blank one.
 *
 * Sources stays open after a failed run on purpose: the corpus that was
 * gathered is real and readable, and dropping it would hide work that exists.
 * That is the flag-don't-drop discipline, not a special case.
 */
function openTabs(status: RunStatus | null | undefined): readonly LifecycleTab[] {
  if (status === null || status === undefined) return ["plan", "share"];
  switch (status) {
    case "running":
    case "paused":
      return ["plan", "sources", "share", "history"];
    case "succeeded":
    case "degraded":
      return LIFECYCLE_TABS;
    case "failed":
    case "aborted":
    case "interrupted":
      return ["plan", "sources", "share", "history"];
  }
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
 * Where a task row in the tasks list should land.
 *
 * One destination per state, never a generic detail page: a finished task
 * opens what the reader came for, and everything else opens the plan, which
 * is the only stage guaranteed to have something in it.
 */
export function taskDestination(projectId: string, status: RunStatus | null | undefined): string {
  const base = `/projects/${projectId}`;
  return status === "succeeded" ? `${base}/results` : base;
}

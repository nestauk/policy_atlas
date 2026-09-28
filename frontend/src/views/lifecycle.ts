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
function openTabs(
  status: RunStatus | null | undefined,
  options?: TabOptions,
): readonly LifecycleTab[] {
  const open = baseTabs(status);
  // Task 044 (A17): an options-scoping task's Result is its baseline, and the
  // baseline outlives the walk that wrote it — a walk aborted at the gate
  // ("Change the plan") still leaves a readable profile behind. So Result
  // opens as soon as a baseline exists, whatever the walk's ending. Task 045
  // (A7): a longlist opens it the same way — the Result then opens on the
  // longlist.
  const hasScopingResult = options?.hasBaseline === true || options?.hasLonglist === true;
  if (hasScopingResult && !open.includes("result")) {
    return LIFECYCLE_TABS.filter((tab) => tab === "result" || open.includes(tab));
  }
  return open;
}

/** Availability that run state alone cannot decide. */
export interface TabOptions {
  /** An options-scoping task with a baseline artefact written (task 044). */
  hasBaseline?: boolean;
  /** An options-scoping task with a longlist (task 045, `TaskOut.has_longlist`). */
  hasLonglist?: boolean;
}

function baseTabs(status: RunStatus | null | undefined): readonly LifecycleTab[] {
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
export function isTabOpen(
  tab: LifecycleTab,
  status: RunStatus | null | undefined,
  options?: TabOptions,
): boolean {
  return openTabs(status, options).includes(tab);
}

/** The five tabs with their label, path and availability at this run state. */
export function lifecycleTabs(
  base: string,
  status: RunStatus | null | undefined,
  options?: TabOptions,
) {
  const open = openTabs(status, options);
  return LIFECYCLE_TABS.map((tab) => ({
    tab,
    label: LIFECYCLE_LABELS[tab],
    to: `${base}${TAB_PATHS[tab]}`,
    locked: !open.includes(tab),
  }));
}

/**
 * Carry the Agent overlay's open chat (`?chat=`) onto the tab links, so a
 * move between tabs keeps the panel as it was (owner, 2026-09-05). The
 * Agent tab keeps its own default — the Task Agent — and never inherits it.
 */
export function withChat<T extends { tab: LifecycleTab; to: string }>(
  items: T[],
  chat: string | null,
): T[] {
  if (chat === null) return items;
  return items.map((item) =>
    item.tab === "agent" ? item : { ...item, to: `${item.to}?chat=${encodeURIComponent(chat)}` },
  );
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
export function taskDestination(
  taskId: string,
  status: RunStatus | null | undefined,
  options?: { hasLonglist?: boolean },
): string {
  const base = `/tasks/${taskId}`;
  // Task 045: a scoping task with a longlist opens on it, whatever its
  // latest walk is doing.
  return status === "succeeded" || options?.hasLonglist === true ? `${base}/result` : base;
}

/** The views the Result tab switches between for an options-scoping task
 *  (task 045, deliverable 9). */
export type ResultViewKey = "baseline" | "longlist" | "report";

/** One entry of the Result's view switch. */
export interface ResultViewOption {
  key: ResultViewKey;
  label: string;
  /** False for a view that is on the switch but cannot be opened yet. */
  available: boolean;
  /** Why an unavailable view is unavailable. */
  note?: string;
}

/**
 * The Result's view switch: **Baseline · Longlist · Report**, Report shown
 * but not openable until assessment (task 045, deliverable 9). `null` when
 * there is nothing to switch between — an Evidence search, or a scoping task
 * before its longlist exists (the Result is then the baseline alone).
 */
export function resultViews(options?: TabOptions): readonly ResultViewOption[] | null {
  if (options?.hasLonglist !== true) return null;
  return [
    { key: "baseline", label: "Baseline", available: true },
    { key: "longlist", label: "Longlist", available: true },
    { key: "report", label: "Report", available: false, note: "available after assessment" },
  ];
}

/**
 * Which view the Result opens on: the longlist once one exists, the baseline
 * before (ruling 50; task 045, A7). A requested view is honoured only when
 * the switch offers it and it can be opened.
 */
export function resultView(requested: string | null, options?: TabOptions): "baseline" | "longlist" {
  const views = resultViews(options);
  if (views === null) return "baseline";
  const match = views.find((view) => view.key === requested && view.available);
  return match?.key === "baseline" ? "baseline" : "longlist";
}

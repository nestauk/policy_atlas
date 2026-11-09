import { LIFECYCLE_LABELS } from "../lib/vocabulary";
import type { components } from "../api/gen/types";
import { rememberedChoice } from "../lib/remembered";

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
    // The option cards are the Result's (owner, round 14): the Result tab
    // stays current on them, its rule full.
    ...(tab === "result" ? { activePrefix: RESULT_PREFIXES.map((path) => `${base}${path}`) } : {}),
  }));
}

/** Every path the Result tab owns: its views and the option cards. */
const RESULT_PREFIXES = ["/result", "/options"] as const;

/**
 * Which Sources view the Sources tab opens on (annex § Owner round after the
 * trace, item 8): the view whose step has landed. While an Evidence search
 * runs, All sources until classification completes, then Landscape, then
 * Themes once mapping completes; with no run live, Themes (the Sources
 * index) as before. A scoping walk keeps the index.
 *
 * Args:
 *   status: The live run's status, if any.
 *   stages: The live run's stage frames.
 *   evidenceSearch: True when the task is an Evidence search.
 *
 * Returns:
 *   The path after `/sources`: `"/all"`, `"/landscape"` or `""`.
 */
export function sourcesLanding(
  status: RunStatus | null | undefined,
  stages: readonly { stage: string; status: string }[],
  evidenceSearch: boolean,
): "" | "/all" | "/landscape" {
  if (!evidenceSearch || (status !== "running" && status !== "paused")) return "";
  const done = (stage: string) => stages.some((entry) => entry.stage === stage && entry.status === "completed");
  if (done("characterise")) return "";
  // Classifying is one step of two stages (classify, then appraise): it has
  // completed once neither of them is still open.
  const classifying = stages.filter((entry) => entry.stage === "classify" || entry.stage === "appraise");
  const classified = done("classify") && classifying.every((entry) => entry.status !== "started");
  return classified ? "/landscape" : "/all";
}

/** The subtab paths after `/sources` ("" is Themes, the index). */
export type SourcesSubtab = "" | "/landscape" | "/all" | "/findings";

const SOURCES_SUBTABS: readonly SourcesSubtab[] = ["", "/landscape", "/all", "/findings"];

/**
 * The Sources subtab a reader last chose on a task (owner, round 10), kept
 * under `policy-atlas:sources-subtab:<taskId>` (Themes stored as "themes").
 * Before the reader has chosen one, the Sources tab lands by stage
 * (`sourcesLanding`); once they pick a subtab on this task, the Sources tab
 * returns them there, live or done, until they pick another.
 */
export const sourcesSubtabChoice = rememberedChoice<SourcesSubtab>("sources-subtab", {
  write: (subtab) => (subtab === "" ? "themes" : subtab),
  read: (stored) => {
    const subtab = stored === "themes" ? "" : stored;
    return SOURCES_SUBTABS.find((candidate) => candidate === subtab) ?? null;
  },
});

/** Point the Sources tab's link at the subtab the reader last chose on this
 *  task (owner, round 10: kept per task in `localStorage`), or, before they
 *  have chosen one or when the storage cannot be read, at `sourcesLanding`'s
 *  view; any `?chat=` is kept, and the tab stays marked on every Sources
 *  view. */
export function withSourcesLanding<T extends { tab: string; to: string }>(
  items: T[],
  landing: "" | "/all" | "/landscape",
): Array<T & { activePrefix?: string }> {
  return items.map((item) => {
    if (item.tab !== "sources") return item;
    const [path, query] = item.to.split("?");
    const taskId = /\/tasks\/([^/]+)\/sources$/.exec(path)?.[1];
    const chosen = taskId === undefined ? null : sourcesSubtabChoice.read(decodeURIComponent(taskId));
    return {
      ...item,
      to: `${path}${chosen ?? landing}${query === undefined ? "" : `?${query}`}`,
      activePrefix: path,
    };
  });
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
  // latest walk is doing. A degraded finish opens the report like a
  // succeeded one (task 058, N14).
  return hasResult(status) || options?.hasLonglist === true ? `${base}/result` : base;
}

/**
 * The lifecycle tab a path inside the task belongs to, or `null` outside it.
 *
 * Args:
 *   pathname: The current location's path.
 *   base: The task's root path (`/tasks/:taskId`).
 *
 * Returns:
 *   The tab whose page the path is on (Sources' subviews count as Sources).
 */
export function tabOfPath(pathname: string, base: string): LifecycleTab | null {
  if (pathname === base || pathname === `${base}/`) return "agent";
  if (!pathname.startsWith(`${base}/`)) return null;
  const segment = pathname.slice(base.length + 1).split("/")[0];
  // An option card is the Result's (round 14).
  if (segment === "options") return "result";
  return LIFECYCLE_TABS.find((tab) => tab !== "agent" && TAB_PATHS[tab] === `/${segment}`) ?? null;
}

/** The Result's view switch once a scoping task has a longlist (task 045,
 *  deliverable 9; task 055 adds Shortlist): **Baseline · Longlist · Shortlist · Report**,
 *  Report shown but not openable until assessment. */
export const RESULT_VIEWS: readonly { key: string; label: string; note?: string }[] = [
  { key: "baseline", label: "Baseline" },
  { key: "longlist", label: "Longlist" },
  { key: "shortlist", label: "Shortlist" },
  { key: "report", label: "Report", note: "available after assessment" },
];

/** Which view the Result opens on: the longlist unless the baseline is asked
 *  for (ruling 50; task 045, A7). */
export function resultView(requested: string | null): "baseline" | "longlist" | "shortlist" {
  if (requested === "baseline" || requested === "shortlist") return requested;
  return "longlist";
}

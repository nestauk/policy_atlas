import type { components } from "../api/gen/types";

/**
 * What exists and what is active (task 045, S15; ADR 0039 decision 5).
 *
 * An options-scoping task runs several walks — the baseline, the longlist,
 * the longlist's option searches (its children) and the searches a chat
 * *add* starts — so "the latest run" no longer answers the readers'
 * questions. A scoping reader asks two things instead: is any walk running or
 * paused (`TaskOut.active_run`, children included), and which results exist
 * (`TaskOut.has_longlist`, the baseline artefact). An Evidence search keeps
 * reading `latest_run` exactly as before. The rule lives here once; every
 * reader calls these helpers rather than re-deriving it.
 */

type LatestRun = components["schemas"]["LatestRun"];
type RunStatus = LatestRun["status"];

/** The `TaskOut` fields these helpers read. All optional so a list row or a
 *  test fixture assembled by hand still type-checks. */
export interface TaskActivity {
  capability?: string | null;
  latest_run?: LatestRun | null;
  active_run?: LatestRun | null;
  has_longlist?: boolean | null;
}

const ACTIVE_STATUSES: ReadonlySet<RunStatus> = new Set<RunStatus>(["running", "paused"]);

/** Whether this is an options-scoping task. */
export function isScoping(task: TaskActivity | null | undefined): boolean {
  return task?.capability === "options_scoping";
}

/**
 * The walk that is running or paused right now, or `null`.
 *
 * A scoping task reads `active_run` — any walk, children included, so a
 * running option search shows as activity. An Evidence search reads its
 * `latest_run` when that is running or paused, as it always has.
 */
export function activeRun(task: TaskActivity | null | undefined): LatestRun | null {
  if (task == null) return null;
  if (isScoping(task)) return task.active_run ?? null;
  const latest = task.latest_run ?? null;
  return latest !== null && ACTIVE_STATUSES.has(latest.status) ? latest : null;
}

/** Whether any walk of the task is running or paused. */
export function isRunActive(task: TaskActivity | null | undefined): boolean {
  return activeRun(task) !== null;
}

/**
 * The walk a status word describes (the task lists' "Analysing…",
 * "Complete", "Failed").
 *
 * An Evidence search: its `latest_run`, unchanged. A scoping task: the
 * active walk while one runs, else `latest_run` — which the server keeps as
 * the latest walk that is neither a child nor an option search, so a
 * finished option search never becomes what the task "is".
 */
export function statusRun(task: TaskActivity | null | undefined): LatestRun | null {
  if (task == null) return null;
  if (isScoping(task)) return task.active_run ?? task.latest_run ?? null;
  return task.latest_run ?? null;
}

/**
 * The run status the lifecycle tabs are computed from.
 *
 * `latest_run` for both kinds. For a scoping task that is the latest walk
 * that is neither a child nor an option search (S15), so an option search
 * starting or finishing never opens or locks a tab; the results that exist
 * (`hasBaseline`, `hasLonglist`) open Result on top of it.
 */
export function tabRunStatus(task: TaskActivity | null | undefined): RunStatus | undefined {
  return task?.latest_run?.status;
}

/** Whether a scoping task has a longlist. Always false for an Evidence
 *  search. */
export function hasLonglist(task: TaskActivity | null | undefined): boolean {
  return isScoping(task) && task?.has_longlist === true;
}

/**
 * Whether the task has a result to ask about (038 V8 — chats open only
 * then).
 *
 * An Evidence search: its latest run finished with a report. A scoping
 * task: a longlist or a baseline exists, or its latest walk finished with
 * one.
 *
 * Args:
 *   task: The task read model.
 *   options: `hasBaseline` — whether a baseline artefact exists, when the
 *     caller has read it.
 */
export function hasTaskResult(
  task: TaskActivity | null | undefined,
  options?: { hasBaseline?: boolean },
): boolean {
  const finished = (status: RunStatus | undefined) =>
    status === "succeeded" || status === "degraded";
  if (!isScoping(task)) return finished(task?.latest_run?.status);
  return hasLonglist(task) || options?.hasBaseline === true || finished(task?.latest_run?.status);
}

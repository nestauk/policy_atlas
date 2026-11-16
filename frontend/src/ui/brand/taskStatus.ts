/*
 * A task's status words (task 058, consolidation batch B): the one place a
 * task row or a run says what state it is in. The task list's row, the run
 * trace, the run status bar and the browser title all come here, and the
 * caller adds only what is live (the step in progress, its timer).
 *
 * One separator, " · ", across the words (round 10). A paused run names who
 * it waits on: the reader ("waiting on you"), or the owner by first name, or
 * no one when it has no owner (lead ruling P2, round 10). An archived task
 * reads "Archived", whatever its last run.
 */

import type { components } from "../../api/gen/types";
import type { StatusTone } from "./Card";

type LatestRun = components["schemas"]["TaskOut"]["latest_run"];

/** A run's status as the wire names it (`running`, `paused`, `succeeded`,
 *  `degraded`, `failed`, `interrupted`, `aborted`), or none for a task that
 *  has not run. */
export type RunStatusLike = string | null | undefined;

/** Who a task belongs to and where it sits, for the words. */
export type StatusContext = {
  /** `TaskOut.is_owner`; a caller with no organisation owns every row, so
   *  undefined reads as the reader's own task. */
  isOwner?: boolean;
  /** `TaskOut.owner_display`, or null for an ownerless task. */
  ownerName?: string | null;
  /** `TaskOut.status === "archived"`. */
  archived?: boolean;
  /** A finished run old enough to read as stale (`isStale`). */
  stale?: boolean;
};

/** A live run, before the caller adds its step. */
export const RUNNING_WORD = "Running";

/** The first word of a display name ("Grace Hopper" → "Grace"). */
function firstName(name: string | null | undefined): string {
  return name?.trim().split(/\s+/)[0] ?? "";
}

/**
 * The status word for a task row or a run.
 *
 * Args:
 *   status: The latest run's status, or none.
 *   context: Whose task it is, whether it is archived, whether it is stale.
 *
 * Returns:
 *   "Running", "Paused · waiting on you", "Paused · waiting on <first
 *   name>", "Paused", "Complete", "Complete · with gaps", "Stale", "Failed",
 *   "Stopped", "Archived" or "Not started".
 */
export function taskStatusWord(status: RunStatusLike, context: StatusContext = {}): string {
  if (context.archived === true) return "Archived";
  switch (status) {
    case "running":
      return RUNNING_WORD;
    case "paused": {
      if (context.isOwner !== false) return "Paused · waiting on you";
      const owner = firstName(context.ownerName);
      return owner !== "" ? `Paused · waiting on ${owner}` : "Paused";
    }
    case "succeeded":
      return context.stale === true ? "Stale" : "Complete";
    case "degraded":
      return "Complete · with gaps";
    case "failed":
      return "Failed";
    case "interrupted":
    case "aborted":
      return "Stopped";
    default:
      return "Not started";
  }
}

/**
 * The task row's status mark beside the word (`StatusMark`'s tone).
 *
 * Args:
 *   status: The latest run's status, or none.
 *   archived: An archived task's mark is idle, whatever its last run.
 *
 * Returns:
 *   The mark's tone.
 */
export function taskStatusTone(status: RunStatusLike, archived = false): StatusTone {
  if (archived) return "idle";
  switch (status) {
    case "running":
      return "running";
    case "paused":
      return "paused";
    case "succeeded":
    case "degraded":
      return "complete";
    case "failed":
    case "interrupted":
      return "failed";
    default:
      return "idle";
  }
}

/** A task is stale once its finished run is this old. */
const STALE_AFTER_MONTHS = 12;

/**
 * Whether a finished task is old enough to read as stale.
 *
 * Derived, never stored: staleness is a fact about the calendar, not a state
 * the run reaches, so caching it on the row would mean a task quietly staying
 * "fresh" forever. Only a succeeded run can be stale — a failed one has a
 * more important thing to say about itself.
 *
 * Args:
 *   latestRun: The task's latest run (`TaskOut.latest_run`).
 *   now: The current time; a parameter so the twelve-month boundary is
 *     testable without mocking the clock.
 *
 * Returns:
 *   True when the run succeeded more than twelve months before `now`.
 */
export function isStale(latestRun: LatestRun, now: Date = new Date()): boolean {
  if (latestRun?.status !== "succeeded") return false;
  const endedAt = latestRun.ended_at;
  if (endedAt == null) return false;
  const cutoff = new Date(now);
  cutoff.setMonth(cutoff.getMonth() - STALE_AFTER_MONTHS);
  return new Date(endedAt) < cutoff;
}

/** What kind of walk a run is (task 045): an Evidence search, a scoping
 *  task's baseline walk, its longlist walk, an added option's own search, or
 *  the shortlist walk; and a theory of change's walks (task 054): the draft,
 *  an uploaded theory's read, the evidence check and "Update the report".
 *  A finished run's words follow it ("the evidence base is ready" is wrong
 *  for a longlist). */
export type WalkKind =
  | "evidence_search"
  | "baseline"
  | "longlist"
  | "option_search"
  | "shortlist"
  | "toc_draft"
  | "toc_read"
  | "toc_check"
  | "toc_report_update";

/** The words a run that finished well ends with, per walk: the trace's top
 *  line and the browser title's unseen finish ("● Report ready"). A theory
 *  of change's draft and an uploaded theory's read both end "Theory
 *  drafted"; its check ends "Evidence checked" (owner decision 6, task 054). */
export const READY_WORDS: Record<WalkKind, string> = {
  evidence_search: "Report ready",
  baseline: "The baseline is ready",
  longlist: "The longlist is ready",
  option_search: "The option's search is done",
  shortlist: "The shortlist is proposed",
  toc_draft: "Theory drafted",
  toc_read: "Theory drafted",
  toc_check: "Evidence checked",
  toc_report_update: "Report ready",
};

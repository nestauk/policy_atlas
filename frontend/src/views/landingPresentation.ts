import type { components } from "../api/gen/types";

type LatestRun = components["schemas"]["TaskOut"]["latest_run"];

/** The precise local-state reset used when a task rename is cancelled. */
export function cancelledRenameState(taskName: string): { editing: false; draftName: string } {
  return { editing: false, draftName: taskName };
}

/** A task is stale once its finished run is this old. */
const STALE_AFTER_MONTHS = 12;

type RunPresentation = {
  dot: "running" | "complete" | "paused" | "idle" | "failed";
  label: string;
  tone: "default" | "blue" | "soft" | "green" | "yellow" | "red";
};

/** Who a task belongs to, for the words that name who it waits on. */
type StatusContext = {
  /** `TaskOut.is_owner`; a caller with no organisation owns every row, so
   *  undefined reads as the reader's own task. */
  isOwner?: boolean;
  /** `TaskOut.owner_display`, or null for an ownerless task. */
  ownerName?: string | null;
  /** `TaskOut.status === "archived"`. */
  archived?: boolean;
};

/** The first word of a display name ("Grace Hopper" → "Grace"). */
function firstName(name: string | null | undefined): string {
  return name?.trim().split(/\s+/)[0] ?? "";
}

/**
 * Derive a task's presentation from its latest capability run.
 *
 * Run state is never cached on the task row, so this reads the derived
 * `latest_run` read model. This is the app's ONE status vocabulary — the
 * tasks list, the task pages and the landing cards all come here rather
 * than inventing a second set of words for the same states.
 *
 * One separator, " · ", across the words (round 10). A paused task names
 * who it waits on: the reader ("waiting on you"), or the owner by first
 * name, or no one when it has no owner (lead ruling P2, round 10). An
 * archived task reads "Archived", whatever its last run.
 */
export function runPresentation(latestRun: LatestRun, context: StatusContext = {}): RunPresentation {
  if (context.archived === true) return { dot: "idle", label: "Archived", tone: "soft" };
  switch (latestRun?.status) {
    case "running": return { dot: "running", label: "Analysing the evidence…", tone: "yellow" };
    case "paused": {
      const owner = firstName(context.ownerName);
      const label =
        context.isOwner !== false
          ? "Paused · waiting on you"
          : owner !== ""
            ? `Paused · waiting on ${owner}`
            : "Paused";
      return { dot: "paused", label, tone: "yellow" };
    }
    case "succeeded": return { dot: "complete", label: "Complete", tone: "green" };
    case "degraded": return { dot: "complete", label: "Complete · with gaps", tone: "yellow" };
    case "failed": return { dot: "failed", label: "Failed", tone: "red" };
    case "interrupted": return { dot: "failed", label: "Interrupted", tone: "red" };
    case "aborted": return { dot: "idle", label: "Stopped", tone: "soft" };
    default: return { dot: "idle", label: "Not started", tone: "soft" };
  }
}

/**
 * Whether a finished task is old enough to read as stale.
 *
 * Derived, never stored: staleness is a fact about the calendar, not a state
 * the run reaches, so caching it on the row would mean a task quietly staying
 * "fresh" forever. Only a succeeded run can be stale — a failed one has a
 * more important thing to say about itself.
 *
 * `now` is a parameter so the twelve-month boundary is testable without
 * mocking the clock.
 */
export function isStale(latestRun: LatestRun, now: Date = new Date()): boolean {
  if (latestRun?.status !== "succeeded") return false;
  const endedAt = latestRun.ended_at;
  if (endedAt == null) return false;
  const cutoff = new Date(now);
  cutoff.setMonth(cutoff.getMonth() - STALE_AFTER_MONTHS);
  return new Date(endedAt) < cutoff;
}

/** The status word for a task row, with staleness folded in. */
export function taskStatus(
  latestRun: LatestRun,
  now: Date = new Date(),
  context: StatusContext = {},
): RunPresentation {
  const base = runPresentation(latestRun, context);
  return context.archived !== true && isStale(latestRun, now) ? { ...base, label: "Stale", tone: "soft" } : base;
}

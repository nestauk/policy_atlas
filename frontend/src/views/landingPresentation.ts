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

/**
 * Derive a task's presentation from its latest capability run.
 *
 * Run state is never cached on the task row, so this reads the derived
 * `latest_run` read model. This is the app's ONE status vocabulary — the
 * tasks list, the task pages and the landing cards all come here rather
 * than inventing a second set of words for the same states.
 */
export function runPresentation(latestRun: LatestRun): RunPresentation {
  switch (latestRun?.status) {
    case "running": return { dot: "running", label: "Analysing the evidence…", tone: "yellow" };
    case "paused": return { dot: "paused", label: "Paused — waiting on your input", tone: "yellow" };
    case "succeeded": return { dot: "complete", label: "Complete", tone: "green" };
    case "degraded": return { dot: "complete", label: "Complete — with gaps", tone: "yellow" };
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
export function taskStatus(latestRun: LatestRun, now: Date = new Date()): RunPresentation {
  const base = runPresentation(latestRun);
  return isStale(latestRun, now) ? { ...base, label: "Stale", tone: "soft" } : base;
}

import type { components } from "../api/gen/types";

export type CheckInOut = components["schemas"]["CheckInOut"];
export type PlanDraft = components["schemas"]["PlanDraft"];
export type RunStatus = components["schemas"]["RunStatusFrame"]["status"];
export type StageName = components["schemas"]["StageStartedFrame"]["stage"];

export type StageStatus = "started" | "completed" | "failed" | "skipped";

/** One step in the run timeline. Pinned shape (task 025 §4). */
export interface StageEntry {
  stage: StageName;
  label: string;
  status: StageStatus;
  summary?: Record<string, number | string>;
  seconds?: number | null;
  blurb?: string;
}

/** The current run, as far as the reducer needs to track it. */
export interface RunRef {
  id: string;
  status: RunStatus;
}

/** One entry in the resolved-decisions log (a `checkin.resolved` frame,
 *  camelCased for store-side consumption). */
export interface ResolvedDecision {
  checkInId: string;
  response: Record<string, unknown>;
  decidedBy: "user" | "orchestrator" | "standing_default" | null;
  occurredAt: string;
  sequence: number;
}

/** The current plan row, as surfaced by `plan.updated`. */
export interface PlanState {
  version: number;
  plan: PlanDraft;
}

/** Project lifecycle fields as surfaced by `project.updated` audit events.
 *  Fields are independently set (a rename touches `name` only, an archive
 *  touches `status` only) — `null` on the wire means "not touched by this
 *  event", not "cleared". */
export interface ProjectSummary {
  name?: string | null;
  question?: string | null;
  status?: "active" | "archived" | null;
}

/** Last tick note for one stage (or the global key, for stage-less ticks). */
export interface StageLiveness {
  note: string;
  occurredAt: string;
}

/** Liveness key used for `tick` frames with no `stage`. */
export const GLOBAL_LIVENESS_KEY = "_global";

export interface RunStreamState {
  /** Highest applied frame `sequence` — the replay-idempotence gate. */
  lastSequence: number;
  run: RunRef | null;
  runs: Record<string, RunStatus>;
  stages: StageEntry[];
  pendingCheckIn: CheckInOut | null;
  decisions: ResolvedDecision[];
  plan: PlanState | null;
  project: ProjectSummary;
  /** Transient: last note per stage. Never sequence-gated, never replayed
   *  (a fresh mount/reconnect starts this slice empty regardless of
   *  cursor). */
  liveness: Record<string, StageLiveness>;
}

export function createInitialRunStreamState(): RunStreamState {
  return {
    lastSequence: 0,
    run: null,
    runs: {},
    stages: [],
    pendingCheckIn: null,
    decisions: [],
    plan: null,
    project: {},
    liveness: {},
  };
}

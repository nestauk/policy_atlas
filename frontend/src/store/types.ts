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
  /** First `run.status` / `occurred_at` seen for this run id. */
  startedAt: string;
  /** Terminal `run.status` / `occurred_at` — omitted while the run is live. */
  endedAt?: string;
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

/** One presentation-only artefact section received through the live SSE
 * stream. `index` is the display identity: it deliberately does not rely on
 * a title, because titles are not unique. */
export interface LiveSection {
  index: number;
  title: string;
  focus: string;
  state: "planned" | "writing" | "filled";
  prose?: string;
}

/** Liveness key used for `tick` frames with no `stage`. */
export const GLOBAL_LIVENESS_KEY = "_global";

export interface RunStreamState {
  /** Current transport state for the SSE feedback surface. `"connecting"`
   *  is the pre-first-connection state (never shown as a reconnect banner);
   *  `"reconnecting"` is a lapsed live connection. */
  connectionStatus: "connecting" | "connected" | "reconnecting";
  /** Highest applied frame `sequence` — the replay-idempotence gate. */
  lastSequence: number;
  /** Frame `type`s already applied at `lastSequence` — lets two frames that
   *  share a sequence (one durable event emitting both, e.g.
   *  `checkin.resolved` + `plan.updated`) each apply once instead of the
   *  second being dropped by the sequence gate. Reset whenever the
   *  sequence advances. */
  appliedTypesAtLastSequence: string[];
  run: RunRef | null;
  runs: Record<string, RunStatus>;
  stages: StageEntry[];
  pendingCheckIn: CheckInOut | null;
  decisions: ResolvedDecision[];
  plan: PlanState | null;
  project: ProjectSummary;
  /** Presentation-only live artefact sections, keyed by their display
   * index. They are not the persisted evidence-base artefact. */
  liveSections: Record<number, LiveSection>;
  /** Transient: last note per stage. Never sequence-gated, never replayed
   *  (a fresh mount/reconnect starts this slice empty regardless of
   *  cursor). */
  liveness: Record<string, StageLiveness>;
}

export function createInitialRunStreamState(): RunStreamState {
  return {
    connectionStatus: "connecting",
    lastSequence: 0,
    appliedTypesAtLastSequence: [],
    run: null,
    runs: {},
    stages: [],
    pendingCheckIn: null,
    decisions: [],
    plan: null,
    project: {},
    liveSections: {},
    liveness: {},
  };
}

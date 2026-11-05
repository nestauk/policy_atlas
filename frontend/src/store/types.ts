import type { components } from "../api/gen/types";

export type CheckInOut = components["schemas"]["CheckInOut"];
export type PlanDraft = components["schemas"]["PlanDraft"];
export type RunStatus = components["schemas"]["RunStatusFrame"]["status"];
type StageName = components["schemas"]["StageStartedFrame"]["stage"];

export type StageStatus = "started" | "completed" | "failed" | "skipped";

/** One step in the run timeline. Pinned shape (task 025 §4). */
export interface StageEntry {
  stage: StageName;
  label: string;
  status: StageStatus;
  summary?: Record<string, number | string>;
  seconds?: number | null;
  /** The done row's counts with the server's nouns (task 058, N17). */
  counts?: { value: number; noun: string }[];
  blurb?: string;
  /** When the stage started: the `occurred_at` of its `stage.started`
   *  frame, kept through `stage.completed` / `stage.failed` so the card can
   *  show the in-progress row's elapsed time and a merged row's span
   *  (task 058, N5). */
  startedAt: string;
}

/** The current run, as far as the reducer needs to track it. */
interface RunRef {
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
  decidedBy: "user" | "agent" | "standing_default" | null;
  occurredAt: string;
  sequence: number;
}

/** The current plan row, as surfaced by `plan.updated`. */
interface PlanState {
  version: number;
  /** Null for an Options scoping task: its plan travels on `scoping` and the
   *  plan document reads it from the plan query, not the stream (task 044). */
  plan: PlanDraft | null;
}

/** Project lifecycle fields as surfaced by `task.updated` audit events.
 *  Fields are independently set (a rename touches `name` only, an archive
 *  touches `status` only) — `null` on the wire means "not touched by this
 *  event", not "cleared". */
interface TaskSummary {
  name?: string | null;
  question?: string | null;
  status?: "active" | "archived" | null;
}

/** The latest tick for one stage (or the global key, for stage-less
 *  ticks) — what the model is doing now (task 058, D2). Null counts on the
 *  wire are left out here. The view decides from `occurredAt` whether the
 *  activity dot still breathes. */
export interface StageLiveness {
  /** The activity line, in the server's words; shown as it is. */
  activity: string;
  /** Items finished so far, when the stage has an honest count. */
  done?: number;
  /** The total known before the stage's loop started. */
  total?: number;
  /** What `done` and `total` count (`documents`, `batches`, ...). */
  unit?: string;
  /** The writer's section line ("Section 3 of 7 · Costs"), while writing. */
  section?: string;
  /** True when the server repeated the tick because a model call is still
   *  running, not because anything changed. */
  heartbeat: boolean;
  /** The server's dropped-tick counter for this task. */
  dropped: number;
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
  /** What the section is (`key_findings`, `case_studies`, `body` or
   *  `intro`), from the skeleton, so the page orders live sections by the
   *  same rule as the saved report (task 058, round 7). `intro` (round 8) is
   *  the paragraph the saved report shows under "Full report": after the
   *  executive summary, before the body sections, whatever its index. */
  role?: string;
  prose?: string;
  /** The prose streamed so far for a section being written, from the
   *  ephemeral `artefact.section_delta` frames. Kept apart from `prose`
   *  (the durable record) and cleared when the section completes
   *  (task 058, N7). */
  draft?: string;
  /** Character spans of `draft` the checker failed and the writer is now
   *  revising (`artefact.section_revising`); cleared on completion. */
  revising?: { start: number; end: number }[];
  /** The sources the writer has read so far for this section, in the order
   *  first read (`artefact.section_sources`; each frame replaces the set);
   *  cleared on completion. */
  sources?: LiveSource[];
  /** The writer's own citations as they close, each a code-point span of
   *  `draft` and the sources it cites (`artefact.section_claim`). Not yet
   *  checked; cleared on completion and when the draft is replaced. */
  claims?: LiveClaim[];
  /** The checked section's citations (`artefact.section_completed`), each a
   *  code-point span of `prose` with its report-wide reference number. Set
   *  on completion when the section has any, and kept until the committed
   *  report replaces the live view (task 058, round 7). */
  citations?: LiveCitation[];
  /** Case-study cards as each one closes in the streamed reply
   *  (`artefact.section_card`), in order; cleared on completion and when the
   *  draft is replaced (task 058, round 7). */
  cards?: LiveCard[];
}

/** One checked citation on a completed live section (task 058, round 7).
 *  `[start, end)` counts code points of the section's `prose`; `n` is the
 *  report-wide reference number; `tier` is the judge's verdict, or null.
 *  `citationId` and `claimId` are the ids the committed report's citation and
 *  claim carry (the chunk context is asked for by `citationId`), and `quote`
 *  the checked quote (round 8); the ids are null and the quote empty on a
 *  frame recorded before round 8. */
export interface LiveCitation {
  start: number;
  end: number;
  n: number;
  sourceId: string | null;
  title: string;
  tier: string | null;
  citationId: string | null;
  claimId: string | null;
  quote: string;
}

/** One most-relevant-source note as it is written (`artefact.source_note`,
 *  task 058, round 8). Display-only: the committed report brings the notes
 *  it keeps. */
export interface LiveSourceNote {
  sourceId: string;
  title: string;
  note: string;
}

/** One case-study card as it closes in the streamed reply (task 058, round 7). */
export interface LiveCard {
  title: string;
  prose: string;
}

/** A source named on the page while a section is written. */
export interface LiveSource {
  sourceId: string;
  title: string;
}

/** One provisional citation in a section draft (task 058, owner 2026-11-05). */
export interface LiveClaim {
  start: number;
  end: number;
  sources: LiveSource[];
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
  /** Runs first seen while another walk was running or paused — child walks
   *  (task 045 option searches). None of them ever becomes `run`. */
  childRunIds: string[];
  stages: StageEntry[];
  pendingCheckIn: CheckInOut | null;
  decisions: ResolvedDecision[];
  plan: PlanState | null;
  task: TaskSummary;
  /** Presentation-only live artefact sections, keyed by their display
   * index. They are not the persisted evidence-search artefact. */
  liveSections: Record<number, LiveSection>;
  /** Transient: streamed drafts for section indices the store has no
   *  skeleton for yet. The next `artefact.skeleton` folds them into its
   *  sections, so no streamed prose is lost (task 058, N7). */
  pendingDrafts: Record<number, string>;
  /** The run's source notes as each is written, in order, one per source
   *  (`artefact.source_note`; a reconnect's repeat replaces, never doubles).
   *  Absent until the first note; cleared when a new run starts (task 058,
   *  round 8). */
  liveSourceNotes?: LiveSourceNote[];
  /** Transient: latest tick per stage. Never sequence-gated, never replayed
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
    childRunIds: [],
    stages: [],
    pendingCheckIn: null,
    decisions: [],
    plan: null,
    task: {},
    liveSections: {},
    pendingDrafts: {},
    liveness: {},
  };
}

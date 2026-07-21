import type { SseFrame } from "../api/sseFrame";
import { GLOBAL_LIVENESS_KEY, type ResolvedDecision, type RunStreamState, type StageEntry } from "./types";

/**
 * Pure reducer over the SSE frame stream — no framework, no side effects.
 *
 * Replay-idempotent: every frame except `tick` carries a `sequence`, and
 * any frame with `sequence <= state.lastSequence` is dropped unchanged.
 * That makes folding the same frame stream twice, or resuming the fold
 * from any mid-stream cursor, produce the same final state. `tick` frames
 * are the deliberate exception: they carry no `sequence` at all, update
 * only the transient `liveness` slice, and never advance `lastSequence`.
 */
export function reduceRunStreamFrame(state: RunStreamState, frame: SseFrame): RunStreamState {
  if (frame.type === "tick") {
    const key = frame.stage ?? GLOBAL_LIVENESS_KEY;
    return {
      ...state,
      liveness: { ...state.liveness, [key]: { note: frame.note, occurredAt: frame.occurred_at } },
    };
  }

  if (frame.sequence <= state.lastSequence) {
    return state; // already applied — idempotent drop
  }

  const base: RunStreamState = { ...state, lastSequence: frame.sequence };

  switch (frame.type) {
    case "run.status":
      return {
        ...base,
        run: { id: frame.capability_run_id, status: frame.status },
        runs: { ...base.runs, [frame.capability_run_id]: frame.status },
      };

    case "stage.started":
      return {
        ...base,
        stages: [
          ...base.stages,
          { stage: frame.stage, label: frame.label, status: "started", blurb: frame.blurb },
        ],
      };

    case "stage.completed":
      return {
        ...base,
        stages: replaceStartedStage(base.stages, frame.stage, {
          stage: frame.stage,
          label: frame.label,
          status: "completed",
          summary: frame.summary,
          seconds: frame.seconds,
        }),
      };

    case "stage.failed":
      // The pinned stage-entry shape (task 025 §4) has no `reason` field —
      // the failure reason travels in `summary` instead, the one bucket
      // already typed to hold an arbitrary string value.
      return {
        ...base,
        stages: replaceStartedStage(base.stages, frame.stage, {
          stage: frame.stage,
          label: frame.label,
          status: frame.skipped ? "skipped" : "failed",
          summary: { reason: frame.reason },
        }),
      };

    case "checkin.pending":
      return { ...base, pendingCheckIn: frame.check_in };

    case "checkin.resolved": {
      const decision: ResolvedDecision = {
        checkInId: frame.check_in_id,
        response: frame.response,
        decidedBy: frame.decided_by,
        occurredAt: frame.occurred_at,
        sequence: frame.sequence,
      };
      const clearsPending = base.pendingCheckIn?.check_in_id === frame.check_in_id;
      return {
        ...base,
        pendingCheckIn: clearsPending ? null : base.pendingCheckIn,
        decisions: [...base.decisions, decision],
      };
    }

    case "plan.updated":
      return { ...base, plan: { version: frame.version, plan: frame.plan } };

    case "project.updated":
      // `null` on the wire means "not touched by this event" — preserve
      // whatever the store already had for a field this event didn't set.
      return {
        ...base,
        project: {
          name: frame.name ?? base.project.name,
          question: frame.question ?? base.project.question,
          status: frame.status ?? base.project.status,
        },
      };

    default:
      return assertNever(frame);
  }
}

/** Find the most recent `started` entry for `stage` and replace it in
 *  place; append instead if none is found (defensive — shouldn't happen
 *  given the server's start-before-terminal ordering). */
function replaceStartedStage(
  stages: StageEntry[],
  stage: StageEntry["stage"],
  replacement: StageEntry,
): StageEntry[] {
  for (let index = stages.length - 1; index >= 0; index--) {
    if (stages[index].stage === stage && stages[index].status === "started") {
      const next = stages.slice();
      next[index] = replacement;
      return next;
    }
  }
  return [...stages, replacement];
}

function assertNever(value: never): never {
  throw new Error(`Unhandled SSE frame type: ${JSON.stringify(value)}`);
}

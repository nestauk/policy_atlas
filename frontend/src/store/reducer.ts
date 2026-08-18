import type { SseFrame } from "../api/sseFrame";
import {
  GLOBAL_LIVENESS_KEY,
  type LiveSection,
  type ResolvedDecision,
  type RunStreamState,
  type StageEntry,
} from "./types";

/**
 * Pure reducer over the SSE frame stream — no framework, no side effects.
 *
 * Replay-idempotent: every frame except `tick` carries a `sequence`. A
 * frame with `sequence < state.lastSequence` is a stale re-delivery and is
 * dropped unchanged. One durable event can emit more than one frame
 * *type* at the same sequence (e.g. `checkin.resolved` + `plan.updated`
 * from one steering decision) — those must each apply once, so a frame
 * with `sequence === state.lastSequence` is dropped only if its `type` is
 * already recorded in `appliedTypesAtLastSequence` for that sequence.
 * That set resets whenever the sequence actually advances. Together this
 * makes folding the same frame stream twice, or resuming the fold from
 * any mid-stream cursor (however the redelivery is sliced), produce the
 * same final state. `tick` frames are the deliberate exception: they
 * carry no `sequence` at all, update only the transient `liveness` slice,
 * and never advance `lastSequence`.
 */
export function reduceRunStreamFrame(state: RunStreamState, frame: SseFrame): RunStreamState {
  if (frame.type === "tick") {
    const key = frame.stage ?? GLOBAL_LIVENESS_KEY;
    return {
      ...state,
      liveness: { ...state.liveness, [key]: { note: frame.note, occurredAt: frame.occurred_at } },
    };
  }

  if (frame.sequence < state.lastSequence) {
    return state; // a stale re-delivery — idempotent drop
  }
  if (frame.sequence === state.lastSequence && state.appliedTypesAtLastSequence.includes(frame.type)) {
    return state; // this exact frame type already applied at this sequence
  }

  const sequenceAdvanced = frame.sequence > state.lastSequence;
  const base: RunStreamState = {
    ...state,
    lastSequence: frame.sequence,
    appliedTypesAtLastSequence: sequenceAdvanced
      ? [frame.type]
      : [...state.appliedTypesAtLastSequence, frame.type],
  };

  switch (frame.type) {
    case "run.status": {
      // A `run.status(running)` for a different run than the one the store
      // currently tracks is a fresh walk — its timeline must not inherit
      // the previous (possibly interrupted) run's stage entries or liveness.
      const current = base.run;
      const isNewRun = frame.status === "running" && frame.capability_run_id !== current?.id;
      const sameRun = current !== null && current.id === frame.capability_run_id;
      const isTerminal =
        frame.status === "succeeded" ||
        frame.status === "failed" ||
        frame.status === "aborted" ||
        frame.status === "interrupted" ||
        frame.status === "degraded";
      return {
        ...base,
        run: {
          id: frame.capability_run_id,
          status: frame.status,
          startedAt: sameRun ? current.startedAt : frame.occurred_at,
          ...(isTerminal
            ? { endedAt: frame.occurred_at }
            : sameRun && current.endedAt !== undefined
              ? { endedAt: current.endedAt }
              : {}),
        },
        runs: { ...base.runs, [frame.capability_run_id]: frame.status },
        stages: isNewRun ? [] : base.stages,
        liveness: isNewRun ? {} : base.liveness,
        liveSections: isNewRun ? {} : base.liveSections,
      };
    }

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

    case "artefact.skeleton":
      return {
        ...base,
        liveSections: Object.fromEntries(
          frame.sections.map((section) => [
            section.index,
            {
              index: section.index,
              title: section.title,
              focus: section.focus,
              state: "planned",
            } satisfies LiveSection,
          ]),
        ),
      };

    case "artefact.section_started": {
      const section = base.liveSections[frame.index];
      // Frames name skeleton display indices. Do not manufacture a section
      // if a malformed/out-of-order stream lacks its skeleton.
      if (section === undefined) return base;
      return {
        ...base,
        liveSections: {
          ...base.liveSections,
          [frame.index]: { ...section, state: "writing" },
        },
      };
    }

    case "artefact.section_completed": {
      const section = base.liveSections[frame.index];
      if (section === undefined) return base;
      // An empty prose completion closes an optional section (notably key
      // findings). Removing it is honest: the view must hide, never fake.
      if (frame.prose.length === 0) {
        const remainingSections = { ...base.liveSections };
        delete remainingSections[frame.index];
        return { ...base, liveSections: remainingSections };
      }
      return {
        ...base,
        liveSections: {
          ...base.liveSections,
          [frame.index]: {
            ...section,
            title: frame.title,
            prose: frame.prose,
            state: "filled",
          },
        },
      };
    }

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

/**
 * Report whether live presentation sections must be labelled as an
 * incomplete draft after a terminal run outcome.
 *
 * Args:
 *   state: Current stream state.
 *
 * Returns:
 *   True only for failed, aborted, or interrupted runs retaining at least
 *   one streamed section. Sections deliberately remain available for view
 *   rendering beneath the terminal-honesty banner.
 */
export function hasTerminalPartialLiveArtefact(state: RunStreamState): boolean {
  return (
    state.run !== null &&
    ["failed", "aborted", "interrupted"].includes(state.run.status) &&
    Object.keys(state.liveSections).length > 0
  );
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

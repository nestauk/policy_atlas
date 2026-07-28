import type { components } from "../api/gen/types";

export type PlanningThreadTurn = components["schemas"]["PlanningTranscriptTurnOut"];
export type PlanningThreadRun = components["schemas"]["RunOut"];
export type PlanningThreadDecision = components["schemas"]["DecisionOut"];

/** A run from the runs read plus its durable run-phase boundary. This
 * boundary deliberately is not inferred from timestamps: planning turns are
 * ordered by `turn_index`, and an active/parked run 409-fences new turns. */
export interface RunThreadBoundary {
  run: PlanningThreadRun;
  /** The last planning turn before this run block, or null if no turn
   * precedes the run (for imported/pre-transcript history). */
  afterTurnIndex: number | null;
}

/** A steering decision keeps its own durable record and declares the run
 * block it belongs to. It is never copied into the planning-turn list. */
export interface RunThreadDecision {
  decision: PlanningThreadDecision;
  capabilityRunId: string;
}

export type PlanningThreadItem =
  | { type: "planning_turn"; turn: PlanningThreadTurn }
  | {
      type: "run_block";
      run: PlanningThreadRun;
      decisions: PlanningThreadDecision[];
    };

/**
 * Compose a planning conversation into turn and run blocks.
 *
 * Args:
 *   turns: Durable transcript rows; sorted by `turn_index`, never timestamp.
 *   runBoundaries: Run-read rows with their run-phase boundary; sorted by the
 *     boundary coordinate, then run start/id only as deterministic ties.
 *   decisions: Steering records associated to their owning run blocks.
 *
 * Returns:
 *   Discriminated items for the rail. Each planning turn occurs once between
 *   run blocks, and each decision occurs once inside its run block in
 *   ascending event-log sequence.
 */
export function composePlanningThread(
  turns: PlanningThreadTurn[],
  runBoundaries: RunThreadBoundary[],
  decisions: RunThreadDecision[],
): PlanningThreadItem[] {
  const orderedTurns = [...turns].sort((left, right) => left.turn_index - right.turn_index);
  const orderedRuns = [...runBoundaries].sort((left, right) => {
    const leftBoundary = left.afterTurnIndex ?? -1;
    const rightBoundary = right.afterTurnIndex ?? -1;
    if (leftBoundary !== rightBoundary) return leftBoundary - rightBoundary;
    if (left.run.started_at !== right.run.started_at) {
      return left.run.started_at.localeCompare(right.run.started_at);
    }
    return left.run.capability_run_id.localeCompare(right.run.capability_run_id);
  });
  const decisionsByRun = new Map<string, PlanningThreadDecision[]>();
  for (const { capabilityRunId, decision } of decisions) {
    const entries = decisionsByRun.get(capabilityRunId) ?? [];
    entries.push(decision);
    decisionsByRun.set(capabilityRunId, entries);
  }

  const items: PlanningThreadItem[] = [];
  let turnCursor = 0;
  for (const boundary of orderedRuns) {
    while (
      turnCursor < orderedTurns.length &&
      (boundary.afterTurnIndex === null || orderedTurns[turnCursor].turn_index <= boundary.afterTurnIndex)
    ) {
      items.push({ type: "planning_turn", turn: orderedTurns[turnCursor] });
      turnCursor += 1;
    }
    items.push({
      type: "run_block",
      run: boundary.run,
      decisions: [...(decisionsByRun.get(boundary.run.capability_run_id) ?? [])].sort(
        (left, right) => left.sequence - right.sequence,
      ),
    });
  }
  for (; turnCursor < orderedTurns.length; turnCursor += 1) {
    items.push({ type: "planning_turn", turn: orderedTurns[turnCursor] });
  }
  return items;
}

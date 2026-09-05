import type { components } from "../api/gen/types";

export type PlanningThreadTurn = components["schemas"]["PlanningTranscriptTurnOut"];
export type PlanningThreadRun = components["schemas"]["RunOut"];
export type PlanningThreadDecision = components["schemas"]["DecisionOut"];

interface SessionAnsweredCheckIn {
  chosenOptionLabel: string;
  rejectedOptionLabels: string[];
}

const ANSWERED_CHECK_INS_SESSION_KEY = "policy-atlas.answered-check-ins";

function readSessionAnsweredCheckIns(): Record<string, SessionAnsweredCheckIn> {
  if (typeof window === "undefined") return {};
  try {
    const stored = window.sessionStorage.getItem(ANSWERED_CHECK_INS_SESSION_KEY);
    if (stored === null) return {};
    const parsed: unknown = JSON.parse(stored);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).flatMap(([checkInId, value]) => {
        if (value === null || typeof value !== "object" || Array.isArray(value)) return [];
        const record = value as Partial<SessionAnsweredCheckIn>;
        return typeof record.chosenOptionLabel === "string" && Array.isArray(record.rejectedOptionLabels)
          && record.rejectedOptionLabels.every((label) => typeof label === "string")
          ? [[checkInId, { chosenOptionLabel: record.chosenOptionLabel, rejectedOptionLabels: record.rejectedOptionLabels }]]
          : [];
      }),
    );
  } catch {
    return {};
  }
}

/** Record the visible answer labels for this browser session only. The public
 * durable decision payload does not retain an option id or label. */
export function recordSessionAnsweredCheckIn(
  checkInId: string,
  chosenOptionLabel: string,
  rejectedOptionLabels: string[],
): void {
  if (typeof window === "undefined") return;
  const entries = readSessionAnsweredCheckIns();
  entries[checkInId] = { chosenOptionLabel, rejectedOptionLabels };
  try {
    window.sessionStorage.setItem(ANSWERED_CHECK_INS_SESSION_KEY, JSON.stringify(entries));
  } catch {
    // Private browsing or quota failure only removes this non-durable echo.
  }
}

/** Return the session-local option labels, if an answer was made in this tab. */
export function sessionAnsweredCheckIn(checkInId: string): SessionAnsweredCheckIn | null {
  return readSessionAnsweredCheckIns()[checkInId] ?? null;
}

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
      // A null boundary means NO turn precedes this run — flush nothing.
      boundary.afterTurnIndex !== null &&
      orderedTurns[turnCursor].turn_index <= boundary.afterTurnIndex
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

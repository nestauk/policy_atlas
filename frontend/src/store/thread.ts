import type { components } from "../api/gen/types";

export type TaskAgentThreadTurn = components["schemas"]["TaskAgentTranscriptTurnOut"];
export type TaskAgentThreadRun = components["schemas"]["RunOut"];
export type TaskAgentThreadDecision = components["schemas"]["DecisionOut"];

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
 * boundary deliberately is not inferred from timestamps: task_agent turns are
 * ordered by `turn_index`, and an active/parked run 409-fences new turns. */
export interface RunThreadBoundary {
  run: TaskAgentThreadRun;
  /** The last task_agent turn before this run block, or null if no turn
   * precedes the run (for imported/pre-transcript history). */
  afterTurnIndex: number | null;
}

/** A steering decision keeps its own durable record and declares the run
 * block it belongs to. It is never copied into the task_agent-turn list. */
export interface RunThreadDecision {
  decision: TaskAgentThreadDecision;
  capabilityRunId: string;
}

/** The gate check-in as the thread sees it (task 044, Phase 5.5). */
export type TaskAgentThreadCheckIn = components["schemas"]["CheckInOut"];

/** The gate's recorded decision when the **card endpoint** answered it, so no
 *  `decision` turn carries it. Read off the check-in's own decision event
 *  (`checkin.resolved`); the label is always the server-supplied option
 *  label, never one invented here. */
export interface GateThreadDecision {
  checkInId: string;
  /** The chosen option's label, exactly as the card offered it. */
  label: string;
  /** The plan version the decision was taken against, or null when unknown. */
  planVersion: number | null;
  occurredAt: string;
}

/** Everything the baseline gate contributes to the thread. */
export interface GateThreadInput {
  /** The gate check-in. Its card renders while `status === "pending"`. */
  checkIn: TaskAgentThreadCheckIn;
  /** The card-endpoint decision, when one was recorded. */
  decision: GateThreadDecision | null;
}

export type TaskAgentThreadItem =
  | { type: "task_agent_turn"; turn: TaskAgentThreadTurn }
  | {
      type: "run_block";
      run: TaskAgentThreadRun;
      decisions: TaskAgentThreadDecision[];
    }
  | { type: "gate_check_in"; checkIn: TaskAgentThreadCheckIn }
  | { type: "gate_decision"; decision: GateThreadDecision };

/** What a durable turn is. `kind` is absent on every turn stored before task
 *  044 — those are all replies, so the absence reads as `reply` rather than
 *  as an unknown. Task 045 adds `action`: a confirmed longlist verb. */
export function taskAgentTurnKind(
  turn: TaskAgentThreadTurn,
): "reply" | "answer" | "decision" | "action" {
  return turn.kind ?? "reply";
}

/**
 * Project a Task Agent `answer` turn onto the chat's own turn shape.
 *
 * The citation half of a Task Agent answer is `AnswerPayloadOut` — the exact
 * fields `ChatTurnOut` has always carried, named once on the backend so the
 * two cannot drift. This restates that identity on the client so the chat's
 * citation renderer can read a Task Agent turn directly instead of growing a
 * second, drifting copy of itself.
 *
 * Args:
 *   turn: A durable Task Agent turn whose `kind` is `answer`.
 *
 * Returns:
 *   The same answer as a `ChatTurnOut`. Absent payload fields take the chat's
 *   own defaults, so a turn with no `answer` renders as uncited prose rather
 *   than as an error.
 */
export function taskAgentAnswerRow(
  turn: TaskAgentThreadTurn,
): components["schemas"]["ChatTurnOut"] {
  const answer = turn.answer ?? null;
  return {
    id: turn.client_turn_id,
    conversation_id: turn.conversation_id ?? turn.client_turn_id,
    client_turn_id: turn.client_turn_id,
    turn_index: turn.turn_index,
    user_message: turn.user_message,
    answer: turn.reply,
    citations: answer?.citations ?? [],
    claims: answer?.claims ?? [],
    enrichment: answer?.enrichment ?? null,
    handoff: answer?.handoff ?? null,
    warning_not_evidence_checked: answer?.warning_not_evidence_checked ?? false,
    stopped_before_evidence_check: answer?.stopped_before_evidence_check ?? false,
    status: turn.status,
    created_at: turn.created_at,
    completed_at: turn.completed_at,
  };
}

/**
 * Compose a task_agent conversation into turn and run blocks.
 *
 * Args:
 *   turns: Durable transcript rows; sorted by `turn_index`, never timestamp.
 *   runBoundaries: Run-read rows with their run-phase boundary; sorted by the
 *     boundary coordinate, then run start/id only as deterministic ties.
 *   decisions: Steering records associated to their owning run blocks.
 *   gate: The baseline gate's card and card-endpoint decision, when the task
 *     has one. Both are placed by TIME — the one place in this model where a
 *     timestamp orders anything, and legitimately so: a gate pause and the
 *     turns a paused walk accepts genuinely interleave in real time, unlike
 *     turns and runs, which the 409 fence keeps disjoint.
 *
 * Returns:
 *   Discriminated items for the rail. Each task_agent turn occurs once between
 *   run blocks, and each decision occurs once inside its run block in
 *   ascending event-log sequence. The gate's card sits at its pause time and
 *   its card-endpoint decision at the decision's own time, so a question
 *   asked at the gate reads after the card and a decision after the question.
 */
export function composeTaskAgentThread(
  turns: TaskAgentThreadTurn[],
  runBoundaries: RunThreadBoundary[],
  decisions: RunThreadDecision[],
  gate: GateThreadInput | null = null,
): TaskAgentThreadItem[] {
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
  const decisionsByRun = new Map<string, TaskAgentThreadDecision[]>();
  for (const { capabilityRunId, decision } of decisions) {
    const entries = decisionsByRun.get(capabilityRunId) ?? [];
    entries.push(decision);
    decisionsByRun.set(capabilityRunId, entries);
  }

  const items: TaskAgentThreadItem[] = [];
  let turnCursor = 0;
  for (const boundary of orderedRuns) {
    while (
      turnCursor < orderedTurns.length &&
      // A null boundary means NO turn precedes this run — flush nothing.
      boundary.afterTurnIndex !== null &&
      orderedTurns[turnCursor].turn_index <= boundary.afterTurnIndex
    ) {
      items.push({ type: "task_agent_turn", turn: orderedTurns[turnCursor] });
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
    items.push({ type: "task_agent_turn", turn: orderedTurns[turnCursor] });
  }
  return gate === null ? items : withGateItems(items, orderedTurns, gate);
}

/**
 * Splice the gate's card and its card-endpoint decision into a composed
 * thread at their own times.
 *
 * Args:
 *   items: The composed turn/run thread.
 *   orderedTurns: The same turns, in `turn_index` order.
 *   gate: The gate's check-in and card-endpoint decision.
 *
 * Returns:
 *   A new item list. The card is included only while the check-in is
 *   pending — an answer turn therefore leaves it standing, and it disappears
 *   the moment a decision lands. The decision item is included only when no
 *   `decision` turn already carries that check-in, so a decision recorded
 *   through the Task Agent renders once, as its turn.
 */
function withGateItems(
  items: TaskAgentThreadItem[],
  orderedTurns: TaskAgentThreadTurn[],
  gate: GateThreadInput,
): TaskAgentThreadItem[] {
  const decidedByTurn = orderedTurns.some(
    (turn) => turn.decision?.check_in_id === gate.checkIn.check_in_id,
  );
  const placements: Array<{ at: string; item: TaskAgentThreadItem }> = [];
  if (gate.checkIn.status === "pending") {
    placements.push({
      at: gate.checkIn.created_at,
      item: { type: "gate_check_in", checkIn: gate.checkIn },
    });
  }
  if (gate.decision !== null && !decidedByTurn) {
    placements.push({
      at: gate.decision.occurredAt,
      item: { type: "gate_decision", decision: gate.decision },
    });
  }
  // Latest placement first, so an earlier splice cannot shift a later one.
  const ordered = [...placements].sort((left, right) => right.at.localeCompare(left.at));
  const spliced = [...items];
  for (const { at, item } of ordered) {
    spliced.splice(gateInsertionIndex(spliced, at), 0, item);
  }
  return spliced;
}

/** The index a gate item at time `at` belongs at: after every turn received
 *  by then and after every run started by then, so the card follows the walk
 *  that paused and the turns a paused walk accepts follow the card. */
function gateInsertionIndex(items: TaskAgentThreadItem[], at: string): number {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index];
    const itemAt =
      item.type === "task_agent_turn"
        ? item.turn.created_at
        : item.type === "run_block"
          ? item.run.started_at
          : item.type === "gate_check_in"
            ? item.checkIn.created_at
            : item.decision.occurredAt;
    if (itemAt <= at) return index + 1;
  }
  return 0;
}

import { useCallback, useEffect, useReducer, useRef } from "react";

import { TaskAgentStreamInterruptedError, useTaskAgentTurn } from "../api/mutations";
import { useTaskAgentTurns } from "../api/queries";
import { errorCode } from "../lib/errors";
import type { components } from "../api/gen/types";

export type TaskAgentTranscriptTurn = components["schemas"]["TaskAgentTranscriptTurnOut"];

/** A local composer row which exists before the durable transcript query can
 * return the corresponding server row. */
export interface OptimisticTaskAgentTurn {
  clientTurnId: string;
  userMessage: string;
  createdAt: string;
  /** `pending` while the reply streams; `interrupted` when the connection
   *  dropped mid-stream (the turn finishes on the server and the transcript
   *  is re-read until it lands); `failed` on a refusal or a failed turn. */
  status: "pending" | "failed" | "interrupted";
  /** The reply so far: the stream's `delta` pieces joined (task 058, N9). */
  reply?: string;
  /** The stream's latest `progress` label ("Drafting the plan"). */
  progressLabel?: string;
  errorMessage?: string;
  /** The API's machine-readable conflict code, when the failure carried one. */
  errorCode?: string;
}

interface OptimisticTranscriptState {
  turns: OptimisticTaskAgentTurn[];
}

type OptimisticTranscriptAction =
  | { type: "submitted"; turn: OptimisticTaskAgentTurn }
  | { type: "progress"; clientTurnId: string; label: string }
  | { type: "delta"; clientTurnId: string; text: string }
  | { type: "interrupted"; clientTurnId: string }
  | { type: "reconciled"; clientTurnId: string }
  | { type: "failed"; clientTurnId: string; errorMessage: string; errorCode?: string }
  | { type: "discarded"; clientTurnId: string };

export const initialOptimisticTranscriptState: OptimisticTranscriptState = { turns: [] };

/**
 * Fold local composer transitions without changing the durable transcript.
 *
 * Args:
 *   state: Current local optimistic rows.
 *   action: Submission, durable reconciliation, or failed-send transition.
 *
 * Returns:
 *   The next local optimistic state. A reconciliation removes its temporary
 *   row because the mutation invalidates the durable transcript query.
 */
export function reduceOptimisticTranscript(
  state: OptimisticTranscriptState,
  action: OptimisticTranscriptAction,
): OptimisticTranscriptState {
  switch (action.type) {
    case "submitted":
      return {
        ...state,
        turns: state.turns.some((turn) => turn.clientTurnId === action.turn.clientTurnId)
          ? state.turns.map((turn) =>
              turn.clientTurnId === action.turn.clientTurnId ? action.turn : turn,
            )
          : [...state.turns, action.turn],
      };
    case "progress":
      return updateTurn(state, action.clientTurnId, (turn) => ({ ...turn, progressLabel: action.label }));
    case "delta":
      return updateTurn(state, action.clientTurnId, (turn) => ({
        ...turn,
        reply: (turn.reply ?? "") + action.text,
      }));
    case "interrupted":
      return updateTurn(state, action.clientTurnId, (turn) => ({ ...turn, status: "interrupted" }));
    case "reconciled":
    case "discarded":
      return {
        ...state,
        turns: state.turns.filter((turn) => turn.clientTurnId !== action.clientTurnId),
      };
    case "failed":
      return {
        ...state,
        turns: state.turns.map((turn) =>
          turn.clientTurnId === action.clientTurnId
            ? {
                ...turn,
                status: "failed",
                errorMessage: action.errorMessage,
                errorCode: action.errorCode,
              }
            : turn,
        ),
      };
    default:
      return assertNever(action);
  }
}

function updateTurn(
  state: OptimisticTranscriptState,
  clientTurnId: string,
  update: (turn: OptimisticTaskAgentTurn) => OptimisticTaskAgentTurn,
): OptimisticTranscriptState {
  return {
    ...state,
    turns: state.turns.map((turn) => (turn.clientTurnId === clientTurnId ? update(turn) : turn)),
  };
}

/** How often the transcript is re-read while an interrupted turn finishes on
 *  the server, and for how long at most. */
const INTERRUPTED_REREAD_MS = 2_000;
const INTERRUPTED_REREAD_CAP_MS = 120_000;

/**
 * Get the retry payload for an incomplete optimistic turn.
 *
 * Args:
 *   state: Current local optimistic rows.
 *   clientTurnId: The caller-minted id of the failed logical turn.
 *
 * Returns:
 *   The original message and the same id, or null when the row is not a
 *   retryable failed turn.
 */
export function retryInputForOptimisticTurn(
  state: OptimisticTranscriptState,
  clientTurnId: string,
): { message: string; clientTurnId: string } | null {
  const turn = state.turns.find((candidate) => candidate.clientTurnId === clientTurnId);
  if (turn === undefined || turn.status !== "failed") return null;
  return { message: turn.userMessage, clientTurnId: turn.clientTurnId };
}

/**
 * Combine the durable transcript page and local composer rows for a view.
 *
 * Args:
 *   durableTurns: Rows returned by the task-agent-turns query.
 *   optimisticTurns: Locally pending or failed turns awaiting reconciliation.
 *
 * Returns:
 *   Durable rows in their server-defined turn order followed by local rows;
 *   pending rows have no durable `turn_index` until the query refetches.
 */
export function transcriptRows(
  durableTurns: TaskAgentTranscriptTurn[],
  optimisticTurns: OptimisticTaskAgentTurn[],
): Array<TaskAgentTranscriptTurn | OptimisticTaskAgentTurn> {
  return [...durableTurns, ...optimisticTurns];
}

/**
 * Query the durable task_agent transcript and expose optimistic composer
 * transitions. The UI owns id minting for a new logical message; retrying
 * always resends the original `client_turn_id`.
 *
 * Args:
 *   taskId: Project whose single task_agent conversation is active.
 *   query: Optional transcript page parameters.
 *
 * Returns:
 *   Query state, merged rows, and submit/retry actions for the composer.
 */
export function useTaskAgentTranscript(
  taskId: string,
  query?: { page?: number; page_size?: number },
) {
  const transcript = useTaskAgentTurns(taskId, query);
  const taskAgentTurn = useTaskAgentTurn(taskId);
  const [optimistic, dispatch] = useReducer(reduceOptimisticTranscript, initialOptimisticTranscriptState);

  const send = useCallback(
    async (input: { message: string; clientTurnId: string }) => {
      dispatch({
        type: "submitted",
        turn: {
          clientTurnId: input.clientTurnId,
          userMessage: input.message,
          createdAt: new Date().toISOString(),
          status: "pending",
        },
      });
      try {
        // The mutation re-reads the transcript before it resolves, so the
        // durable turn replaces the streamed one with no gap between them.
        const result = await taskAgentTurn.mutateAsync({
          ...input,
          onEvent: (event) => {
            if (event.type === "progress") {
              dispatch({ type: "progress", clientTurnId: input.clientTurnId, label: event.label });
            } else if (event.type === "delta") {
              dispatch({ type: "delta", clientTurnId: input.clientTurnId, text: event.text });
            }
          },
        });
        dispatch({ type: "reconciled", clientTurnId: input.clientTurnId });
        return result;
      } catch (error) {
        if (error instanceof TaskAgentStreamInterruptedError) {
          // The turn is durable and finishes on the server: keep what has
          // streamed and re-read the transcript until it lands (N9).
          dispatch({ type: "interrupted", clientTurnId: input.clientTurnId });
          return null;
        }
        dispatch({
          type: "failed",
          clientTurnId: input.clientTurnId,
          errorMessage: error instanceof Error ? error.message : "That turn couldn't be processed.",
          errorCode: errorCode(error),
        });
        throw error;
      }
    },
    [taskAgentTurn],
  );

  // An interrupted turn gives way to its durable row once that row is no
  // longer pending; until then the transcript is re-read on a short timer.
  const durable = transcript.data?.data;
  const interrupted = optimistic.turns.filter((turn) => turn.status === "interrupted");
  const interruptedKey = interrupted.map((turn) => turn.clientTurnId).join(",");
  const startedAt = useRef<number | null>(null);
  const { refetch } = transcript;
  useEffect(() => {
    if (interruptedKey === "") {
      startedAt.current = null;
      return undefined;
    }
    startedAt.current ??= Date.now();
    let waiting = false;
    for (const clientTurnId of interruptedKey.split(",")) {
      const landed = durable?.find((turn) => turn.client_turn_id === clientTurnId);
      if (landed !== undefined && landed.status !== "pending") {
        dispatch({ type: "reconciled", clientTurnId });
      } else {
        waiting = true;
      }
    }
    if (!waiting || Date.now() - startedAt.current > INTERRUPTED_REREAD_CAP_MS) return undefined;
    const id = window.setTimeout(() => void refetch(), INTERRUPTED_REREAD_MS);
    return () => window.clearTimeout(id);
  }, [durable, interruptedKey, refetch]);

  const retry = useCallback(
    async (clientTurnId: string) => {
      const input = retryInputForOptimisticTurn(optimistic, clientTurnId);
      if (input === null) return null;
      return send(input);
    },
    [optimistic, send],
  );

  const discard = useCallback(
    (clientTurnId: string) => {
      // For a stale_turn conflict the same id can never succeed again —
      // drop the local row and re-read the durable conversation instead.
      dispatch({ type: "discarded", clientTurnId });
      void transcript.refetch();
    },
    [transcript],
  );

  return {
    ...transcript,
    optimisticTurns: optimistic.turns,
    rows: transcriptRows(transcript.data?.data ?? [], optimistic.turns),
    send,
    retry,
    discard,
    /** True while a turn's reply is streaming in (task 058, N9). */
    isSubmitting: taskAgentTurn.isPending,
  };
}

function assertNever(value: never): never {
  throw new Error(`Unhandled optimistic transcript action: ${JSON.stringify(value)}`);
}

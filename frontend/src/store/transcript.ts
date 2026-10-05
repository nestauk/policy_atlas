import { useCallback, useReducer } from "react";

import { usePlanningTurn } from "../api/mutations";
import { usePlanningTurns } from "../api/queries";
import { errorCode } from "../lib/errors";
import type { components } from "../api/gen/types";

export type PlanningTranscriptTurn = components["schemas"]["PlanningTranscriptTurnOut"];

/** A local composer row which exists before the durable transcript query can
 * return the corresponding server row. */
export interface OptimisticPlanningTurn {
  clientTurnId: string;
  userMessage: string;
  createdAt: string;
  status: "pending" | "failed";
  errorMessage?: string;
  /** The API's machine-readable conflict code, when the failure carried one. */
  errorCode?: string;
}

interface OptimisticTranscriptState {
  turns: OptimisticPlanningTurn[];
}

type OptimisticTranscriptAction =
  | { type: "submitted"; turn: OptimisticPlanningTurn }
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
 *   durableTurns: Rows returned by the planning-turns query.
 *   optimisticTurns: Locally pending or failed turns awaiting reconciliation.
 *
 * Returns:
 *   Durable rows in their server-defined turn order followed by local rows;
 *   pending rows have no durable `turn_index` until the query refetches.
 */
export function transcriptRows(
  durableTurns: PlanningTranscriptTurn[],
  optimisticTurns: OptimisticPlanningTurn[],
): Array<PlanningTranscriptTurn | OptimisticPlanningTurn> {
  return [...durableTurns, ...optimisticTurns];
}

/**
 * Query the durable planning transcript and expose optimistic composer
 * transitions. The UI owns id minting for a new logical message; retrying
 * always resends the original `client_turn_id`.
 *
 * Args:
 *   taskId: Project whose single planning conversation is active.
 *   query: Optional transcript page parameters.
 *
 * Returns:
 *   Query state, merged rows, and submit/retry actions for the composer.
 */
export function usePlanningTranscript(
  taskId: string,
  query?: { page?: number; page_size?: number },
) {
  const transcript = usePlanningTurns(taskId, query);
  const planningTurn = usePlanningTurn(taskId);
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
        const result = await planningTurn.mutateAsync(input);
        dispatch({ type: "reconciled", clientTurnId: input.clientTurnId });
        return result;
      } catch (error) {
        dispatch({
          type: "failed",
          clientTurnId: input.clientTurnId,
          errorMessage: error instanceof Error ? error.message : "That turn couldn't be processed.",
          errorCode: errorCode(error),
        });
        throw error;
      }
    },
    [planningTurn],
  );

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
    isSubmitting: planningTurn.isPending,
  };
}

function assertNever(value: never): never {
  throw new Error(`Unhandled optimistic transcript action: ${JSON.stringify(value)}`);
}

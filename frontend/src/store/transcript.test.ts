import { describe, expect, it } from "vitest";

import {
  initialOptimisticTranscriptState,
  reduceOptimisticTranscript,
  retryInputForOptimisticTurn,
  transcriptRows,
} from "./transcript";
import type { OptimisticPlanningTurn, PlanningTranscriptTurn } from "./transcript";

const optimisticTurn: OptimisticPlanningTurn = {
  clientTurnId: "11111111-1111-1111-1111-111111111111",
  userMessage: "Which interventions improve attendance?",
  createdAt: "2026-07-28T10:00:00Z",
  status: "pending",
};

const durableTurn: PlanningTranscriptTurn = {
  turn_index: 0,
  client_turn_id: "11111111-1111-1111-1111-111111111111",
  user_message: "Which interventions improve attendance?",
  reply: "I will focus the evidence search on attendance interventions.",
  suggestions: [],
  part: null,
  status: "completed",
  created_at: "2026-07-28T10:00:00Z",
  completed_at: "2026-07-28T10:00:02Z",
};

describe("optimistic planning transcript", () => {
  it("shows the user message immediately and removes it when the durable response reconciles", () => {
    const pending = reduceOptimisticTranscript(initialOptimisticTranscriptState, {
      type: "submitted",
      turn: optimisticTurn,
    });
    expect(pending.turns).toEqual([optimisticTurn]);
    expect(transcriptRows([durableTurn], pending.turns)).toEqual([durableTurn, optimisticTurn]);

    const reconciled = reduceOptimisticTranscript(pending, {
      type: "reconciled",
      clientTurnId: optimisticTurn.clientTurnId,
    });
    expect(reconciled.turns).toEqual([]);
    expect(transcriptRows([durableTurn], reconciled.turns)).toEqual([durableTurn]);
  });

  it("retains a failed turn honestly and retries with its original client turn id", () => {
    const pending = reduceOptimisticTranscript(initialOptimisticTranscriptState, {
      type: "submitted",
      turn: optimisticTurn,
    });
    const failed = reduceOptimisticTranscript(pending, {
      type: "failed",
      clientTurnId: optimisticTurn.clientTurnId,
      errorMessage: "The planner is unavailable.",
    });
    expect(failed.turns[0]).toEqual({
      ...optimisticTurn,
      status: "failed",
      errorMessage: "The planner is unavailable.",
    });
    expect(retryInputForOptimisticTurn(failed, optimisticTurn.clientTurnId)).toEqual({
      message: optimisticTurn.userMessage,
      clientTurnId: optimisticTurn.clientTurnId,
    });
  });

  it("moves a retry back to pending without duplicating the local user message", () => {
    const failed = reduceOptimisticTranscript(
      reduceOptimisticTranscript(initialOptimisticTranscriptState, {
        type: "submitted",
        turn: optimisticTurn,
      }),
      {
        type: "failed",
        clientTurnId: optimisticTurn.clientTurnId,
        errorMessage: "The planner is unavailable.",
      },
    );
    const retried = reduceOptimisticTranscript(failed, { type: "submitted", turn: optimisticTurn });

    expect(retried.turns).toEqual([optimisticTurn]);
    expect(retryInputForOptimisticTurn(retried, optimisticTurn.clientTurnId)).toBeNull();
  });
});

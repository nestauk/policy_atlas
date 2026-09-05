import { describe, expect, it } from "vitest";

import { composePlanningThread } from "./thread";
import type { PlanningThreadDecision, PlanningThreadRun, PlanningThreadTurn } from "./thread";

function turn(turnIndex: number): PlanningThreadTurn {
  return {
    turn_index: turnIndex,
    client_turn_id: `00000000-0000-0000-0000-00000000000${turnIndex}`,
    user_message: `Question ${turnIndex}`,
    reply: `Reply ${turnIndex}`,
    suggestions: [],
    part: null,
    status: "completed",
    created_at: `2026-07-28T10:0${turnIndex}:00Z`,
    completed_at: `2026-07-28T10:0${turnIndex}:01Z`,
  };
}

function run(id: string, startedAt: string): PlanningThreadRun {
  return {
    capability_run_id: id,
    task_id: "task-1",
    plan_id: `plan-${id}`,
    plan_version: 1,
    status: "succeeded",
    started_at: startedAt,
    ended_at: null,
  };
}

function decision(sequence: number): PlanningThreadDecision {
  return {
    sequence,
    occurred_at: "2026-07-28T10:03:00Z",
    kind: "steering.decision",
    summary: `Decision ${sequence}`,
    decided_by: "user",
    detail: {},
  };
}

describe("composePlanningThread", () => {
  it("places turn-index ordered planning turns between run blocks and keeps decisions inside their own block", () => {
    const firstRun = run("run-1", "2026-07-28T10:02:00Z");
    const secondRun = run("run-2", "2026-07-28T10:05:00Z");
    const firstDecision = decision(8);
    const secondDecision = decision(3);
    const result = composePlanningThread(
      [turn(2), turn(0), turn(1)],
      [
        { run: secondRun, afterTurnIndex: 1 },
        { run: firstRun, afterTurnIndex: 0 },
      ],
      [
        { capabilityRunId: "run-1", decision: firstDecision },
        { capabilityRunId: "run-1", decision: secondDecision },
        { capabilityRunId: "run-2", decision: decision(12) },
      ],
    );

    expect(result.map((item) => item.type === "planning_turn" ? `turn:${item.turn.turn_index}` : `run:${item.run.capability_run_id}`)).toEqual([
      "turn:0",
      "run:run-1",
      "turn:1",
      "run:run-2",
      "turn:2",
    ]);
    const firstBlock = result[1];
    expect(firstBlock.type).toBe("run_block");
    if (firstBlock.type === "run_block") {
      expect(firstBlock.decisions).toEqual([secondDecision, firstDecision]);
      expect(firstBlock.decisions).not.toContain(result[0]);
    }
  });

  it("renders a run with no preceding turn before every turn, not after them", () => {
    const result = composePlanningThread(
      [turn(0)],
      [{ run: run("run-1", "2026-07-28T09:00:00Z"), afterTurnIndex: null }],
      [],
    );

    expect(
      result.map((item) =>
        item.type === "planning_turn" ? `turn:${item.turn.turn_index}` : `run:${item.run.capability_run_id}`,
      ),
    ).toEqual(["run:run-1", "turn:0"]);
  });
});

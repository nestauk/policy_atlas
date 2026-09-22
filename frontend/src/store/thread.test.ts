import { describe, expect, it } from "vitest";

import { composeTaskAgentThread, taskAgentAnswerRow, taskAgentTurnKind } from "./thread";
import type {
  GateThreadInput,
  TaskAgentThreadCheckIn,
  TaskAgentThreadDecision,
  TaskAgentThreadRun,
  TaskAgentThreadTurn,
} from "./thread";

function turn(turnIndex: number): TaskAgentThreadTurn {
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

function run(id: string, startedAt: string): TaskAgentThreadRun {
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

function decision(sequence: number): TaskAgentThreadDecision {
  return {
    sequence,
    occurred_at: "2026-07-28T10:03:00Z",
    kind: "steering.decision",
    summary: `Decision ${sequence}`,
    decided_by: "user",
    detail: {},
  };
}

describe("composeTaskAgentThread", () => {
  it("places turn-index ordered task_agent turns between run blocks and keeps decisions inside their own block", () => {
    const firstRun = run("run-1", "2026-07-28T10:02:00Z");
    const secondRun = run("run-2", "2026-07-28T10:05:00Z");
    const firstDecision = decision(8);
    const secondDecision = decision(3);
    const result = composeTaskAgentThread(
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

    expect(result.map((item) => item.type === "task_agent_turn" ? `turn:${item.turn.turn_index}` : item.type === "run_block" ? `run:${item.run.capability_run_id}` : item.type)).toEqual([
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
    const result = composeTaskAgentThread(
      [turn(0)],
      [{ run: run("run-1", "2026-07-28T09:00:00Z"), afterTurnIndex: null }],
      [],
    );

    expect(
      result.map((item) =>
        item.type === "task_agent_turn"
          ? `turn:${item.turn.turn_index}`
          : item.type === "run_block"
            ? `run:${item.run.capability_run_id}`
            : item.type,
      ),
    ).toEqual(["run:run-1", "turn:0"]);
  });
});

const GATE_CHECK_IN_ID = "9c1acbe7-c4a1-4e0b-8d5a-bb25ea2ef600";

function gateCheckIn(createdAt: string, status: "pending" | "decided"): TaskAgentThreadCheckIn {
  return {
    check_in_id: GATE_CHECK_IN_ID,
    kind: "baseline_confirm",
    boundary: "after_component",
    component: "synthesise",
    stage: "synthesise",
    render: "Confirm the plan against the baseline",
    options: [
      { id: "confirm_plan", label: "Confirm plan and build longlist", description: "", requires_user_input: false, suggested: false, why: null, endorsement: null },
      { id: "change_plan", label: "Change the plan", description: "", requires_user_input: false, suggested: false, why: null, endorsement: null },
    ],
    triggers: [],
    bundle: null,
    segment_reentry_allowed: false,
    rerun_component: null,
    status,
    created_at: createdAt,
    sequence: 40,
  };
}

/** A turn at a given wall-clock time — the gate's own items are placed by
 *  time, so these fixtures set `created_at` explicitly. */
function timedTurn(
  turnIndex: number,
  createdAt: string,
  extra: Partial<TaskAgentThreadTurn> = {},
): TaskAgentThreadTurn {
  return { ...turn(turnIndex), created_at: createdAt, ...extra };
}

function labelOf(item: ReturnType<typeof composeTaskAgentThread>[number]): string {
  switch (item.type) {
    case "task_agent_turn":
      return `turn:${item.turn.turn_index}:${item.turn.kind ?? "reply"}`;
    case "run_block":
      return `run:${item.run.capability_run_id}`;
    case "gate_check_in":
      return "gate-card";
    case "gate_decision":
      return `gate-decision:${item.decision.label}`;
  }
}

describe("composeTaskAgentThread at the baseline gate", () => {
  const gateRun = run("run-1", "2026-07-28T10:00:00Z");

  it("orders the gate card, then the question answered at it, then the decision", () => {
    const answerTurn = timedTurn(1, "2026-07-28T10:12:00Z", { kind: "answer" });
    const decisionTurn = timedTurn(2, "2026-07-28T10:14:00Z", {
      kind: "decision",
      decision: {
        option_id: "change_plan",
        label: "Change the plan",
        check_in_id: GATE_CHECK_IN_ID,
        capability_run_id: "run-1",
        plan_version: 1,
      },
    });
    const gate: GateThreadInput = {
      checkIn: gateCheckIn("2026-07-28T10:10:00Z", "pending"),
      decision: null,
    };

    const result = composeTaskAgentThread(
      [decisionTurn, answerTurn],
      [{ run: gateRun, afterTurnIndex: null }],
      [],
      gate,
    );

    expect(result.map(labelOf)).toEqual([
      "run:run-1",
      "gate-card",
      "turn:1:answer",
      "turn:2:decision",
    ]);
  });

  it("renders a decision taken on the card, with no turn, as its own decision item", () => {
    const gate: GateThreadInput = {
      checkIn: gateCheckIn("2026-07-28T10:10:00Z", "decided"),
      decision: {
        checkInId: GATE_CHECK_IN_ID,
        label: "Change the plan",
        planVersion: 3,
        occurredAt: "2026-07-28T10:15:00Z",
      },
    };

    const result = composeTaskAgentThread(
      [timedTurn(1, "2026-07-28T10:12:00Z", { kind: "answer" })],
      [{ run: gateRun, afterTurnIndex: null }],
      [],
      gate,
    );

    expect(result.map(labelOf)).toEqual([
      "run:run-1",
      "turn:1:answer",
      "gate-decision:Change the plan",
    ]);
  });

  it("keeps two turns taken before the card in their own order, above it", () => {
    const gate: GateThreadInput = {
      checkIn: gateCheckIn("2026-07-28T10:10:00Z", "pending"),
      decision: null,
    };

    const result = composeTaskAgentThread(
      [timedTurn(2, "2026-07-28T09:05:00Z"), timedTurn(1, "2026-07-28T09:01:00Z")],
      [],
      [],
      gate,
    );

    expect(result.map(labelOf)).toEqual(["turn:1:reply", "turn:2:reply", "gate-card"]);
  });

  it("drops the card once a decision turn carries the same check-in", () => {
    const decisionTurn = timedTurn(1, "2026-07-28T10:14:00Z", {
      kind: "decision",
      decision: {
        option_id: "confirm_plan",
        label: "Confirm plan and build longlist",
        check_in_id: GATE_CHECK_IN_ID,
        capability_run_id: "run-1",
        plan_version: 2,
      },
    });
    const gate: GateThreadInput = {
      checkIn: gateCheckIn("2026-07-28T10:10:00Z", "decided"),
      decision: {
        checkInId: GATE_CHECK_IN_ID,
        label: "Confirm plan and build longlist",
        planVersion: 2,
        occurredAt: "2026-07-28T10:14:00Z",
      },
    };

    const result = composeTaskAgentThread([decisionTurn], [], [], gate);

    // The turn is the record; the card-endpoint item would double it.
    expect(result.map(labelOf)).toEqual(["turn:1:decision"]);
  });

  it("leaves an Evidence search thread composed exactly as before when no gate is supplied", () => {
    const result = composeTaskAgentThread([turn(1)], [{ run: run("run-1", "2026-07-28T10:02:00Z"), afterTurnIndex: 1 }], []);
    expect(result.map(labelOf)).toEqual(["turn:1:reply", "run:run-1"]);
  });
});

describe("taskAgentTurnKind", () => {
  it("reads a pre-044 turn, which carries no kind at all, as a reply", () => {
    expect(taskAgentTurnKind(turn(1))).toBe("reply");
    expect(taskAgentTurnKind({ ...turn(1), kind: "answer" })).toBe("answer");
  });

  it("reads a confirmed longlist verb as an action (task 045)", () => {
    expect(taskAgentTurnKind({ ...turn(1), kind: "action" })).toBe("action");
  });
});

describe("taskAgentAnswerRow", () => {
  it("projects an answer turn onto the chat's turn shape, citations and all", () => {
    const row = taskAgentAnswerRow({
      ...turn(1),
      kind: "answer",
      reply: "The baseline holds one study [1].",
      answer: {
        citations: [{ n: 1, source_title: "A study" }],
        claims: [{ claim_id: "c1", citation_ns: [1] }],
        enrichment: null,
        handoff: null,
        warning_not_evidence_checked: true,
        stopped_before_evidence_check: false,
      },
    });

    expect(row.answer).toBe("The baseline holds one study [1].");
    expect(row.citations).toEqual([{ n: 1, source_title: "A study" }]);
    expect(row.claims).toEqual([{ claim_id: "c1", citation_ns: [1] }]);
    expect(row.warning_not_evidence_checked).toBe(true);
  });

  it("gives a turn with no answer payload the chat's own empty defaults", () => {
    const row = taskAgentAnswerRow({ ...turn(1), kind: "answer" });
    expect(row.citations).toEqual([]);
    expect(row.claims).toEqual([]);
    expect(row.warning_not_evidence_checked).toBe(false);
  });
});

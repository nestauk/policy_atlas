import { describe, expect, it } from "vitest";

import type { PlanningThreadDecision, PlanningThreadRun, PlanningThreadTurn } from "../../store";
import { presentRunDecisions, threadInputs } from "./PlanningPane";

function turn(index: number, createdAt: string): PlanningThreadTurn {
  return {
    turn_index: index,
    client_turn_id: `00000000-0000-0000-0000-00000000000${index}`,
    user_message: `Question ${index}`,
    reply: `Reply ${index}`,
    suggestions: [],
    part: null,
    status: "completed",
    created_at: createdAt,
    completed_at: createdAt,
  };
}

function run(id: string, startedAt: string, endedAt: string | null): PlanningThreadRun {
  return {
    capability_run_id: id,
    project_id: "p1",
    plan_id: `plan-${id}`,
    plan_version: 1,
    status: endedAt === null ? "running" : "succeeded",
    started_at: startedAt,
    ended_at: endedAt,
  };
}

function decision(sequence: number, occurredAt: string): PlanningThreadDecision {
  return { kind: "steering.decision", sequence, occurred_at: occurredAt, summary: `Decision ${sequence}` };
}

describe("threadInputs", () => {
  it("anchors each run after its preceding turn and owns mid-window decisions", () => {
    const turns = [
      turn(0, "2026-07-28T10:00:00Z"),
      turn(1, "2026-07-28T10:05:00Z"),
      turn(2, "2026-07-28T12:00:00Z"),
    ];
    const runs = [run("r1", "2026-07-28T10:30:00Z", "2026-07-28T11:30:00Z")];
    const decisions = [
      decision(7, "2026-07-28T10:45:00Z"),
      decision(9, "2026-07-28T13:00:00Z"), // outside every run window → dropped
    ];
    const { boundaries, runDecisions } = threadInputs(turns, runs, decisions);
    expect(boundaries).toEqual([{ run: runs[0], afterTurnIndex: 1 }]);
    expect(runDecisions).toEqual([{ decision: decisions[0], capabilityRunId: "r1" }]);
  });

  it("gives a run with no preceding turn a null boundary", () => {
    const runs = [run("r1", "2026-07-28T09:00:00Z", null)];
    const { boundaries } = threadInputs([turn(0, "2026-07-28T10:00:00Z")], runs, []);
    expect(boundaries[0].afterTurnIndex).toBeNull();
  });
});

describe("presentRunDecisions", () => {
  it("collapses consecutive search echoes with a counter and stage-labels completed components", () => {
    const entries: PlanningThreadDecision[] = [
      { kind: "search.executed", sequence: 1, occurred_at: "2026-07-28T10:00:00Z", summary: "Executed a search query." },
      { kind: "search.executed", sequence: 2, occurred_at: "2026-07-28T10:00:01Z", summary: "Executed a search query." },
      { kind: "component.completed", sequence: 3, occurred_at: "2026-07-28T10:00:02Z", summary: "Completed an evidence-base step.", detail: { component: "screen_full" } },
      { kind: "component.completed", sequence: 4, occurred_at: "2026-07-28T10:00:03Z", summary: "Completed an evidence-base step.", detail: { component: "unknown" } },
    ];

    expect(presentRunDecisions(entries, [])).toEqual([
      { sequence: 1, summary: "Executed a search query", count: 2 },
      { sequence: 3, summary: "Completed: Screening for relevance", count: 1 },
    ]);
  });
});

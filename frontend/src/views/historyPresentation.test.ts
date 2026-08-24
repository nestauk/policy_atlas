import { describe, expect, it } from "vitest";

import { mergeHistory } from "./historyPresentation";

describe("mergeHistory", () => {
  it("merges planning turns and decisions into one list ordered by time, question and plan first", () => {
    const turns = [
      { turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "What is the policy landscape?", status: "completed" as const },
      { turn_index: 1, created_at: "2026-07-28T09:05:00Z", user_message: "Focus on the UK only.", status: "completed" as const },
    ];
    const decisions = [
      { sequence: 1, occurred_at: "2026-07-28T09:10:00Z", kind: "plan.approved", summary: "Plan approved." },
      { sequence: 2, occurred_at: "2026-07-28T09:20:00Z", kind: "component.completed", summary: "Search completed." },
    ];
    const result = mergeHistory(decisions, turns);
    expect(result.map((r) => r.id)).toEqual([
      "turn-0",
      "turn-1",
      "decision-plan.approved-1",
      "decision-component.completed-2",
    ]);
  });

  it("breaks ties on identical timestamps by turn index / decision sequence", () => {
    const turns = [
      { turn_index: 1, created_at: "2026-07-28T09:00:00Z", user_message: "second", status: "completed" as const },
      { turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "first", status: "completed" as const },
    ];
    const decisions = [
      { sequence: 2, occurred_at: "2026-07-28T10:00:00Z", kind: "plan.approved", summary: "later" },
      { sequence: 1, occurred_at: "2026-07-28T10:00:00Z", kind: "component.completed", summary: "earlier" },
    ];
    const result = mergeHistory(decisions, turns);
    expect(result.map((r) => r.id)).toEqual([
      "turn-0",
      "turn-1",
      "decision-component.completed-1",
      "decision-plan.approved-2",
    ]);
  });

  it("gives turn_index 0 the Question category and later turns Planning", () => {
    const turns = [
      { turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "Start", status: "completed" as const },
      { turn_index: 1, created_at: "2026-07-28T09:05:00Z", user_message: "Refine", status: "completed" as const },
    ];
    const result = mergeHistory([], turns);
    expect(result[0].category).toBe("Question");
    expect(result[1].category).toBe("Planning");
  });

  it("renders a failed turn's honest state with the red tone", () => {
    const turns = [
      { turn_index: 1, created_at: "2026-07-28T09:05:00Z", user_message: "Refine", status: "failed" as const },
    ];
    const result = mergeHistory([], turns);
    expect(result[0].tone).toBe("red");
    expect(result[0].sentence).toContain("didn't complete");
  });

  it("never lets a raw event kind reach the output", () => {
    const decisions = [
      { sequence: 1, occurred_at: "2026-07-28T09:00:00Z", kind: "component.weird_internal_name", summary: "Something happened." },
    ];
    const result = mergeHistory(decisions, []);
    expect(result).toHaveLength(1);
    const row = result[0];
    expect(row.category).toBe("Recorded");
    // `id` is documented as an internal stable list key, never rendered text,
    // so the reader-facing fields are what must stay free of the raw kind.
    for (const [key, value] of Object.entries(row)) {
      if (key === "id") continue;
      expect(String(JSON.stringify(value))).not.toContain("component.weird_internal_name");
    }
  });

  it("gives a turn with a reply a details entry, and one without none", () => {
    const turns = [
      { turn_index: 0, created_at: "2026-07-28T09:00:00Z", user_message: "Start", reply: "Here is the plan.", status: "completed" as const },
      { turn_index: 1, created_at: "2026-07-28T09:05:00Z", user_message: "Refine", status: "completed" as const },
    ];
    const result = mergeHistory([], turns);
    expect(result[0].details).toEqual([{ label: "The planner replied", value: "Here is the plan." }]);
    expect(result[1].details).toBeUndefined();
  });

  it("returns an empty array for empty inputs", () => {
    expect(mergeHistory([], [])).toEqual([]);
    expect(mergeHistory(undefined, undefined)).toEqual([]);
  });
});

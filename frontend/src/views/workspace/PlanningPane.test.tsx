import type { ComponentProps } from "react";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PlanningThreadDecision, PlanningThreadRun, PlanningThreadTurn } from "../../store";
import { Composer, planningComposerPlaceholder, presentRunDecisions, threadInputs } from "./PlanningPane";

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

describe("Composer", () => {
  function renderComposer(overrides: Partial<ComponentProps<typeof Composer>> = {}) {
    const onChange = vi.fn();
    const onSubmit = vi.fn();
    render(
      <Composer
        value=""
        onChange={onChange}
        onSubmit={onSubmit}
        placeholder="What do you need evidence on?"
        disabled={false}
        sendDisabled={false}
        {...overrides}
      />,
    );
    return { onChange, onSubmit };
  }

  it("Enter sends: submits without inserting a newline", async () => {
    const user = userEvent.setup();
    const { onSubmit, onChange } = renderComposer({ value: "Map school-meal evidence." });

    await user.click(screen.getByLabelText("Message the planner"));
    await user.keyboard("{Enter}");

    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("Shift+Enter breaks: inserts a newline instead of submitting", async () => {
    const user = userEvent.setup();
    const { onSubmit, onChange } = renderComposer({ value: "Map school-meal evidence." });

    await user.click(screen.getByLabelText("Message the planner"));
    await user.keyboard("{Shift>}{Enter}{/Shift}");

    expect(onSubmit).not.toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith("Map school-meal evidence.\n");
  });

  it("disabled-during-run: honest copy swaps in and both controls disable", () => {
    renderComposer({
      disabled: true,
      sendDisabled: true,
      placeholder: "Replanning unlocks when this run finishes.",
    });

    const textarea = screen.getByLabelText("Message the planner");
    expect(textarea).toBeDisabled();
    expect(textarea).toHaveAttribute("placeholder", "Replanning unlocks when this run finishes.");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("shows the Enter/Shift+Enter hint line", () => {
    renderComposer();
    expect(screen.getByText("Enter to send · Shift+Enter for a new line")).toBeInTheDocument();
  });
});

describe("planningComposerPlaceholder", () => {
  it("matches the run state", () => {
    expect(planningComposerPlaceholder(undefined)).toBe(
      "Describe the policy question you need evidence for.",
    );
    expect(planningComposerPlaceholder(undefined, true)).toBe(
      "Suggest changes here, or edit directly in the plan.",
    );
    expect(planningComposerPlaceholder("running")).toBe(
      "Replanning unlocks when this run finishes.",
    );
    expect(planningComposerPlaceholder("paused")).toBe(
      "Replanning unlocks when this run finishes.",
    );
    expect(planningComposerPlaceholder("succeeded", true)).toBe(
      "Describe a change to the plan to run again.",
    );
    expect(planningComposerPlaceholder("failed")).toBe(
      "Describe what to change, then start again.",
    );
  });
});

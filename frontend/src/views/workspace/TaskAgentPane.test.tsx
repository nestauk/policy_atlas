import type { ComponentProps } from "react";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "../../api/gen/types";
import * as mutations from "../../api/mutations";
import * as queries from "../../api/queries";
import { createInitialRunStreamState } from "../../store";
import type { TaskAgentThreadDecision, TaskAgentThreadRun, TaskAgentThreadTurn } from "../../store";
import { ToastProvider } from "../../ui/radix/Toast";
import { Composer, TaskAgentPane, taskAgentComposerPlaceholder, presentRunDecisions, threadInputs } from "./TaskAgentPane";

type CheckInOut = components["schemas"]["CheckInOut"];

// Task 033 phase 10c (contract § 11 / rubric 37): the full-render read-only
// suite below mocks every query/mutation `TaskAgentPane` and its children
// (`PlanCard`, `CheckInCard`) resolve through — same shape as
// `PlanCard.test.tsx` / `PlanDocument.test.tsx`'s `usePlan` mock, extended
// to the rest of the task_agent surface.
vi.mock("../../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/queries")>();
  return {
    ...actual,
    useTaskAgentTurns: vi.fn(),
    usePlan: vi.fn(),
    useRuns: vi.fn(),
    useDecisions: vi.fn(),
    useCheckIns: vi.fn(),
    useFunnel: vi.fn(),
  };
});
vi.mock("../../api/mutations", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/mutations")>();
  return {
    ...actual,
    useTaskAgentTurn: vi.fn(),
    useStartRun: vi.fn(),
    usePatchPlan: vi.fn(),
    useAnswerCheckIn: vi.fn(),
  };
});

function turn(index: number, createdAt: string): TaskAgentThreadTurn {
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

function run(id: string, startedAt: string, endedAt: string | null): TaskAgentThreadRun {
  return {
    capability_run_id: id,
    task_id: "p1",
    plan_id: `plan-${id}`,
    plan_version: 1,
    status: endedAt === null ? "running" : "succeeded",
    started_at: startedAt,
    ended_at: endedAt,
  };
}

function decision(sequence: number, occurredAt: string): TaskAgentThreadDecision {
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
    const entries: TaskAgentThreadDecision[] = [
      { kind: "search.executed", sequence: 1, occurred_at: "2026-07-28T10:00:00Z", summary: "Executed a search query." },
      { kind: "search.executed", sequence: 2, occurred_at: "2026-07-28T10:00:01Z", summary: "Executed a search query." },
      { kind: "component.completed", sequence: 3, occurred_at: "2026-07-28T10:00:02Z", summary: "Completed an evidence-search step.", detail: { component: "screen_full" } },
      { kind: "component.completed", sequence: 4, occurred_at: "2026-07-28T10:00:03Z", summary: "Completed an evidence-search step.", detail: { component: "unknown" } },
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

    await user.click(screen.getByLabelText("Message the Task Agent"));
    await user.keyboard("{Enter}");

    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("Shift+Enter breaks: inserts a newline instead of submitting", async () => {
    const user = userEvent.setup();
    const { onSubmit, onChange } = renderComposer({ value: "Map school-meal evidence." });

    await user.click(screen.getByLabelText("Message the Task Agent"));
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

    const textarea = screen.getByLabelText("Message the Task Agent");
    expect(textarea).toBeDisabled();
    expect(textarea).toHaveAttribute("placeholder", "Replanning unlocks when this run finishes.");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("shows the Enter/Shift+Enter hint line", () => {
    renderComposer();
    expect(screen.getByText("Enter to send · Shift+Enter for a new line")).toBeInTheDocument();
  });
});

describe("taskAgentComposerPlaceholder", () => {
  it("matches the run state", () => {
    expect(taskAgentComposerPlaceholder(undefined)).toBe(
      "Describe the policy question you need evidence for.",
    );
    expect(taskAgentComposerPlaceholder(undefined, true)).toBe(
      "Suggest changes here, or edit directly in the plan.",
    );
    expect(taskAgentComposerPlaceholder("running")).toBe(
      "Replanning unlocks when this run finishes.",
    );
    expect(taskAgentComposerPlaceholder("paused")).toBe(
      "Replanning unlocks when this run finishes.",
    );
    expect(taskAgentComposerPlaceholder("succeeded", true)).toBe(
      "Describe a change to the plan to run again.",
    );
    expect(taskAgentComposerPlaceholder("failed")).toBe(
      "Describe what to change, then start again.",
    );
  });

  it("names the owner-only limit for a non-owner regardless of run state (task 033 phase 10c, rubric 37)", () => {
    expect(taskAgentComposerPlaceholder(undefined, false, false)).toBe(
      "Steering is limited to the task owner.",
    );
    expect(taskAgentComposerPlaceholder("running", false, false)).toBe(
      "Steering is limited to the task owner.",
    );
    expect(taskAgentComposerPlaceholder("failed", true, false)).toBe(
      "Steering is limited to the task owner.",
    );
  });
});

describe("TaskAgentPane — non-owner read-only (task 033 phase 10c, contract § 11 / rubric 37)", () => {
  const TASK_ID = "11111111-1111-1111-1111-111111111111";

  function readyTurn(): TaskAgentThreadTurn {
    return {
      turn_index: 0,
      client_turn_id: "00000000-0000-0000-0000-000000000000",
      user_message: "How effective are school meals at raising uptake?",
      reply: "Here's a first pass.",
      suggestions: [],
      part: null,
      status: "completed",
      created_at: "2026-07-28T10:00:00Z",
      completed_at: "2026-07-28T10:00:05Z",
    };
  }

  function checkIn(): CheckInOut {
    return {
      boundary: "after_component",
      check_in_id: "22222222-2222-2222-2222-222222222222",
      component: "screen",
      created_at: "2026-07-28T10:05:00Z",
      kind: "pause",
      options: [{ id: "continue", label: "Continue", description: "", requires_user_input: false, suggested: false, why: null, endorsement: null }],
      render: "Screening paused for review.",
      rerun_component: null,
      segment_reentry_allowed: false,
      sequence: 3,
      stage: "screen",
      status: "pending",
      triggers: [],
      bundle: null,
    };
  }

  beforeEach(() => {
    vi.mocked(queries.useTaskAgentTurns).mockReturnValue({
      data: { data: [readyTurn()] },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useTaskAgentTurns>);
    vi.mocked(queries.usePlan).mockReturnValue({
      data: { plan: { question: "Q", ready: true }, status: "approved", version: 1 },
    } as unknown as ReturnType<typeof queries.usePlan>);
    vi.mocked(queries.useRuns).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<
      typeof queries.useRuns
    >);
    vi.mocked(queries.useDecisions).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<
      typeof queries.useDecisions
    >);
    vi.mocked(queries.useCheckIns).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<
      typeof queries.useCheckIns
    >);
    vi.mocked(queries.useFunnel).mockReturnValue({ data: undefined } as unknown as ReturnType<
      typeof queries.useFunnel
    >);
    vi.mocked(mutations.useTaskAgentTurn).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof mutations.useTaskAgentTurn>);
    vi.mocked(mutations.useStartRun).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof mutations.useStartRun>);
    vi.mocked(mutations.usePatchPlan).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof mutations.usePatchPlan>);
    vi.mocked(mutations.useAnswerCheckIn).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof mutations.useAnswerCheckIn>);
  });

  function renderPane(overrides: Partial<ComponentProps<typeof TaskAgentPane>> = {}) {
    return render(
      <MemoryRouter>
        <ToastProvider>
          <TaskAgentPane
            taskId={TASK_ID}
            runStatus={undefined}
            stream={createInitialRunStreamState()}
            isOwner={false}
            {...overrides}
          />
        </ToastProvider>
      </MemoryRouter>,
    );
  }

  it("disables the composer with the owner-only placeholder", () => {
    renderPane();
    const textarea = screen.getByLabelText("Message the Task Agent");
    expect(textarea).toBeDisabled();
    expect(textarea).toHaveAttribute("placeholder", "Steering is limited to the task owner.");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("hides Start search from the plan-ready card but keeps Review the plan", () => {
    renderPane();
    expect(screen.getByRole("button", { name: "Review the plan" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start search" })).not.toBeInTheDocument();
  });

  it("never mounts the check-in card for a pending check-in", () => {
    renderPane({ stream: { ...createInitialRunStreamState(), pendingCheckIn: checkIn() } });
    expect(screen.queryByText("Waiting on your input")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continue" })).not.toBeInTheDocument();
  });

  it("renders the check-in card and Start search for the owner, by contrast", () => {
    renderPane({ isOwner: true, stream: { ...createInitialRunStreamState(), pendingCheckIn: checkIn() } });
    expect(screen.getByText("Waiting on your input")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start search" })).toBeInTheDocument();
    expect(screen.getByLabelText("Message the Task Agent")).not.toBeDisabled();
  });
});

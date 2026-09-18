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
import { TooltipProvider } from "../../ui/radix/Tooltip";
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

  it("invites a question about the baseline while a scoping walk waits at the gate (task 044)", () => {
    expect(taskAgentComposerPlaceholder("paused", true, true, true)).toBe("Question the baseline…");
    // The fence stays wherever the gate is not open.
    expect(taskAgentComposerPlaceholder("paused", true, true, false)).toBe(
      "Replanning unlocks when this run finishes.",
    );
    expect(taskAgentComposerPlaceholder("paused", true, false, true)).toBe(
      "Steering is limited to the task owner.",
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

/**
 * Task 044 Phase 5.5: the Task Agent thread at the baseline gate. The gate's
 * card sits IN the thread; the composer stays open; a turn comes back as a
 * planning reply, a cited answer, or a recorded decision.
 */
describe("TaskAgentPane — the options-scoping baseline gate", () => {
  const TASK_ID = "11111111-1111-1111-1111-111111111111";
  const GATE_ID = "33333333-3333-3333-3333-333333333333";

  function gateCheckIn(): CheckInOut {
    return {
      boundary: "after_component",
      check_in_id: GATE_ID,
      component: "synthesise",
      created_at: "2026-07-28T10:10:00Z",
      kind: "baseline_confirm",
      options: [
        { id: "confirm_plan", label: "Confirm plan and build longlist", description: "", requires_user_input: false, suggested: false, why: null, endorsement: null },
        { id: "change_plan", label: "Change the plan", description: "", requires_user_input: false, suggested: false, why: null, endorsement: null },
      ],
      render: "Confirm the plan against the baseline",
      rerun_component: null,
      segment_reentry_allowed: false,
      sequence: 40,
      stage: "synthesise",
      status: "pending",
      triggers: [],
      bundle: {
        key_assumption: "Careers advice reaches those still in school.",
        settings: { target_unit: "16-24 year-olds", where: "United Kingdom", outcomes: [], depth: "standard" },
      },
    };
  }

  function esCheckIn(): CheckInOut {
    return { ...gateCheckIn(), check_in_id: "44444444-4444-4444-4444-444444444444", kind: "pause", options: [] };
  }

  function answerTurn(): TaskAgentThreadTurn {
    return {
      turn_index: 2,
      client_turn_id: "00000000-0000-0000-0000-0000000000a2",
      user_message: "Does the baseline cover young people who already left school?",
      reply: "It does not — the one study in scope is school-based [1].",
      suggestions: [],
      part: null,
      kind: "answer",
      answer: {
        citations: [{ n: 1, source_title: "Careers advice in secondary schools", quote: "school-based provision only" }],
        claims: [],
        enrichment: null,
        handoff: null,
        warning_not_evidence_checked: false,
        stopped_before_evidence_check: false,
      },
      status: "completed",
      created_at: "2026-07-28T10:12:00Z",
      completed_at: "2026-07-28T10:12:04Z",
    };
  }

  function decisionTurn(): TaskAgentThreadTurn {
    return {
      turn_index: 3,
      client_turn_id: "00000000-0000-0000-0000-0000000000a3",
      user_message: "Change the plan",
      reply: null,
      suggestions: [],
      part: null,
      kind: "decision",
      decision: {
        option_id: "change_plan",
        label: "Change the plan",
        check_in_id: GATE_ID,
        capability_run_id: "run-1",
        plan_version: 2,
      },
      status: "completed",
      created_at: "2026-07-28T10:14:00Z",
      completed_at: "2026-07-28T10:14:01Z",
    };
  }

  function mockPane({
    turns,
    capability = "options_scoping",
  }: {
    turns: TaskAgentThreadTurn[];
    capability?: string;
  }) {
    vi.mocked(queries.useTaskAgentTurns).mockReturnValue({
      data: { data: turns },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof queries.useTaskAgentTurns>);
    vi.mocked(queries.usePlan).mockReturnValue({
      data:
        capability === "options_scoping"
          ? { capability, plan: null, scoping: { ready: true }, status: "approved", version: 2 }
          : { capability, plan: { question: "Q", ready: true }, status: "approved", version: 2 },
    } as unknown as ReturnType<typeof queries.usePlan>);
    vi.mocked(queries.useRuns).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<typeof queries.useRuns>);
    vi.mocked(queries.useDecisions).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<typeof queries.useDecisions>);
    vi.mocked(queries.useCheckIns).mockReturnValue({ data: { data: [] } } as unknown as ReturnType<typeof queries.useCheckIns>);
    vi.mocked(queries.useFunnel).mockReturnValue({ data: undefined } as unknown as ReturnType<typeof queries.useFunnel>);
    vi.mocked(mutations.useTaskAgentTurn).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof mutations.useTaskAgentTurn>);
    vi.mocked(mutations.useStartRun).mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useStartRun>);
    vi.mocked(mutations.usePatchPlan).mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.usePatchPlan>);
    vi.mocked(mutations.useAnswerCheckIn).mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useAnswerCheckIn>);
  }

  function renderPane(overrides: Partial<ComponentProps<typeof TaskAgentPane>> = {}) {
    // `AppShell` mounts the TooltipProvider in the app; the chat's citation
    // renderer, reused here, needs it.
    return render(
      <MemoryRouter>
        <ToastProvider>
          <TooltipProvider>
            <TaskAgentPane
              taskId={TASK_ID}
              runStatus="paused"
              stream={{ ...createInitialRunStreamState(), pendingCheckIn: gateCheckIn() }}
              isOwner
              {...overrides}
            />
          </TooltipProvider>
        </ToastProvider>
      </MemoryRouter>,
    );
  }

  it("shows the gate card, the cited answer and the recorded decision in that order", () => {
    mockPane({ turns: [answerTurn(), decisionTurn()] });
    const { container } = renderPane();

    expect(screen.getByRole("heading", { name: "Confirm the plan against the baseline" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm plan and build longlist" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Change the plan" })).toBeInTheDocument();
    // The chat's own citation renderer, reused: the References footer and the
    // `[n]` marker button come from `ChatAnswer`, not from a second copy.
    expect(screen.getByText("References (1)")).toBeInTheDocument();
    expect(screen.getByText("Change the plan", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText(/plan version 2/)).toBeInTheDocument();

    const text = container.textContent ?? "";
    expect(text.indexOf("Confirm the plan against the baseline")).toBeLessThan(
      text.indexOf("Does the baseline cover young people"),
    );
    expect(text.indexOf("Does the baseline cover young people")).toBeLessThan(text.indexOf("recorded"));
  });

  it("keeps the composer open at the gate, with the baseline question placeholder", () => {
    mockPane({ turns: [] });
    renderPane();

    const textarea = screen.getByLabelText("Message the Task Agent");
    expect(textarea).not.toBeDisabled();
    expect(textarea).toHaveAttribute("placeholder", "Question the baseline…");
  });

  it("keeps the fence for an Evidence search task's paused walk", () => {
    mockPane({ turns: [], capability: "evidence_search" });
    renderPane({ stream: { ...createInitialRunStreamState(), pendingCheckIn: esCheckIn() } });

    const textarea = screen.getByLabelText("Message the Task Agent");
    expect(textarea).toBeDisabled();
    expect(textarea).toHaveAttribute("placeholder", "Replanning unlocks when this run finishes.");
  });

  it("keeps the fence for a scoping walk that is still running, not parked at the gate", () => {
    mockPane({ turns: [] });
    renderPane({ runStatus: "running", stream: createInitialRunStreamState() });

    expect(screen.getByLabelText("Message the Task Agent")).toBeDisabled();
  });

  it("renders an already-answered turn as an inline notice with a refresh, not a retry", async () => {
    mockPane({ turns: [] });
    const conflict = Object.assign(new Error("conflict"), { error: { code: "already_answered" } });
    vi.mocked(mutations.useTaskAgentTurn).mockReturnValue({
      mutateAsync: vi.fn().mockRejectedValue(conflict),
      isPending: false,
    } as unknown as ReturnType<typeof mutations.useTaskAgentTurn>);
    const user = userEvent.setup();
    renderPane();

    await user.type(screen.getByLabelText("Message the Task Agent"), "Change the plan");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(
      await screen.findByText("This check-in has already been answered. Refresh to see the recorded decision."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh conversation" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  // Task 044 review, C3: the walk is `paused` (so `runActive` is true) but
  // the composer stays open at the gate — the suggestion chips must gate on
  // that same fence, not on `runActive`, or an ask-back turn's suggestions
  // never render while parked on the gate.
  it("renders an ask-back turn's suggestions as chips at the gate", async () => {
    mockPane({ turns: [] });
    vi.mocked(mutations.useTaskAgentTurn).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({ suggestions: ["Does this cover care leavers?"] }),
      isPending: false,
    } as unknown as ReturnType<typeof mutations.useTaskAgentTurn>);
    const user = userEvent.setup();
    renderPane();

    await user.type(
      screen.getByLabelText("Message the Task Agent"),
      "Does the baseline cover care leavers?",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(
      await screen.findByRole("button", { name: "Does this cover care leavers?" }),
    ).toBeInTheDocument();
  });
});

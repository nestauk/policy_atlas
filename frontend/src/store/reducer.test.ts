import { describe, expect, it } from "vitest";

import type { SseFrame } from "../api/sseFrame";
import { hasTerminalPartialLiveArtefact, reduceRunStreamFrame } from "./reducer";
import { createInitialRunStreamState } from "./types";
import type { CheckInOut, PlanDraft, RunStreamState } from "./types";

const PROJECT_RUN_ID = "11111111-1111-1111-1111-111111111111";
const CHECK_IN_ID = "22222222-2222-2222-2222-222222222222";

/** Minimal-but-complete draft plan (every field is a required, nullable
 *  key on the generated `PlanDraft` type — only `steps` is optional). */
function planDraft(overrides: Partial<PlanDraft> = {}): PlanDraft {
  return {
    analysis_depth: null,
    assumptions: null,
    backend_scope: null,
    component_rationale: null,
    components: null,
    expected_artefact_shape: null,
    extract_profiles: null,
    grouping_facets: null,
    question: null,
    ready: true,
    scope_constraints: null,
    scoping_notes: null,
    screening_criteria: null,
    search_effort: null,
    section_budget: null,
    steering_mode: null,
    time_band: null,
    title: null,
    ...overrides,
  };
}

function checkIn(overrides: Partial<CheckInOut> = {}): CheckInOut {
  return {
    boundary: "after_component",
    check_in_id: CHECK_IN_ID,
    component: "screen",
    created_at: "2026-07-21T10:00:00Z",
    kind: "pause",
    options: [],
    render: "Screening paused for review.",
    rerun_component: null,
    segment_reentry_allowed: false,
    sequence: 3,
    stage: "screen",
    status: "pending",
    triggers: [],
    ...overrides,
  };
}

/** A short, realistic frame stream: run open, one stage lifecycle, a
 *  check-in pause + resolution, a plan supersession, a lifecycle rename,
 *  and the run finishing. Sequences are contiguous 1..7. */
function sampleFrames(): SseFrame[] {
  return [
    {
      type: "run.status",
      capability_run_id: PROJECT_RUN_ID,
      status: "running",
      occurred_at: "2026-07-21T10:00:00Z",
      sequence: 1,
    },
    {
      type: "stage.started",
      stage: "acquire",
      label: "Acquiring sources",
      blurb: "Searching academic and grey-lit backends.",
      occurred_at: "2026-07-21T10:00:01Z",
      sequence: 2,
    },
    {
      type: "stage.completed",
      stage: "acquire",
      label: "Acquiring sources",
      summary: { found: 42 },
      seconds: 12,
      occurred_at: "2026-07-21T10:00:13Z",
      sequence: 3,
    },
    {
      type: "checkin.pending",
      check_in: checkIn({ sequence: 4 }),
      occurred_at: "2026-07-21T10:00:14Z",
      sequence: 4,
    },
    {
      type: "checkin.resolved",
      check_in_id: CHECK_IN_ID,
      response: { kind: "option", option_id: "continue" },
      decided_by: "user",
      occurred_at: "2026-07-21T10:00:20Z",
      sequence: 5,
    },
    {
      type: "plan.updated",
      plan: planDraft(),
      version: 2,
      occurred_at: "2026-07-21T10:00:21Z",
      sequence: 6,
    },
    {
      type: "run.status",
      capability_run_id: PROJECT_RUN_ID,
      status: "succeeded",
      occurred_at: "2026-07-21T10:05:00Z",
      sequence: 7,
    },
  ];
}

function fold(state: RunStreamState, frames: SseFrame[]): RunStreamState {
  return frames.reduce(reduceRunStreamFrame, state);
}

describe("reduceRunStreamFrame — replay idempotence", () => {
  it("applying the same frame stream twice leaves state unchanged after the first pass", () => {
    const frames = sampleFrames();
    const afterOnce = fold(createInitialRunStreamState(), frames);
    const afterTwice = fold(afterOnce, frames);
    expect(afterTwice).toEqual(afterOnce);
  });

  it("resuming from a mid-stream cursor with overlapping re-delivery matches a full fold", () => {
    const frames = sampleFrames();
    const fullFold = fold(createInitialRunStreamState(), frames);

    // Simulate a reconnect after sequence 3: the client has this snapshot...
    const atCursor3 = fold(createInitialRunStreamState(), frames.slice(0, 3));
    // ...and the resumed stream (over-cautiously) redelivers frames 1-3
    // before continuing with 4-7, exactly as an at-least-once backlog
    // replay might.
    const resumed = fold(atCursor3, frames);

    expect(resumed).toEqual(fullFold);
  });
});

describe("reduceRunStreamFrame — equal-sequence distinct-type frames", () => {
  /** One durable steering decision can emit `checkin.resolved` AND
   *  `plan.updated` at the SAME sequence — both must apply, not just
   *  the first. */
  function sharedSequenceFrames(): SseFrame[] {
    return [
      {
        type: "run.status",
        capability_run_id: PROJECT_RUN_ID,
        status: "running",
        occurred_at: "2026-07-21T10:00:00Z",
        sequence: 1,
      },
      {
        type: "checkin.resolved",
        check_in_id: CHECK_IN_ID,
        response: { kind: "option", option_id: "continue" },
        decided_by: "user",
        occurred_at: "2026-07-21T10:00:20Z",
        sequence: 2,
      },
      {
        type: "plan.updated",
        plan: planDraft(),
        version: 2,
        occurred_at: "2026-07-21T10:00:20Z",
        sequence: 2,
      },
    ];
  }

  it("applies both same-sequence frames once each", () => {
    const state = fold(createInitialRunStreamState(), sharedSequenceFrames());
    expect(state.decisions).toHaveLength(1);
    expect(state.plan).toEqual({ version: 2, plan: planDraft() });
    expect(state.lastSequence).toBe(2);
  });

  it("a full replay of the shared-sequence stream is still idempotent", () => {
    const frames = sharedSequenceFrames();
    const once = fold(createInitialRunStreamState(), frames);
    const twice = fold(once, frames);
    expect(twice).toEqual(once);

    // Redelivery landing mid-way through the shared sequence: only the
    // `checkin.resolved` half was seen before the resumed stream (over-
    // cautiously) replays the whole thing.
    const atCursor = fold(createInitialRunStreamState(), frames.slice(0, 2));
    const resumed = fold(atCursor, frames);
    expect(resumed).toEqual(once);
  });
});

describe("reduceRunStreamFrame — new-run reset", () => {
  it("a running run.status frame for a different run resets stages and liveness", () => {
    let state = createInitialRunStreamState();
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: PROJECT_RUN_ID,
      status: "running",
      occurred_at: "2026-07-21T10:00:00Z",
      sequence: 1,
    });
    state = reduceRunStreamFrame(state, {
      type: "stage.started",
      stage: "acquire",
      label: "Acquiring sources",
      blurb: "Searching.",
      occurred_at: "2026-07-21T10:00:01Z",
      sequence: 2,
    });
    state = reduceRunStreamFrame(state, {
      type: "tick",
      note: "Still working...",
      stage: "acquire",
      occurred_at: "2026-07-21T10:00:02Z",
      ephemeral: true,
    });
    // The run is interrupted before finishing.
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: PROJECT_RUN_ID,
      status: "interrupted",
      occurred_at: "2026-07-21T10:00:03Z",
      sequence: 3,
    });
    expect(state.stages).toHaveLength(1);

    const OTHER_RUN_ID = "33333333-3333-3333-3333-333333333333";
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: OTHER_RUN_ID,
      status: "running",
      occurred_at: "2026-07-21T10:05:00Z",
      sequence: 4,
    });

    expect(state.stages).toEqual([]);
    expect(state.liveness).toEqual({});
    expect(state.run).toEqual({ id: OTHER_RUN_ID, status: "running" });
    // The interrupted run's status is still recorded in the `runs` map.
    expect(state.runs[PROJECT_RUN_ID]).toBe("interrupted");
  });

  it("the interrupted run's stages don't survive into the next run's timeline after replay", () => {
    const OTHER_RUN_ID = "33333333-3333-3333-3333-333333333333";
    const frames: SseFrame[] = [
      {
        type: "run.status",
        capability_run_id: PROJECT_RUN_ID,
        status: "running",
        occurred_at: "2026-07-21T10:00:00Z",
        sequence: 1,
      },
      {
        type: "stage.started",
        stage: "acquire",
        label: "Acquiring sources",
        blurb: "Searching.",
        occurred_at: "2026-07-21T10:00:01Z",
        sequence: 2,
      },
      {
        type: "run.status",
        capability_run_id: PROJECT_RUN_ID,
        status: "interrupted",
        occurred_at: "2026-07-21T10:00:03Z",
        sequence: 3,
      },
      {
        type: "run.status",
        capability_run_id: OTHER_RUN_ID,
        status: "running",
        occurred_at: "2026-07-21T10:05:00Z",
        sequence: 4,
      },
      {
        type: "stage.started",
        stage: "acquire",
        label: "Acquiring sources",
        blurb: "Searching again.",
        occurred_at: "2026-07-21T10:05:01Z",
        sequence: 5,
      },
    ];

    const once = fold(createInitialRunStreamState(), frames);
    expect(once.stages).toHaveLength(1);
    expect(once.stages[0].blurb).toBe("Searching again.");

    const twice = fold(once, frames);
    expect(twice).toEqual(once);

    const atCursor = fold(createInitialRunStreamState(), frames.slice(0, 3));
    const resumed = fold(atCursor, frames);
    expect(resumed).toEqual(once);
  });
});

describe("reduceRunStreamFrame — live artefact sections", () => {
  const OTHER_RUN_ID = "33333333-3333-3333-3333-333333333333";

  function liveFrames(): SseFrame[] {
    return [
      {
        type: "run.status",
        capability_run_id: PROJECT_RUN_ID,
        status: "running",
        occurred_at: "2026-07-28T10:00:00Z",
        sequence: 1,
      },
      {
        type: "artefact.skeleton",
        sections: [
          { index: 0, title: "Key findings", focus: "The headline evidence." },
          { index: 3, title: "Conclusion", focus: "What the evidence means." },
        ],
        occurred_at: "2026-07-28T10:01:00Z",
        sequence: 2,
      },
      {
        type: "artefact.section_started",
        index: 3,
        occurred_at: "2026-07-28T10:01:01Z",
        sequence: 3,
      },
      {
        type: "artefact.section_completed",
        index: 3,
        title: "Conclusion",
        prose: "The available evidence supports the intervention.",
        occurred_at: "2026-07-28T10:01:20Z",
        sequence: 4,
      },
    ];
  }

  it("builds planned, writing, and filled display-indexed sections", () => {
    const skeleton = fold(createInitialRunStreamState(), liveFrames().slice(0, 2));
    expect(skeleton.liveSections).toEqual({
      0: { index: 0, title: "Key findings", focus: "The headline evidence.", state: "planned" },
      3: { index: 3, title: "Conclusion", focus: "What the evidence means.", state: "planned" },
    });

    const writing = fold(skeleton, liveFrames().slice(2, 3));
    expect(writing.liveSections[3].state).toBe("writing");

    const filled = fold(writing, liveFrames().slice(3));
    expect(filled.liveSections[3]).toEqual({
      index: 3,
      title: "Conclusion",
      focus: "What the evidence means.",
      state: "filled",
      prose: "The available evidence supports the intervention.",
    });
  });

  it("drops a completed empty-prose slot instead of inventing section content", () => {
    const state = fold(createInitialRunStreamState(), [
      ...liveFrames().slice(0, 2),
      {
        type: "artefact.section_completed",
        index: 0,
        title: "Key findings",
        prose: "",
        occurred_at: "2026-07-28T10:01:10Z",
        sequence: 3,
      },
    ]);

    expect(state.liveSections[0]).toBeUndefined();
    expect(state.liveSections[3]?.state).toBe("planned");
  });

  it("clears sections only when a different running run starts", () => {
    let state = fold(createInitialRunStreamState(), liveFrames());
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: PROJECT_RUN_ID,
      status: "interrupted",
      occurred_at: "2026-07-28T10:02:00Z",
      sequence: 5,
    });
    expect(state.liveSections[3]?.state).toBe("filled");
    expect(hasTerminalPartialLiveArtefact(state)).toBe(true);

    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: OTHER_RUN_ID,
      status: "running",
      occurred_at: "2026-07-28T10:03:00Z",
      sequence: 6,
    });
    expect(state.liveSections).toEqual({});
    expect(hasTerminalPartialLiveArtefact(state)).toBe(false);
  });

  it("keeps streamed-section state replay-idempotent", () => {
    const frames = liveFrames();
    const once = fold(createInitialRunStreamState(), frames);
    const twice = fold(once, frames);
    expect(twice).toEqual(once);
  });
});

describe("reduceRunStreamFrame — check-in pending/resolved lifecycle", () => {
  it("checkin.pending sets pendingCheckIn; its checkin.resolved clears it into decisions", () => {
    const pending = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "checkin.pending",
      check_in: checkIn(),
      occurred_at: "2026-07-21T10:00:14Z",
      sequence: 1,
    });
    expect(pending.pendingCheckIn?.check_in_id).toBe(CHECK_IN_ID);
    expect(pending.decisions).toHaveLength(0);

    const resolved = reduceRunStreamFrame(pending, {
      type: "checkin.resolved",
      check_in_id: CHECK_IN_ID,
      response: { kind: "option", option_id: "continue" },
      decided_by: "user",
      occurred_at: "2026-07-21T10:00:20Z",
      sequence: 2,
    });

    expect(resolved.pendingCheckIn).toBeNull();
    expect(resolved.decisions).toEqual([
      {
        checkInId: CHECK_IN_ID,
        response: { kind: "option", option_id: "continue" },
        decidedBy: "user",
        occurredAt: "2026-07-21T10:00:20Z",
        sequence: 2,
      },
    ]);
  });

  it("a resolved frame for a different check-in leaves an unrelated pending card alone", () => {
    const pending = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "checkin.pending",
      check_in: checkIn({ check_in_id: "other-check-in" }),
      occurred_at: "2026-07-21T10:00:14Z",
      sequence: 1,
    });

    const resolved = reduceRunStreamFrame(pending, {
      type: "checkin.resolved",
      check_in_id: CHECK_IN_ID,
      response: { kind: "abort" },
      decided_by: "standing_default",
      occurred_at: "2026-07-21T10:00:20Z",
      sequence: 2,
    });

    expect(resolved.pendingCheckIn?.check_in_id).toBe("other-check-in");
    expect(resolved.decisions).toHaveLength(1);
  });
});

describe("reduceRunStreamFrame — tick transience", () => {
  it("updates only the transient liveness slice and never touches lastSequence", () => {
    const base = fold(createInitialRunStreamState(), sampleFrames());

    const withTick = reduceRunStreamFrame(base, {
      type: "tick",
      note: "Still screening batch 4 of 9...",
      stage: "screen",
      occurred_at: "2026-07-21T10:02:00Z",
      ephemeral: true,
    });

    expect(withTick.liveness.screen).toEqual({
      note: "Still screening batch 4 of 9...",
      occurredAt: "2026-07-21T10:02:00Z",
    });
    expect(withTick.lastSequence).toBe(base.lastSequence);
    expect({ ...withTick, liveness: {} }).toEqual({ ...base, liveness: {} });
  });

  it("a stage-less tick lands under the global liveness key", () => {
    const withTick = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "tick",
      note: "Warming up...",
      stage: null,
      occurred_at: "2026-07-21T10:00:00Z",
      ephemeral: true,
    });

    expect(withTick.liveness._global).toEqual({
      note: "Warming up...",
      occurredAt: "2026-07-21T10:00:00Z",
    });
  });

  it("repeated ticks for the same stage overwrite (last note wins), never accumulate", () => {
    let state = createInitialRunStreamState();
    state = reduceRunStreamFrame(state, {
      type: "tick",
      note: "First note",
      stage: "extract",
      occurred_at: "2026-07-21T10:00:00Z",
      ephemeral: true,
    });
    state = reduceRunStreamFrame(state, {
      type: "tick",
      note: "Second note",
      stage: "extract",
      occurred_at: "2026-07-21T10:00:05Z",
      ephemeral: true,
    });

    expect(Object.keys(state.liveness)).toEqual(["extract"]);
    expect(state.liveness.extract.note).toBe("Second note");
  });
});

describe("reduceRunStreamFrame — stage lifecycle", () => {
  it("stage.completed updates the matching started entry in place rather than appending", () => {
    const started = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "stage.started",
      stage: "screen",
      label: "Screening",
      blurb: "Applying inclusion criteria.",
      occurred_at: "2026-07-21T10:00:00Z",
      sequence: 1,
    });
    const completed = reduceRunStreamFrame(started, {
      type: "stage.completed",
      stage: "screen",
      label: "Screening",
      summary: { included: 10 },
      seconds: 5,
      occurred_at: "2026-07-21T10:00:05Z",
      sequence: 2,
    });

    expect(completed.stages).toHaveLength(1);
    expect(completed.stages[0]).toEqual({
      stage: "screen",
      label: "Screening",
      status: "completed",
      summary: { included: 10 },
      seconds: 5,
    });
  });

  it("stage.failed with skipped=true records status skipped and carries the reason", () => {
    const started = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "stage.started",
      stage: "group",
      label: "Grouping",
      blurb: "Clustering findings.",
      occurred_at: "2026-07-21T10:00:00Z",
      sequence: 1,
    });
    const skipped = reduceRunStreamFrame(started, {
      type: "stage.failed",
      stage: "group",
      label: "Grouping",
      reason: "insufficient findings to cluster",
      skipped: true,
      occurred_at: "2026-07-21T10:00:02Z",
      sequence: 2,
    });

    expect(skipped.stages[0].status).toBe("skipped");
    expect(skipped.stages[0].summary).toEqual({ reason: "insufficient findings to cluster" });
  });
});

describe("reduceRunStreamFrame — project.updated partial merge", () => {
  it("merges only the fields the event actually touched", () => {
    let state = createInitialRunStreamState();
    state = reduceRunStreamFrame(state, {
      type: "project.updated",
      name: "Original name",
      question: "Original question",
      status: "active",
      occurred_at: "2026-07-21T09:00:00Z",
      sequence: 1,
    });
    // A rename-only event: question/status are `null` (not touched), not cleared.
    state = reduceRunStreamFrame(state, {
      type: "project.updated",
      name: "Renamed",
      question: null,
      status: null,
      occurred_at: "2026-07-21T09:05:00Z",
      sequence: 2,
    });

    expect(state.project).toEqual({
      name: "Renamed",
      question: "Original question",
      status: "active",
    });
  });
});

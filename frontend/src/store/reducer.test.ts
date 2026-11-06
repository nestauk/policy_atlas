import { describe, expect, it } from "vitest";

import type { SseFrame } from "../api/sseFrame";
import { hasTerminalPartialLiveArtefact, reduceRunStreamFrame } from "./reducer";
import { createInitialRunStreamState } from "./types";
import type { CheckInOut, PlanDraft, RunStreamState, StageEntry } from "./types";

const TASK_RUN_ID = "11111111-1111-1111-1111-111111111111";
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
    bundle: null,
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
      capability_run_id: TASK_RUN_ID,
      status: "running",
      occurred_at: "2026-07-21T10:00:00Z",
      sequence: 1,
    },
    {
      type: "stage.started", capability_run_id: null,
      stage: "acquire",
      label: "Acquiring sources",
      blurb: "Searching academic and grey-lit backends.",
      occurred_at: "2026-07-21T10:00:01Z",
      sequence: 2,
    },
    {
      type: "stage.completed", capability_run_id: null,
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
      scoping: null,
      plan: planDraft(),
      version: 2,
      occurred_at: "2026-07-21T10:00:21Z",
      sequence: 6,
    },
    {
      type: "run.status",
      capability_run_id: TASK_RUN_ID,
      status: "succeeded",
      occurred_at: "2026-07-21T10:05:00Z",
      sequence: 7,
    },
  ];
}

function fold(state: RunStreamState, frames: SseFrame[]): RunStreamState {
  return frames.reduce(reduceRunStreamFrame, state);
}

type TickFrame = Extract<SseFrame, { type: "tick" }>;

/** A tick with every optional field at its wire default. */
function tick(overrides: Partial<TickFrame> = {}): TickFrame {
  return {
    type: "tick",
    activity: "Screening abstracts",
    stage: "screen",
    done: null,
    total: null,
    unit: null,
    section: null,
    heartbeat: false,
    dropped: 0,
    capability_run_id: null,
    occurred_at: "2026-07-21T10:02:00Z",
    ephemeral: true,
    ...overrides,
  };
}

function delta(index: number, text: string, mode: "append" | "replace" = "append"): SseFrame {
  return {
    type: "artefact.section_delta",
    index,
    text,
    mode,
    occurred_at: "2026-07-28T10:01:05Z",
    ephemeral: true,
  };
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
        capability_run_id: TASK_RUN_ID,
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
      scoping: null,
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
      capability_run_id: TASK_RUN_ID,
      status: "running",
      occurred_at: "2026-07-21T10:00:00Z",
      sequence: 1,
    });
    state = reduceRunStreamFrame(state, {
      type: "stage.started", capability_run_id: null,
      stage: "acquire",
      label: "Acquiring sources",
      blurb: "Searching.",
      occurred_at: "2026-07-21T10:00:01Z",
      sequence: 2,
    });
    state = reduceRunStreamFrame(
      state,
      tick({ activity: "Searching", stage: "acquire", occurred_at: "2026-07-21T10:00:02Z" }),
    );
    // The run is interrupted before finishing.
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: TASK_RUN_ID,
      status: "interrupted",
      occurred_at: "2026-07-21T10:00:03Z",
      sequence: 3,
    });
    expect(state.stages).toHaveLength(1);
    expect(state.run?.endedAt).toBe("2026-07-21T10:00:03Z");

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
    expect(state.run).toEqual({
      id: OTHER_RUN_ID,
      status: "running",
      startedAt: "2026-07-21T10:05:00Z",
    });
    // The interrupted run's status is still recorded in the `runs` map.
    expect(state.runs[TASK_RUN_ID]).toBe("interrupted");
  });

  it("the interrupted run's stages don't survive into the next run's timeline after replay", () => {
    const OTHER_RUN_ID = "33333333-3333-3333-3333-333333333333";
    const frames: SseFrame[] = [
      {
        type: "run.status",
        capability_run_id: TASK_RUN_ID,
        status: "running",
        occurred_at: "2026-07-21T10:00:00Z",
        sequence: 1,
      },
      {
        type: "stage.started", capability_run_id: null,
        stage: "acquire",
        label: "Acquiring sources",
        blurb: "Searching.",
        occurred_at: "2026-07-21T10:00:01Z",
        sequence: 2,
      },
      {
        type: "run.status",
        capability_run_id: TASK_RUN_ID,
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
        type: "stage.started", capability_run_id: null,
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
        capability_run_id: TASK_RUN_ID,
        status: "running",
        occurred_at: "2026-07-28T10:00:00Z",
        sequence: 1,
      },
      {
        type: "artefact.skeleton",
        sections: [
          { index: 0, title: "Key findings", focus: "The headline evidence.", role: "key_findings" },
          { index: 3, title: "Conclusion", focus: "What the evidence means.", role: "body" },
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
      0: { index: 0, title: "Key findings", focus: "The headline evidence.", role: "key_findings", state: "planned" },
      3: { index: 3, title: "Conclusion", focus: "What the evidence means.", role: "body", state: "planned" },
    });

    const writing = fold(skeleton, liveFrames().slice(2, 3));
    expect(writing.liveSections[3].state).toBe("writing");

    const filled = fold(writing, liveFrames().slice(3));
    expect(filled.liveSections[3]).toEqual({
      index: 3,
      title: "Conclusion",
      focus: "What the evidence means.",
      role: "body",
      state: "filled",
      prose: "The available evidence supports the intervention.",
    });
  });

  // Task 044 (X8): an options-scoping baseline streams no "Key findings"
  // section. The reducer must render exactly the titles the server sent, in
  // the order it sent them — it inserts nothing of its own, and a section
  // turns into its prose as its own `section_completed` arrives.
  it("renders exactly the skeleton the server sent, in order, for a baseline walk", () => {
    const titles = [
      "What is in place",
      "Trend if nothing changes",
      "Who is affected",
      "What is already changing",
      "What is contested",
      "How the transition is tracked",
      "Cost of inaction",
      "Key assumption",
      "Sources",
    ];
    const skeleton = fold(createInitialRunStreamState(), [
      liveFrames()[0],
      {
        type: "artefact.skeleton",
        sections: titles.map((title, index) => ({ index, title, focus: `${title} focus.`, role: "body" as const })),
        occurred_at: "2026-07-28T10:01:00Z",
        sequence: 2,
      },
    ]);
    const ordered = Object.values(skeleton.liveSections).sort((a, b) => a.index - b.index);
    expect(ordered.map((section) => section.title)).toEqual(titles);
    expect(ordered.every((section) => section.state === "planned")).toBe(true);

    // The fourth section finishes before the others: only that slot fills.
    const filled = fold(skeleton, [
      {
        type: "artefact.section_completed",
        index: 3,
        title: "What is already changing",
        prose: "A devolved adult-skills settlement takes effect next year.",
        occurred_at: "2026-07-28T10:02:00Z",
        sequence: 3,
      },
    ]);
    expect(filled.liveSections[3].state).toBe("filled");
    expect(filled.liveSections[4].state).toBe("planned");
    expect(
      Object.values(filled.liveSections)
        .sort((a, b) => a.index - b.index)
        .map((section) => section.title),
    ).toEqual(titles);
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
      capability_run_id: TASK_RUN_ID,
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

// Task 058, N7: the ephemeral delta and revising frames build a draft beside
// the durable prose.
describe("reduceRunStreamFrame — streamed drafts", () => {
  const OTHER_RUN_ID = "33333333-3333-3333-3333-333333333333";

  function writingFrames(): SseFrame[] {
    return [
      {
        type: "run.status",
        capability_run_id: TASK_RUN_ID,
        status: "running",
        occurred_at: "2026-07-28T10:00:00Z",
        sequence: 1,
      },
      {
        type: "artefact.skeleton",
        sections: [
          { index: 0, title: "Key findings", focus: "The headline evidence.", role: "key_findings" },
          { index: 3, title: "Conclusion", focus: "What the evidence means.", role: "body" },
        ],
        occurred_at: "2026-07-28T10:01:00Z",
        sequence: 2,
      },
      { type: "artefact.section_started", index: 3, occurred_at: "2026-07-28T10:01:01Z", sequence: 3 },
    ];
  }

  const completed: SseFrame = {
    type: "artefact.section_completed",
    index: 3,
    title: "Conclusion",
    prose: "The evidence supports the intervention.",
    occurred_at: "2026-07-28T10:01:20Z",
    sequence: 4,
  };

  it("append concatenates onto the draft and replace resets it", () => {
    let state = fold(createInitialRunStreamState(), writingFrames());
    state = fold(state, [delta(3, "The evidence "), delta(3, "supports")]);
    expect(state.liveSections[3].draft).toBe("The evidence supports");
    expect(state.liveSections[3].prose).toBeUndefined();

    state = reduceRunStreamFrame(state, delta(3, "Restarted", "replace"));
    expect(state.liveSections[3].draft).toBe("Restarted");
    state = reduceRunStreamFrame(state, delta(3, "", "replace"));
    expect(state.liveSections[3].draft).toBe("");
  });

  it("revising marks spans of the draft; completion sets prose and clears draft and revising", () => {
    let state = fold(createInitialRunStreamState(), writingFrames());
    state = reduceRunStreamFrame(state, delta(3, "The evidence supports it. It costs little."));
    state = reduceRunStreamFrame(state, {
      type: "artefact.section_revising",
      index: 3,
      spans: [{ start: 26, end: 42 }],
      occurred_at: "2026-07-28T10:01:10Z",
      ephemeral: true,
    });
    expect(state.liveSections[3].revising).toEqual([{ start: 26, end: 42 }]);

    state = reduceRunStreamFrame(state, completed);
    expect(state.liveSections[3]).toEqual({
      index: 3,
      title: "Conclusion",
      focus: "What the evidence means.",
      role: "body",
      state: "filled",
      prose: "The evidence supports the intervention.",
    });
  });

  it("sources replace the set, claims append, and completion clears both (evidence shown live)", () => {
    const sources = (set: { source_id: string; title: string }[]): SseFrame => ({
      type: "artefact.section_sources",
      index: 3,
      sources: set,
      occurred_at: "2026-07-28T10:01:05Z",
      ephemeral: true,
    });
    const claim = (start: number, end: number, title: string): SseFrame => ({
      type: "artefact.section_claim",
      index: 3,
      start,
      end,
      sources: [{ source_id: `id-${title}`, title }],
      occurred_at: "2026-07-28T10:01:12Z",
      ephemeral: true,
    });
    const base = fold(createInitialRunStreamState(), writingFrames());
    let state = fold(base, [
      sources([{ source_id: "a", title: "Smith 2023" }]),
      sources([
        { source_id: "a", title: "Smith 2023" },
        { source_id: "b", title: "DfE 2022" },
      ]),
    ]);
    expect(state.liveSections[3].sources).toEqual([
      { sourceId: "a", title: "Smith 2023" },
      { sourceId: "b", title: "DfE 2022" },
    ]);

    state = fold(state, [delta(3, "The evidence supports it. It costs little."), claim(0, 25, "Smith 2023")]);
    state = reduceRunStreamFrame(state, claim(26, 42, "DfE 2022"));
    expect(state.liveSections[3].claims).toEqual([
      { start: 0, end: 25, sources: [{ sourceId: "id-Smith 2023", title: "Smith 2023" }] },
      { start: 26, end: 42, sources: [{ sourceId: "id-DfE 2022", title: "DfE 2022" }] },
    ]);
    // Neither frame moves the cursor.
    expect(state.lastSequence).toBe(base.lastSequence);
    expect(state.appliedTypesAtLastSequence).toEqual(base.appliedTypesAtLastSequence);

    // A replaced draft drops the citations bound to the old text; the sources stay.
    const replaced = reduceRunStreamFrame(state, delta(3, "", "replace"));
    expect(replaced.liveSections[3].claims).toBeUndefined();
    expect(replaced.liveSections[3].sources).toHaveLength(2);

    state = reduceRunStreamFrame(state, completed);
    expect(state.liveSections[3].sources).toBeUndefined();
    expect(state.liveSections[3].claims).toBeUndefined();
    // A late frame never reopens the completed section, and an unknown index is ignored.
    const late = fold(state, [sources([{ source_id: "c", title: "Late" }]), claim(0, 3, "Late")]);
    expect(late.liveSections).toEqual(state.liveSections);
    const unknown = reduceRunStreamFrame(base, { ...claim(0, 3, "X"), index: 9 } as SseFrame);
    expect(unknown).toBe(base);
  });

  it("completion sets the checked citations and keeps them; a replay rebuilds them (round 7)", () => {
    const withCitations: SseFrame = {
      ...completed,
      citations: [
        { start: 0, end: 12, n: 2, source_id: "tss-a", title: "Breakfast clubs", tier: "tier_2" },
        { start: 0, end: 12, n: 5, source_id: null, title: "Unknown source", tier: null },
      ],
    } as SseFrame;
    const live = fold(createInitialRunStreamState(), [...writingFrames(), delta(3, "The evidence")]);
    const state = reduceRunStreamFrame(live, withCitations);
    // Recorded in the round-7 shape: the round-8 ids are null, the quote empty.
    const expected = [
      { start: 0, end: 12, n: 2, sourceId: "tss-a", title: "Breakfast clubs", tier: "tier_2", citationId: null, claimId: null, quote: "" },
      { start: 0, end: 12, n: 5, sourceId: null, title: "Unknown source", tier: null, citationId: null, claimId: null, quote: "" },
    ];
    expect(state.liveSections[3].citations).toEqual(expected);
    // Kept: a late ephemeral frame or the next section's frames leave them.
    const later = fold(state, [delta(3, "late"), {
      type: "artefact.section_card",
      index: 3,
      title: "Late",
      prose: "Late card.",
      occurred_at: "2026-07-28T10:01:30Z",
      ephemeral: true,
    }]);
    expect(later.liveSections[3].citations).toEqual(expected);
    // A replay (durable frames only) rebuilds the same citations.
    const replayed = fold(createInitialRunStreamState(), [...writingFrames(), withCitations]);
    expect(replayed.liveSections[3].citations).toEqual(expected);
    // A section with no citations, or a frame recorded before the field
    // existed, carries none.
    const older = reduceRunStreamFrame(live, completed);
    expect(older.liveSections[3].citations).toBeUndefined();
  });

  it("completion carries each citation's saved ids and quote (round 8)", () => {
    const withIds: SseFrame = {
      ...completed,
      citations: [
        {
          start: 0,
          end: 12,
          n: 2,
          source_id: "tss-a",
          title: "Breakfast clubs",
          tier: "tier_2",
          citation_id: "c-1",
          claim_id: "u-1",
          quote: "Participation rose.",
        },
      ],
    };
    const state = fold(createInitialRunStreamState(), [...writingFrames(), withIds]);
    expect(state.liveSections[3].citations).toEqual([
      {
        start: 0,
        end: 12,
        n: 2,
        sourceId: "tss-a",
        title: "Breakfast clubs",
        tier: "tier_2",
        citationId: "c-1",
        claimId: "u-1",
        quote: "Participation rose.",
      },
    ]);
  });

  it("source notes arrive one per source, in order, never move the cursor, and go with the run (round 8)", () => {
    const note = (sourceId: string, text: string): SseFrame => ({
      type: "artefact.source_note",
      source_id: sourceId,
      title: `Title ${sourceId}`,
      note: text,
      occurred_at: "2026-07-28T10:01:40Z",
      ephemeral: true,
    });
    const base = fold(createInitialRunStreamState(), writingFrames());
    expect(base.liveSourceNotes).toBeUndefined();
    let state = fold(base, [note("s1", "One."), note("s2", "Two.")]);
    expect(state.liveSourceNotes).toEqual([
      { sourceId: "s1", title: "Title s1", note: "One." },
      { sourceId: "s2", title: "Title s2", note: "Two." },
    ]);
    expect(state.lastSequence).toBe(base.lastSequence);
    expect(state.appliedTypesAtLastSequence).toEqual(base.appliedTypesAtLastSequence);
    // A reconnect's snapshot sends them again: replaced in place, never doubled.
    state = fold(state, [note("s1", "One."), note("s2", "Two, again.")]);
    expect(state.liveSourceNotes?.map((entry) => entry.note)).toEqual(["One.", "Two, again."]);
    // The same run's later frames keep them; a new run starts without them.
    state = reduceRunStreamFrame(state, completed);
    expect(state.liveSourceNotes).toHaveLength(2);
    state = fold(state, [
      {
        type: "run.status",
        capability_run_id: TASK_RUN_ID,
        status: "succeeded",
        occurred_at: "2026-07-28T10:02:00Z",
        sequence: 8,
      },
    ]);
    expect(state.liveSourceNotes).toHaveLength(2);
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: OTHER_RUN_ID,
      status: "running",
      occurred_at: "2026-07-28T10:05:00Z",
      sequence: 9,
    });
    expect(state.liveSourceNotes).toBeUndefined();
  });

  it("search queries go out, come back in place, never move the cursor, and go with the run (round 9)", () => {
    const query = (
      text: string,
      results: number | null,
      kind: "topic" | "semantic" | "citations" | "lookup" = "topic",
      backend = "openalex",
    ): SseFrame => ({
      type: "search.query",
      backend,
      query: text,
      kind,
      results,
      occurred_at: "2026-07-28T10:00:10Z",
      ephemeral: true,
    });
    const base = fold(createInitialRunStreamState(), writingFrames());
    expect(base.liveSearchQueries).toBeUndefined();
    let state = fold(base, [
      query("school breakfast attainment", null),
      query("school breakfast attainment", null, "semantic"),
      query("school breakfast attainment", null, "topic", "overton"),
      query("school breakfast attainment", 40),
      query("Following citations from 50 sources", null, "citations"),
    ]);
    expect(state.liveSearchQueries).toEqual([
      { backend: "openalex", query: "school breakfast attainment", kind: "topic", results: 40 },
      { backend: "openalex", query: "school breakfast attainment", kind: "semantic", results: null },
      { backend: "overton", query: "school breakfast attainment", kind: "topic", results: null },
      { backend: "openalex", query: "Following citations from 50 sources", kind: "citations", results: null },
    ]);
    expect(state.lastSequence).toBe(base.lastSequence);
    expect(state.appliedTypesAtLastSequence).toEqual(base.appliedTypesAtLastSequence);
    // A reconnect's snapshot repeats the rows in their latest state: never doubled.
    state = fold(state, [query("school breakfast attainment", 40), query("Following citations from 50 sources", 212, "citations")]);
    expect(state.liveSearchQueries).toHaveLength(4);
    expect(state.liveSearchQueries?.[3].results).toBe(212);
    // The run ends; the next top-level run starts without them.
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: TASK_RUN_ID,
      status: "succeeded",
      occurred_at: "2026-07-28T10:04:00Z",
      sequence: 98,
    });
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: OTHER_RUN_ID,
      status: "running",
      occurred_at: "2026-07-28T10:05:00Z",
      sequence: 99,
    });
    expect(state.liveSearchQueries).toBeUndefined();
  });

  it("themes arrive once found, a repeat replaces them, and they go with the run (round 9)", () => {
    const themes = (labels: string[]): SseFrame => ({
      type: "characterise.themes",
      stage: "characterise",
      themes: labels.map((label, i) => ({ label, description: i === 0 ? null : `About ${label}.` })),
      occurred_at: "2026-07-28T10:00:40Z",
      ephemeral: true,
    });
    const base = fold(createInitialRunStreamState(), writingFrames());
    expect(base.liveThemes).toBeUndefined();
    let state = reduceRunStreamFrame(base, themes(["Attendance", "Attainment"]));
    expect(state.liveThemes).toEqual([
      { label: "Attendance", description: null },
      { label: "Attainment", description: "About Attainment." },
    ]);
    expect(state.lastSequence).toBe(base.lastSequence);
    state = reduceRunStreamFrame(state, themes(["Attendance", "Attainment", "Costs"]));
    expect(state.liveThemes?.map((theme) => theme.label)).toEqual(["Attendance", "Attainment", "Costs"]);
    // The run ends; the next top-level run starts without them.
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: TASK_RUN_ID,
      status: "succeeded",
      occurred_at: "2026-07-28T10:04:00Z",
      sequence: 98,
    });
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: OTHER_RUN_ID,
      status: "running",
      occurred_at: "2026-07-28T10:05:00Z",
      sequence: 99,
    });
    expect(state.liveThemes).toBeUndefined();
  });

  it("the longlist's options and themes land beside the search's themes, each by its stage (round 11)", () => {
    const names = (stage: "characterise" | "longlist" | "theme", labels: string[]): SseFrame => ({
      type: "characterise.themes",
      stage,
      themes: labels.map((label) => ({ label, description: null })),
      occurred_at: "2026-07-28T10:00:40Z",
      ephemeral: true,
    });
    let state = fold(createInitialRunStreamState(), writingFrames());
    state = reduceRunStreamFrame(state, names("characterise", ["Attendance"]));
    state = reduceRunStreamFrame(state, names("longlist", ["Free breakfasts", "Tutoring"]));
    expect(state.liveOptions?.map((option) => option.label)).toEqual(["Free breakfasts", "Tutoring"]);
    expect(state.liveOptionThemes).toBeUndefined();
    // The residual pass sends the whole list again: it replaces the first.
    state = reduceRunStreamFrame(state, names("longlist", ["Free breakfasts", "Tutoring", "Mentoring"]));
    state = reduceRunStreamFrame(state, names("theme", ["Food", "Learning"]));
    expect(state.liveOptions?.map((option) => option.label)).toEqual(["Free breakfasts", "Tutoring", "Mentoring"]);
    expect(state.liveOptionThemes?.map((theme) => theme.label)).toEqual(["Food", "Learning"]);
    expect(state.liveThemes?.map((theme) => theme.label)).toEqual(["Attendance"]);
    // A new top-level run starts without any of them.
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: TASK_RUN_ID,
      status: "succeeded",
      occurred_at: "2026-07-28T10:04:00Z",
      sequence: 98,
    });
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: OTHER_RUN_ID,
      status: "running",
      occurred_at: "2026-07-28T10:05:00Z",
      sequence: 99,
    });
    expect(state.liveOptions).toBeUndefined();
    expect(state.liveOptionThemes).toBeUndefined();
  });

  it("an intro slot keeps its role and completes with its prose (round 8)", () => {
    const state = fold(createInitialRunStreamState(), [
      writingFrames()[0],
      {
        type: "artefact.skeleton",
        sections: [
          { index: 0, title: "Key findings", focus: "", role: "key_findings" },
          { index: 1, title: "Costs", focus: "", role: "body" },
          { index: 2, title: "Case studies", focus: "", role: "case_studies" },
          { index: 3, title: "Full report", focus: "", role: "intro" },
        ],
        occurred_at: "2026-07-28T10:01:00Z",
        sequence: 2,
      },
      { type: "artefact.section_started", index: 3, occurred_at: "2026-07-28T10:03:00Z", sequence: 3 },
      delta(3, "The report first"),
      delta(3, " weighs the evidence."),
    ]);
    expect(state.liveSections[3]).toMatchObject({ role: "intro", state: "writing", draft: "The report first weighs the evidence." });
    const done = reduceRunStreamFrame(state, {
      type: "artefact.section_completed",
      index: 3,
      title: "Full report",
      prose: "The report first weighs the evidence.",
      citations: [],
      occurred_at: "2026-07-28T10:03:05Z",
      sequence: 4,
    });
    expect(done.liveSections[3]).toMatchObject({ role: "intro", state: "filled", prose: "The report first weighs the evidence." });
    expect(done.liveSections[3].draft).toBeUndefined();
    expect(done.liveSections[3].citations).toBeUndefined();
  });

  it("cards append in order, a replace clears them, completion clears them (round 7)", () => {
    const card = (title: string, prose: string, index = 3): SseFrame => ({
      type: "artefact.section_card",
      index,
      title,
      prose,
      occurred_at: "2026-07-28T10:01:10Z",
      ephemeral: true,
    });
    const base = fold(createInitialRunStreamState(), writingFrames());
    let state = fold(base, [card("Leeds", "Breakfast in every primary."), card("Bristol", "Walking buses.")]);
    expect(state.liveSections[3].cards).toEqual([
      { title: "Leeds", prose: "Breakfast in every primary." },
      { title: "Bristol", prose: "Walking buses." },
    ]);
    // Cards never move the cursor.
    expect(state.lastSequence).toBe(base.lastSequence);
    expect(state.appliedTypesAtLastSequence).toEqual(base.appliedTypesAtLastSequence);
    // The reply is written again: the old cards go.
    const replaced = reduceRunStreamFrame(state, delta(3, "", "replace"));
    expect(replaced.liveSections[3].cards).toBeUndefined();
    state = reduceRunStreamFrame(state, completed);
    expect(state.liveSections[3].cards).toBeUndefined();
    expect(state.liveSections[3].state).toBe("filled");
    // A late card never reopens the section, and an unknown index is ignored.
    expect(reduceRunStreamFrame(state, card("Late", "x")).liveSections).toEqual(state.liveSections);
    expect(reduceRunStreamFrame(base, card("X", "y", 9))).toBe(base);
  });

  it("a late delta never reopens a completed section", () => {
    const state = fold(createInitialRunStreamState(), [...writingFrames(), completed, delta(3, "late")]);
    expect(state.liveSections[3].draft).toBeUndefined();
    expect(state.liveSections[3].state).toBe("filled");
  });

  it("a delta before the skeleton is held and folded in by the skeleton", () => {
    const [runStatus, skeleton, started] = writingFrames();
    let state = fold(createInitialRunStreamState(), [runStatus, delta(3, "So far "), delta(3, "so good")]);
    expect(state.liveSections).toEqual({});
    expect(state.pendingDrafts).toEqual({ 3: "So far so good" });

    state = fold(state, [skeleton, started, delta(3, ".")]);
    expect(state.liveSections[3].draft).toBe("So far so good.");
    expect(state.liveSections[0].draft).toBeUndefined();
    expect(state.pendingDrafts).toEqual({});
  });

  it("a reload mid-section: the replay then a replace delta restores the prose so far", () => {
    // The snapshot sends the replay (which has the skeleton), then the hub's
    // draft as one replace delta, then live appends.
    const state = fold(createInitialRunStreamState(), [
      ...writingFrames(),
      delta(3, "Written before the reload", "replace"),
      delta(3, ", and after."),
    ]);
    expect(state.liveSections[3].draft).toBe("Written before the reload, and after.");
  });

  it("the ephemeral frames never advance lastSequence or the applied-types set", () => {
    const base = fold(createInitialRunStreamState(), writingFrames());
    const after = fold(base, [
      delta(3, "text"),
      delta(9, "held"),
      {
        type: "artefact.section_revising",
        index: 3,
        spans: [{ start: 0, end: 4 }],
        occurred_at: "2026-07-28T10:01:10Z",
        ephemeral: true,
      },
    ]);
    expect(after.lastSequence).toBe(base.lastSequence);
    expect(after.appliedTypesAtLastSequence).toEqual(base.appliedTypesAtLastSequence);
  });

  it("a replay with no deltas rebuilds prose only", () => {
    const live = fold(createInitialRunStreamState(), [...writingFrames(), delta(3, "draft"), completed]);
    const replayed = fold(createInitialRunStreamState(), [...writingFrames(), completed]);
    expect(replayed.liveSections).toEqual(live.liveSections);
    expect(replayed.liveSections[3].draft).toBeUndefined();
  });

  it("a new run clears drafts, held drafts and liveness", () => {
    let state = fold(createInitialRunStreamState(), [
      ...writingFrames(),
      delta(3, "draft"),
      delta(7, "held"),
      tick({ stage: "synthesise" }),
      {
        type: "run.status",
        capability_run_id: TASK_RUN_ID,
        status: "interrupted",
        occurred_at: "2026-07-28T10:02:00Z",
        sequence: 4,
      },
    ]);
    expect(state.liveSections[3].draft).toBe("draft");
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: OTHER_RUN_ID,
      status: "running",
      occurred_at: "2026-07-28T10:05:00Z",
      sequence: 5,
    });
    expect(state.liveSections).toEqual({});
    expect(state.pendingDrafts).toEqual({});
    expect(state.liveness).toEqual({});
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

    const withTick = reduceRunStreamFrame(base, tick());

    expect(withTick.liveness.screen).toEqual({
      activity: "Screening abstracts",
      heartbeat: false,
      dropped: 0,
      occurredAt: "2026-07-21T10:02:00Z",
    });
    expect(withTick.lastSequence).toBe(base.lastSequence);
    expect({ ...withTick, liveness: {} }).toEqual({ ...base, liveness: {} });
  });

  it("keeps a tick's counts, unit, section line, heartbeat and dropped counter (task 058, N5)", () => {
    const state = reduceRunStreamFrame(
      createInitialRunStreamState(),
      tick({
        activity: "Writing",
        stage: "synthesise",
        done: 3,
        total: 7,
        unit: "sections",
        section: "Section 3 of 7 · Costs",
        heartbeat: true,
        dropped: 2,
      }),
    );
    expect(state.liveness.synthesise).toEqual({
      activity: "Writing",
      done: 3,
      total: 7,
      unit: "sections",
      section: "Section 3 of 7 · Costs",
      heartbeat: true,
      dropped: 2,
      occurredAt: "2026-07-21T10:02:00Z",
    });
  });

  it("stores heartbeats per stage, each stage keeping its own latest tick", () => {
    let state = createInitialRunStreamState();
    state = reduceRunStreamFrame(state, tick({ stage: "screen", activity: "Screening abstracts" }));
    state = reduceRunStreamFrame(state, tick({ stage: "classify", activity: "Classifying" }));
    state = reduceRunStreamFrame(
      state,
      tick({ stage: "screen", activity: "Screening abstracts", heartbeat: true, occurred_at: "2026-07-21T10:02:10Z" }),
    );
    expect(state.liveness.screen).toMatchObject({ heartbeat: true, occurredAt: "2026-07-21T10:02:10Z" });
    expect(state.liveness.classify).toMatchObject({ activity: "Classifying", heartbeat: false });
  });

  it("a stage-less tick lands under the global liveness key", () => {
    const withTick = reduceRunStreamFrame(
      createInitialRunStreamState(),
      tick({ stage: null, activity: "Warming up", occurred_at: "2026-07-21T10:00:00Z" }),
    );
    expect(withTick.liveness._global).toEqual({
      activity: "Warming up",
      heartbeat: false,
      dropped: 0,
      occurredAt: "2026-07-21T10:00:00Z",
    });
  });

  it("repeated ticks for the same stage overwrite (last tick wins), never accumulate", () => {
    let state = createInitialRunStreamState();
    state = reduceRunStreamFrame(state, tick({ stage: "extract", activity: "First" }));
    state = reduceRunStreamFrame(state, tick({ stage: "extract", activity: "Second" }));
    expect(Object.keys(state.liveness)).toEqual(["extract"]);
    expect(state.liveness.extract.activity).toBe("Second");
  });
});

describe("reduceRunStreamFrame — stage lifecycle", () => {
  it("stage.completed updates the matching started entry in place rather than appending", () => {
    const started = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "stage.started", capability_run_id: null,
      stage: "screen",
      label: "Screening",
      blurb: "Applying inclusion criteria.",
      occurred_at: "2026-07-21T10:00:00Z",
      sequence: 1,
    });
    const completed = reduceRunStreamFrame(started, {
      type: "stage.completed", capability_run_id: null,
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
      startedAt: "2026-07-21T10:00:00Z",
    });
  });

  it("records startedAt from stage.started and keeps it through completion and failure (task 058, N5)", () => {
    let state = fold(createInitialRunStreamState(), [
      {
        type: "stage.started", capability_run_id: null,
        stage: "acquire", label: "Searching", blurb: "",
        occurred_at: "2026-07-21T10:00:00Z", sequence: 1,
      },
      {
        type: "stage.started", capability_run_id: null,
        stage: "screen", label: "Screening", blurb: "",
        occurred_at: "2026-07-21T10:01:00Z", sequence: 2,
      },
    ]);
    expect(state.stages.map((entry) => entry.startedAt)).toEqual([
      "2026-07-21T10:00:00Z",
      "2026-07-21T10:01:00Z",
    ]);
    state = fold(state, [
      {
        type: "stage.completed", capability_run_id: null,
        stage: "acquire", label: "Searching", summary: {}, seconds: 64,
        occurred_at: "2026-07-21T10:01:04Z", sequence: 3,
      },
      {
        type: "stage.failed", capability_run_id: null,
        stage: "screen", label: "Screening", reason: "boom", skipped: false,
        occurred_at: "2026-07-21T10:02:00Z", sequence: 4,
      },
    ]);
    expect(state.stages.map((entry) => [entry.status, entry.startedAt])).toEqual([
      ["completed", "2026-07-21T10:00:00Z"],
      ["failed", "2026-07-21T10:01:00Z"],
    ]);
  });

  it("a completion with no started entry dates its start back by its seconds", () => {
    const state = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "stage.completed", capability_run_id: null,
      stage: "group", label: "Grouping", summary: {}, seconds: 30,
      occurred_at: "2026-07-21T10:00:30Z", sequence: 1,
    });
    expect(state.stages[0].startedAt).toBe("2026-07-21T10:00:00.000Z");
  });

  it("stage.failed with skipped=true records status skipped and carries the reason", () => {
    const started = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "stage.started", capability_run_id: null,
      stage: "group",
      label: "Grouping",
      blurb: "Clustering findings.",
      occurred_at: "2026-07-21T10:00:00Z",
      sequence: 1,
    });
    const skipped = reduceRunStreamFrame(started, {
      type: "stage.failed", capability_run_id: null,
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

describe("reduceRunStreamFrame — task.updated partial merge", () => {
  it("merges only the fields the event actually touched", () => {
    let state = createInitialRunStreamState();
    state = reduceRunStreamFrame(state, {
      type: "task.updated",
      name: "Original name",
      question: "Original question",
      status: "active",
      occurred_at: "2026-07-21T09:00:00Z",
      sequence: 1,
    });
    // A rename-only event: question/status are `null` (not touched), not cleared.
    state = reduceRunStreamFrame(state, {
      type: "task.updated",
      name: "Renamed",
      question: null,
      status: null,
      occurred_at: "2026-07-21T09:05:00Z",
      sequence: 2,
    });

    expect(state.task).toEqual({
      name: "Renamed",
      question: "Original question",
      status: "active",
    });
  });
});

// Task 045 (S12): a longlist walk's option searches publish on the same task
// stream; they never become the live run.
describe("reduceRunStreamFrame — child walks", () => {
  it("records a child's status without switching the live run or its stages", () => {
    const CHILD_ID = "44444444-4444-4444-4444-444444444444";
    let state = createInitialRunStreamState();
    state = reduceRunStreamFrame(state, {
      type: "run.status",
      capability_run_id: TASK_RUN_ID,
      status: "running",
      occurred_at: "2026-09-22T10:00:00Z",
      sequence: 1,
    });
    state = reduceRunStreamFrame(state, {
      type: "stage.started", capability_run_id: null,
      stage: "suggest",
      label: "Suggesting options",
      blurb: "",
      occurred_at: "2026-09-22T10:00:01Z",
      sequence: 2,
    });
    for (const [status, sequence] of [["running", 3], ["succeeded", 4]] as const) {
      state = reduceRunStreamFrame(state, {
        type: "run.status",
        capability_run_id: CHILD_ID,
        status,
        occurred_at: "2026-09-22T10:00:02Z",
        sequence,
      });
    }
    expect(state.run?.id).toBe(TASK_RUN_ID);
    expect(state.run?.status).toBe("running");
    expect(state.stages).toHaveLength(1);
    expect(state.runs[CHILD_ID]).toBe("succeeded");
  });

  // A3: a child's stage frames name the child; they stay off the walk's timeline.
  it("drops a stage frame that names a different run than the tracked one", () => {
    const CHILD_ID = "44444444-4444-4444-4444-444444444444";
    let state = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "run.status",
      capability_run_id: TASK_RUN_ID,
      status: "running",
      occurred_at: "2026-09-22T10:00:00Z",
      sequence: 1,
    });
    state = reduceRunStreamFrame(state, {
      type: "stage.started",
      capability_run_id: CHILD_ID,
      stage: "acquire",
      label: "Searching",
      blurb: "",
      occurred_at: "2026-09-22T10:00:01Z",
      sequence: 2,
    });
    state = reduceRunStreamFrame(state, {
      type: "stage.started",
      capability_run_id: TASK_RUN_ID,
      stage: "suggest",
      label: "Suggesting options",
      blurb: "",
      occurred_at: "2026-09-22T10:00:02Z",
      sequence: 3,
    });
    expect(state.stages.map((entry) => entry.stage)).toEqual(["suggest"]);
    expect(state.lastSequence).toBe(3);
  });

  // Round 11 (owner: "Searching for each option" and "Searching" both live).
  // The order a page load mid-walk replays, taken from the owner's live run
  // (2026-11-06): the longlist walk dispatches its option searches, then runs
  // its own broad search while they run, and joins them before screening.
  // The two live rows are both the walk's; the children's searches stay out.
  it("replays a longlist walk mid-search: its own search beside its option searches, no child rows", () => {
    const BASELINE_RUN_ID = "5e284cf5-0000-4000-8000-000000000000";
    const WALK = "fe6cd29c-e072-4e52-b518-f80c6476ffe2";
    const CHILD_A = "74e8be1a-0000-4000-8000-000000000001";
    const CHILD_B = "eb7d0890-0000-4000-8000-000000000002";
    const at = "2026-11-06T09:10:00Z";
    const started = (stage: StageEntry["stage"], sequence: number, runId: string | null): SseFrame => ({
      type: "stage.started",
      capability_run_id: runId,
      stage,
      label: stage,
      blurb: "",
      occurred_at: at,
      sequence,
    });
    const status = (runId: string, value: "running" | "succeeded", sequence: number): SseFrame => ({
      type: "run.status",
      capability_run_id: runId,
      status: value,
      occurred_at: at,
      sequence,
    });
    const replay: SseFrame[] = [
      status(BASELINE_RUN_ID, "running", 2),
      started("acquire", 3, BASELINE_RUN_ID),
      status(BASELINE_RUN_ID, "succeeded", 194),
      status(WALK, "running", 195),
      started("inherit", 196, WALK),
      started("suggest", 202, WALK),
      status(CHILD_A, "running", 208),
      status(CHILD_B, "running", 209),
      started("acquire", 210, CHILD_B),
      started("acquire", 213, CHILD_A),
      started("option_searches", 235, WALK),
      started("acquire", 246, WALK),
    ];
    const state = fold(createInitialRunStreamState(), replay);
    expect(state.run?.id).toBe(WALK);
    expect(state.childRunIds).toEqual([CHILD_A, CHILD_B]);
    expect(state.stages.map((entry) => entry.stage)).toEqual(["inherit", "suggest", "option_searches", "acquire"]);
    // The walk-level row before round 11 named no walk; it still applies.
    const unnamed = fold(createInitialRunStreamState(), [...replay.slice(0, 10), started("option_searches", 235, null)]);
    expect(unnamed.stages.map((entry) => entry.stage)).toEqual(["inherit", "suggest", "option_searches"]);
  });

  // Round 11: a child's tick names the child; it never lands on the walk's
  // own Searching row or the run status bar.
  it("drops a tick that names a different run than the tracked one", () => {
    const CHILD_ID = "44444444-4444-4444-4444-444444444444";
    const tick = (activity: string, runId: string | null): SseFrame => ({
      type: "tick",
      ephemeral: true,
      stage: "acquire",
      activity,
      done: null,
      total: null,
      unit: null,
      section: null,
      heartbeat: false,
      dropped: 0,
      capability_run_id: runId,
      occurred_at: "2026-09-22T10:00:02Z",
    });
    let state = reduceRunStreamFrame(createInitialRunStreamState(), {
      type: "run.status",
      capability_run_id: TASK_RUN_ID,
      status: "running",
      occurred_at: "2026-09-22T10:00:00Z",
      sequence: 1,
    });
    state = reduceRunStreamFrame(state, tick("the walk's search", TASK_RUN_ID));
    state = reduceRunStreamFrame(state, tick("an option's search", CHILD_ID));
    expect(state.liveness.acquire?.activity).toBe("the walk's search");
    // A tick that names no walk (an older server) still applies.
    state = reduceRunStreamFrame(state, tick("unnamed", null));
    expect(state.liveness.acquire?.activity).toBe("unnamed");
  });

  // A9: a child's late terminal frame, after the walk has finished, must not
  // replace the walk as the tracked run.
  it("keeps the finished walk when a child's run.finished arrives late", () => {
    const CHILD_ID = "44444444-4444-4444-4444-444444444444";
    const frames: SseFrame[] = [
      { type: "run.status", capability_run_id: TASK_RUN_ID, status: "running", occurred_at: "2026-09-22T10:00:00Z", sequence: 1 },
      { type: "run.status", capability_run_id: CHILD_ID, status: "running", occurred_at: "2026-09-22T10:00:01Z", sequence: 2 },
      { type: "run.status", capability_run_id: TASK_RUN_ID, status: "succeeded", occurred_at: "2026-09-22T10:05:00Z", sequence: 3 },
      { type: "run.status", capability_run_id: CHILD_ID, status: "interrupted", occurred_at: "2026-09-22T10:05:01Z", sequence: 4 },
    ];
    const state = frames.reduce(reduceRunStreamFrame, createInitialRunStreamState());
    expect(state.run?.id).toBe(TASK_RUN_ID);
    expect(state.run?.status).toBe("succeeded");
    expect(state.runs[CHILD_ID]).toBe("interrupted");
  });
});

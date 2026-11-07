import type { SseFrame } from "../api/sseFrame";
import {
  GLOBAL_LIVENESS_KEY,
  type LiveSearchQuery,
  type LiveSection,
  type LiveSource,
  type LiveSourceNote,
  type ResolvedDecision,
  type RunStreamState,
  type StageEntry,
  type StageLiveness,
} from "./types";

/**
 * Pure reducer over the SSE frame stream — no framework, no side effects.
 *
 * Replay-idempotent: every frame except `tick` carries a `sequence`. A
 * frame with `sequence < state.lastSequence` is a stale re-delivery and is
 * dropped unchanged. One durable event can emit more than one frame
 * *type* at the same sequence (e.g. `checkin.resolved` + `plan.updated`
 * from one steering decision) — those must each apply once, so a frame
 * with `sequence === state.lastSequence` is dropped only if its `type` is
 * already recorded in `appliedTypesAtLastSequence` for that sequence.
 * That set resets whenever the sequence actually advances. Together this
 * makes folding the same frame stream twice, or resuming the fold from
 * any mid-stream cursor (however the redelivery is sliced), produce the
 * same final state. The nine ephemeral frame types are the deliberate
 * exception: they carry no `sequence` at all and never advance
 * `lastSequence`. `tick` updates only the transient `liveness` slice;
 * `artefact.section_delta` and `artefact.section_revising` update only a
 * section's `draft` and `revising` (task 058, N7);
 * `artefact.section_sources` and `artefact.section_claim` update only its
 * `sources` and `claims` (task 058, evidence shown live);
 * `artefact.section_card` appends to its `cards` (task 058, round 7);
 * `artefact.source_note` adds to the run's `liveSourceNotes`, one per source
 * (round 8); `search.query` adds or updates a row of `liveSearchQueries` and
 * `characterise.themes` sets `liveThemes`, `liveOptions` or
 * `liveOptionThemes` by its `stage` (rounds 9 and 11). A replay carries none of them, so folding a replay rebuilds
 * `prose` and `citations` alone.
 */
/** Task 045 (A3): a stage frame names its walk; one from a different walk
 *  than the tracked run (a longlist walk's option search) is not this
 *  timeline's. A frame without a run id (older events) still applies. Ticks
 *  name their walk too (round 11). */
export function isOtherRunsStage(state: RunStreamState, runId: string | null): boolean {
  return runId !== null && state.run !== null && runId !== state.run.id;
}

export function reduceRunStreamFrame(state: RunStreamState, frame: SseFrame): RunStreamState {
  if (frame.type === "tick") {
    // A tick names its walk (round 11): a longlist walk's option searches run
    // `acquire` too, and their lines are not the tracked walk's.
    if (isOtherRunsStage(state, frame.capability_run_id ?? null)) return state;
    const key = frame.stage ?? GLOBAL_LIVENESS_KEY;
    const entry: StageLiveness = {
      activity: frame.activity,
      heartbeat: frame.heartbeat,
      dropped: frame.dropped,
      occurredAt: frame.occurred_at,
    };
    // Null on the wire means "no such value for this tick"; leave it out.
    if (frame.done !== null) entry.done = frame.done;
    if (frame.total !== null) entry.total = frame.total;
    if (frame.unit !== null) entry.unit = frame.unit;
    if (frame.section !== null) entry.section = frame.section;
    return { ...state, liveness: { ...state.liveness, [key]: entry } };
  }

  if (frame.type === "artefact.section_delta") {
    const section = state.liveSections[frame.index];
    if (section === undefined) {
      // No skeleton yet: hold the text until the skeleton arrives.
      const held = state.pendingDrafts[frame.index] ?? "";
      return {
        ...state,
        pendingDrafts: {
          ...state.pendingDrafts,
          [frame.index]: frame.mode === "append" ? held + frame.text : frame.text,
        },
      };
    }
    // A completed section's prose is the record; a late delta never
    // reopens it.
    if (section.state === "filled") return state;
    const draft = frame.mode === "append" ? (section.draft ?? "") + frame.text : frame.text;
    const next: LiveSection = { ...section, draft };
    // A replaced draft is new text: citations bound to the old one, and
    // cards from the old reply, go.
    if (frame.mode === "replace") {
      delete next.claims;
      delete next.cards;
    }
    return {
      ...state,
      liveSections: { ...state.liveSections, [frame.index]: next },
    };
  }

  if (frame.type === "artefact.section_sources") {
    const section = state.liveSections[frame.index];
    if (section === undefined || section.state === "filled") return state;
    return {
      ...state,
      liveSections: {
        ...state.liveSections,
        [frame.index]: { ...section, sources: liveSources(frame.sources) },
      },
    };
  }

  if (frame.type === "artefact.section_claim") {
    const section = state.liveSections[frame.index];
    if (section === undefined || section.state === "filled") return state;
    const claim = { start: frame.start, end: frame.end, sources: liveSources(frame.sources) };
    return {
      ...state,
      liveSections: {
        ...state.liveSections,
        [frame.index]: { ...section, claims: [...(section.claims ?? []), claim] },
      },
    };
  }

  if (frame.type === "artefact.section_card") {
    const section = state.liveSections[frame.index];
    if (section === undefined || section.state === "filled") return state;
    const card = { title: frame.title, prose: frame.prose };
    return {
      ...state,
      liveSections: {
        ...state.liveSections,
        [frame.index]: { ...section, cards: [...(section.cards ?? []), card] },
      },
    };
  }

  if (frame.type === "artefact.source_note") {
    // One note per source, in the order written: a reconnect's snapshot
    // sends the notes again, and a repeat replaces rather than doubles.
    const note: LiveSourceNote = { sourceId: frame.source_id, title: frame.title, note: frame.note };
    const notes = state.liveSourceNotes ?? [];
    const at = notes.findIndex((existing) => existing.sourceId === note.sourceId);
    const next = at === -1 ? [...notes, note] : notes.map((existing, i) => (i === at ? note : existing));
    return { ...state, liveSourceNotes: next };
  }

  if (frame.type === "search.query") {
    // One row per (backend, query, kind), in the order first sent: the frame
    // sent when the query comes back updates its row, and a reconnect's
    // snapshot repeats rows rather than doubling them.
    const row: LiveSearchQuery = { backend: frame.backend, query: frame.query, kind: frame.kind, results: frame.results };
    const rows = state.liveSearchQueries ?? [];
    const at = rows.findIndex(
      (existing) => existing.backend === row.backend && existing.query === row.query && existing.kind === row.kind,
    );
    const next = at === -1 ? [...rows, row] : rows.map((existing, i) => (i === at ? row : existing));
    return { ...state, liveSearchQueries: next };
  }

  if (frame.type === "characterise.themes") {
    // One frame, three stages (round 11): the Evidence search's themes, the
    // longlist's options and the longlist's themes, each in its own slot.
    const names = frame.themes.map((theme) => ({ label: theme.label, description: theme.description }));
    const slot = frame.stage === "longlist" ? "liveOptions" : frame.stage === "theme" ? "liveOptionThemes" : "liveThemes";
    return { ...state, [slot]: names };
  }

  if (frame.type === "artefact.section_revising") {
    const section = state.liveSections[frame.index];
    if (section === undefined || section.state === "filled") return state;
    const revising = frame.spans.map(({ start, end }) => ({ start, end }));
    return {
      ...state,
      liveSections: { ...state.liveSections, [frame.index]: { ...section, revising } },
    };
  }

  if (frame.sequence < state.lastSequence) {
    return state; // a stale re-delivery — idempotent drop
  }
  if (frame.sequence === state.lastSequence && state.appliedTypesAtLastSequence.includes(frame.type)) {
    return state; // this exact frame type already applied at this sequence
  }

  const sequenceAdvanced = frame.sequence > state.lastSequence;
  const base: RunStreamState = {
    ...state,
    lastSequence: frame.sequence,
    appliedTypesAtLastSequence: sequenceAdvanced
      ? [frame.type]
      : [...state.appliedTypesAtLastSequence, frame.type],
  };

  switch (frame.type) {
    case "run.status": {
      // A `run.status(running)` for a different run than the one the store
      // currently tracks is a fresh walk — its timeline must not inherit
      // the previous (possibly interrupted) run's stage entries or liveness.
      const current = base.run;
      // Task 045 (S12): a longlist walk's option searches are child walks on
      // the same task stream. A different run's frame while the tracked walk
      // is still running or paused can only be such a child (the admission
      // fences never open a second parentless walk beside a live one), so it
      // is recorded but never becomes the live run.
      // Task 045 (A9): a child seen that way stays a child — its late
      // terminal frame, arriving after the walk itself has finished, must not
      // replace the walk as the tracked run.
      if (
        (current !== null &&
          current.id !== frame.capability_run_id &&
          (current.status === "running" || current.status === "paused")) ||
        base.childRunIds.includes(frame.capability_run_id)
      ) {
        return {
          ...base,
          runs: { ...base.runs, [frame.capability_run_id]: frame.status },
          childRunIds: base.childRunIds.includes(frame.capability_run_id)
            ? base.childRunIds
            : [...base.childRunIds, frame.capability_run_id],
        };
      }
      const isNewRun = frame.status === "running" && frame.capability_run_id !== current?.id;
      const sameRun = current !== null && current.id === frame.capability_run_id;
      const isTerminal =
        frame.status === "succeeded" ||
        frame.status === "failed" ||
        frame.status === "aborted" ||
        frame.status === "interrupted" ||
        frame.status === "degraded";
      const next: RunStreamState = {
        ...base,
        run: {
          id: frame.capability_run_id,
          status: frame.status,
          startedAt: sameRun ? current.startedAt : frame.occurred_at,
          ...(isTerminal
            ? { endedAt: frame.occurred_at }
            : sameRun && current.endedAt !== undefined
              ? { endedAt: current.endedAt }
              : {}),
        },
        runs: { ...base.runs, [frame.capability_run_id]: frame.status },
        stages: isNewRun ? [] : base.stages,
        liveness: isNewRun ? {} : base.liveness,
        liveSections: isNewRun ? {} : base.liveSections,
        pendingDrafts: isNewRun ? {} : base.pendingDrafts,
      };
      // A new run's notes, queries and themes start empty (task 058, rounds
      // 8 and 9).
      if (isNewRun) {
        delete next.liveSourceNotes;
        delete next.liveSearchQueries;
        delete next.liveThemes;
        delete next.liveOptions;
        delete next.liveOptionThemes;
      }
      return next;
    }

    case "stage.started":
      if (isOtherRunsStage(base, frame.capability_run_id)) return base;
      return {
        ...base,
        stages: [
          ...base.stages,
          {
            stage: frame.stage,
            label: frame.label,
            status: "started",
            blurb: frame.blurb,
            startedAt: frame.occurred_at,
          },
        ],
      };

    case "stage.completed":
      if (isOtherRunsStage(base, frame.capability_run_id)) return base;
      return {
        ...base,
        stages: replaceStartedStage(
          base.stages,
          frame.stage,
          {
            stage: frame.stage,
            label: frame.label,
            status: "completed",
            summary: frame.summary,
            seconds: frame.seconds,
            counts: frame.counts,
          },
          frame.occurred_at,
        ),
      };

    case "stage.failed":
      // The pinned stage-entry shape (task 025 §4) has no `reason` field —
      // the failure reason travels in `summary` instead, the one bucket
      // already typed to hold an arbitrary string value.
      if (isOtherRunsStage(base, frame.capability_run_id)) return base;
      return {
        ...base,
        stages: replaceStartedStage(
          base.stages,
          frame.stage,
          {
            stage: frame.stage,
            label: frame.label,
            status: frame.skipped ? "skipped" : "failed",
            summary: { reason: frame.reason },
          },
          frame.occurred_at,
        ),
      };

    case "artefact.skeleton":
      // Drafts that streamed in before the skeleton (held in
      // `pendingDrafts`) are folded into their sections here.
      return {
        ...base,
        liveSections: Object.fromEntries(
          frame.sections.map((section) => {
            const held = base.pendingDrafts[section.index];
            const live: LiveSection = {
              index: section.index,
              title: section.title,
              focus: section.focus,
              role: section.role,
              state: "planned",
            };
            if (held !== undefined) live.draft = held;
            return [section.index, live];
          }),
        ),
        pendingDrafts: {},
      };

    case "artefact.section_started": {
      const section = base.liveSections[frame.index];
      // Frames name skeleton display indices. Do not manufacture a section
      // if a malformed/out-of-order stream lacks its skeleton.
      if (section === undefined) return base;
      return {
        ...base,
        liveSections: {
          ...base.liveSections,
          [frame.index]: { ...section, state: "writing" },
        },
      };
    }

    case "artefact.section_completed": {
      const section = base.liveSections[frame.index];
      if (section === undefined) return base;
      // An empty prose completion closes an optional section (notably key
      // findings). Removing it is honest: the view must hide, never fake.
      if (frame.prose.length === 0) {
        const remainingSections = { ...base.liveSections };
        delete remainingSections[frame.index];
        return { ...base, liveSections: remainingSections };
      }
      const settled: LiveSection = { ...section };
      delete settled.draft;
      delete settled.revising;
      delete settled.sources;
      delete settled.claims;
      delete settled.cards;
      // The checked citations stay until the committed report replaces the
      // live view (task 058, round 7). A section with none carries none.
      delete settled.citations;
      delete settled.checkedClaims;
      if (frame.claims !== undefined && frame.claims.length > 0) {
        // Round 13: the checker's verdict, per claim.
        settled.checkedClaims = frame.claims.map((claim) => ({
          claimId: claim.claim_id ?? null,
          start: claim.start,
          end: claim.end,
          tier: claim.tier ?? null,
          rationale: claim.rationale ?? null,
        }));
      }
      if (frame.citations !== undefined && frame.citations.length > 0) {
        settled.citations = frame.citations.map((citation) => ({
          start: citation.start,
          end: citation.end,
          n: citation.n,
          sourceId: citation.source_id,
          title: citation.title,
          // Round 8: absent on a frame recorded before the fields existed.
          citationId: citation.citation_id ?? null,
          claimId: citation.claim_id ?? null,
          quote: citation.quote ?? "",
        }));
      }
      return {
        ...base,
        liveSections: {
          ...base.liveSections,
          [frame.index]: {
            ...settled,
            title: frame.title,
            prose: frame.prose,
            state: "filled",
          },
        },
      };
    }

    case "checkin.pending":
      return { ...base, pendingCheckIn: frame.check_in };

    case "checkin.resolved": {
      const decision: ResolvedDecision = {
        checkInId: frame.check_in_id,
        response: frame.response,
        decidedBy: frame.decided_by,
        occurredAt: frame.occurred_at,
        sequence: frame.sequence,
      };
      const clearsPending = base.pendingCheckIn?.check_in_id === frame.check_in_id;
      return {
        ...base,
        pendingCheckIn: clearsPending ? null : base.pendingCheckIn,
        decisions: [...base.decisions, decision],
      };
    }

    case "plan.updated":
      return { ...base, plan: { version: frame.version, plan: frame.plan } };

    case "task.updated":
      // `null` on the wire means "not touched by this event" — preserve
      // whatever the store already had for a field this event didn't set.
      return {
        ...base,
        task: {
          name: frame.name ?? base.task.name,
          question: frame.question ?? base.task.question,
          status: frame.status ?? base.task.status,
        },
      };

    default:
      return assertNever(frame);
  }
}

/** The wire's `{source_id, title}` pairs as the store keeps them. */
function liveSources(sources: readonly { source_id: string; title: string }[]): LiveSource[] {
  return sources.map(({ source_id, title }) => ({ sourceId: source_id, title }));
}

/**
 * Report whether live presentation sections must be labelled as an
 * incomplete draft after a terminal run outcome.
 *
 * Args:
 *   state: Current stream state.
 *
 * Returns:
 *   True only for failed, aborted, or interrupted runs retaining at least
 *   one streamed section. Sections deliberately remain available for view
 *   rendering beneath the terminal-honesty banner.
 */
export function hasTerminalPartialLiveArtefact(state: RunStreamState): boolean {
  return (
    state.run !== null &&
    ["failed", "aborted", "interrupted"].includes(state.run.status) &&
    Object.keys(state.liveSections).length > 0
  );
}

/** Find the most recent `started` entry for `stage` and replace it in
 *  place, keeping its `startedAt`; append instead if none is found
 *  (defensive — shouldn't happen given the server's start-before-terminal
 *  ordering), dating the start back by `seconds` when the frame has them. */
function replaceStartedStage(
  stages: StageEntry[],
  stage: StageEntry["stage"],
  replacement: Omit<StageEntry, "startedAt">,
  occurredAt: string,
): StageEntry[] {
  for (let index = stages.length - 1; index >= 0; index--) {
    if (stages[index].stage === stage && stages[index].status === "started") {
      const next = stages.slice();
      next[index] = { ...replacement, startedAt: stages[index].startedAt };
      return next;
    }
  }
  return [...stages, { ...replacement, startedAt: fallbackStartedAt(occurredAt, replacement.seconds) }];
}

function fallbackStartedAt(occurredAt: string, seconds: number | null | undefined): string {
  const ended = Date.parse(occurredAt);
  if (typeof seconds !== "number" || Number.isNaN(ended)) return occurredAt;
  return new Date(ended - seconds * 1000).toISOString();
}

function assertNever(value: never): never {
  throw new Error(`Unhandled SSE frame type: ${JSON.stringify(value)}`);
}

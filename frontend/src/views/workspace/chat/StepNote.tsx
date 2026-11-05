import { useEffect, useRef, useState } from "react";

import { STALL_AFTER_MS, useFreshness } from "../../../lib/freshness";
import { scrub } from "../../../lib/scrub";
import type { RunStreamState } from "../../../store";
import { StatusMark } from "../../../ui/brand/Card";
import { FinishedLine, type RowContext } from "../RunTrace";
import { cardRows, currentRow, rowDetail, rowLiveness, traceWords, walkKind, type CardRow } from "../runProgress";

/** How long a step note holds before it retracts (owner, round 6: "about 6 s"). */
export const STEP_NOTE_HOLD_MS = 6_000;

/** How long the retract takes; the note leaves the DOM after it. */
const STEP_NOTE_EXIT_MS = 160;

/** A step that finished this long before the rail mounted is history the
 *  stream replays on connect, not news: it gets no note. */
const STEP_NOTE_FRESH_MS = 60_000;

/** When a row's last stage finished, from its start and its seconds. */
function finishedAt(row: CardRow): number | null {
  const last = row.entries[row.entries.length - 1];
  if (last === undefined || typeof last.seconds !== "number") return null;
  const start = Date.parse(last.startedAt);
  return Number.isNaN(start) ? null : start + last.seconds * 1000;
}

type NoteTrack = {
  signature: string;
  noting: boolean;
  states: ReadonlyMap<string, CardRow["state"]>;
  noteKey: string | null;
};

/**
 * What the shut rail shows of a run (task 058, owner round 6): the trace
 * header's words for the Task Agent mark's tooltip and name, and the newest
 * plan step to have just finished, for the step note.
 *
 * Args:
 *   taskId: The task, for the note's link.
 *   stream: The task's run stream.
 *   capability: The task's capability, for the walk kind.
 *   isOwner: Only the owner is told a check-in waits on them.
 *   noting: True while the rail is on show (the sidebar shut); a step that
 *     finishes while it is not gets no note, now or later. Writing's finish
 *     never gets one.
 *
 * Returns:
 *   `words` (empty before the first frame), the note's `context`, the `note`
 *   row (or null) and `dismiss`.
 */
export function useRailRun(
  taskId: string,
  stream: RunStreamState,
  capability: string | null | undefined,
  isOwner: boolean,
  noting: boolean,
) {
  const status = stream.run?.status;
  const rows = cardRows(stream.stages, stream.plan?.plan, status);
  const row = currentRow(rows);
  const progress = row !== null && row.state === "progress" ? row : null;
  const tick = progress === null ? undefined : rowLiveness(progress, stream.liveness);
  const stamp = tick?.occurredAt ?? progress?.entries[0]?.startedAt;
  const quiet = !useFreshness(stamp, STALL_AFTER_MS);
  const paused = status === "paused" || stream.pendingCheckIn != null;
  const stalled = progress !== null && stamp !== undefined && quiet && !paused;
  const words = scrub(traceWords(row, rowDetail(tick), paused ? "paused" : stalled ? "stalled" : "live", isOwner));
  const kind = walkKind(capability, stream.stages, null);
  // A note is a finished row: its wall time does not read the clock. The
  // rail does not read the findings count either; the Findings link belongs
  // to a step no standard plan shows as a row.
  const context: RowContext = { rows, taskId, kind, hasFindings: false, nowMs: 0 };

  // The rows' states are followed as they change (state adjusted during
  // render): a row that turns done while the rail is on show is the note,
  // and a newer one replaces it; nothing stacks.
  const [mountedAt] = useState(() => Date.now());
  const signature = rows.map((candidate) => `${candidate.key}:${candidate.state}`).join("|");
  const [track, setTrack] = useState<NoteTrack>(() => ({
    signature,
    noting,
    states: new Map(rows.map((candidate) => [candidate.key, candidate.state])),
    noteKey: null,
  }));
  let noteKey = track.noteKey;
  if (track.signature !== signature || track.noting !== noting) {
    let landed: string | null = null;
    for (const candidate of rows) {
      const before = track.states.get(candidate.key);
      if (before === undefined || before === "done" || candidate.state !== "done") continue;
      const at = finishedAt(candidate);
      if (at !== null && at < mountedAt - STEP_NOTE_FRESH_MS) continue;
      // Writing's finish gets no note: the title marker, the tab mark and the
      // swap to the report already say it (lead, round 6).
      if (candidate.stages.includes("synthesise")) continue;
      landed = candidate.key;
    }
    noteKey = noting ? (landed ?? track.noteKey) : null;
    setTrack({
      signature,
      noting,
      states: new Map(rows.map((candidate) => [candidate.key, candidate.state])),
      noteKey,
    });
  }

  const note = noteKey === null ? null : (rows.find((candidate) => candidate.key === noteKey) ?? null);
  const dismiss = () => setTrack((current) => ({ ...current, noteKey: null }));
  return { words, context, note, dismiss };
}

type Timers = { current: number[] };

function clearTimers(timers: Timers): void {
  for (const id of timers.current) window.clearTimeout(id);
  timers.current = [];
}

/** Hold the note, then retract it and, once the retract has run, remove it;
 *  nothing while a pointer or focus holds it. */
function scheduleRetract(timers: Timers, held: { current: boolean }, retract: () => void, remove: () => void): void {
  clearTimers(timers);
  if (held.current) return;
  timers.current.push(
    window.setTimeout(() => {
      retract();
      timers.current.push(window.setTimeout(remove, STEP_NOTE_EXIT_MS));
    }, STEP_NOTE_HOLD_MS),
  );
}

/**
 * The step note (task 058, owner round 6; DESIGN.md § Overlays): when a plan
 * step finishes while the sidebar is shut, its one line (without the wall
 * time; lead, round 6) slides out from the
 * rail's Task Agent mark into the page, holds about six seconds and retracts
 * into the rail. A newer note replaces the one on show and holds afresh.
 * Pointer or keyboard focus on it holds it. No close control. Under reduced
 * motion it appears and goes without sliding.
 *
 * The live region is always in the DOM, so a screen reader hears each note.
 *
 * Args:
 *   row: The step that just finished, or null for none.
 *   context: What its link needs (`RowContext`).
 *   onDone: Called when the note has retracted.
 */
export function StepNote({
  row,
  context,
  onDone,
}: {
  row: CardRow | null;
  context: RowContext;
  onDone: () => void;
}) {
  const key = row?.key ?? null;
  // The retract runs on a timer; a new note (a new key) cancels it.
  const [leaving, setLeaving] = useState<string | null>(null);
  const held = useRef(false);
  const timers = useRef<number[]>([]);
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (key === null) return undefined;
    scheduleRetract(timers, held, () => setLeaving(key), () => done.current());
    return () => clearTimers(timers);
  }, [key]);

  const shown = key !== null && leaving !== key;
  const hold = () => {
    held.current = true;
    clearTimers(timers);
    setLeaving(null);
  };
  const release = () => {
    held.current = false;
    if (key !== null) scheduleRetract(timers, held, () => setLeaving(key), () => done.current());
  };

  return (
    <div
      role="status"
      aria-live="polite"
      // At the mark's height, just past the rail's edge (the rail is 48 px;
      // the mark's column is 32 px and centred).
      className="pointer-events-none absolute top-1/2 left-full z-30 ml-3 -translate-y-1/2"
    >
      {row !== null && (
        <div
          data-testid="step-note"
          data-shown={shown ? "true" : "false"}
          onPointerEnter={hold}
          onPointerLeave={release}
          onFocus={hold}
          onBlur={release}
          className="step-note pointer-events-auto flex w-max max-w-[min(34rem,calc(100vw-6rem))] items-start gap-2 border border-line-2 bg-paper px-3 py-2 text-meta text-grey shadow-[0_10px_30px_rgba(15,41,74,0.14)]"
        >
          <span className="flex h-[1lh] shrink-0 items-center">
            <StatusMark tone="complete" />
          </span>
          <p className="min-w-0">
            <FinishedLine row={row} context={context} withTime={false} />
          </p>
        </div>
      )}
    </div>
  );
}

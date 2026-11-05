import { useState } from "react";

import { Figures } from "../lib/figures";
import { useNow } from "../lib/freshness";
import { createInitialRunStreamState } from "../store";
import { LiveMark, StatusMark } from "../ui/brand/Card";
import { cn } from "../ui/brand/cn";
import { useMountedTraces, useTaskLive } from "./taskLive";
import { elapsedSeconds, formatElapsed } from "./workspace/runProgress";
import { useRunWords } from "./workspace/runWords";

/** A stream with no run, for the shell before the live layer is enabled. */
const NO_STREAM = createInitialRunStreamState();

/** A no-break space binds each "·" to the word before it, so a separator
 *  never starts a line (lead, 2026-11-05). */
function bound(text: string): string {
  return text.replaceAll(" · ", " · ");
}

type Shown = { words: string; paused: boolean; elapsed: string; key: string };

/**
 * The run strip (task 058, owner round 7: it returns, the step note having
 * gone): under the lifecycle tabs on every tab but Agent, while a run is live
 * or paused, and nowhere else. One line on paper over a hairline: the turning
 * fold mark (the orange square while a check-in waits), the trace header's
 * words in Meta grey, and the elapsed time at the end in tabular figures.
 * Status only: no link and no button (contract D8: the Agent tab and the
 * rail's mark are the routes to the agent). Long words truncate; the time
 * stays in view.
 *
 * It opens and closes over 200 ms on the strong ease-out, so the page eases
 * rather than jumps, and its words rise in when the step changes; both hold
 * still under reduced motion. Its live region is quiet while a run trace is
 * mounted (the sidebar's), so one change is announced once.
 */
export function RunStrip() {
  const live = useTaskLive();
  const stream = live?.stream ?? NO_STREAM;
  const run = stream.run;
  const ticking = run?.status === "running" || run?.status === "paused";
  const open = live !== null && live.tab !== null && live.tab !== "agent" && ticking;
  const nowMs = useNow(open);
  const { words, row, paused } = useRunWords(stream, live?.isOwner ?? false);
  const traces = useMountedTraces();

  const now: Shown | null =
    open && run !== null
      ? {
          words,
          paused,
          elapsed: formatElapsed(elapsedSeconds(run.startedAt, undefined, nowMs)),
          key: paused ? "paused" : (row?.key ?? "start"),
        }
      : null;
  // Kept as the strip closes, so it folds away with its last words.
  const [last, setLast] = useState<Shown | null>(now);
  if (now !== null && (last === null || now.words !== last.words || now.elapsed !== last.elapsed || now.key !== last.key)) {
    setLast(now);
  }
  const shown = now ?? last;

  return (
    <>
      <div
        data-testid="run-strip"
        data-open={open}
        aria-hidden={open ? undefined : true}
        className={cn(
          "grid shrink-0 transition-[grid-template-rows] duration-200 ease-[var(--ease-out-strong)] motion-reduce:transition-none",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="min-h-0 overflow-hidden">
          {shown !== null && (
            <div className="flex min-h-9 items-center gap-2 border-b border-line bg-paper px-6 py-2 text-meta text-grey max-md:px-4">
              <span className="flex size-3.5 shrink-0 items-center justify-center">
                {shown.paused ? <StatusMark tone="paused" /> : <LiveMark />}
              </span>
              <span key={shown.key} className="anim-rise min-w-0 flex-1 truncate">
                <Figures text={bound(shown.words)} />
              </span>
              <span className="shrink-0 whitespace-nowrap">
                <Figures text={shown.elapsed} />
              </span>
            </div>
          )}
        </div>
      </div>
      {/* The words for a screen reader, without the ticking clock; quiet
          while a run trace (the sidebar's) announces the same words. */}
      {traces === 0 && (
        <p role="status" aria-live="polite" className="sr-only">
          {open ? words : ""}
        </p>
      )}
    </>
  );
}

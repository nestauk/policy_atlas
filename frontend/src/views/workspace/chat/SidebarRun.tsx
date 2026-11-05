import { useEffect, useRef } from "react";

import { useFreshness, useNow } from "../../../lib/freshness";
import { scrub } from "../../../lib/scrub";
import type { RunStreamState, StageEntry } from "../../../store";
import { cn } from "../../../ui/brand/cn";
import { CheckInCard } from "../CheckInCard";
import { elapsedSeconds, formatElapsed } from "../runProgress";
import { Composer, taskAgentComposerPlaceholder } from "../TaskAgentPane";

/** The stage the run is in now: the latest one started and not yet done. */
function currentStage(stages: StageEntry[]): StageEntry | undefined {
  return [...stages].reverse().find((stage) => stage.status === "started");
}

/** The check-in's place in the run, in the stage's own words:
 *  "check-in after searching and screening". Null when the stream has no
 *  label for its stage yet. */
export function checkInPlace(stage: string | null | undefined, stages: StageEntry[]): string | null {
  if (stage == null) return null;
  const label = [...stages].reverse().find((entry) => entry.stage === stage)?.label;
  return label === undefined ? null : `check-in after ${label.toLowerCase()}`;
}

/**
 * The Task Agent in the sidebar while a run is live (task 058, N13; annex
 * scene 13): the same agent as the Agent tab, folded to a column.
 *
 * Top to bottom: a compact run line (dot, the current row and the elapsed
 * time; orange and paused while a check-in waits), the thread tail (the
 * card's current row with its activity line), the pending check-in,
 * answerable here, and the composer locked with the Agent tab's own
 * placeholder. Opening the panel while a check-in waits lands on it; the
 * card glows once as it mounts.
 *
 * Args:
 *   taskId: The task the run belongs to.
 *   stream: The task's one run stream (`useRunStream`).
 *   isOwner: Steering is owner-only; a colleague sees no check-in card.
 */
export function SidebarRun({
  taskId,
  stream,
  isOwner,
}: {
  taskId: string;
  stream: RunStreamState;
  isOwner: boolean;
}) {
  const status = stream.run?.status;
  const pending = stream.pendingCheckIn;
  const paused = status === "paused" || pending !== null;
  const stage = currentStage(stream.stages);
  const liveness = stage === undefined ? undefined : stream.liveness[stage.stage];
  const breathing = useFreshness(paused ? undefined : liveness?.occurredAt);
  const nowMs = useNow(status === "running" || status === "paused");
  const elapsed = formatElapsed(elapsedSeconds(stream.run?.startedAt, stream.run?.endedAt, nowMs));
  const rowLabel = stage?.label ?? stream.stages.at(-1)?.label ?? null;
  const place = pending === null ? null : checkInPlace(pending.stage ?? pending.component, stream.stages);

  const checkInRef = useRef<HTMLDivElement>(null);
  const pendingId = pending?.check_in_id ?? null;
  useEffect(() => {
    if (pendingId === null) return;
    checkInRef.current?.scrollIntoView?.({ block: "start" });
  }, [pendingId]);

  // Only the clock takes tabular figures: Averta's tabular set also widens
  // its spaces and hyphens, which spreads the words apart.
  const runLine = paused
    ? place === null
      ? "Paused · a check-in is waiting on you"
      : `Paused · ${place}`
    : rowLabel === null
      ? null
      : `${rowLabel} · `;

  return (
    <section aria-label="Task Agent run" className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 [scrollbar-gutter:stable]">
        <p
          role="status"
          data-testid="sidebar-run-line"
          className="flex items-center gap-2 text-meta text-ink"
        >
          <span
            aria-hidden="true"
            data-testid="sidebar-run-dot"
            className={cn(
              "inline-block size-2 flex-none rounded-full",
              paused ? "bg-orange" : "bg-yellow",
              !paused && breathing && "anim-breathe",
            )}
          />
          <span>
            {runLine}
            {!paused && <span className="tabular-nums">{elapsed}</span>}
          </span>
        </p>

        {!paused && stage !== undefined && (
          <div data-testid="sidebar-thread-tail" className="mt-4 border-t border-line pt-4">
            {/* The run line above already names the row; the tail is the activity only. */}
            {liveness !== undefined && liveness.activity !== "" ? (
              <p className="text-meta text-grey">{scrub(liveness.activity)}</p>
            ) : (
              <p className="text-body font-semibold text-navy">{scrub(stage.label)}</p>
            )}
          </div>
        )}

        {pending !== null && (
          <div ref={checkInRef} data-testid="sidebar-check-in" className="mt-4 scroll-mt-4">
            <CheckInCard
              key={pending.check_in_id}
              taskId={taskId}
              checkIn={pending}
              stages={stream.stages}
              isOwner={isOwner}
              compact
            />
          </div>
        )}
      </div>
      <div className="shrink-0 border-t border-line px-3 py-3">
        <Composer
          id="sidebar-task-agent-message"
          value=""
          onChange={() => {}}
          onSubmit={() => {}}
          placeholder={taskAgentComposerPlaceholder(status, false, isOwner)}
          disabled
          sendDisabled
        />
      </div>
    </section>
  );
}

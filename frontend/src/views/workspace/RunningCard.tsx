import { Link } from "react-router";

import { Figures } from "../../lib/figures";
import { STALL_AFTER_MS, useFreshness, useNow } from "../../lib/freshness";
import { scrub } from "../../lib/scrub";
import type { PlanDraft, RunStatus, StageEntry, StageLiveness } from "../../store";
import { Card, StatusDot } from "../../ui/brand/Card";
import { cn } from "../../ui/brand/cn";
import {
  CHAT_PRIMARY_CTA_CLASS,
  cardRows,
  collapsedStatusLine,
  elapsedSeconds,
  formatElapsed,
  resultsSignpost,
  rowCounts,
  rowLink,
  rowLiveness,
  rowSeconds,
  runningCardCopy,
  walkKind,
  type CardRow,
  type WalkKind,
} from "./runProgress";

/** The words a stalled step reads after two minutes of silence (N5). */
const STALLED_LINE = "Still working on this step";

const TOP_DOT = {
  running: "running",
  paused: "paused",
  done: "complete",
  stopped: "failed",
} as const;

/** Quiet grey text control (Minimise, Expand): a link in look, a button in kind. */
const QUIET_CONTROL_CLASS =
  "shrink-0 cursor-pointer text-meta font-semibold text-grey underline decoration-line-2 underline-offset-[3px] hover:text-navy hover:decoration-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue";

/** Screen-reader word for the colour of a row's mark. */
const STATE_WORD: Record<CardRow["state"], string> = {
  done: "done",
  progress: "in progress",
  upcoming: "to come",
  failed: "stopped",
  skipped: "skipped",
};

/** Where a row's mark sits on the spine: the middle of its first line. */
const MARK_TOP: Record<CardRow["state"], string> = {
  done: "top-[18px]",
  failed: "top-[18px]",
  skipped: "top-[18px]",
  progress: "top-[18px] sm:top-[20px]",
  upcoming: "top-[14px]",
};

function SpineMark({ row, paused, fresh }: { row: CardRow; paused: boolean; fresh: boolean }) {
  const place = cn("absolute left-0 z-10", MARK_TOP[row.state]);
  if (row.state === "upcoming" || row.state === "skipped") {
    return (
      <span
        aria-hidden="true"
        className={cn(place, "size-2 rounded-full bg-paper shadow-[inset_0_0_0_1px_var(--color-line-2)]")}
      />
    );
  }
  const tone =
    row.state === "done" ? "complete" : row.state === "failed" ? "failed" : paused ? "paused" : "running";
  return <StatusDot tone={tone} className={cn(place, row.state === "progress" && fresh && !paused && "anim-breathe")} />;
}

function SpineRow({
  row,
  rows,
  index,
  taskId,
  kind,
  hasFindings,
  liveness,
  paused,
  nowMs,
}: {
  row: CardRow;
  rows: CardRow[];
  index: number;
  taskId: string;
  kind: WalkKind;
  hasFindings: boolean;
  liveness?: Record<string, StageLiveness>;
  paused: boolean;
  nowMs: number;
}) {
  const progress = row.state === "progress";
  const tick = progress ? rowLiveness(row, liveness) : undefined;
  const fresh = useFreshness(tick?.occurredAt);
  // Silence is measured from the last tick, or from the step's start when
  // none has come yet; a paused run is waiting on a person, not stalled.
  const stalled = !useFreshness(tick?.occurredAt ?? row.entries[0]?.startedAt, STALL_AFTER_MS) && !paused;
  const seconds = row.state === "upcoming" ? null : rowSeconds(row, nowMs);
  const time = seconds === null ? null : formatElapsed(seconds);
  const link = rowLink(row, rows, taskId, kind, hasFindings);
  const counts =
    row.state === "done" ? rowCounts(row) : row.state === "failed" ? ["Stopped"] : row.state === "skipped" ? ["Skipped"] : [];
  const meta = [...counts, ...(time !== null ? [time] : [])].join(" · ");
  const section = progress && !stalled ? tick?.section?.trim() : undefined;
  const activity = progress ? (stalled ? STALLED_LINE : tick?.activity.trim()) : undefined;
  const first = index === 0;
  const last = index === rows.length - 1;

  return (
    <li className="relative pl-[26px]">
      {/* The spine: a hairline from the first mark to the last. */}
      {!(first && last) && (
        <span
          aria-hidden="true"
          className={cn(
            "absolute left-[3.5px] w-px bg-line-2",
            first ? MARK_TOP[row.state] : "top-0",
            last ? (row.state === "upcoming" ? "h-[14px]" : "h-[20px]") : "bottom-0",
          )}
        />
      )}
      <SpineMark row={row} paused={paused} fresh={fresh} />
      <div
        className={cn(
          "grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-6 sm:grid-cols-[minmax(0,1fr)_auto_5.5rem]",
          row.state === "upcoming" ? "py-1.5" : "py-2.5",
        )}
      >
        {/* On a phone a done row's counts drop under its label, beside the
            link; the step in progress keeps its clock on the label's line,
            so the label, then what it is doing, read as one block. */}
        <span
          className={cn(
            "min-w-0",
            !progress && "col-span-2 sm:col-span-1",
            progress ? "text-lead font-semibold text-navy max-sm:text-body" : "text-body",
            row.state === "upcoming" ? "text-grey" : "text-navy",
          )}
        >
          {scrub(row.label)}
          <span className="sr-only">, {STATE_WORD[row.state]}</span>
        </span>
        {row.state !== "upcoming" && (
          <span className={cn("text-meta text-grey", progress ? "text-right" : "sm:text-right")}>
            <Figures text={meta} />
          </span>
        )}
        {row.state !== "upcoming" && (link !== null || !progress) && (
          <span className="text-right text-meta">
            {link !== null && (
              <Link
                to={link.href}
                className="font-semibold whitespace-nowrap text-blue no-underline hover:underline"
              >
                {link.label} →
              </Link>
            )}
          </span>
        )}
      </div>
      {progress && (section || activity) && (
        <div className="-mt-1.5 pb-3">
          {section && <p className="text-body text-navy">{scrub(section)}</p>}
          {activity && (
            <p className="text-meta text-grey">
              <Figures text={scrub(activity)} />
            </p>
          )}
        </div>
      )}
    </li>
  );
}

/**
 * The running card in the Agent tab (task 058, D5, direction C): a paper
 * card whose top line carries the run's state, its elapsed time and
 * Minimise, over a spine of one row per plan step. Done rows show their
 * counts, wall time and link; the step in progress shows what the model is
 * doing now; steps to come show their names. Every label is the server's.
 */
export function RunningCard({
  taskId,
  status,
  stages,
  plan,
  startedAt,
  endedAt,
  hasFindings,
  minimised,
  onMinimisedChange,
  onSeePlan,
  capability,
  purpose,
  liveness,
}: {
  taskId: string;
  status: RunStatus | undefined;
  stages: StageEntry[];
  /** The latest tick per stage: the in-progress row's activity line. */
  liveness?: Record<string, StageLiveness>;
  /** The task's capability — the card's words follow the walk kind (task 045). */
  capability?: string | null;
  /** The run's own purpose (`RunOut.purpose`) — an added option's search
   *  reads as its own kind, not the baseline (task 045, A7). */
  purpose?: string | null;
  plan: PlanDraft | null | undefined;
  startedAt?: string;
  endedAt?: string;
  hasFindings: boolean;
  minimised: boolean;
  onMinimisedChange: (minimised: boolean) => void;
  /** Opens the plan document (owner, polish round 2: the plan's link lives on
   *  the card, not in the task nav). */
  onSeePlan?: () => void;
}) {
  const kind = walkKind(capability, stages, purpose);
  const { eyebrow, tone } = runningCardCopy(status, kind);
  const rows = cardRows(stages, plan, status);
  const ticking = status === "running" || status === "paused";
  const nowMs = useNow(ticking);
  const elapsedLabel = formatElapsed(elapsedSeconds(startedAt, ticking ? undefined : endedAt, nowMs));
  const results = resultsSignpost(taskId, status, kind);

  if (minimised) {
    return (
      <Card aria-label="Analysis run" role="region" className="px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <p className="flex min-w-0 items-center gap-2 text-body text-navy">
            <StatusDot tone={TOP_DOT[tone]} />
            <span className="min-w-0 truncate">
              <Figures text={scrub(collapsedStatusLine(status, rows, elapsedLabel))} />
            </span>
          </p>
          <button type="button" className={QUIET_CONTROL_CLASS} onClick={() => onMinimisedChange(false)}>
            Expand
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card aria-label="Analysis run" role="region">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 pt-3.5 pb-2.5 max-sm:px-3">
        <p className="flex items-center gap-2 text-meta font-extrabold tracking-label text-grey">
          <StatusDot tone={TOP_DOT[tone]} />
          {eyebrow}
        </p>
        <div className="flex items-baseline gap-4">
          <span className="text-body text-grey">
            <Figures text={elapsedLabel} />
          </span>
          {onSeePlan !== undefined && (
            <button type="button" className={QUIET_CONTROL_CLASS} onClick={onSeePlan}>
              See plan
            </button>
          )}
          {tone !== "stopped" && (
            <button type="button" className={QUIET_CONTROL_CLASS} onClick={() => onMinimisedChange(true)}>
              Minimise
            </button>
          )}
        </div>
      </div>

      {rows.length > 0 && (
        <ol aria-label="Stage timeline" className="px-4 pt-0.5 pb-1.5 max-sm:px-3">
          {rows.map((row, index) => (
            <SpineRow
              key={row.key}
              row={row}
              rows={rows}
              index={index}
              taskId={taskId}
              kind={kind}
              hasFindings={hasFindings}
              liveness={liveness}
              paused={status === "paused"}
              nowMs={nowMs}
            />
          ))}
        </ol>
      )}

      {results !== null && (
        <div className="border-t border-line px-4 py-3 max-sm:px-3">
          <Link to={results.href} className={CHAT_PRIMARY_CTA_CLASS}>
            {results.label}
          </Link>
        </div>
      )}
    </Card>
  );
}

/** Collapsed strip above the composer when the in-thread card is off-screen. */
export function RunningCardDock({
  status,
  stages,
  plan,
  elapsedLabel,
  onOpen,
}: {
  status: RunStatus | undefined;
  stages: StageEntry[];
  plan: PlanDraft | null | undefined;
  elapsedLabel: string;
  onOpen: () => void;
  liveness?: Record<string, StageLiveness>;
}) {
  const rows = cardRows(stages, plan, status);
  const { tone } = runningCardCopy(status);
  return (
    <button
      type="button"
      aria-label="Show the analysis run"
      onClick={onOpen}
      className="flex w-full cursor-pointer items-center justify-between gap-3 border-b border-line bg-paper px-4 py-2.5 text-left hover:bg-paper-2"
    >
      <span className="flex min-w-0 items-center gap-2 text-body text-navy">
        <StatusDot tone={TOP_DOT[tone]} />
        <span className="min-w-0 truncate">
          <Figures text={scrub(collapsedStatusLine(status, rows, elapsedLabel))} />
        </span>
      </span>
      <span className="shrink-0 text-meta font-semibold text-grey underline decoration-line-2 underline-offset-[3px]">
        Show
      </span>
    </button>
  );
}

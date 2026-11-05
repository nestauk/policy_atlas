import { useId, useState } from "react";
import { Link } from "react-router";

import { Figures } from "../../lib/figures";
import { STALL_AFTER_MS, useFreshness, useNow } from "../../lib/freshness";
import { scrub } from "../../lib/scrub";
import type { PlanDraft, RunStatus, StageEntry, StageLiveness, TaskAgentThreadRun } from "../../store";
import { LiveMark, StatusMark, type StatusTone } from "../../ui/brand/Card";
import { cn } from "../../ui/brand/cn";
import { RUN_BLOCK_STATUS } from "./planVocabulary";
import {
  STALLED_LINE,
  cardRows,
  currentRow,
  elapsedSeconds,
  endedLine,
  formatElapsed,
  formatMinutes,
  resultHref,
  rowCounts,
  rowDetail,
  rowLink,
  rowLiveness,
  rowSeconds,
  stepCount,
  traceWords,
  walkKind,
  type CardRow,
  type WalkKind,
} from "./runProgress";

/** Quiet grey text control ("See plan"): a link in look, a button in kind. */
const QUIET_CONTROL_CLASS =
  "cursor-pointer text-meta font-semibold text-grey underline decoration-line-2 underline-offset-[3px] hover:text-navy hover:decoration-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue";

/** A box one line tall (`1lh`) and as wide as the live mark, that centres
 *  the mark on the first line of the words beside it, also when they wrap,
 *  at whatever size the line is set (Lead in the thread, Body in the
 *  sidebar). The square sits in the same column, so the words do not move
 *  when the run ends. */
const FIRST_LINE_BOX = "flex h-[1lh] w-3.5 shrink-0 items-center justify-center";

/** The step list's hairline runs down the middle of the mark's column. */
const UNDER_THE_MARK = "ml-[6.5px] border-l border-line pl-3.5";

/** The separator between items. A no-break space binds each "·" to the word
 *  before it, so a separator never starts a line; the line breaks after it
 *  (lead, 2026-11-05). */
const SEP = "\u00A0· ";

/** Server words with their separators bound the same way. */
function bound(text: string): string {
  return text.replaceAll(" · ", SEP);
}

/** The deep green of the green tint's text: green words that pass contrast. */
const GREEN_TEXT = "text-[#0c6b5a]";

/** Screen-reader word for a row's state, which the list shows by colour and counts. */
const STATE_WORD: Record<CardRow["state"], string> = {
  done: "done",
  progress: "in progress",
  upcoming: "to come",
  failed: "stopped",
  skipped: "skipped",
};

type RowContext = {
  rows: CardRow[];
  taskId: string;
  kind: WalkKind;
  hasFindings: boolean;
  nowMs: number;
};

/** A finished row as one line: its label, then in grey its counts, its wall
 *  time and its link ("Searching and screening · 312 found · 118 relevant ·
 *  1 min 4 s · Sources →"). A stopped or skipped row says so after the label. */
function FinishedLine({ row, context, quiet = false }: { row: CardRow; context: RowContext; quiet?: boolean }) {
  const seconds = rowSeconds(row, context.nowMs);
  const words =
    row.state === "failed" ? ["Stopped"] : row.state === "skipped" ? ["Skipped"] : rowCounts(row);
  const meta = [...words, ...(seconds === null ? [] : [formatElapsed(seconds)])];
  const link = rowLink(row, context.rows, context.taskId, context.kind, context.hasFindings);
  return (
    <>
      <span className={quiet ? undefined : "text-navy"}>{scrub(row.label)}</span>
      {meta.length > 0 && (
        <>
          {SEP}
          <Figures text={meta.join(SEP)} />
        </>
      )}
      {link !== null && (
        <>
          {SEP}
          <Link to={link.href} className="font-semibold whitespace-nowrap text-blue no-underline hover:underline">
            {link.label} →
          </Link>
        </>
      )}
    </>
  );
}

/**
 * One plan step in the open list: a finished step as its one line; the step
 * in progress as its label and its own elapsed time, with the writer's
 * section and what the model is doing now under it; a step to come as its
 * name in grey.
 */
function SpineRow({
  row,
  context,
  liveness,
  stalled,
}: {
  row: CardRow;
  context: RowContext;
  liveness?: Record<string, StageLiveness>;
  /** True when this is the current step and two quiet minutes have passed. */
  stalled: boolean;
}) {
  const state = <span className="sr-only">, {STATE_WORD[row.state]}</span>;
  if (row.state === "upcoming") {
    return (
      <li className="text-grey">
        {scrub(row.label)}
        {state}
      </li>
    );
  }
  if (row.state !== "progress") {
    return (
      <li className="text-grey">
        <FinishedLine row={row} context={context} />
        {state}
      </li>
    );
  }
  const tick = rowLiveness(row, liveness);
  const seconds = rowSeconds(row, context.nowMs);
  const section = stalled ? undefined : tick?.section?.trim();
  const activity = stalled ? STALLED_LINE : tick?.activity.trim();
  return (
    <li className="py-0.5">
      <p>
        <span className="font-semibold text-navy">{scrub(row.label)}</span>
        {state}
        {seconds !== null && (
          <span className="text-grey">
            {SEP}
            <Figures text={formatElapsed(seconds)} />
          </span>
        )}
      </p>
      {section && <p className="text-navy">{bound(scrub(section))}</p>}
      {activity && (
        <p className="text-grey">
          <Figures text={bound(scrub(activity))} />
        </p>
      )}
    </li>
  );
}

/**
 * The run trace (task 058; annex § The run trace, owner 2026-11-05): the one
 * place a run's progress shows, as a borderless block at the run's place in
 * the Task Agent thread, in the Agent tab and the sidebar alike.
 *
 * Live, its header is a button: the blue square mark (breathing while
 * updates arrive), the current step and what it is doing now, the run's
 * elapsed time and "· 6 steps"; under it the last finished step's line. Open,
 * it lists every plan step under a hairline rule with "See plan" at the
 * foot. Paused, the mark turns orange and the header says a check-in waits.
 * Ended, it folds to one line ("Report ready · 14 min · Read it →"), which
 * is the run's one destination. Every label and count is the server's.
 */
export function RunTrace({
  taskId,
  status,
  stages,
  liveness,
  plan,
  startedAt,
  endedAt,
  hasFindings,
  capability,
  purpose,
  isOwner,
  checkInWaiting = false,
  onSeePlan,
}: {
  taskId: string;
  status: RunStatus | undefined;
  stages: StageEntry[];
  /** The latest tick per stage: what the step in progress is doing now. */
  liveness?: Record<string, StageLiveness>;
  plan: PlanDraft | null | undefined;
  startedAt?: string;
  endedAt?: string;
  hasFindings: boolean;
  /** The task's capability: the finished words follow the walk kind (task 045). */
  capability?: string | null;
  /** The run's own purpose (`RunOut.purpose`): an added option's search
   *  reads as its own kind, not the baseline (task 045, A7). */
  purpose?: string | null;
  /** Only the owner is told that a check-in waits on them. */
  isOwner: boolean;
  /** A check-in waits (the stream may say so before the status turns). */
  checkInWaiting?: boolean;
  /** Opens the plan document, from the foot of the open list. */
  onSeePlan?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const kind = walkKind(capability, stages, purpose);
  const ended = endedLine(status, kind);
  const ticking = ended === null && (status === "running" || status === "paused");
  const paused = ended === null && (status === "paused" || checkInWaiting);
  const nowMs = useNow(ticking);
  const rows = cardRows(stages, plan, status);
  const row = currentRow(rows);
  const progress = row !== null && row.state === "progress" ? row : null;
  const tick = progress === null ? undefined : rowLiveness(progress, liveness);
  // Silence is measured from the last tick, or from the step's start when
  // none has come yet; a paused run is waiting on a person, not stalled.
  const stamp = tick?.occurredAt ?? progress?.entries[0]?.startedAt;
  const quiet = !useFreshness(stamp, STALL_AFTER_MS);
  const stalled = progress !== null && stamp !== undefined && quiet && !paused;
  const seconds = elapsedSeconds(startedAt, ticking ? undefined : endedAt, nowMs);
  const context: RowContext = { rows, taskId, kind, hasFindings, nowMs };

  const tone: StatusTone = ended !== null ? ended.tone : paused ? "paused" : "running";
  const words =
    ended !== null
      ? ended.words
      : traceWords(row, rowDetail(tick), paused ? "paused" : stalled ? "stalled" : "live", isOwner);
  const time = ended !== null ? formatMinutes(seconds) : formatElapsed(seconds);
  const [head = "", ...rest] = scrub(words).split(" · ");
  const doing = rest.join(" · ");
  const lastFinished = [...rows]
    .reverse()
    .find((candidate) => candidate.state === "done" || candidate.state === "failed" || candidate.state === "skipped");
  const canOpen = rows.length > 0;

  return (
    <div role="region" aria-label="Analysis run" className="@container mr-8">
      {/* The header's words for a screen reader, announced as they change;
          the ticking clock stays out of it. */}
      <p role="status" aria-live="polite" className="sr-only">
        {scrub(words)}
      </p>
      {/* The header reads at the chat's size (owner, 2026-11-05): Lead in the
          thread, as the agent's prose and the settled parts are. */}
      <div className="flex min-w-0 items-start gap-x-1.5 text-lead">
        <button
          type="button"
          aria-expanded={canOpen ? open : undefined}
          aria-controls={canOpen && open ? listId : undefined}
          disabled={!canOpen}
          onClick={() => setOpen((value) => !value)}
          className="group inline-flex max-w-full min-w-0 cursor-pointer items-start gap-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue disabled:cursor-default"
        >
          {/* Live, the mark is the fold mark turning; paused or ended, the
              6 px square in its state's colour (owner, 2026-11-05). */}
          <span className={FIRST_LINE_BOX}>
            {tone === "running" ? <LiveMark /> : <StatusMark tone={tone} />}
          </span>
          {ended !== null && canOpen && (
            <span
              aria-hidden="true"
              className={cn(
                "inline-block w-2 shrink-0 text-grey transition-transform duration-150 ease-out group-hover:text-navy",
                open && "rotate-90",
              )}
            >
              ›
            </span>
          )}
          {/* In a narrow column (a phone, the sidebar) the words take up to
              two lines and the line wraps after them, so the count and the
              elapsed time stay in view; wider, a long line truncates its
              words on one line instead. The trace's own width decides. */}
          <span className="flex min-w-0 flex-wrap items-baseline gap-x-1.5 @xl:flex-nowrap">
            <span
              key={ended !== null ? "ended" : paused ? "paused" : (row?.key ?? "none")}
              className={cn(
                "anim-rise line-clamp-2 max-w-full min-w-0 @xl:line-clamp-none @xl:truncate",
                ended?.link ? GREEN_TEXT : "text-navy",
              )}
            >
              {/* The step's label semibold, what it is doing in regular
                  weight (lead, 2026-11-05). */}
              <span className="font-semibold">
                <Figures text={head} />
              </span>
              {doing !== "" && (
                <>
                  {SEP}
                  <Figures text={bound(doing)} />
                </>
              )}
              {/* The separator before the time ends this line, so the time
                  never opens one with a dot. */}
              {words !== "" && <span aria-hidden="true" className="text-grey">{"\u00A0·"}</span>}
            </span>
            <span className="shrink-0 whitespace-nowrap text-grey">
              <Figures text={time} />
              {ended === null && canOpen && (
                <span className="decoration-line-2 underline-offset-[3px] group-hover:text-navy group-hover:underline">
                  {SEP}
                  {open ? "hide steps" : stepCount(rows.length)}
                </span>
              )}
            </span>
          </span>
        </button>
        {ended?.link && (
          <span className={cn("shrink-0 whitespace-nowrap", GREEN_TEXT)}>
            <span aria-hidden="true">· </span>
            <Link to={resultHref(taskId, kind)} className={cn("font-semibold underline-offset-[3px] hover:underline", GREEN_TEXT)}>
              Read it →
            </Link>
          </span>
        )}
      </div>

      {open ? (
        <div id={listId} className={cn("mt-1.5 text-body", UNDER_THE_MARK)}>
          <ol aria-label="Run steps" className="space-y-1">
            {rows.map((step) => (
              <SpineRow
                key={step.key}
                row={step}
                context={context}
                liveness={liveness}
                stalled={stalled && step.key === progress?.key}
              />
            ))}
          </ol>
          {onSeePlan !== undefined && (
            <button type="button" className={cn(QUIET_CONTROL_CLASS, "mt-2")} onClick={onSeePlan}>
              See plan
            </button>
          )}
        </div>
      ) : (
        ended === null &&
        lastFinished !== undefined && (
          // The last finished step, rising in as each new one lands.
          <p key={lastFinished.key} className={cn("anim-rise mt-1 text-body text-grey", UNDER_THE_MARK)}>
            <FinishedLine row={lastFinished} context={context} quiet />
          </p>
        )
      )}
    </div>
  );
}

/**
 * A past run in the thread (one the stream is not following): folded to its
 * status word and its wall time, with no step list (annex § The run trace).
 * The words are the ones its own walk ended with ("Report ready", "The
 * longlist is ready", "Stopped", "Failed"), so every run reads alike.
 */
export function PastRunLine({ run, capability }: { run: TaskAgentThreadRun; capability?: string | null }) {
  const status = run.status as RunStatus;
  const ended = endedLine(status, walkKind(capability, [], run.purpose));
  const fallback = RUN_BLOCK_STATUS[run.status] ?? run.status;
  const words = ended?.words ?? fallback.charAt(0).toUpperCase() + fallback.slice(1);
  const tone: StatusTone = ended?.tone ?? (status === "paused" ? "paused" : "running");
  const time =
    run.ended_at == null ? null : formatMinutes(elapsedSeconds(run.started_at, run.ended_at, Date.parse(run.ended_at)));
  return (
    <p className="mr-8 flex items-start gap-2 text-lead text-grey">
      <span className={FIRST_LINE_BOX}>
        <StatusMark tone={tone} />
      </span>
      <span className="min-w-0">
        <span className="font-semibold">{scrub(words)}</span>
        {time !== null && (
          <>
            {SEP}
            <Figures text={time} />
          </>
        )}
      </span>
    </p>
  );
}

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

/** The spine's hairline runs down the middle of the mark column (14 px wide,
 *  so the centre is 7 px in; a 1 px line starts half a pixel before it). */
const SPINE_X = "left-[6.5px]";

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

/** Screen-reader word for a row's state, which the list shows by its mark,
 *  colour and counts. */
const STATE_WORD: Record<CardRow["state"], string> = {
  done: "done",
  progress: "in progress",
  upcoming: "to come",
  failed: "stopped",
  skipped: "skipped",
};

/** A still row's mark: the 6 px square in its state's tone. */
const ROW_TONE: Record<Exclude<CardRow["state"], "progress">, StatusTone> = {
  done: "complete",
  failed: "failed",
  skipped: "idle",
  upcoming: "idle",
};

/** A row's vertical padding, and the spine's reach to the middle of its
 *  first line (the padding plus half a line). Steps to come sit tighter. */
const ROW_PAD = { roomy: "py-2", tight: "py-1.5" } as const;
const MARK_MIDDLE = { roomy: "top-[calc(0.5rem+0.5lh)]", tight: "top-[calc(0.375rem+0.5lh)]" } as const;
const MARK_REACH = { roomy: "h-[calc(0.5rem+0.5lh)]", tight: "h-[calc(0.375rem+0.5lh)]" } as const;

/** What a step row needs beyond itself to say where it points. */
export type RowContext = {
  rows: CardRow[];
  taskId: string;
  kind: WalkKind;
  hasFindings: boolean;
  nowMs: number;
};

/** A finished row as one line: its label in navy, then in grey its counts,
 *  its wall time and its link ("Searching and screening · 312 found · 118
 *  relevant · 1 min 4 s · Sources →"). A stopped or skipped row says so after
 *  the label. */
export function FinishedLine({
  row,
  context,
  withTime = true,
}: {
  row: CardRow;
  context: RowContext;
  /** False for the step note, which reads without the wall time (lead, round 6). */
  withTime?: boolean;
}) {
  const seconds = withTime ? rowSeconds(row, context.nowMs) : null;
  const words =
    row.state === "failed" ? ["Stopped"] : row.state === "skipped" ? ["Skipped"] : rowCounts(row);
  const meta = [...words, ...(seconds === null ? [] : [formatElapsed(seconds)])];
  const link = rowLink(row, context.rows, context.taskId, context.kind, context.hasFindings);
  return (
    <>
      <span className="text-navy">{scrub(row.label)}</span>
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
 * One plan step on the spine (the running card's body, owner 2026-11-05,
 * round 6): its mark on the hairline, a hairline rule above it from the
 * second row on, and its words. A finished step is its one line; the step in
 * progress is its label and its own elapsed time, with the writer's section
 * and what the model is doing now under it, and the turning fold mark as its
 * mark (the orange square while the run waits on a person); a step to come is
 * its name, grey and smaller.
 */
function SpineRow({
  row,
  context,
  first,
  last,
  landed,
  indent,
  paused,
  liveness,
  stalled,
}: {
  row: CardRow;
  context: RowContext;
  first: boolean;
  last: boolean;
  /** True when the step finished while this trace was on screen: it rises in once. */
  landed: boolean;
  /** True on an ended trace, whose header carries the chevron: the words
   *  step in by its width so they stand under the header's words, while the
   *  marks stay on the spine under the header's mark. */
  indent: boolean;
  paused: boolean;
  liveness?: Record<string, StageLiveness>;
  /** True when this is the current step and two quiet minutes have passed. */
  stalled: boolean;
}) {
  const upcoming = row.state === "upcoming";
  const progress = row.state === "progress";
  const room = upcoming ? "tight" : "roomy";
  // The step in progress takes the blue square, breathing while updates
  // arrive (DESIGN.md: it holds still 1.5 s after the last); the header's
  // fold mark is the block's one turning mark (lead, round 6). Paused, the
  // square is orange.
  const fresh = useFreshness(progress ? rowLiveness(row, liveness)?.occurredAt : undefined);
  const mark =
    row.state === "progress" ? (
      <StatusMark tone={paused ? "paused" : "running"} breathing={fresh && !paused} />
    ) : (
      <StatusMark tone={ROW_TONE[row.state]} />
    );
  const state = <span className="sr-only">, {STATE_WORD[row.state]}</span>;

  let words;
  if (upcoming) {
    words = (
      <p>
        {scrub(row.label)}
        {state}
      </p>
    );
  } else if (!progress) {
    words = (
      <p className="text-grey">
        <FinishedLine row={row} context={context} />
        {state}
      </p>
    );
  } else {
    const tick = rowLiveness(row, liveness);
    const seconds = rowSeconds(row, context.nowMs);
    const section = stalled ? undefined : tick?.section?.trim();
    const activity = stalled ? STALLED_LINE : tick?.activity.trim();
    words = (
      <>
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
      </>
    );
  }

  return (
    <li
      data-state={row.state}
      className={cn("relative flex gap-2", upcoming ? "text-meta text-grey" : "text-body", landed && "anim-rise")}
    >
      {/* The spine: one hairline from the first row's mark to the last's,
          drawn a row at a time. */}
      {!(first && last) && (
        <span
          aria-hidden="true"
          className={cn(
            "absolute w-px bg-line-2",
            SPINE_X,
            first ? cn(MARK_MIDDLE[room], "bottom-0") : "top-0",
            last ? MARK_REACH[room] : !first && "bottom-0",
          )}
        />
      )}
      <span className={cn(FIRST_LINE_BOX, "relative", room === "tight" ? "mt-1.5" : "mt-2")}>{mark}</span>
      <div className={cn("min-w-0 flex-1", ROW_PAD[room], indent && "ml-4", !first && "border-t border-line")}>{words}</div>
    </li>
  );
}

/**
 * The run trace (task 058; annex § The run trace, owner 2026-11-05): the one
 * place a run's progress shows, as a borderless block at the run's place in
 * the Task Agent thread, in the Agent tab and the sidebar alike.
 *
 * Live or paused, its header line carries the mark, the current step and what
 * it is doing now, and the run's elapsed time; under it the running card's
 * body (owner, round 6): one row per plan step in plan order, top to bottom,
 * each with its mark on a hairline spine and a hairline rule between rows,
 * and "See plan" at the foot. The list stays open. Paused, the mark turns
 * orange and the header says a check-in waits. Ended, it folds to one line
 * ("Report ready · 14 min · Read it →"), the run's one destination, whose
 * chevron opens the rows. Every label and count is the server's.
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
  /** Opens the plan document, from the foot of the list. */
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
  const landed = useLandedRows(rows);

  const tone: StatusTone = ended !== null ? ended.tone : paused ? "paused" : "running";
  const words =
    ended !== null
      ? ended.words
      : traceWords(row, rowDetail(tick), paused ? "paused" : stalled ? "stalled" : "live", isOwner);
  const time = ended !== null ? formatMinutes(seconds) : formatElapsed(seconds);
  // Live, the header is the turning mark and the run's elapsed time only:
  // the step's words live on its row (lead, round 6). Paused and ended, the
  // header keeps its words. A screen reader hears `words` either way.
  const shown = ended === null && !paused ? "" : words;
  const [head = "", ...rest] = scrub(shown).split(" · ");
  const doing = rest.join(" · ");
  // Live or paused the rows are the trace's body and stay open; ended, the
  // chevron opens them.
  const foldable = ended !== null && rows.length > 0;
  const showRows = rows.length > 0 && (ended === null || open);

  const headerInner = (
    <>
      {/* Live, the mark is the fold mark turning; paused or ended, the
          6 px square in its state's colour (owner, 2026-11-05). */}
      <span className={FIRST_LINE_BOX}>{tone === "running" ? <LiveMark /> : <StatusMark tone={tone} />}</span>
      {foldable && (
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
          two lines and the line wraps after them, so the elapsed time stays
          in view; wider, a long line truncates its words on one line
          instead. The trace's own width decides. */}
      <span className="flex min-w-0 flex-wrap items-baseline gap-x-1.5 @xl:flex-nowrap">
        {shown !== "" && (
          <span
            key={ended !== null ? "ended" : "paused"}
            className={cn(
              "anim-rise line-clamp-2 max-w-full min-w-0 @xl:line-clamp-none @xl:truncate",
              ended?.link ? GREEN_TEXT : "text-navy",
            )}
          >
            {/* The step's label semibold, what it is doing in regular weight
                (lead, 2026-11-05). */}
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
            <span aria-hidden="true" className="text-grey">{"\u00A0·"}</span>
          </span>
        )}
        <span className="shrink-0 whitespace-nowrap text-grey">
          <Figures text={time} />
        </span>
      </span>
    </>
  );

  return (
    <div role="region" aria-label="Analysis run" className="@container mr-8">
      {/* The header's words for a screen reader, announced as they change;
          the ticking clock stays out of it. */}
      <p role="status" aria-live="polite" className="sr-only">
        {scrub(words)}
      </p>
      {/* The header reads at the chat's size (owner, 2026-11-05): Lead in the
          thread, as the agent's prose and the settled parts are. */}
      <div data-testid="trace-header" className="flex min-w-0 items-start gap-x-1.5 text-lead">
        {foldable ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={open ? listId : undefined}
            onClick={() => setOpen((value) => !value)}
            className="group inline-flex max-w-full min-w-0 cursor-pointer items-start gap-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
          >
            {headerInner}
          </button>
        ) : (
          <p className="inline-flex max-w-full min-w-0 items-start gap-2">{headerInner}</p>
        )}
        {ended?.link && (
          <span className={cn("shrink-0 whitespace-nowrap", GREEN_TEXT)}>
            <span aria-hidden="true">· </span>
            <Link to={resultHref(taskId, kind)} className={cn("font-semibold underline-offset-[3px] hover:underline", GREEN_TEXT)}>
              Read it →
            </Link>
          </span>
        )}
      </div>

      {showRows && (
        <div id={listId} className="mt-1.5">
          <ol aria-label="Run steps">
            {rows.map((step, index) => (
              <SpineRow
                key={step.key}
                row={step}
                context={context}
                first={index === 0}
                last={index === rows.length - 1}
                landed={landed.has(step.key)}
                indent={foldable}
                paused={paused}
                liveness={liveness}
                stalled={stalled && step.key === progress?.key}
              />
            ))}
          </ol>
          {onSeePlan !== undefined && (
            <button
              type="button"
              className={cn(QUIET_CONTROL_CLASS, "mt-2", foldable ? "ml-[38px]" : "ml-[22px]")}
              onClick={onSeePlan}
            >
              See plan
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** The rows that finished while this trace has been on screen: each rises in
 *  once as it lands, and keeps the class after so a re-render never replays
 *  or cuts the rise. Rows already done when the trace mounts hold still.
 *  Derived as the rows change (state adjusted during render, React's pattern
 *  for state that follows a prop). */
function useLandedRows(rows: CardRow[]): ReadonlySet<string> {
  const signature = rows.map((row) => `${row.key}:${row.state}`).join("|");
  const [track, setTrack] = useState<{ signature: string; states: ReadonlyMap<string, CardRow["state"]>; landed: ReadonlySet<string> }>(
    () => ({ signature, states: new Map(rows.map((row) => [row.key, row.state])), landed: new Set() }),
  );
  if (track.signature !== signature) {
    const landed = new Set(track.landed);
    for (const row of rows) {
      const before = track.states.get(row.key);
      if (before !== undefined && before !== "done" && row.state === "done") landed.add(row.key);
    }
    setTrack({ signature, states: new Map(rows.map((row) => [row.key, row.state])), landed });
    return landed;
  }
  return track.landed;
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

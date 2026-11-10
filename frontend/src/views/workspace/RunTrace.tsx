import { useId, useState, type ReactNode } from "react";
import { Link } from "react-router";

import { Figures } from "../../lib/figures";
import { STALL_AFTER_MS, useFreshness, useNow } from "../../lib/freshness";
import { scrub } from "../../lib/scrub";
import type { PlanDraft, RunStatus, StageEntry, StageLiveness, TaskAgentThreadRun } from "../../store";
import { Card, LiveMark, StatusMark, type StatusTone } from "../../ui/brand/Card";
import { cn } from "../../ui/brand/cn";
import { Collapse } from "../../ui/motion/Collapse";
import { prefersReducedMotion } from "../../ui/motion/motion";
import { useEasedHeight } from "../streamPacing";
import { useRegisterTrace } from "../taskLive";
import { RUN_BLOCK_STATUS } from "./planVocabulary";
import {
  STALLED_LINE,
  cardRows,
  currentRow,
  elapsedSeconds,
  endedLine,
  formatElapsed,
  resultHref,
  rowCounts,
  rowDetail,
  rowLink,
  rowLiveness,
  rowSeconds,
  threadRunStages,
  traceWords,
  walkKind,
  type CardRow,
} from "./runProgress";
import { RUNNING_WORD, type WalkKind } from "../../ui/brand/taskStatus";
import { LINK_CLASS, QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";
import { DisclosureChevron } from "../../ui/brand/Disclosure";

/** Quiet grey text control ("See plan", "Show steps"): a link in look, a
 *  button in kind. */

/**
 * Every line of the card shares one line box (owner, round 8: equal row
 * heights): the Body line height, 1.55rem, whatever the line's text size, so
 * the top line, a done row and a step to come stand the same height and the
 * marks sit at the same place on each.
 */
const LINE = "leading-[1.55rem]";

/** A box one line tall (`1lh`) and as wide as the live mark, that centres
 *  the mark on the first line of the words beside it, also when they wrap.
 *  The square sits in the same column, so the words do not move when the
 *  run ends. */
const FIRST_LINE_BOX = "flex h-[1lh] w-3.5 shrink-0 items-center justify-center";

/** The spine's hairline runs down the middle of the mark column (14 px wide,
 *  so the centre is 7 px in; a 1 px line starts half a pixel before it). */
const SPINE_X = "left-[6.5px]";

/** A row's vertical padding, and the spine's reach to the middle of its
 *  first line (the padding plus half a line). One value for every row. */
const ROW_PAD = "py-2";
const MARK_MIDDLE = "top-[calc(0.5rem+0.5lh)]";
const MARK_REACH = "h-[calc(0.5rem+0.5lh)]";

/** The words column starts after the mark column and its gap (14 + 8 px):
 *  where the quiet controls under the rows line up. */
const WORDS_INDENT = "ml-[22px]";

/**
 * The card reads as a table (owner, round 8): the words on the left, then
 * the counts and times right-aligned in one column, then the links
 * right-aligned in the last. The same template on the top line and on every
 * row, so the columns line up down the card. Once the card is narrower than
 * 32rem (a phone, the sidebar) the template lets go: the right group follows
 * the words, wrapping under them.
 */
const TABLE_ROW =
  "flex min-w-0 flex-1 flex-wrap items-baseline gap-x-1.5 @lg:grid @lg:grid-cols-[minmax(0,1fr)_auto_5.75rem] @lg:gap-x-5";

/** The right group (counts and time, then the link): two of the table's
 *  columns when wide; narrow, right-aligned on the row's right edge as the
 *  wide table is (owner, round 14), on the label's line or the line under
 *  it, the link wrapping to its own line at the right edge when the two do
 *  not fit. */
const RIGHT_GROUP = "flex min-w-0 flex-1 flex-wrap items-baseline justify-end gap-x-1.5 @lg:contents";

/** The separator between items. A no-break space binds each "·" to the word
 *  before it, so a separator never starts a line; the line breaks after it
 *  (lead, 2026-11-05). */
const SEP = " · ";

/** Server words with their separators bound the same way. */
function bound(text: string): string {
  return text.replaceAll(" · ", SEP);
}

/** The card's state word in the label style (uppercase, Extrabold, tracked,
 *  grey), as the running card first had it. */
const TOP_LINE_LABEL = "font-extrabold uppercase tracking-label text-grey";

/** A link in the table's last column: the Link style, never wrapped. */
const TRACE_LINK_CLASS = `${LINK_CLASS} whitespace-nowrap`;

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

/** What a step row needs beyond itself to say where it points. */
export type RowContext = {
  rows: CardRow[];
  taskId: string;
  kind: WalkKind;
  hasFindings: boolean;
  nowMs: number;
};

/**
 * The right-hand cells of a line: what it measured (counts, a time) in grey
 * tabular figures, then where it points in blue. Narrow, they sit at the
 * row's right edge with a separator bound to the cell before the link, so a
 * wrapped link never opens its line with a dot; wide, each takes its column,
 * right-aligned, and an empty cell keeps the column.
 */
function RightCells({ meta, link, landed = false }: { meta: string | null; link: ReactNode; landed?: boolean }) {
  return (
    <span className={cn(RIGHT_GROUP, "text-meta", LINE)}>
      <span className={cn("text-right text-grey", landed && "anim-swap-in")}>
        {meta !== null && <Figures text={meta} />}
        {meta !== null && link !== null && <NarrowSeparator />}
      </span>
      {link !== null ? <span className="text-right">{link}</span> : <span aria-hidden="true" className="hidden @lg:block" />}
    </span>
  );
}

/** The dot between a cell and the link after it, shown only while the cells
 *  run on one line (narrow); bound to the cell before it. */
function NarrowSeparator() {
  return (
    <span aria-hidden="true" className="@lg:hidden">
      {"\u00A0·"}
    </span>
  );
}

/**
 * One plan step on the spine (the running card's body, owner 2026-11-05,
 * round 6; laid out as a table in round 8): its mark on the hairline, a
 * hairline rule above it from the second row on, its label on the left and
 * its counts, time and link on the right. The step in progress adds the
 * writer's section and what the model is doing now under its label; that
 * activity line breathes with the step's square while updates arrive. A
 * step to come is its name, grey and smaller, on the same line height.
 */
function SpineRow({
  row,
  context,
  first,
  last,
  landed,
  paused,
  liveness,
  stalled,
}: {
  row: CardRow;
  context: RowContext;
  first: boolean;
  last: boolean;
  /** True when the step finished while this trace was on screen: it keeps
   *  its place, its counts and time fade in and its square eases to green
   *  (lead, round 9: a row that shrank as it landed and rose too read as a
   *  jump). */
  landed: boolean;
  paused: boolean;
  liveness?: Record<string, StageLiveness>;
  /** True when this is the current step and two quiet minutes have passed. */
  stalled: boolean;
}) {
  const upcoming = row.state === "upcoming";
  const progress = row.state === "progress";
  // The step in progress takes the blue square, breathing while updates
  // arrive (DESIGN.md: it holds still 1.5 s after the last); the top line's
  // fold mark is the block's one turning mark (lead, round 6). Paused, the
  // square is orange.
  const tick = progress ? rowLiveness(row, liveness) : undefined;
  const fresh = useFreshness(tick?.occurredAt);
  const breathing = progress && fresh && !paused;
  const mark = row.state === "progress" ? (
    <StatusMark tone={paused ? "paused" : "running"} breathing={breathing} />
  ) : (
    <StatusMark tone={ROW_TONE[row.state]} />
  );
  const state = <span className="sr-only">, {STATE_WORD[row.state]}</span>;
  const seconds = upcoming ? null : rowSeconds(row, context.nowMs);
  const link = rowLink(row, context.rows, context.taskId, context.kind, context.hasFindings);
  const linkNode =
    link === null ? null : (
      <Link to={link.href} className={TRACE_LINK_CLASS}>
        {link.label} →
      </Link>
    );

  let words: ReactNode;
  if (upcoming) {
    words = (
      <p className={cn("min-w-0 text-meta text-grey", LINE)}>
        {scrub(row.label)}
        {state}
      </p>
    );
  } else {
    const counts =
      row.state === "failed" ? ["Stopped"] : row.state === "skipped" ? ["Skipped"] : progress ? [] : rowCounts(row);
    const metaParts = [...counts, ...(seconds === null ? [] : [formatElapsed(seconds)])];
    const meta = metaParts.length === 0 ? null : metaParts.join(SEP);
    const section = progress && !stalled ? tick?.section?.trim() : undefined;
    const activity = progress ? (stalled ? STALLED_LINE : tick?.activity.trim()) : undefined;
    words = (
      <>
        <div className={TABLE_ROW}>
          {/* A finished step's counts take their own line under the label
              when narrow; the step in progress keeps its clock on the
              label's line (polish round 1). */}
          <p
            className={cn(
              "min-w-0 text-body",
              LINE,
              progress ? "flex-1 font-semibold text-navy" : "basis-full text-navy @lg:basis-auto",
            )}
          >
            {scrub(row.label)}
            {state}
          </p>
          <RightCells meta={meta} link={linkNode} landed={landed} />
        </div>
        {section && <p className={cn("text-body text-navy", LINE)}>{bound(scrub(section))}</p>}
        {activity && (
          // What the model is doing now breathes with the step's square
          // (owner, round 8): opacity only, still under reduced motion.
          <p data-testid="row-activity" className={cn("text-meta text-grey", LINE, breathing && "anim-breathe-soft")}>
            <Figures text={bound(scrub(activity))} />
          </p>
        )}
      </>
    );
  }

  return (
    <li data-state={row.state} data-landed={landed || undefined} className={cn("relative flex gap-2 text-body", LINE)}>
      {/* The spine: one hairline from the first row's mark to the last's,
          drawn a row at a time. */}
      {!(first && last) && (
        <span
          aria-hidden="true"
          className={cn(
            "absolute w-px bg-line-2",
            SPINE_X,
            first ? cn(MARK_MIDDLE, "bottom-0") : "top-0",
            last ? MARK_REACH : !first && "bottom-0",
          )}
        />
      )}
      <span className={cn(FIRST_LINE_BOX, "relative mt-2")}>{mark}</span>
      <div className={cn("min-w-0 flex-1", ROW_PAD, !first && "border-t border-line")}>{words}</div>
    </li>
  );
}

/** Whether the ended words are a status word ("Report ready", "Stopped")
 *  that takes the label style, or a sentence that keeps its case. */
function isStateWord(words: string): boolean {
  return !/\.(\s|$)/.test(words);
}

/**
 * The card's top line (owner, rounds 7 and 8): the mark, the state word in
 * the label style and what it says, the run's time right-aligned in the
 * table's time column, and the link in its last column. One line box with
 * the rows, so the card reads as a table.
 */
function TopLine({
  mark,
  label,
  rest,
  time,
  link,
  labelKey,
  rise,
}: {
  mark: ReactNode;
  /** The state word ("Running", "Paused", "Report ready"), or a sentence. */
  label: string;
  /** What follows the state word, in grey ("waiting on you"). */
  rest: string;
  time: string;
  link: ReactNode;
  /** Changing it re-mounts the words, so they rise in on a state change. */
  labelKey: string;
  rise: boolean;
}) {
  const stateWord = isStateWord(label);
  return (
    <div className={cn("flex gap-2 text-meta", LINE)}>
      <span className={FIRST_LINE_BOX}>{mark}</span>
      <div className={cn(TABLE_ROW, "justify-between")}>
        <p key={labelKey} className={cn("min-w-0 flex-1", rise && "anim-rise")}>
          <span className={stateWord ? TOP_LINE_LABEL : "text-navy"}>{scrub(label)}</span>
          {/* "waiting on you" never splits across lines (design lane review). */}
          {rest !== "" && (
            <span className="whitespace-nowrap text-grey">
              {SEP}
              <Figures text={bound(rest)} />
            </span>
          )}
        </p>
        {/* The time never truncates or wraps inside: the words give way. */}
        <span className={cn(RIGHT_GROUP, "shrink-0")}>
          <span data-testid="trace-time" className="whitespace-nowrap text-grey @lg:text-right">
            <Figures text={time} />
            {link !== null && <NarrowSeparator />}
          </span>
          {link !== null ? <span className="@lg:text-right">{link}</span> : <span aria-hidden="true" className="hidden @lg:block" />}
        </span>
      </div>
    </div>
  );
}

/**
 * The run trace (task 058; annex § The run trace, owner 2026-11-05): the one
 * place a run's progress shows, at the run's place in the Task Agent thread,
 * in the Agent tab and the sidebar alike.
 *
 * It is one card through the whole run (owner, round 8: the ended state is
 * the same card). Live, its top line is the turning fold mark, "Running" in
 * the label style and the run's elapsed time at the right; under it one row
 * per plan step in plan order, each with its mark on a hairline spine, its
 * counts, time and link right-aligned, and "See plan" at the foot; the list
 * stays open. Paused, the mark is the orange square and the top line says a
 * check-in waits. Ended, the top line is the finish: the green square (red
 * when it stopped or failed), the finish words in the label style, the wall
 * time and "Read it →"; the rows fold behind "Show steps". Every label and
 * count is the server's.
 */
export function RunTrace(props: TraceProps) {
  // While a trace is mounted the run status bar's live region stays quiet.
  useRegisterTrace();
  return <TraceCard {...props} />;
}

type TraceProps = {
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
  /** A theory of change's walk kind (`RunOut.toc_walk`, task 054): its
   *  finish words and its rows' links follow it. */
  tocWalk?: string | null;
  /** The owner is told a paused run waits on them. */
  isOwner: boolean;
  /** The task's owner (`TaskOut.owner_display`), whom a colleague is told a
   *  paused run waits on. */
  ownerName?: string | null;
  /** A check-in waits (the stream may say so before the status turns). */
  checkInWaiting?: boolean;
  /** Opens the plan document, from the foot of the list. */
  onSeePlan?: () => void;
  /** The run stream is connected: the live mark turns only while it is, and
   *  holds still when the connection is down (lead ruling). */
  streamOpen?: boolean;
};

/**
 * The card both a followed run and a past run draw (owner, round 11: the
 * past run is the ended card, not a copy of it). `past` marks a run the
 * stream is not following: no landmark (the thread's one "Analysis run"
 * region is the run the stream follows) and no live region (nothing about
 * it changes).
 */
function TraceCard({
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
  tocWalk,
  isOwner,
  ownerName = null,
  checkInWaiting = false,
  onSeePlan,
  streamOpen = true,
  past = false,
}: TraceProps & { past?: boolean }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const kind = walkKind(capability, stages, purpose, tocWalk);
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
  // A step that gains or loses its section and activity lines eases the
  // card to its new height (300 ms, strong ease-out; the animation sweep's
  // entry 4), so the rows below glide rather than jump. A cut under reduced
  // motion.
  const [stepsBox, stepsContent] = useEasedHeight(ticking && !prefersReducedMotion());

  const words =
    ended !== null
      ? ended.words
      : traceWords(row, rowDetail(tick), paused ? "paused" : stalled ? "stalled" : "live", isOwner, ownerName);
  // Live, the top line reads "Running": the step's words live on its row
  // (lead, round 6). Paused, it keeps its words. A screen reader hears
  // `words` either way.
  const [head = "", ...restParts] = scrub(words).split(" · ");
  const label = ended !== null ? scrub(ended.words) : paused ? head : RUNNING_WORD;
  const rest = ended === null && paused ? restParts.join(" · ") : "";
  const time = ended !== null ? formatElapsed(seconds, { withSeconds: false }) : formatElapsed(seconds);
  const mark =
    ended !== null ? <StatusMark tone={ended.tone} /> : paused ? <StatusMark tone="paused" /> : <LiveMark still={!streamOpen} />;
  const readIt = ended?.link ? (
    <Link to={resultHref(taskId, kind)} className={TRACE_LINK_CLASS}>
      Read it →
    </Link>
  ) : null;

  // Live or paused the rows are the card's body and stay open; ended, they
  // fold behind "Show steps".
  const foldable = ended !== null && rows.length > 0;
  const showRows = rows.length > 0 && (ended === null || open);

  // Ended, the rows fold and open over 200 ms (the chevron's time) by their
  // height and opacity; a cut under reduced motion.
  const list = rows.length > 0 && (
    <Collapse show={showRows} durationMs={200}>
    <div id={listId} className={cn("px-4 pt-0.5 pb-3 max-sm:px-3", showRows && "border-t border-line")}>
      <div ref={stepsBox}>
      <div ref={stepsContent}>
      <ol aria-label="Run steps">
        {rows.map((step, index) => (
          <SpineRow
            key={step.key}
            row={step}
            context={context}
            first={index === 0}
            last={index === rows.length - 1}
            landed={landed.has(step.key)}
            paused={paused}
            liveness={liveness}
            stalled={stalled && step.key === progress?.key}
          />
        ))}
      </ol>
      </div>
      </div>
      {onSeePlan !== undefined && (
        <button type="button" data-plan-opener="" className={cn(QUIET_CONTROL_CLASS, "mt-2 text-meta", WORDS_INDENT)} onClick={onSeePlan}>
          See plan
        </button>
      )}
    </div>
    </Collapse>
  );

  return (
    <Card
      {...(past ? { "data-testid": "past-run" } : { role: "region", "aria-label": "Analysis run" })}
      className="@container"
    >
      {/* The header's words for a screen reader, announced as they change;
          the ticking clock stays out of it. A past run says nothing new. */}
      {!past && (
        <p role="status" aria-live="polite" className="sr-only">
          {scrub(words)}
        </p>
      )}
      <div
        data-testid="trace-header"
        className="px-4 pt-3 pb-2.5 max-sm:px-3"
      >
        <TopLine
          mark={mark}
          label={label}
          rest={rest}
          time={time}
          link={readIt}
          labelKey={ended !== null ? "ended" : paused ? "paused" : "running"}
          rise={ended !== null || paused}
        />
        {/* Ended, the steps fold behind one quiet control under the words
            (owner, round 8). It stays where it is when the rows open below
            it, so the pointer that opened them can close them. */}
        {foldable && (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={open ? listId : undefined}
            onClick={() => setOpen((value) => !value)}
            className={cn(QUIET_CONTROL_CLASS, "group mt-0.5 inline-flex text-meta items-center gap-1", WORDS_INDENT)}
          >
            {/* The one disclosure chevron, turning down as the steps open. */}
            <DisclosureChevron open={open} className="-ml-0.5" />
            {open ? "Hide steps" : "Show steps"}
          </button>
        )}
      </div>
      {list}
    </Card>
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
 * A past run in the thread (one the stream is not following): the same card
 * as a run that ended in front of you (owner, round 8), drawn by the same
 * code (owner, round 11). Its top line is its mark, the words its own walk
 * ended with ("Report ready", "The baseline is ready", "Stopped") in the
 * label style, its wall time and the link that walk ended with ("Read it →"
 * to the report, the baseline or the longlist; none after a stop or a
 * failure). When its thread run carries its steps, they fold behind "Show
 * steps" as the ended card's do; without them there is no control. A run
 * the thread lists that has not ended keeps its status word and no link.
 */
export function PastRunLine({
  run,
  leadRun = null,
  taskId,
  capability,
  hasFindings = false,
}: {
  run: TaskAgentThreadRun;
  /** A theory of change's draft that this check followed by itself (task
   *  054, S10): one card for the two, its rows first and its start the
   *  card's start. */
  leadRun?: TaskAgentThreadRun | null;
  taskId: string;
  capability?: string | null;
  /** Whether the task has findings, for a done Extracting row's link. */
  hasFindings?: boolean;
}) {
  const status = run.status as RunStatus;
  const stages = [...(leadRun !== null ? threadRunStages(leadRun) : []), ...threadRunStages(run)];
  if (endedLine(status, walkKind(capability, stages, run.purpose, run.toc_walk)) !== null) {
    return (
      <TraceCard
        past
        taskId={taskId}
        status={status}
        stages={stages}
        plan={null}
        startedAt={leadRun?.started_at ?? run.started_at}
        endedAt={run.ended_at ?? undefined}
        hasFindings={hasFindings}
        capability={capability}
        purpose={run.purpose}
        tocWalk={run.toc_walk}
        isOwner={false}
      />
    );
  }
  const fallback = RUN_BLOCK_STATUS[run.status] ?? run.status;
  return (
    <Card data-testid="past-run" className="@container">
      <div className="px-4 pt-3 pb-2.5 max-sm:px-3">
        <TopLine
          mark={<StatusMark tone={status === "paused" ? "paused" : "running"} />}
          label={scrub(fallback.charAt(0).toUpperCase() + fallback.slice(1))}
          rest=""
          time=""
          link={null}
          labelKey="past"
          rise={false}
        />
      </div>
    </Card>
  );
}

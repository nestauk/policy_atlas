import { useId, useState, type ReactNode } from "react";
import { Link } from "react-router";

import { Figures } from "../../lib/figures";
import { STALL_AFTER_MS, useFreshness, useNow } from "../../lib/freshness";
import { scrub } from "../../lib/scrub";
import type { PlanDraft, RunStatus, StageEntry, StageLiveness, TaskAgentThreadRun } from "../../store";
import { Card, LiveMark, StatusMark, type StatusTone } from "../../ui/brand/Card";
import { cn } from "../../ui/brand/cn";
import { useRegisterTrace } from "../taskLive";
import { ChevronIcon } from "./chat/icons";
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

/** Quiet grey text control ("See plan", "Show steps"): a link in look, a
 *  button in kind. */
const QUIET_CONTROL_CLASS =
  "cursor-pointer text-meta font-semibold text-grey underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 hover:text-navy hover:decoration-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue";

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

/** The right group (counts and time, then the link): its own line under the
 *  words when narrow, two of the table's columns when wide. */
const RIGHT_GROUP = "flex items-baseline gap-x-1.5 @lg:contents";

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

/** A link in the table's last column: blue, semibold, right-aligned. */
const LINK_CLASS = "font-semibold whitespace-nowrap text-blue no-underline hover:underline";

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
 * tabular figures, then where it points in blue. Narrow, they follow the
 * words with a separator bound to the cell before the link, so a wrapped
 * link never opens its line with a dot; wide, each takes its column,
 * right-aligned, and an empty cell keeps the column.
 */
function RightCells({ meta, link }: { meta: string | null; link: ReactNode }) {
  return (
    <span className={cn(RIGHT_GROUP, "text-meta", LINE)}>
      <span className="text-grey @lg:text-right">
        {meta !== null && <Figures text={meta} />}
        {meta !== null && link !== null && <NarrowSeparator />}
      </span>
      {link !== null ? <span className="@lg:text-right">{link}</span> : <span aria-hidden="true" className="hidden @lg:block" />}
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
  /** True when the step finished while this trace was on screen: it rises in once. */
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
      <Link to={link.href} className={LINK_CLASS}>
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
          <RightCells meta={meta} link={linkNode} />
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
    <li data-state={row.state} className={cn("relative flex gap-2 text-body", LINE, landed && "anim-rise")}>
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
  /** What follows the state word, in grey ("a check-in is waiting on you"). */
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
          {rest !== "" && (
            <span className="text-grey">
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
  // While a trace is mounted the run strip's live region stays quiet.
  useRegisterTrace();
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

  const words =
    ended !== null
      ? ended.words
      : traceWords(row, rowDetail(tick), paused ? "paused" : stalled ? "stalled" : "live", isOwner);
  // Live, the top line reads "Running": the step's words live on its row
  // (lead, round 6). Paused, it keeps its words. A screen reader hears
  // `words` either way.
  const [head = "", ...restParts] = scrub(words).split(" · ");
  const label = ended !== null ? scrub(ended.words) : paused ? head : "Running";
  const rest = ended === null && paused ? restParts.join(" · ") : "";
  const time = ended !== null ? formatMinutes(seconds) : formatElapsed(seconds);
  const mark =
    ended !== null ? <StatusMark tone={ended.tone} /> : paused ? <StatusMark tone="paused" /> : <LiveMark />;
  const readIt = ended?.link ? (
    <Link to={resultHref(taskId, kind)} className={LINK_CLASS}>
      Read it →
    </Link>
  ) : null;

  // Live or paused the rows are the card's body and stay open; ended, they
  // fold behind "Show steps".
  const foldable = ended !== null && rows.length > 0;
  const showRows = rows.length > 0 && (ended === null || open);

  const list = showRows && (
    <div id={listId} className="px-4 pt-0.5 pb-3 max-sm:px-3">
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
      {onSeePlan !== undefined && (
        <button type="button" className={cn(QUIET_CONTROL_CLASS, "mt-2", WORDS_INDENT)} onClick={onSeePlan}>
          See plan
        </button>
      )}
    </div>
  );

  return (
    <Card role="region" aria-label="Analysis run" className="@container">
      {/* The header's words for a screen reader, announced as they change;
          the ticking clock stays out of it. */}
      <p role="status" aria-live="polite" className="sr-only">
        {scrub(words)}
      </p>
      <div
        data-testid="trace-header"
        className={cn("px-4 pt-3 pb-2.5 max-sm:px-3", showRows && "border-b border-line")}
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
            className={cn(QUIET_CONTROL_CLASS, "mt-0.5 inline-flex items-center gap-1", WORDS_INDENT)}
          >
            {/* The conversation surfaces' chevron (one stroke family), turning
                down as the steps open. */}
            <ChevronIcon
              size={12}
              className={cn("-ml-0.5 shrink-0 transition-transform duration-200 ease-[var(--ease-out-strong)]", open && "rotate-90")}
            />
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
 * as a run that ended in front of you, folded to its top line (owner, round
 * 8): its mark, its status word in the label style and its wall time. It has
 * no step list, so no "Show steps", and no link (annex § The run trace). The
 * words are the ones its own walk ended with ("Report ready", "The longlist
 * is ready", "Stopped", "Failed"), so every run reads alike.
 */
export function PastRunLine({ run, capability }: { run: TaskAgentThreadRun; capability?: string | null }) {
  const status = run.status as RunStatus;
  const ended = endedLine(status, walkKind(capability, [], run.purpose));
  const fallback = RUN_BLOCK_STATUS[run.status] ?? run.status;
  const words = ended?.words ?? fallback.charAt(0).toUpperCase() + fallback.slice(1);
  const tone: StatusTone = ended?.tone ?? (status === "paused" ? "paused" : "running");
  const time =
    run.ended_at == null ? "" : formatMinutes(elapsedSeconds(run.started_at, run.ended_at, Date.parse(run.ended_at)));
  // Not a landmark: the thread's one "Analysis run" region is the run the
  // stream follows.
  return (
    <Card data-testid="past-run" className="@container">
      <div className="px-4 pt-3 pb-2.5 max-sm:px-3">
        <TopLine
          mark={<StatusMark tone={tone} />}
          label={scrub(words)}
          rest=""
          time={time}
          link={null}
          labelKey="past"
          rise={false}
        />
      </div>
    </Card>
  );
}

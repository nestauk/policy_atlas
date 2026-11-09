import { useId, useState } from "react";
import { useParams } from "react-router";

import { useDecisions, useTaskAgentTurns, useTask, useToc } from "../api/queries";
import { formatDate } from "../lib/dates";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { LIFECYCLE_LABELS } from "../lib/vocabulary";
import { StatusMark } from "../ui/brand/Card";
import { QUIET_CONTROL_CLASS } from "../ui/brand/inlineActions";
import { LABEL_CLASS } from "../ui/brand/label";
import { cn } from "../ui/brand/cn";
import { ReauthRedirect } from "../ui/feedback";
import { Collapse } from "../ui/motion/Collapse";
import {
  groupByDay,
  mergeHistory,
  type HistoryEntry,
  type HistoryRun,
} from "./historyPresentation";
import { isToc } from "./scopingActivity";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";
import { ListEmpty, ListError } from "../ui/brand/list/ListStates";
import { DisclosureChevron } from "../ui/brand/Disclosure";
import { UndoToast, useTocEditor, type Editor } from "./toc/Editing";

const PAGE_SIZE = 200;

/** The list's frame: Paper, a Line 2 hairline. Nothing inside needs
 *  clipping, so a row's focus ring shows whole (H9). */
const FRAME_CLASS = "border border-line-2 bg-paper";

/**
 * One row's grid (H1, H4): the time in a 3.5 rem column, the sentence, the
 * chevron. Below `md` the time sits over the sentence, which takes the full
 * width, and the chevron stays top-right.
 */
const ROW_GRID =
  "grid items-baseline gap-x-4 px-4 " +
  "grid-cols-[3.5rem_minmax(0,1fr)_auto] [grid-template-areas:'time_text_mark'] " +
  "max-md:grid-cols-[minmax(0,1fr)_auto] max-md:gap-y-1 max-md:[grid-template-areas:'time_mark'_'text_text']";

/** Detail and steps start under the sentence, not under the time (H10). */
const SENTENCE_INDENT = "md:pl-[5.5rem]";

/** A run's steps hang on a Line 2 hairline spine in the sentence column
 *  (the run trace's spine), so they read as the run's, not as rows of their
 *  own; below `md` the spine runs at the row's left edge. */
const STEP_SPINE =
  "relative before:absolute before:inset-y-0 before:left-[5.5rem] before:w-px before:bg-line-2 " +
  "max-md:before:left-4";

/** A disclosure row: hover and focus inside the frame (DESIGN.md § The Focus Rule). */
const DISCLOSURE_CLASS =
  "group w-full cursor-pointer text-left transition-colors duration-150 ease-[ease] hover:bg-blue-tint-2 " +
  "focus-visible:-outline-offset-2";

/**
 * History: the whole task, in the order it happened.
 *
 * The decision log started at plan approval, which left out the question that
 * began the work and the conversation that shaped the plan. Both are merged
 * in here, so they appear above the run events rather than nowhere. Rows are
 * grouped by day, each run folds to its outcome line, and every sentence
 * names who acted (round 10). A theory of change's edits are merged in too,
 * with Undo for an editor (task 054).
 */
export function HistoryView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const decisions = useDecisions(taskId, { page_size: PAGE_SIZE });
  const turns = useTaskAgentTurns(taskId, { page_size: PAGE_SIZE });
  const toc = useToc(isToc(task.data) ? taskId : "");
  // Only an editor reads a theory's edits: the list names people.
  const { editor, toast, dismissToast, undoLast, error: editError, history: edits } = useTocEditor(
    taskId,
    toc.data?.can_edit === true,
  );
  useDocumentTitle(task.data?.name, LIFECYCLE_LABELS.history);
  const headingId = useId();

  // Rows only once both reads have landed (H8): a half list beside the
  // skeleton, or a partial list under an error, would present part of the
  // record as the whole of it.
  const isError = decisions.isError || turns.isError;
  const isPending = !isError && (decisions.isPending || turns.isPending);

  if (isError && errorCode(decisions.error ?? turns.error) === "unauthenticated") {
    return <ReauthRedirect />;
  }

  const items =
    isPending || isError
      ? []
      : mergeHistory(
          decisions.data?.data,
          turns.data?.data,
          {
            isOwner: task.data?.is_owner ?? true,
            ownerName: task.data?.owner_display ?? null,
            capability: task.data?.capability,
          },
          edits,
        );
  const days = groupByDay(items);

  return (
    <main aria-labelledby={headingId} className={`${LIFECYCLE_PAGE_CLASS} py-8`}>
      <h1 id={headingId} className="sr-only">
        {LIFECYCLE_LABELS.history}
      </h1>

      {isPending && <HistorySkeleton />}

      {isError && (
        <ListError
          actionLabel="Try again"
          onRetry={() => {
            void decisions.refetch();
            void turns.refetch();
          }}
        >
          The history couldn't be loaded.
        </ListError>
      )}

      {!isPending && !isError && days.length === 0 && (
        <ListEmpty label="Nothing yet.">Your question and what follows will be listed here.</ListEmpty>
      )}

      {editError !== null && (
        <p role="alert" className="mb-2 text-body text-red">
          {editError}
        </p>
      )}

      {days.map((day) => (
        <section key={day.key} aria-labelledby={`history-day-${day.key}`} className="mt-4 first-of-type:mt-0">
          {/* The day heading stays at the top of the pane while its rows
              scroll under it, from md up (H4). */}
          <h2
            id={`history-day-${day.key}`}
            className="z-10 bg-ground pt-2 pb-2 text-meta font-semibold text-navy md:sticky md:top-0"
          >
            {day.heading}
          </h2>
          <ol aria-labelledby={`history-day-${day.key}`} className={FRAME_CLASS}>
            {day.items.map((item) => (
              <li key={item.id} className="border-b border-line last:border-b-0">
                {item.kind === "run" ? <RunRow run={item} /> : <EntryRow entry={item} editor={editor} />}
              </li>
            ))}
          </ol>
        </section>
      ))}
      {toast !== null && <UndoToast text={toast} onUndo={undoLast} onClose={dismissToast} />}
    </main>
  );
}

/** The time cell: absolute local time, the whole timestamp on hover and in
 *  `dateTime` (H4). */
function RowTime({ at, className }: { at: string; className?: string }) {
  return (
    <time
      dateTime={at}
      title={`${formatDate(at, "long")} at ${formatDate(at, "time")}`}
      className={cn("text-meta tabular-nums text-grey [grid-area:time]", className)}
    >
      {formatDate(at, "time")}
    </time>
  );
}

/** The sentence, with the red mark before a failure (H5) and a scope edit's
 *  lines under it. Spans, so it can sit inside a disclosure button. */
function Sentence({
  item,
  className,
}: {
  item: Pick<HistoryEntry, "sentence" | "lines" | "failed">;
  className?: string;
}) {
  return (
    <span className={cn("min-w-0 text-body text-ink [grid-area:text]", className)}>
      {item.failed && <StatusMark tone="failed" className="mr-2 align-middle" />}
      {scrub(item.sentence)}
      {(item.lines ?? []).map((line, index) => (
        <span key={index} className="block">
          {scrub(line)}
        </span>
      ))}
    </span>
  );
}

/**
 * One recorded event. A row with something behind it (the Task Agent's reply,
 * a step's counts) is a disclosure; a row without is plain text in its list
 * item, not a disabled button (H9).
 */
function EntryRow({ entry, step = false, editor }: { entry: HistoryEntry; step?: boolean; editor?: Editor }) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  // A run's step: a tighter row on the run's spine, its words indented off it.
  const padding = step ? cn("py-1.5", STEP_SPINE) : "py-3";
  const timeClass = step ? "max-md:pl-4" : undefined;
  const textClass = step ? "pl-4" : undefined;
  const details = entry.details ?? [];

  if (details.length === 0) {
    return (
      <div className={cn(ROW_GRID, padding)}>
        <RowTime at={entry.at} className={timeClass} />
        <Sentence item={entry} className={textClass} />
        {/* A theory-of-change edit the reader may undo (task 054). */}
        {editor !== undefined && entry.undoEventId !== undefined && (
          <button
            type="button"
            disabled={editor.busy}
            onClick={() => editor.run({ kind: "undo", eventId: entry.undoEventId as string }, "Undid a change")}
            className="cursor-pointer text-body font-bold text-blue [grid-area:mark] hover:underline disabled:cursor-default disabled:text-grey"
          >
            Undo
          </button>
        )}
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={open ? detailsId : undefined}
        onClick={() => setOpen((value) => !value)}
        className={cn(ROW_GRID, padding, DISCLOSURE_CLASS)}
      >
        <RowTime at={entry.at} className={timeClass} />
        <Sentence item={entry} className={textClass} />
        <DisclosureChevron open={open} className="[grid-area:mark]" />
      </button>
      <Collapse show={open} durationMs={200}>
        <dl id={detailsId} className={cn("px-4 pb-3", SENTENCE_INDENT, step && cn(STEP_SPINE, "pl-8 md:pl-[6.5rem]"))}>
          {details.map((detail) => (
            <div key={detail.label} className="mt-1 first:mt-0">
              <dt className={LABEL_CLASS}>{detail.label}</dt>
              <dd className="mt-1 max-w-[44em] whitespace-pre-wrap text-body text-ink">{scrub(detail.value)}</dd>
            </div>
          ))}
        </dl>
      </Collapse>
    </>
  );
}

/**
 * One run, folded to its outcome and time, its steps behind "Show steps"
 * with the conversation surfaces' chevron: the run trace's ended card's
 * vocabulary (H7). The steps open by their height and opacity over 200 ms,
 * the chevron's time; a cut under reduced motion.
 */
function RunRow({ run }: { run: HistoryRun }) {
  const [open, setOpen] = useState(false);
  const stepsId = useId();
  return (
    <>
      <div className={cn(ROW_GRID, "py-3")}>
        <RowTime at={run.at} />
        <span className="min-w-0 [grid-area:text]">
          <Sentence item={run} />
          <button
            type="button"
            aria-expanded={open}
            aria-controls={open ? stepsId : undefined}
            onClick={() => setOpen((value) => !value)}
            className={cn(QUIET_CONTROL_CLASS, "group mt-0.5 flex items-center gap-1 text-meta")}
          >
            <DisclosureChevron open={open} className="-ml-0.5" />
            {open ? "Hide steps" : "Show steps"}
          </button>
        </span>
      </div>
      <Collapse show={open} durationMs={200}>
        <ol id={stepsId} aria-label="Run steps" className="pb-2">
          {run.steps.map((step) => (
            <li key={step.id}>
              <EntryRow entry={step} step />
            </li>
          ))}
        </ol>
      </Collapse>
    </>
  );
}

/**
 * The history loading (H8): the list's own shape, a day heading's bar over
 * the frame and five 48 px rows, each a time bar and a sentence bar, so the
 * rows arrive into it. The bars breathe, and hold still under reduced motion.
 */
function HistorySkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the history">
      <div aria-hidden="true" className="flex h-[2.3125rem] items-center">
        <span className="placeholder-bar h-2.5 w-28" />
      </div>
      <ul aria-hidden="true" className={FRAME_CLASS}>
        {["w-3/5", "w-2/5", "w-1/2", "w-3/4", "w-1/3"].map((width, index) => (
          <li
            key={index}
            className={cn(ROW_GRID, "h-12 items-center border-b border-line last:border-b-0 max-md:h-[4.5rem] max-md:content-center")}
          >
            <span className="placeholder-bar h-2.5 w-10 [grid-area:time]" />
            <span className={cn("placeholder-bar h-2.5 [grid-area:text]", width)} />
          </li>
        ))}
      </ul>
    </div>
  );
}


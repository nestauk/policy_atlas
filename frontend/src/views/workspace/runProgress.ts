import type { PlanDraft, RunStatus, StageEntry, StageLiveness, TaskAgentThreadRun } from "../../store";
import { isScoping } from "../scopingActivity";
import { formatCount } from "../../lib/format";
import { READY_WORDS, taskStatusWord, type WalkKind } from "../../ui/brand/taskStatus";

/** How a step row reads: done, in progress, still to come, or ended badly. */
export type RowState = "done" | "progress" | "upcoming" | "failed" | "skipped";

/**
 * One row of the run trace's step list (task 058, D5): one plan step, or
 * several stages the server says share a row ("Searching and screening" is
 * search plus screen; "Classifying" is classify plus appraise).
 */
export type CardRow = {
  /** The server's row key from `PlanStep.row`, or the frame label for a row
   *  built from stage frames alone. Unique in the trace. */
  key: string;
  /** The server's label for the row. */
  label: string;
  /** The row's stage keys, in plan order (or arrival order). */
  stages: string[];
  /** The row's stage frames, in arrival order. */
  entries: StageEntry[];
  state: RowState;
};

const LONGLIST_STAGES = new Set([
  "inherit",
  "suggest",
  "option_searches",
  "extract_interventions",
  "longlist",
  "option_profile",
  "constrain",
  "theme",
]);

/** A theory of change's walk kinds as the run read names them
 *  (`RunOut.toc_walk`, task 054, S3). */
const TOC_WALK_KINDS: Record<string, WalkKind> = {
  draft: "toc_draft",
  read: "toc_read",
  check: "toc_check",
  report_update: "toc_report_update",
};

/** Whether a walk kind is one of a theory of change's. */
export function isTocWalk(kind: WalkKind): boolean {
  return kind.startsWith("toc_");
}

/** Decide the walk kind from the task's capability and the run's own
 *  purpose (task 045, A7/A8); the stages decide only when the purpose is not
 *  known yet. A theory of change's walk follows the run read's `toc_walk`
 *  (task 054, S3); before the read has it, its first step says: an upload's
 *  read reports `toc_read`, a draft `toc_draft`, and anything else is a
 *  check. */
export function walkKind(
  capability: string | null | undefined,
  stages: StageEntry[],
  purpose?: string | null,
  tocWalk?: string | null,
): WalkKind {
  if (capability === "theory_of_change") {
    const named = tocWalk != null ? TOC_WALK_KINDS[tocWalk] : undefined;
    if (named !== undefined) return named;
    if (stages.some((entry) => entry.stage === "toc_read")) return "toc_read";
    if (stages.some((entry) => entry.stage === "toc_draft")) return "toc_draft";
    return "toc_check";
  }
  if (!isScoping({ capability })) return "evidence_search";
  if (purpose === "targeted") return "option_search";
  if (purpose === "longlist" || purpose === "baseline" || purpose === "shortlist") return purpose;
  // The longlist walk ends in a shortlist step; a walk with only that step
  // is the standalone shortlist walk.
  if (stages.some((entry) => LONGLIST_STAGES.has(entry.stage))) return "longlist";
  return stages.some((entry) => entry.stage === "shortlist") ? "shortlist" : "baseline";
}

/** The Result tab, opened on the view this walk produced. */
export function resultHref(taskId: string, kind: WalkKind): string {
  if (kind === "longlist" || kind === "option_search") return `/tasks/${taskId}/result?view=longlist`;
  if (kind === "shortlist") return `/tasks/${taskId}/result?view=shortlist`;
  if (kind === "baseline") return `/tasks/${taskId}/result?view=baseline`;
  return `/tasks/${taskId}/result`;
}

/** Whether a run has finished with something to read (`degraded` opens the
 *  report like `succeeded`; task 058, N14). */
export function isFinished(status: RunStatus | undefined): boolean {
  return status === "succeeded" || status === "degraded";
}

/**
 * A duration in the trace's words: `45 s`, `6 min 12 s`, `1 h 4 min`. Elapsed
 * time only, never a countdown (annex § Voice rules).
 *
 * Args:
 *   seconds: The duration.
 *   withSeconds: Keep the seconds after the minutes (`6 min 12 s`, the
 *     default); false gives the duration to the minute (`6 min`), for the
 *     folded trace line, History and the task list. Under a minute it is
 *     always seconds, and from an hour up always hours and minutes.
 *
 * Returns:
 *   The duration as the reader sees it.
 */
export function formatElapsed(seconds: number, { withSeconds = true }: { withSeconds?: boolean } = {}): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total} s`;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return minutes === 0 ? `${hours} h` : `${hours} h ${minutes} min`;
  const rest = total % 60;
  return rest === 0 || !withSeconds ? `${minutes} min` : `${minutes} min ${rest} s`;
}

/**
 * Seconds between start and end. When `endedAt` is missing, `nowMs` is the
 * live clock — callers must freeze `nowMs` (or pass `endedAt`) once the run
 * is no longer ticking.
 */
export function elapsedSeconds(
  startedAt: string | undefined,
  endedAt: string | undefined,
  nowMs: number,
): number {
  if (startedAt === undefined || startedAt === "") return 0;
  const started = Date.parse(startedAt);
  if (Number.isNaN(started)) return 0;
  const ended =
    endedAt !== undefined && endedAt !== "" ? Date.parse(endedAt) : Number.NaN;
  const endMs = Number.isNaN(ended) ? nowMs : ended;
  return Math.max(0, (endMs - started) / 1000);
}

/**
 * The trace's rows: the plan's steps grouped by the server's `row` key, with
 * the stage frames laid over them (task 058, D5, N17). Labels are the
 * server's. Upcoming rows come from the plan only, so a walk with no plan
 * steps on the stream (the scoping walks) builds its rows from the frames as
 * they arrive and shows none still to come. A stage the plan does not name
 * joins the row whose label it shares, else gets its own row.
 */
export function cardRows(
  stages: StageEntry[],
  plan: PlanDraft | null | undefined,
  status?: RunStatus,
): CardRow[] {
  const rows: CardRow[] = [];
  const byKey = new Map<string, CardRow>();
  const rowOfStage = new Map<string, CardRow>();
  const planned = new Set<string>();

  for (const step of plan?.steps ?? []) {
    let row = byKey.get(step.row);
    if (row === undefined) {
      row = { key: step.row, label: step.label, stages: [], entries: [], state: "upcoming" };
      byKey.set(step.row, row);
      rows.push(row);
    }
    if (!row.stages.includes(step.stage)) row.stages.push(step.stage);
    rowOfStage.set(step.stage, row);
    planned.add(step.stage);
  }

  for (const entry of stages) {
    let row = rowOfStage.get(entry.stage) ?? rows.find((candidate) => candidate.label === entry.label);
    if (row === undefined) {
      row = { key: `stage:${entry.stage}`, label: entry.label, stages: [], entries: [], state: "upcoming" };
      byKey.set(row.key, row);
      rows.push(row);
    }
    if (!row.stages.includes(entry.stage)) row.stages.push(entry.stage);
    rowOfStage.set(entry.stage, row);
    row.entries.push(entry);
  }

  const live = status === "running" || status === "paused";
  const lastActive = rows.reduce((last, row, index) => (row.entries.length > 0 ? index : last), -1);
  return rows.map((row, index) => ({ ...row, state: rowState(row, index, lastActive, planned, live) }));
}

function rowState(
  row: CardRow,
  index: number,
  lastActive: number,
  planned: ReadonlySet<string>,
  live: boolean,
): RowState {
  if (row.entries.length === 0) return "upcoming";
  if (row.entries.some((entry) => entry.status === "started")) return "progress";
  if (row.entries.some((entry) => entry.status === "failed")) return "failed";
  if (row.entries.every((entry) => entry.status === "skipped")) return "skipped";
  // Between two stages of one row (search done, screening about to start)
  // the row is still the one in progress.
  const seen = new Set<string>(row.entries.map((entry) => entry.stage));
  const waiting = row.stages.some((stage) => planned.has(stage) && !seen.has(stage));
  return waiting && live && index === lastActive ? "progress" : "done";
}

/**
 * A thread run's steps (`RunOut.stages`, owner round 11: what
 * `stage.started` and `stage.completed` carried, read back from the event
 * log) as the trace's stage entries, for `cardRows`, so an earlier walk's
 * card folds its steps as the ended card does. Empty when the read carries
 * none. A step's wall time is the server's `seconds`, else its end less its
 * start.
 */
export function threadRunStages(run: TaskAgentThreadRun): StageEntry[] {
  return (run.stages ?? []).map((step) => {
    const startedAt = step.started_at ?? "";
    const start = parsed(startedAt);
    const end = parsed(step.ended_at ?? undefined);
    const seconds =
      typeof step.seconds === "number" ? step.seconds : start !== null && end !== null ? Math.max(0, (end - start) / 1000) : null;
    const entry: StageEntry = {
      stage: step.stage,
      label: step.label,
      status: step.status,
      startedAt,
      seconds,
      summary: step.summary ?? {},
    };
    if (step.counts !== undefined) entry.counts = step.counts;
    return entry;
  });
}

/** The row being worked on now, else the last row that has run. */
export function currentRow(rows: CardRow[]): CardRow | null {
  return (
    rows.find((row) => row.state === "progress") ??
    [...rows].reverse().find((row) => row.entries.length > 0) ??
    null
  );
}

/** The counts a done row shows: `312 found`, `118 relevant`. A stage that ran
 *  twice (a second search pass) shows its latest counts. */
export function rowCounts(row: CardRow): string[] {
  return row.stages.flatMap((stage) => {
    const latest = [...row.entries].reverse().find((entry) => entry.stage === stage);
    // The server names the counts and their nouns on the frame (task 058, N17).
    return (latest?.counts ?? []).map(({ value, noun }) => `${formatCount(value)} ${noun}`);
  });
}

function parsed(at: string | undefined): number | null {
  if (at === undefined || at === "") return null;
  const ms = Date.parse(at);
  return Number.isNaN(ms) ? null : ms;
}

/**
 * A row's wall time in seconds. A done row with one stage frame shows that
 * stage's `seconds`; a row that ran several (search then screen) spans from
 * the first frame's start to the last frame's end. An in-progress row counts
 * up from its first frame's start. `null` when the frames do not say.
 */
export function rowSeconds(row: CardRow, nowMs: number): number | null {
  const first = row.entries[0];
  const last = row.entries[row.entries.length - 1];
  if (first === undefined || last === undefined) return null;
  const start = parsed(first.startedAt);
  if (row.state === "progress") return start === null ? null : Math.max(0, (nowMs - start) / 1000);
  if (row.entries.length === 1) return typeof last.seconds === "number" ? last.seconds : null;
  const lastStart = parsed(last.startedAt);
  if (start !== null && lastStart !== null && typeof last.seconds === "number") {
    return Math.max(0, (lastStart + last.seconds * 1000 - start) / 1000);
  }
  const known = row.entries.map((entry) => entry.seconds).filter((value): value is number => typeof value === "number");
  return known.length > 0 ? known.reduce((sum, value) => sum + value, 0) : null;
}

/** The newest tick among a row's stages: what the model is doing on it now. */
export function rowLiveness(
  row: CardRow,
  liveness: Record<string, StageLiveness> | undefined,
): StageLiveness | undefined {
  let newest: StageLiveness | undefined;
  for (const stage of row.stages) {
    const tick = liveness?.[stage];
    if (tick === undefined) continue;
    if (newest === undefined || (parsed(tick.occurredAt) ?? 0) >= (parsed(newest.occurredAt) ?? 0)) newest = tick;
  }
  return newest;
}

/** The longlist walk's steps whose done rows point at the longlist they
 *  made (owner, round 12). */
const LONGLIST_MADE = new Set(["suggest", "longlist", "option_profile", "constrain", "theme"]);

/**
 * Where a row points (annex § The running card, kept by the trace).
 *
 * A done row: the Sources table after searching or screening, the themes
 * after mapping, the landscape after classifying (at once: lead, round 8,
 * superseding round 4's "after Mapping"), the findings once there are any,
 * the report after writing. Shortlisting and reading have nowhere to point.
 *
 * The step in progress points where its output is landing (owner, round 8):
 * Searching and Screening to Sources, Classifying to the landscape, Mapping
 * to the themes, Writing to the report.
 *
 * A scoping walk links too (round 10, lead ruling D4; owner, round 11).
 * The baseline walk maps as an Evidence search does, its Writing row
 * pointing at the baseline ("Baseline →"). A longlist walk searches,
 * screens and classifies as an Evidence search does, so those rows take the
 * Evidence search's links, running and done: Searching and Screening to
 * Sources, Classifying to the landscape. Its step in progress from
 * Suggesting options on points at the longlist being built ("Longlist →",
 * the Result tab's default view). Done, the steps that make the longlist
 * (Suggesting options, Clustering, Estimating, Applying your constraints,
 * Grouping into themes) point at it too, and Shortlisting at the shortlist
 * page ("Shortlist →"; owner, round 12, replacing round 11's done rows that
 * pointed nowhere). Done, Searching for each option and Reading the
 * abstracts point at the Sources table, where the option searches' results
 * are (lead, round 12). Reading the linked search links nothing. The shortlist
 * walk's done Shortlisting row points at the shortlist page as well; an
 * added option's search links nothing.
 */
export function rowLink(
  row: CardRow,
  // The other rows: no link waits on another step since round 8; kept so
  // callers need not change.
  _rows: CardRow[],
  taskId: string,
  kind: WalkKind,
  hasFindings: boolean,
): { href: string; label: string } | null {
  const has = (stage: string) => row.stages.includes(stage);
  const searched = has("acquire") || has("screen");
  const classified = has("classify") || has("appraise");
  if (kind === "longlist" || kind === "shortlist") {
    if (row.state !== "progress" && row.state !== "done") return null;
    const longlist = { href: `/tasks/${taskId}/result`, label: "Longlist" };
    if (row.state === "done" && has("shortlist")) {
      return { href: `/tasks/${taskId}/result?view=shortlist`, label: "Shortlist" };
    }
    if (kind === "shortlist") return null;
    if (searched) return { href: `/tasks/${taskId}/sources/all`, label: "Sources" };
    if (classified) return { href: `/tasks/${taskId}/sources/landscape`, label: "Landscape" };
    if (row.state === "done") {
      // The option searches' results are in the Sources table (lead, round 12).
      if (has("option_searches") || has("extract_interventions")) {
        return { href: `/tasks/${taskId}/sources/all`, label: "Sources" };
      }
      return row.stages.some((stage) => LONGLIST_MADE.has(stage)) ? longlist : null;
    }
    return row.stages.every((stage) => stage === "inherit") ? null : longlist;
  }
  if (isTocWalk(kind)) return tocRowLink(row, taskId);
  if (kind !== "evidence_search" && kind !== "baseline") return null;
  const written =
    kind === "baseline"
      ? { href: `/tasks/${taskId}/result?view=baseline`, label: "Baseline" }
      : { href: `/tasks/${taskId}/result`, label: "Report" };
  if (row.state === "progress") {
    if (searched) return { href: `/tasks/${taskId}/sources/all`, label: "Sources" };
    if (classified) return { href: `/tasks/${taskId}/sources/landscape`, label: "Landscape" };
    if (has("characterise")) return { href: `/tasks/${taskId}/sources`, label: "Themes" };
    if (has("synthesise")) return written;
    return null;
  }
  if (row.state !== "done") return null;
  if (searched) return { href: `/tasks/${taskId}/sources/all`, label: "Sources" };
  // Mapping's output is the themes (the Sources tab's first view; owner, polish round 2).
  if (has("characterise")) return { href: `/tasks/${taskId}/sources`, label: "Themes" };
  if (classified) return { href: `/tasks/${taskId}/sources/landscape`, label: "Landscape" };
  if (has("extract") && hasFindings) return { href: `/tasks/${taskId}/sources/findings`, label: "Findings" };
  if (has("synthesise")) return written;
  return null;
}

/** A theory of change's steps whose rows point at the theory on the Result
 *  tab, and those that point at the Sources table (task 054, § 8: the
 *  links of the mock brief's table). Merging, the figures and the titles
 *  point nowhere. */
const TOC_THEORY_STAGES = new Set(["toc_draft", "toc_read", "toc_discover", "toc_judge", "toc_search_again", "toc_retry_searches", "toc_choose"]);
const TOC_SOURCES_STAGES = new Set(["toc_item_searches", "toc_select", "toc_search_new", "toc_new_link_searches", "classify", "appraise"]);

/** Where a theory of change's row points, running and done: "Theory →",
 *  "Sources →" or "Report →". */
function tocRowLink(row: CardRow, taskId: string): { href: string; label: string } | null {
  if (row.state !== "progress" && row.state !== "done") return null;
  const has = (stages: ReadonlySet<string>) => row.stages.some((stage) => stages.has(stage));
  if (has(TOC_SOURCES_STAGES)) return { href: `/tasks/${taskId}/sources/all`, label: "Sources" };
  if (has(TOC_THEORY_STAGES)) return { href: `/tasks/${taskId}/result`, label: "Theory" };
  if (row.stages.includes("toc_report")) return { href: `/tasks/${taskId}/result`, label: "Report" };
  return null;
}

/** What the trace's header says the step in progress is doing: the writer's
 *  section while writing ("Section 3 of 7 · Costs and funding"), else the
 *  activity line, in the server's words. */
export function rowDetail(tick: StageLiveness | undefined): string | null {
  if (tick === undefined) return null;
  const section = tick.section?.trim();
  if (section) return section;
  const activity = tick.activity.trim();
  return activity === "" ? null : activity;
}

/** The words a step in progress reads after two minutes of silence (N5). */
export const STALLED_LINE = "Still working on this step";

/** The trace's header words while the run is live or paused (annex § The run
 *  trace): the current row's label and what it is doing now; paused, the
 *  task's status words, naming who the run waits on (`taskStatusWord`).
 *  Every label is the server's; the client adds only the separators.
 *
 * Args:
 *   row: The row in progress, else the last that ran; null before any frame.
 *   detail: The row's activity (`rowDetail`), or null.
 *   state: `stalled` once two minutes pass with no tick.
 *   isOwner: The owner is told the run waits on them.
 *   ownerName: The owner's display name, which a colleague is told.
 *
 * Returns:
 *   The words, without the elapsed time.
 */
export function traceWords(
  row: CardRow | null,
  detail: string | null,
  state: "live" | "stalled" | "paused",
  isOwner: boolean,
  ownerName: string | null = null,
): string {
  if (state === "paused") return taskStatusWord("paused", { isOwner, ownerName });
  const doing = state === "stalled" ? STALLED_LINE : detail;
  // A step verb that repeats the row's label ("Classifying · Classifying")
  // says nothing twice (owner round 11, via the mock's scoping walk).
  const detailWords = doing !== null && doing.trim().toLowerCase() === (row?.label ?? "").trim().toLowerCase() ? null : doing;
  return [row?.label, detailWords].filter((part): part is string => Boolean(part)).join(" · ");
}

/** A degraded shortlist walk's ended words: it proposed nothing. */
export const NO_SHORTLIST = "Policy Atlas could not propose a shortlist. Your places are unchanged.";

/** "1 step", "6 steps". */
export function stepCount(count: number): string {
  return count === 1 ? "1 step" : `${formatCount(count)} steps`;
}

/**
 * How a run that has ended reads, folded to one line (annex § The run trace):
 * the finish words per walk kind with the Result tab as its one link, or
 * the status word ("Stopped", "Failed") with no link. A degraded shortlist walk ended with
 * no shortlist, so it says so in the existing sentence (lead ruling,
 * 2026-11-05). Null while the run has not ended.
 */
export function endedLine(
  status: RunStatus | undefined,
  kind: WalkKind,
): { words: string; tone: "complete" | "failed"; link: boolean } | null {
  if (kind === "shortlist" && status === "degraded") return { words: NO_SHORTLIST, tone: "failed", link: false };
  if (isFinished(status)) return { words: READY_WORDS[kind], tone: "complete", link: true };
  if (status === "failed" || status === "aborted" || status === "interrupted") {
    return { words: taskStatusWord(status), tone: "failed", link: false };
  }
  return null;
}

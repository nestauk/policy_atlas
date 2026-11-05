import { LIFECYCLE_LABELS } from "../../lib/vocabulary";
import type { PlanDraft, RunStatus, StageEntry, StageLiveness } from "../../store";
import { isScoping } from "../scopingActivity";

type RunningCardTone = "running" | "paused" | "done" | "stopped";

/** How a card row reads: done, in progress, still to come, or ended badly. */
export type RowState = "done" | "progress" | "upcoming" | "failed" | "skipped";

/**
 * One row of the running card (task 058, D5, direction C): one plan step, or
 * several stages the server says share a row ("Searching and screening" is
 * search plus screen; "Classifying" is classify plus appraise).
 */
export type CardRow = {
  /** The server's row key from `PlanStep.row`, or the frame label for a row
   *  built from stage frames alone. Unique on the card. */
  key: string;
  /** The server's label for the row. */
  label: string;
  /** The row's stage keys, in plan order (or arrival order). */
  stages: string[];
  /** The row's stage frames, in arrival order. */
  entries: StageEntry[];
  state: RowState;
};

type StageSignpost = { href: string; label: string; message: string };

/** Chat-thread primary CTA — same size as Review the plan / Start search. */
export const CHAT_PRIMARY_CTA_CLASS =
  "cutout inline-block bg-blue px-6 py-3.5 text-body font-bold text-white";

/** What kind of walk a run card describes (task 045): an Evidence search, a
 *  scoping task's baseline walk, its longlist walk, or an added option's own
 *  search. The words on the card and the finished notice follow it — "the
 *  evidence base is ready" is wrong for a longlist. */
export type WalkKind = "evidence_search" | "baseline" | "longlist" | "option_search" | "shortlist";

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

/** Decide the walk kind from the task's capability and the run's own
 *  purpose (task 045, A7/A8); the stages decide only when the purpose is not
 *  known yet. */
export function walkKind(
  capability: string | null | undefined,
  stages: StageEntry[],
  purpose?: string | null,
): WalkKind {
  if (!isScoping({ capability })) return "evidence_search";
  if (purpose === "targeted") return "option_search";
  if (purpose === "longlist" || purpose === "baseline" || purpose === "shortlist") return purpose;
  // The longlist walk ends in a shortlist step; a walk with only that step
  // is the standalone shortlist walk.
  if (stages.some((entry) => LONGLIST_STAGES.has(entry.stage))) return "longlist";
  return stages.some((entry) => entry.stage === "shortlist") ? "shortlist" : "baseline";
}

/** The run strip's finished words, before its one link (annex § scene 7;
 *  "the capability's wording" for the scoping walks). */
export const READY_WORDS: Record<WalkKind, string> = {
  evidence_search: "Report ready",
  baseline: "The baseline is ready",
  longlist: "The longlist is ready",
  option_search: "The option's search is done",
  shortlist: "The shortlist is proposed",
};

const RESULTS_LABEL: Record<WalkKind, string> = {
  evidence_search: "Read the report",
  baseline: "Read the baseline",
  longlist: "Read the longlist",
  option_search: "Read the longlist",
  shortlist: "Read the shortlist",
};

/** The finished notice, split around the Result-tab link it carries. */
export const FINISHED_NOTICE: Record<WalkKind, { before: string; after: string }> = {
  evidence_search: { before: "Evidence search is finished. You can read the report in the", after: "tab." },
  baseline: { before: "The baseline is written. Read it in the", after: "tab." },
  longlist: { before: "The longlist is built. Open it in the", after: "tab." },
  option_search: { before: "The option's search is done. See it in the", after: "tab." },
  shortlist: { before: "Policy Atlas has proposed a shortlist. Open it in the", after: "tab." },
};

/** The finished notice for this walk and status: a degraded shortlist walk
 *  means the proposal failed (its one step is non-spine), so it says so. */
export function finishedNotice(kind: WalkKind, status: RunStatus | undefined): { before: string; after: string } {
  if (kind === "shortlist" && status === "degraded") {
    return {
      before: "Policy Atlas could not propose a shortlist. Your places are unchanged. Open the",
      after: "tab.",
    };
  }
  return FINISHED_NOTICE[kind];
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

/** The card's top-line word and tone for a run status. */
export function runningCardCopy(
  status: RunStatus | undefined,
  kind: WalkKind = "evidence_search",
): { tone: RunningCardTone; eyebrow: string } {
  if (status === "paused") return { tone: "paused", eyebrow: "PAUSED" };
  if (kind === "shortlist" && status === "degraded") return { tone: "stopped", eyebrow: "STOPPED" };
  if (isFinished(status)) return { tone: "done", eyebrow: "DONE" };
  if (status === "failed" || status === "aborted" || status === "interrupted") {
    return { tone: "stopped", eyebrow: "STOPPED" };
  }
  return { tone: "running", eyebrow: "RUNNING" };
}

/**
 * A duration in the card's words: `45 s`, `6 min 12 s`, `1 h 4 min`. Elapsed
 * time only, never a countdown (annex § Voice rules).
 */
export function formatElapsed(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total} s`;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return minutes === 0 ? `${hours} h` : `${hours} h ${minutes} min`;
  const rest = total % 60;
  return rest === 0 ? `${minutes} min` : `${minutes} min ${rest} s`;
}

/** A duration to the minute, for the run strip and the task list (`14 min`). */
export function formatMinutes(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total} s`;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return minutes === 0 ? `${hours} h` : `${hours} h ${minutes} min`;
  return `${minutes} min`;
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
 * The card's rows: the plan's steps grouped by the server's `row` key, with
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

/** The row being worked on now, else the last row that has run. */
export function currentRow(rows: CardRow[]): CardRow | null {
  return (
    rows.find((row) => row.state === "progress") ??
    [...rows].reverse().find((row) => row.entries.length > 0) ??
    null
  );
}

const COUNT_FORMAT = new Intl.NumberFormat("en-GB");

/** The counts a done row shows: `312 found`, `118 relevant`. A stage that ran
 *  twice (a second search pass) shows its latest counts. */
export function rowCounts(row: CardRow): string[] {
  return row.stages.flatMap((stage) => {
    const latest = [...row.entries].reverse().find((entry) => entry.stage === stage);
    // The server names the counts and their nouns on the frame (task 058, N17).
    return (latest?.counts ?? []).map(({ value, noun }) => `${COUNT_FORMAT.format(value)} ${noun}`);
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

/**
 * Where a done row points (annex § The running card): the Sources table after
 * searching and screening, the landscape after mapping (and after
 * categorising once mapping is done), the findings once there are any, the
 * report after writing. Shortlisting and reading have nowhere to point. Only
 * an Evidence search's rows link.
 */
export function rowLink(
  row: CardRow,
  rows: CardRow[],
  taskId: string,
  kind: WalkKind,
  hasFindings: boolean,
): { href: string; label: string } | null {
  if (kind !== "evidence_search" || row.state !== "done") return null;
  const has = (stage: string) => row.stages.includes(stage);
  const mapped = rows.some((other) => other.stages.includes("characterise") && other.state === "done");
  if (has("acquire") || has("screen")) return { href: `/tasks/${taskId}/sources/all`, label: "Sources" };
  if (has("characterise") || ((has("classify") || has("appraise")) && mapped)) {
    return { href: `/tasks/${taskId}/sources/landscape`, label: "Landscape" };
  }
  if (has("extract") && hasFindings) return { href: `/tasks/${taskId}/sources/findings`, label: "Findings" };
  if (has("synthesise")) return { href: `/tasks/${taskId}/result`, label: "Report" };
  return null;
}

/** The run strip's middle part: the writer's section while writing, else the
 *  activity line, in the server's words. */
export function rowDetail(tick: StageLiveness | undefined, options: { short?: boolean } = {}): string | null {
  if (tick === undefined) return null;
  const section = tick.section?.trim();
  // The strip's short form keeps "Section 3 of 7" and drops the title (annex scene 7).
  if (section) return options.short ? section.split(" · ")[0] : section;
  const activity = tick.activity.trim();
  return activity === "" ? null : activity;
}

/** Link to a lifecycle tab that now has something to read. */
function signpostForStage(
  stage: string,
  taskId: string,
  hasFindings: boolean,
): StageSignpost | null {
  if (stage === "acquire") {
    return {
      href: `/tasks/${taskId}/sources/all`,
      label: "Sources are ready",
      message: "Searching has finished.",
    };
  }
  if (stage === "characterise") {
    return {
      href: `/tasks/${taskId}/sources/landscape`,
      label: "The landscape is ready",
      message: "Mapping has finished.",
    };
  }
  if (stage === "extract" && hasFindings) {
    return {
      href: `/tasks/${taskId}/sources/findings`,
      label: "Findings are ready",
      message: "Findings are ready.",
    };
  }
  return null;
}

/** Chat-thread destination once the write-up exists — last word, not a stage echo. */
export function runFinishedSignpost(
  taskId: string,
  status: RunStatus | undefined,
  kind: WalkKind = "evidence_search",
): StageSignpost | null {
  if (!isFinished(status)) return null;
  const notice = finishedNotice(kind, status);
  return {
    href: resultHref(taskId, kind),
    label: LIFECYCLE_LABELS.result,
    message: `${notice.before} ${LIFECYCLE_LABELS.result} ${notice.after}`,
  };
}

/** Completed-stage signposts in timeline order, one per destination. */
export function completedSignposts(
  stages: StageEntry[],
  taskId: string,
  hasFindings: boolean,
): StageSignpost[] {
  const out: StageSignpost[] = [];
  const seen = new Set<string>();
  for (const entry of stages) {
    if (entry.status !== "completed") continue;
    const signpost = signpostForStage(entry.stage, taskId, hasFindings);
    if (signpost === null || seen.has(signpost.href)) continue;
    seen.add(signpost.href);
    out.push(signpost);
  }
  return out;
}

/** Results link once the write-up exists. */
export function resultsSignpost(
  taskId: string,
  status: RunStatus | undefined,
  kind: WalkKind = "evidence_search",
): StageSignpost | null {
  if (!isFinished(status)) return null;
  const notice = finishedNotice(kind, status);
  return {
    href: resultHref(taskId, kind),
    label: RESULTS_LABEL[kind],
    message: `${notice.before} ${LIFECYCLE_LABELS.result} ${notice.after}`,
  };
}

/** One-line collapsed status (`RUNNING · Searching and screening · 13 s`). */
export function collapsedStatusLine(
  status: RunStatus | undefined,
  rows: CardRow[],
  elapsedLabel: string,
): string {
  const { eyebrow } = runningCardCopy(status);
  const row = currentRow(rows);
  return row === null ? `${eyebrow} · ${elapsedLabel}` : `${eyebrow} · ${row.label} · ${elapsedLabel}`;
}

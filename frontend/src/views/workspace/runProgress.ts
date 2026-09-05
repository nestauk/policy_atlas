import { LIFECYCLE_LABELS } from "../../lib/vocabulary";
import type { PlanDraft, RunStatus, StageEntry, StageStatus } from "../../store";
import { timelineSummary } from "./journey/presentation";
import { stepsForAnalysisDepth, type PlanStepPreview } from "./planVocabulary";

export type RunningCardTone = "running" | "paused" | "done" | "stopped";

export type StageRow = {
  /** Unique among rows on this card — stage repeats across search rounds. */
  id: string;
  stage: string;
  label: string;
  status: StageStatus | "upcoming";
  blurb?: string;
  summary?: StageEntry["summary"];
  seconds?: number | null;
};

export type StageSignpost = { href: string; label: string; message: string };

/** Chat-thread primary CTA — same size as Review the plan / Start search. */
export const CHAT_PRIMARY_CTA_CLASS =
  "cutout inline-block bg-blue px-6 py-3.5 text-body font-bold text-white";

/** Option C running-card shell: 15% Nesta-green tint, green as the accent. */
export const RUNNING_CARD_SHELL_CLASS =
  "border-2 border-[#17A88D] bg-[#DDF2EE] text-navy";

/** Row rules on the tinted card — Nesta green at 40% opacity. */
export const RUNNING_CARD_RULE_CLASS = "border-t border-[rgba(23,168,141,0.4)]";

/** Outline CTA on the tinted running card (See plan). */
export const SEE_PLAN_CTA_CLASS =
  "inline-block cursor-pointer border-2 border-blue bg-paper px-6 py-3.5 text-body font-bold text-blue";

/** Chat-thread notice once the run has landed. */
export const RUN_FINISHED_MESSAGE =
  `Evidence search is finished. You can read the report in the ${LIFECYCLE_LABELS.result} tab.`;

/** Eyebrow and title for the in-thread running card. */
export function runningCardCopy(status: RunStatus | undefined): {
  tone: RunningCardTone;
  eyebrow: string;
  title: string;
} {
  if (status === "paused") {
    return { tone: "paused", eyebrow: "PAUSED", title: "Paused — waiting on you" };
  }
  if (status === "succeeded" || status === "degraded") {
    return { tone: "done", eyebrow: "DONE", title: "The evidence base is ready" };
  }
  if (status === "failed" || status === "aborted" || status === "interrupted") {
    return { tone: "stopped", eyebrow: "STOPPED", title: "Analysis stopped" };
  }
  return { tone: "running", eyebrow: "RUNNING", title: "Analysis running…" };
}

/** Compact elapsed-time label for the card (`13s`, `2m 4s`). */
export function formatElapsed(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds));
  if (rounded < 60) return `${rounded}s`;
  const minutes = Math.floor(rounded / 60);
  const rest = rounded % 60;
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`;
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

function vocabByStage(backendScope?: string | null): Map<string, PlanStepPreview> {
  return new Map(stepsForAnalysisDepth("deep", backendScope).map((step) => [step.stage, step]));
}

function rowFromVocab(
  step: PlanStepPreview,
  live: StageEntry | undefined,
  { label = step.label, id }: { label?: string; id: string },
): StageRow {
  return {
    id,
    stage: step.stage,
    label,
    blurb: step.blurb,
    status: live?.status ?? "upcoming",
    summary: live?.summary,
    seconds: live?.seconds,
  };
}

const SEARCH_CYCLE_STAGES = new Set(["acquire", "screen"]);

function roundIndexOf(entry: StageEntry): number {
  const value = entry.summary?.round_index;
  return typeof value === "number" && Number.isFinite(value) ? value : 1;
}

/** Screen payloads often omit `round_index`; inherit the last Searching round. */
function cycleRounds(stages: StageEntry[]): number[] {
  let lastAcquireRound = 1;
  return stages.map((entry) => {
    if (entry.stage === "acquire") {
      lastAcquireRound = roundIndexOf(entry);
      return lastAcquireRound;
    }
    if (entry.stage === "screen") {
      const explicit = entry.summary?.round_index;
      return typeof explicit === "number" && Number.isFinite(explicit)
        ? explicit
        : lastAcquireRound;
    }
    return roundIndexOf(entry);
  });
}

function cycleLabel(base: string, roundIndex: number, maxRound: number): string {
  if (maxRound <= 1) return base;
  return `${base} (Round ${roundIndex})`;
}

function nextRowId(counts: Map<string, number>, stage: string, roundIndex: number): string {
  const key = `${stage}:${roundIndex}`;
  const n = (counts.get(key) ?? 0) + 1;
  counts.set(key, n);
  return `${key}:${n}`;
}

/** Agreed plan steps with live SSE status/counts overlaid — labels from the plan panel.

Every acquire/screen SSE entry is kept so Broad/Broadest rounds do not
collapse to the last one. Ingest is omitted from Searching by the server
(unmapped from public acquire).
*/
export function stageRows(stages: StageEntry[], plan: PlanDraft | null | undefined): StageRow[] {
  const liveByStage = new Map<string, StageEntry>(stages.map((entry) => [entry.stage, entry]));
  const scope = plan?.backend_scope;
  const vocab = vocabByStage(scope);
  const depth = plan?.analysis_depth;
  const agreed =
    depth !== undefined && depth !== null ? stepsForAnalysisDepth(depth, scope) : [];
  const rounds = cycleRounds(stages);
  const maxRound = Math.max(1, ...rounds.filter((_, index) => SEARCH_CYCLE_STAGES.has(stages[index]?.stage ?? "")));
  const ids = new Map<string, number>();

  const labelled = (
    step: PlanStepPreview,
    entry: StageEntry | undefined,
    roundIndex: number,
  ): StageRow => {
    const id = nextRowId(ids, step.stage, SEARCH_CYCLE_STAGES.has(step.stage) ? roundIndex : 1);
    if (entry !== undefined && SEARCH_CYCLE_STAGES.has(entry.stage)) {
      return rowFromVocab(step, entry, {
        id,
        label: cycleLabel(step.label, roundIndex, maxRound),
      });
    }
    return rowFromVocab(step, entry, { id });
  };

  if (agreed.length > 0) {
    const seen = new Set(agreed.map((step) => step.stage));
    const extras = stages.flatMap((entry, index) => {
      if (seen.has(entry.stage)) return [];
      const step = vocab.get(entry.stage);
      return step === undefined ? [] : [labelled(step, entry, rounds[index] ?? 1)];
    });
    const rows: StageRow[] = [];
    for (const step of agreed) {
      if (SEARCH_CYCLE_STAGES.has(step.stage)) {
        const matches = stages.flatMap((entry, index) =>
          entry.stage === step.stage ? [{ entry, roundIndex: rounds[index] ?? 1 }] : [],
        );
        if (matches.length === 0) {
          rows.push(rowFromVocab(step, undefined, { id: nextRowId(ids, step.stage, 1) }));
        } else {
          for (const match of matches) rows.push(labelled(step, match.entry, match.roundIndex));
        }
      } else {
        rows.push(labelled(step, liveByStage.get(step.stage), 1));
      }
    }
    return [...rows, ...extras];
  }

  return stages.map((entry, index) => {
    const roundIndex = rounds[index] ?? 1;
    const step = vocab.get(entry.stage);
    if (step === undefined) {
      const base = entry.label;
      return {
        id: nextRowId(ids, entry.stage, SEARCH_CYCLE_STAGES.has(entry.stage) ? roundIndex : 1),
        stage: entry.stage,
        label: SEARCH_CYCLE_STAGES.has(entry.stage)
          ? cycleLabel(base, roundIndex, maxRound)
          : base,
        blurb: entry.blurb,
        status: entry.status,
        summary: entry.summary,
        seconds: entry.seconds,
      };
    }
    return labelled(step, entry, roundIndex);
  });
}

/** Label of the in-flight step, else the last completed one. */
export function currentStepLabel(rows: StageRow[]): string | null {
  const started = rows.find((row) => row.status === "started");
  if (started !== undefined) return started.label;
  const completed = [...rows].reverse().find((row) => row.status === "completed");
  return completed?.label ?? rows[0]?.label ?? null;
}

/** Extra lines shown when a completed step is expanded. */
export function stageDetailLines(row: StageRow): string[] {
  const lines: string[] = [];
  if (row.blurb !== undefined && row.blurb !== "") lines.push(row.blurb);
  const counts = timelineSummary(row);
  if (counts.length > 0) lines.push(counts.join(" · "));
  if (row.status === "completed" && typeof row.seconds === "number") {
    lines.push(`Took ${formatElapsed(row.seconds)}`);
  }
  const reason = typeof row.summary?.reason === "string" ? row.summary.reason : null;
  if (reason !== null) lines.push(reason);
  return lines;
}

/** Link to a lifecycle tab that now has something to read. */
export function signpostForStage(
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
): StageSignpost | null {
  if (status === "succeeded" || status === "degraded") {
    return {
      href: `/tasks/${taskId}/result`,
      label: LIFECYCLE_LABELS.result,
      message: RUN_FINISHED_MESSAGE,
    };
  }
  return null;
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
): StageSignpost | null {
  if (status === "succeeded" || status === "degraded") {
    return {
      href: `/tasks/${taskId}/result`,
      label: "Read the report",
      message: RUN_FINISHED_MESSAGE,
    };
  }
  return null;
}

/** One-line collapsed status (`RUNNING · Searching · 13s`). */
export function collapsedStatusLine(
  status: RunStatus | undefined,
  rows: StageRow[],
  elapsedLabel: string,
): string {
  const { eyebrow } = runningCardCopy(status);
  const step = currentStepLabel(rows);
  return step === null ? `${eyebrow} · ${elapsedLabel}` : `${eyebrow} · ${step} · ${elapsedLabel}`;
}

import { formatDate } from "../lib/dates";
import { friendlyDecisionDetails } from "./decisionsPresentation";
import { confirmTarget } from "./workspace/PartCard";
import { formatElapsed } from "./workspace/runProgress";

/** A detail line under a row, shown when the reader opens it. */
type HistoryDetail = { label: string; value: string };

/** One thing that happened, already reduced to what a reader sees. */
export type HistoryEntry = {
  kind: "entry";
  /** Stable list key, never rendered. */
  id: string;
  /** ISO timestamp the row is ordered and grouped by. */
  at: string;
  /** One plain sentence with its subject ("You chose “Standard depth”."). */
  sentence: string;
  /** A scope edit's own lines, one per change, under the sentence. */
  lines?: string[];
  /** A failure: the row carries the red status mark before its sentence,
   *  and the sentence says what failed (the Word Beside the Colour Rule). */
  failed: boolean;
  /** What the row opens to, when the source carries anything. */
  details?: HistoryDetail[];
  /** A theory-of-change edit the reader may undo (task 054): its event id. */
  undoEventId?: string;
};

/** One run, folded to its outcome line, its steps behind "Show steps". */
export type HistoryRun = {
  kind: "run";
  id: string;
  at: string;
  /** The outcome and the run's time ("Ran the evidence search · 36 min"). */
  sentence: string;
  failed: boolean;
  steps: HistoryEntry[];
};

export type HistoryItem = HistoryEntry | HistoryRun;

/** One day of the history, under its heading. */
export type HistoryDay = {
  /** The local calendar day, `YYYY-MM-DD`; the list key. */
  key: string;
  /** "Today", "Yesterday", else "Tuesday 3 November 2026". */
  heading: string;
  items: HistoryItem[];
};

/**
 * Who is reading, so the Task Agent turns say "You" only for the reader's own
 * words. The decision log's sentences arrive with their subject already
 * resolved for this reader by the server (round 10), and are shown as given.
 */
export type HistoryViewer = {
  /** The reader owns the task: its Task Agent turns are theirs. */
  isOwner: boolean;
  /** The owner's display name, for a colleague reading the owner's task. */
  ownerName: string | null;
  /** The task's capability, which names its runs. */
  capability?: string;
};

/** One theory-of-change edit, as `GET .../toc/history` gives it (task 054). */
type EditLike = {
  event_id: string;
  at: string;
  who: string;
  what: string;
  undoable: boolean;
};

type DecisionLike = {
  sequence: number;
  occurred_at: string;
  kind: string;
  summary: string;
  decided_by?: string | null;
  detail?: Record<string, unknown> | null;
  capability_run_id?: string | null;
};

type TurnLike = {
  turn_index: number;
  created_at: string;
  user_message: string;
  reply?: string | null;
  status: "pending" | "completed" | "failed";
};

/** The subject for an owner whose name is unknown: the server's word. */
const OWNERLESS_SUBJECT = "Someone";

/**
 * The run's own events: folded under the run's one line. Everything else (a
 * check-in answer, a plan approval, a rename, a longlist change) is a
 * decision a reader audits, and stays a row of its own.
 */
const STEP_KINDS = new Set([
  "run.opened",
  "run.parked",
  "run.finished",
  "run.interrupted",
  "component.completed",
  "component.failed",
  "component.skipped",
  "search.executed",
  "steering.pause",
]);

/** What a run is called in its line, by the task's capability. */
const RUN_NOUN: Record<string, string> = {
  evidence_search: "the evidence search",
  options_scoping: "the options scoping",
};

/** The local calendar day of a timestamp, as `YYYY-MM-DD`. */
function dayKey(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/**
 * A day's heading: "Today", "Yesterday", else the long date led by its
 * weekday ("Tuesday 3 November 2026").
 */
export function dayHeading(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const key = dayKey(date);
  if (key === dayKey(now)) return "Today";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (key === dayKey(yesterday)) return "Yesterday";
  return formatDate(date, "long", { weekday: true });
}

/** A string field of a decision's payload, when it is one. */
function stringField(detail: DecisionLike["detail"], key: string): string | null {
  const value = detail?.[key];
  return typeof value === "string" && value.trim() !== "" ? value.trim() : null;
}

/**
 * A Task Agent turn as a sentence. A part card's press carries a machine
 * marker on its last line (`[confirm part=… option=…]`, parsed by the part
 * card's own `confirmTarget`); it reads as the choice, and a scope edit as
 * its changes, one per line (lead ruling H3, wording P7).
 */
/** The full stop after a closing quote, left out when the quoted words end
 *  their own sentence (no "“Why?”."). */
function stopAfter(quoted: string): string {
  return /[.?!]$/.test(quoted) ? "" : ".";
}

function turnSentence(turn: TurnLike, subject: string): { sentence: string; lines?: string[] } {
  const message = turn.user_message.trim();
  // A code-authored line has no user message (task 054, J3).
  if (message === "") return { sentence: "The Task Agent posted an update." };
  const failed = turn.status === "failed" ? " This didn't send." : "";
  if (confirmTarget(message) !== null) {
    const body = message.split("\n").slice(0, -1).join("\n").trim();
    const [first = "", ...rest] = body.split("\n").map((line) => line.trim()).filter((line) => line !== "");
    if (first === "Update the scope:") {
      return {
        sentence: `${subject} changed the scope:${failed}`,
        lines: rest.map((line) => line.replace(/^-\s*/, "")),
      };
    }
    return { sentence: `${subject} chose “${body}”${stopAfter(body)}${failed}` };
  }
  const verb = turn.turn_index === 0 ? "asked" : "wrote";
  return { sentence: `${subject} ${verb}: “${message}”${failed === "" ? "" : `${stopAfter(message)}${failed}`}` };
}

/** A run's search row's terms: every query it sent (the server's
 *  `detail.queries`, in the order sent), one per line. */
function searchTerms(decision: DecisionLike): HistoryDetail[] {
  const queries = decision.detail?.queries;
  const terms = Array.isArray(queries)
    ? queries.filter((term): term is string => typeof term === "string" && term.trim() !== "")
    : [];
  return terms.length === 0 ? [] : [{ label: "Search terms", value: terms.join("\n") }];
}

/**
 * A run's one line: its outcome and its time (lead ruling H7, wording P10).
 * The outcome is read from the run's own events: finished, stopped, a step
 * that failed, waiting at a check-in, or still running.
 */
function runLine(
  steps: readonly HistoryEntry[],
  kinds: readonly string[],
  endStatus: string | null,
  capability: string | undefined,
): {
  sentence: string;
  failed: boolean;
} {
  const noun = RUN_NOUN[capability ?? ""] ?? RUN_NOUN.evidence_search;
  const Noun = noun[0].toUpperCase() + noun.slice(1);
  const start = Date.parse(steps[0].at);
  const end = Date.parse(steps[steps.length - 1].at);
  const time = formatElapsed((end - start) / 1000, { withSeconds: false });
  if (kinds.includes("run.interrupted") || endStatus === "aborted" || endStatus === "interrupted") {
    return { sentence: `${Noun} stopped · ${time}`, failed: true };
  }
  if (endStatus === "failed") return { sentence: `${Noun} didn't complete · ${time}`, failed: true };
  if (kinds.includes("run.finished")) return { sentence: `Ran ${noun} · ${time}`, failed: false };
  if (kinds.includes("component.failed")) return { sentence: `${Noun} didn't complete · ${time}`, failed: true };
  if (kinds[kinds.length - 1] === "run.parked") {
    return { sentence: `${Noun} is waiting at a check-in`, failed: false };
  }
  return { sentence: `${Noun} is running`, failed: false };
}

/**
 * The task's history: what was asked, what was agreed, and what then happened.
 *
 * The decision log alone starts at plan approval, which omits the two things
 * a reader most wants when auditing — the question that started it and the
 * negotiation that shaped the plan. Merging the Task Agent turns in by time
 * puts those first, where they happened. Each run folds to one line, its
 * steps under it (H7). The decision log's sentences come from the server with
 * who acted already in them; the turns name the owner, "You" only for the
 * owner (H6).
 *
 * A theory of change's edits join them, so the conversation, the checks and
 * the user's changes read as one record.
 *
 * Ordering is by timestamp, with the Task Agent turn's own index and the
 * decision's sequence breaking ties, so two records written in the same
 * instant keep the order they were actually recorded in.
 *
 * Args:
 *   decisions: The task's decision log, any order.
 *   turns: The task's Task Agent turns, any order.
 *   viewer: Who is reading (defaults to the owner, unnamed).
 *   edits: A theory of change's edits, any order (task 054).
 *
 * Returns:
 *   The rows in the order they happened.
 */
export function mergeHistory(
  decisions: readonly DecisionLike[] | undefined,
  turns: readonly TurnLike[] | undefined,
  viewer: HistoryViewer = { isOwner: true, ownerName: null },
  edits: readonly EditLike[] = [],
): HistoryItem[] {
  // The tiebreak rides alongside the row rather than on it, so it cannot leak
  // into what the view renders.
  const rows: Array<{ item: HistoryItem; tiebreak: number }> = [];
  const ownerSubject = viewer.isOwner ? "You" : (viewer.ownerName ?? OWNERLESS_SUBJECT);

  for (const turn of turns ?? []) {
    const { sentence, lines } = turnSentence(turn, ownerSubject);
    rows.push({
      tiebreak: turn.turn_index,
      item: {
        kind: "entry",
        id: `turn-${turn.turn_index}`,
        at: turn.created_at,
        sentence,
        lines,
        failed: turn.status === "failed",
        details:
          turn.reply != null && turn.reply !== ""
            ? [{ label: "The Task Agent replied", value: turn.reply }]
            : undefined,
      },
    });
  }

  // The server's sentence as given; details through the client allowlist,
  // and a run's search row opens to its terms.
  const runs = new Map<
    string,
    Array<{ entry: HistoryEntry; kind: string; sequence: number; status: string | null }>
  >();
  for (const decision of decisions ?? []) {
    const details = [
      ...friendlyDecisionDetails(decision.detail as never).map((detail) => ({
        label: detail.label,
        value: String(detail.value),
      })),
      ...(decision.kind === "search.executed" ? searchTerms(decision) : []),
    ];
    const entry: HistoryEntry = {
      kind: "entry",
      id: `decision-${decision.kind}-${decision.sequence}`,
      at: decision.occurred_at,
      sentence: decision.summary,
      failed: decision.kind === "component.failed",
      details: details.length > 0 ? details : undefined,
    };
    const runId = decision.capability_run_id;
    if (runId != null && STEP_KINDS.has(decision.kind)) {
      const steps = runs.get(runId) ?? [];
      steps.push({
        entry,
        kind: decision.kind,
        sequence: decision.sequence,
        status: decision.kind === "run.finished" ? stringField(decision.detail, "status") : null,
      });
      runs.set(runId, steps);
    } else {
      rows.push({ tiebreak: decision.sequence, item: entry });
    }
  }

  for (const [runId, recorded] of runs) {
    recorded.sort((left, right) => left.entry.at.localeCompare(right.entry.at) || left.sequence - right.sequence);
    const steps = recorded.map((step) => step.entry);
    const { sentence, failed } = runLine(
      steps,
      recorded.map((step) => step.kind),
      recorded.find((step) => step.status !== null)?.status ?? null,
      viewer.capability,
    );
    rows.push({
      tiebreak: recorded[0].sequence,
      item: { kind: "run", id: `run-${runId}`, at: steps[0].at, sentence, failed, steps },
    });
  }

  // A theory of change's edits to its boxes, connections and evidence (task
  // 054): who changed what, with Undo where the server allows it.
  for (const [index, edit] of edits.entries()) {
    rows.push({
      tiebreak: index,
      item: {
        kind: "entry",
        id: `edit-${edit.event_id}`,
        at: edit.at,
        sentence: `${edit.what} (${edit.who})`,
        failed: false,
        undoEventId: edit.undoable ? edit.event_id : undefined,
      },
    });
  }

  return rows
    .sort((left, right) => left.item.at.localeCompare(right.item.at) || left.tiebreak - right.tiebreak)
    .map((row) => row.item);
}

/**
 * The history grouped by the local day it happened on, oldest first, each
 * day under its heading (lead ruling H4).
 *
 * Args:
 *   items: The merged rows, in order.
 *   now: The clock "Today" and "Yesterday" are read against.
 *
 * Returns:
 *   One group per day, in order.
 */
export function groupByDay(items: readonly HistoryItem[], now: Date = new Date()): HistoryDay[] {
  const days: HistoryDay[] = [];
  for (const item of items) {
    const key = dayKey(new Date(item.at));
    const last = days[days.length - 1];
    if (last !== undefined && last.key === key) last.items.push(item);
    else days.push({ key, heading: dayHeading(item.at, now), items: [item] });
  }
  return days;
}

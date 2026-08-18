import { friendlyDecisionDetails, groupSearchDecisions } from "./decisionsPresentation";

/** One row of the task's history, already reduced to what a reader sees. */
export type HistoryRow = {
  /** Stable list key. */
  id: string;
  /** ISO timestamp the row is ordered by. */
  at: string;
  /** The category badge — a plain word, never an event type name. */
  category: string;
  tone: "default" | "blue" | "soft" | "green" | "yellow" | "red";
  /** One plain sentence a person auditing the research can read. */
  sentence: string;
  /** Expandable detail rows, when the source carries any. */
  details?: { label: string; value: string }[];
};

type DecisionLike = {
  sequence: number;
  occurred_at: string;
  kind: string;
  summary: string;
  detail?: Record<string, unknown> | null;
};

type TurnLike = {
  turn_index: number;
  created_at: string;
  user_message: string;
  reply?: string | null;
  status: "pending" | "completed" | "failed";
};

/**
 * Category words for the recorded decisions.
 *
 * Anything not listed falls back to "Recorded" rather than printing its event
 * type. A reader auditing the research should never meet `component.failed`
 * or a module name — the vocabulary of the pipeline is not the vocabulary of
 * the work.
 */
const DECISION_CATEGORY: Record<string, { label: string; tone: HistoryRow["tone"] }> = {
  "steering.decision": { label: "Check-in", tone: "blue" },
  "steering.pause": { label: "Check-in", tone: "yellow" },
  "search.executed.grouped": { label: "Search", tone: "soft" },
  "project.renamed": { label: "Task", tone: "soft" },
  "project.archived": { label: "Task", tone: "soft" },
  "plan.approved": { label: "Plan", tone: "green" },
  "component.completed": { label: "Completed", tone: "green" },
  "component.failed": { label: "Failed", tone: "red" },
  "component.skipped": { label: "Skipped", tone: "yellow" },
};

/**
 * The task's history: what was asked, what was agreed, and what then happened.
 *
 * The decision log alone starts at plan approval, which omits the two things
 * a reader most wants when auditing — the question that started it and the
 * negotiation that shaped the plan. Merging the planning turns in by time
 * puts those first, where they happened.
 *
 * Ordering is by timestamp, with the planning turn's own index and the
 * decision's sequence breaking ties, so two records written in the same
 * instant keep the order they were actually recorded in.
 */
export function mergeHistory(
  decisions: readonly DecisionLike[] | undefined,
  turns: readonly TurnLike[] | undefined,
): HistoryRow[] {
  // The tiebreak rides alongside the row rather than on it, so it cannot leak
  // into what the view renders.
  const rows: Array<{ row: HistoryRow; tiebreak: number }> = [];

  for (const turn of turns ?? []) {
    rows.push({
      tiebreak: turn.turn_index,
      row: {
      id: `turn-${turn.turn_index}`,
      at: turn.created_at,
      // The opening turn is the question that started the task; the rest are
      // the negotiation that shaped the plan.
      category: turn.turn_index === 0 ? "Question" : "Planning",
      tone: turn.status === "failed" ? "red" : "blue",
      sentence:
        turn.status === "failed"
          ? `You asked: "${turn.user_message}" — this turn didn't complete.`
          : `You asked: "${turn.user_message}"`,
      details:
        turn.reply != null && turn.reply !== ""
          ? [{ label: "The planner replied", value: turn.reply }]
          : undefined,
      },
    });
  }

  // Search decisions are grouped and details passed through the existing
  // client allowlist, so History keeps everything the decision log showed
  // rather than quietly losing it in the merge.
  for (const decision of groupSearchDecisions([...(decisions ?? [])] as never)) {
    const category = DECISION_CATEGORY[decision.kind] ?? { label: "Recorded", tone: "default" };
    const details = friendlyDecisionDetails(decision.detail).map((detail) => ({
      label: detail.label,
      value: String(detail.value),
    }));
    rows.push({
      tiebreak: decision.sequence,
      row: {
      id: `decision-${decision.kind}-${decision.sequence}`,
      at: decision.occurred_at,
      category: category.label,
      tone: category.tone,
      sentence: decision.summary,
      details: details.length > 0 ? details : undefined,
      },
    });
  }

  return rows
    .sort(
      (left, right) =>
        left.row.at.localeCompare(right.row.at) || left.tiebreak - right.tiebreak,
    )
    .map((entry) => entry.row);
}

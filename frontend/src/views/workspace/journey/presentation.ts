import type { StageEntry } from "../../../store/types";

/** Labels for the small, durable stage-summary vocabulary. Unknown backend
 * keys deliberately do not render: a raw event key is not product copy. */
const SUMMARY_LABELS: Record<string, string> = {
  found: "found",
  relevant: "relevant",
  screened_out: "screened out",
  quality_checked: "quality-checked",
  read_in_full: "read in full",
  selected: "shortlisted",
  findings: "findings extracted",
  cited: "cited",
  sources: "sources",
  queries: "queries",
};

/** The seven durable funnel stages, in the execution order users see. */
export const FUNNEL_STAGES = [
  ["found", "Sources found", "Every record returned by the searches."],
  ["relevant", "Relevant", "Kept after screening titles and abstracts against your question."],
  ["quality_checked", "Quality-checked", "Labelled by evidence type and appraised for strength."],
  ["read_in_full", "Read in full", "Full documents fetched and read."],
  ["selected", "Shortlisted", "The strongest, most varied set chosen for close reading."],
  ["findings", "Findings extracted", "Individual results pulled out with their exact quotes."],
  ["cited", "Cited in the evidence base", "Sources the write-up rests on."],
] as const;

/** Map an event summary to its approved, human-readable count fragments. */
export function timelineSummary(entry: Pick<StageEntry, "summary">): string[] {
  if (entry.summary === undefined) return [];
  return Object.entries(entry.summary).flatMap(([key, value]) => {
    const label = SUMMARY_LABELS[key];
    return label !== undefined && typeof value === "number" ? [`${value} ${label}`] : [];
  });
}

/** Width percentage for a funnel row, guarded for incomplete/empty funnels. */
export function funnelBarWidth(value: number, maximum: number): number {
  if (maximum <= 0) return 0;
  return Math.max(0, Math.min(100, (value / maximum) * 100));
}

/** Outcome-first completion language; all other run statuses are non-completion states. */
/** Completion-card heading per terminal status; body copy was cut (owner,
 *  2026-08-05 — the degraded status banner already carries the caveat). */
export function completionCopy(status: string | undefined): { heading: string } | null {
  if (status === "succeeded") return { heading: "The evidence base is ready" };
  if (status === "degraded") return { heading: "The evidence base is ready with gaps" };
  return null;
}

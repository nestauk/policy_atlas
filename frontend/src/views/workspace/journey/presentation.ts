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

/** Map an event summary to its approved, human-readable count fragments. */
export function timelineSummary(entry: Pick<StageEntry, "summary">): string[] {
  if (entry.summary === undefined) return [];
  return Object.entries(entry.summary).flatMap(([key, value]) => {
    const label = SUMMARY_LABELS[key];
    return label !== undefined && typeof value === "number" ? [`${value} ${label}`] : [];
  });
}

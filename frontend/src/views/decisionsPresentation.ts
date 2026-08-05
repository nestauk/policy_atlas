import type { components } from "../api/gen/types";

type Decision = components["schemas"]["DecisionOut"];

/** The demo server's complete, user-facing decision-detail vocabulary. */
export const DECISION_DETAIL_LABELS: Record<string, string> = {
  acquired: "New sources found",
  results_returned: "Results returned by the databases",
  already_acquired: "Already in the project",
  dropped_over_cap: "Set aside — over this round's limit",
  relevant: "Judged relevant",
  not_relevant: "Screened out",
  screen_failed: "Could not be screened",
  classified: "Sources labelled by evidence type",
  appraised: "Sources quality-appraised",
  ingested: "Read in full",
  fetch_failed: "Could not be fetched",
  parse_failed: "Fetched but unreadable",
  selected: "Shortlisted for close reading",
  extracted: "Documents with findings",
  no_findings: "Documents with nothing to extract",
  failed: "Extraction failures",
  total: "Findings extracted",
  quote_unverified: "Quotes that could not be verified",
  section_count: "Sections written",
  themes: "Themes identified",
  groups: "Groups formed",
  openalex: "Queries run · OpenAlex",
  overton: "Queries run · Overton",
};

export type FriendlyDetail = { label: string; value: string | number | boolean };

/** Return only safe, friendly-labelled scalar decision details. */
export function friendlyDecisionDetails(detail: Decision["detail"]): FriendlyDetail[] {
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return [];
  return Object.entries(detail).flatMap(([key, value]) => {
    const label = DECISION_DETAIL_LABELS[key];
    return label !== undefined && (typeof value === "string" || typeof value === "number" || typeof value === "boolean")
      ? [{ label, value }]
      : [];
  });
}

export type PresentedDecision = Decision & { searchCount?: number };

/** Collapse durable search events into one count without exposing their raw payloads. */
export function groupSearchDecisions(entries: Decision[]): PresentedDecision[] {
  const searchEntries = entries.filter((entry) => entry.kind === "search.executed");
  if (searchEntries.length === 0) return entries;
  const firstSearch = searchEntries[0];
  const grouped: PresentedDecision = {
    ...firstSearch,
    kind: "search.executed.grouped",
    summary: `Search terms used (${searchEntries.length} queries)`,
    detail: null,
    searchCount: searchEntries.length,
  };
  const firstIndex = entries.indexOf(firstSearch);
  return entries.flatMap((entry, index) => {
    if (entry.kind !== "search.executed") return [entry];
    return index === firstIndex ? [grouped] : [];
  });
}

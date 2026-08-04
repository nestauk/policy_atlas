import type { components } from "../api/gen/types";

type EvidenceItem = components["schemas"]["EvidenceItemOut"];

export type EvidenceSortField = "title" | "year" | "type" | "strength" | "status";
export type SortOrder = "asc" | "desc";

/**
 * Sortable sources-table columns: the visible header label (source of truth
 * for "Strength" → "Evidence strength", 028 contract strand 7) and each
 * column's own natural first-click direction — every column starts
 * ascending except year, which starts descending (the server's own default
 * direction when `sort=year` carries no explicit `order`).
 */
export const SOURCE_SORT_COLUMNS: ReadonlyArray<{
  key: EvidenceSortField;
  label: string;
  defaultOrder: SortOrder;
}> = [
  { key: "title", label: "Source", defaultOrder: "asc" },
  { key: "year", label: "Year", defaultOrder: "desc" },
  { key: "type", label: "Evidence type", defaultOrder: "asc" },
  { key: "strength", label: "Evidence strength", defaultOrder: "asc" },
  { key: "status", label: "Status", defaultOrder: "asc" },
];

/** Cycle a sources-table header click: none → the column's own default
 *  direction → the opposite direction → none. */
export function nextEvidenceSort(
  current: { sort: EvidenceSortField | null; order: SortOrder | null },
  field: EvidenceSortField,
): { sort: EvidenceSortField | null; order: SortOrder | null } {
  const column = SOURCE_SORT_COLUMNS.find((candidate) => candidate.key === field);
  if (column === undefined) return { sort: null, order: null };
  if (current.sort !== field) return { sort: field, order: column.defaultOrder };
  if (current.order === column.defaultOrder) {
    return { sort: field, order: column.defaultOrder === "asc" ? "desc" : "asc" };
  }
  return { sort: null, order: null };
}

const STATUS_LABELS: Record<EvidenceItem["status"], string> = {
  found: "Found",
  screened_out: "Screened out",
  relevant: "Included",
  not_selected: "Included — not shortlisted",
  selected: "Shortlisted",
  read_in_full: "Read in full",
  findings_extracted: "Findings extracted",
  cited: "Cited in the evidence base",
  unavailable: "Included — abstract only",
};

/** Return the source's user-facing ladder label, withholding unknown states. */
export function sourceStatusLabel(item: Pick<EvidenceItem, "status" | "screen_status">): string | undefined {
  if (item.screen_status === "excluded_retracted") return "Excluded — retracted";
  return STATUS_LABELS[item.status];
}

/** Build the honest screening detail used by the source-row tooltip. */
export function screeningDetails(
  item: Pick<
    EvidenceItem,
    "screen_confidence" | "screen_basis" | "screen_stage" | "screen_status" | "status_reason"
  >,
): Array<[string, string]> {
  const details: Array<[string, string]> = [];
  if (item.screen_status !== "excluded_retracted" && item.screen_confidence !== null && item.screen_confidence !== undefined) {
    details.push(["Screening confidence", `${Math.round(item.screen_confidence * 100)}%`]);
  }
  if (item.screen_basis === "title_only") details.push(["Read basis", "Title only"]);
  if (item.screen_basis === "title_abstract") details.push(["Read basis", "Title and abstract"]);
  if (item.screen_stage === 2) details.push(["Screening stage", "Confirmed against full text"]);
  if (item.status_reason) details.push(["Reason", item.status_reason]);
  return details;
}

/** Mark an LLM-produced abstract so it is never presented as document prose. */
export function abstractSourceLabel(source: "provider" | "llm_description" | null | undefined): string | undefined {
  return source === "llm_description" ? "AI description" : undefined;
}

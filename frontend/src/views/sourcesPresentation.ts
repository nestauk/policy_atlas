import type { components } from "../api/gen/types";

type EvidenceItem = components["schemas"]["EvidenceItemOut"];

export type EvidenceSortField = "title" | "year" | "type" | "strength" | "status" | "relevance";
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
  // Relevance = the p(relevant) spectrum; desc (the table default) reads
  // confidently-relevant → uncertain → confidently-irrelevant.
  { key: "relevance", label: "Relevant", defaultOrder: "desc" },
];

/** Status/cited/kind chips on All sources and Findings — same size as table headers. */
export const FILTER_CHIP_CLASS =
  "cursor-pointer border px-3 py-1.5 text-meta font-semibold focus-visible:outline-2 focus-visible:outline-blue";

/** All-caps table header type — matches `PaneHeading` / `text-meta`. */
export const TABLE_HEADER_TEXT_CLASS =
  "text-meta font-extrabold uppercase tracking-[0.06em] text-grey";

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

/** Fixed vocabularies for the facet filters (the server's literal params).
 *  "Uploaded" is deliberately not offered — document upload isn't a live
 *  feature yet (owner, 2026-08-05). */
export const ORIGIN_FILTER_OPTIONS = ["OpenAlex", "Overton"] as const;
export const STRENGTH_FILTER_OPTIONS = [
  "Very strong",
  "Strong",
  "Moderate",
  "Limited",
  "Weak",
] as const;

/**
 * Read depth — what of the source the analysis actually read (owner,
 * 2026-08-05: the old ladder label collapsed this once a source was cited).
 * Not read past screening → null (the cell stays empty).
 */
export function readDepthLabel(
  item: Pick<EvidenceItem, "read_in_full" | "screen_status" | "status">,
): string | null {
  if (item.read_in_full) return "Read in full";
  if (item.status === "unavailable" || item.screen_status === "relevant") return "Abstract only";
  return null;
}

/** Human sentences for the backend's reason codes — raw codes never render.
 *  The fetch codes mirror `ingest_full_text`'s failure vocabulary. */
const HUMAN_REASON: Record<string, string> = {
  title_only: "Screened on the title only",
  title_abstract: "Screened on the title and abstract",
  fetch_failed: "The full text couldn't be fetched",
  parse_failed: "The document couldn't be parsed",
  no_url: "No full-text link was available",
  paywall: "The full text is behind a paywall",
  not_found: "The full-text link no longer works",
  too_large: "The document was too large to process",
  timeout: "The fetch timed out",
  corrupt: "The file was corrupt",
  no_text_layer: "The PDF had no extractable text",
  thin_text: "The document contained too little text to use",
  empty: "The fetched document was empty",
  blocked: "The publisher blocked the fetch",
  blocked_by_host: "The publisher's site blocked the fetch",
  fetch_error: "The fetch failed",
  unsupported_type: "The fetched file was not a text document",
};

/** Humanize a backend reason code; unknown snake_case codes de-snake rather
 *  than render as variables, anything else passes through untouched. */
function humanReason(code: string): string {
  if (HUMAN_REASON[code] !== undefined) return HUMAN_REASON[code];
  if (/^[a-z0-9_]+$/.test(code)) {
    const phrase = code.replaceAll("_", " ");
    return phrase.charAt(0).toUpperCase() + phrase.slice(1);
  }
  return code;
}

/**
 * The Abstract-only hover: why the full text wasn't read, in plain words.
 * `null` for read-in-full rows (no hover needed).
 */
export function readDepthHint(
  item: Pick<EvidenceItem, "read_in_full" | "status" | "status_reason">,
): string | null {
  if (item.read_in_full) return null;
  if (item.status === "unavailable") {
    return item.status_reason
      ? `${humanReason(item.status_reason)} — only the abstract was read.`
      : "The full text couldn't be obtained — only the abstract was read.";
  }
  return "The full text hasn't been read — screening and appraisal used the title and abstract.";
}

/** The strength hover, composed the same way as the citation sidebar's. */
export function strengthHint(
  item: Pick<EvidenceItem, "appraisal_tier" | "evidence_type">,
): string {
  return item.appraisal_tier && item.evidence_type
    ? `${item.appraisal_tier} evidence strength — appraised from the document type: ${item.evidence_type}.`
    : "The source's appraised evidence strength — five bands from Weak to Very strong, scored from its classified document type.";
}

const STATUS_LABELS: Record<EvidenceItem["status"], string> = {
  found: "Found",
  screened_out: "Screened out",
  relevant: "Included",
  not_selected: "Included — not shortlisted",
  selected: "Shortlisted",
  read_in_full: "Read in full",
  findings_extracted: "Findings extracted",
  cited: "Cited in the report",
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
    | "screen_confidence"
    | "screen_basis"
    | "screen_stage"
    | "screen_status"
    | "screen_reason"
    | "status_reason"
  >,
): Array<[string, string]> {
  const details: Array<[string, string]> = [];
  if (item.screen_reason) details.push(["Reasoning", item.screen_reason]);
  if (item.screen_status !== "excluded_retracted" && item.screen_confidence !== null && item.screen_confidence !== undefined) {
    details.push(["Screening confidence", `${Math.round(item.screen_confidence * 100)}%`]);
  }
  if (item.screen_basis === "title_only") details.push(["Read basis", "Title only"]);
  if (item.screen_basis === "title_abstract") details.push(["Read basis", "Title and abstract"]);
  if (item.screen_stage === 2) details.push(["Screening stage", "Confirmed against full text"]);
  // status_reason echoes screen_basis for screened-out rows (a duplicate) and
  // carries backend codes elsewhere — humanize codes, skip duplicates.
  if (item.status_reason && item.status_reason !== item.screen_basis) {
    details.push(["Reason", humanReason(item.status_reason)]);
  }
  return details;
}

/** Mark an LLM-produced abstract so it is never presented as document prose. */
export function abstractSourceLabel(source: "provider" | "llm_description" | null | undefined): string | undefined {
  return source === "llm_description" ? "AI description" : undefined;
}

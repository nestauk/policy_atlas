import { useEffect, useRef, useState } from "react";

import type { components } from "../api/gen/types";
import { useRunStream } from "../store";
import { CAPTION_LABEL_CLASS } from "../ui/brand/label";

type EvidenceItem = components["schemas"]["EvidenceItemOut"];

export type EvidenceSortField = "title" | "year" | "type" | "strength" | "status" | "relevance";
export type SortOrder = "asc" | "desc";

/**
 * The read-depth column's header ("Full text" / "Abstract only"), one
 * constant so its name changes in one place: the owner is choosing it
 * (round 10; the lead has proposed "Depth"). It names the header, the
 * phone's sort options and the sort button ("Sort by status").
 */
export const STATUS_COLUMN_HEADER = "Status";

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
  { key: "status", label: STATUS_COLUMN_HEADER, defaultOrder: "asc" },
  // Relevance = the p(relevant) spectrum; desc (the table default) reads
  // confidently-relevant → uncertain → confidently-irrelevant.
  { key: "relevance", label: "Relevant", defaultOrder: "desc" },
];

/** Status/cited/kind chips on All sources and Findings — same size as table headers. */
export const FILTER_CHIP_CLASS =
  "cursor-pointer border px-3 py-1.5 text-meta font-semibold max-md:px-2 max-md:py-1 max-md:text-caption";

/** A filter toggle chip, on or off: one look on Sources, Findings and the
 *  longlist (task 058 consistency pass). On is the blue tint; off is Paper
 *  with a Line 2 border, its grey label turning Navy on hover. */
export function filterChipClass(active: boolean): string {
  return `${FILTER_CHIP_CLASS} transition-colors ${
    active ? "border-blue bg-blue-tint text-blue" : "border-line-2 bg-paper text-grey hover:text-navy"
  }`;
}

/** Table header type: the Label style at Caption size (12 px Bold,
 *  uppercase, tracked), one line, so the headers label the columns without
 *  outweighing the rows (task 058, round 10, sources table entry 6). */
export const TABLE_HEADER_TEXT_CLASS = `${CAPTION_LABEL_CLASS} whitespace-nowrap`;

/** Evidence types in sentence case: the report's one formatter (round 10),
 *  re-exported so the Sources views keep one import. Display only; filters
 *  and links keep the classifier's own value. */
export { evidenceTypeLabel } from "./artefactPresentation";

/**
 * The phone's sort choices (below `md` the table's headers are hidden, so
 * sorting moves to a "Sort" select in the filter row): each column in the
 * table's order, both directions, the column's own first direction first.
 */
const PHONE_SORTS: ReadonlyArray<{ label: string; sort: EvidenceSortField; order: SortOrder }> = [
  { sort: "title", order: "asc", label: "Source, A to Z" },
  { sort: "title", order: "desc", label: "Source, Z to A" },
  { sort: "year", order: "desc", label: "Year, newest first" },
  { sort: "year", order: "asc", label: "Year, oldest first" },
  { sort: "type", order: "asc", label: "Evidence type, A to Z" },
  { sort: "type", order: "desc", label: "Evidence type, Z to A" },
  { sort: "strength", order: "desc", label: "Evidence strength, strongest first" },
  { sort: "strength", order: "asc", label: "Evidence strength, weakest first" },
  { sort: "relevance", order: "desc", label: "Relevant, most likely first" },
  { sort: "relevance", order: "asc", label: "Relevant, least likely first" },
  { sort: "status", order: "asc", label: `${STATUS_COLUMN_HEADER}, ascending` },
  { sort: "status", order: "desc", label: `${STATUS_COLUMN_HEADER}, descending` },
];

/** The phone's sort choices with their select values (`sort:order`). */
export const PHONE_SORT_OPTIONS = PHONE_SORTS.map((option) => ({ ...option, value: `${option.sort}:${option.order}` }));

/** The URL params the filter row sets, besides the screening toggles:
 *  "Clear filters" removes these and keeps the screening choice. */
export const FACET_PARAMS = ["cited", "theme", "origin", "type", "strength", "year_from", "year_to", "country"] as const;

/**
 * A year range in words: "2015 to 2020", "2016" for one year, "2015 to
 * any" or "Any to 2020" when one end is open; `null` when neither is set.
 *
 * Args:
 *   from: The first year, if any.
 *   to: The last year, if any.
 */
export function yearRangeLabel(from: number | string | undefined, to: number | string | undefined): string | null {
  if (from === undefined && to === undefined) return null;
  if (from !== undefined && to !== undefined) return String(from) === String(to) ? String(from) : `${from} to ${to}`;
  return from !== undefined ? `${from} to any` : `Any to ${to}`;
}


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
  // Task 056: no score (Unknown or Non-evidence documents); always last.
  "Unrated",
] as const;

/**
 * Read depth — what of the source the analysis actually read (owner,
 * 2026-08-05: the old ladder label collapsed this once a source was cited).
 * Not read past screening → null (the cell stays empty).
 */
export function readDepthLabel(
  item: Pick<EvidenceItem, "read_in_full" | "screen_status" | "status">,
): string | null {
  // "Full text", not "Read in full": the text is fetched and made
  // searchable, not read by a model at that step (owner, round 9).
  if (item.read_in_full) return "Full text";
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
  return "The full text hasn't been collected — screening and appraisal used the title and abstract.";
}

/** The strength hover, composed the same way as the citation sidebar's. */
export function strengthHint(
  item: Pick<EvidenceItem, "appraisal_tier" | "evidence_type">,
): string {
  if (item.appraisal_tier === "Unrated" && item.evidence_type) {
    return `Unrated — the document type (${item.evidence_type}) is not scored; the source can be cited but counts below the evidence bar.`;
  }
  return item.appraisal_tier && item.evidence_type
    ? `${item.appraisal_tier} evidence strength — appraised from the document type: ${item.evidence_type}.`
    : "The source's appraised evidence strength — five bands from Weak to Very strong, scored from its classified document type; Unrated when the type is not scored.";
}

const STATUS_LABELS: Record<EvidenceItem["status"], string> = {
  found: "Found",
  screened_out: "Screened out",
  relevant: "Included",
  not_selected: "Included — not shortlisted",
  selected: "Shortlisted",
  read_in_full: "Full text collected",
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

/**
 * The stages whose output lands on the Sources tab: while one runs, the
 * tab's views refetch every few seconds so a value replaces its placeholder
 * as it lands (task 058, owner round 8; before, they refreshed only when the
 * stage finished).
 */
const FEEDS_SOURCES = new Set([
  "acquire",
  "screen",
  "classify",
  "appraise",
  "ingest",
  "characterise",
  "extract",
  "group",
]);

/** How often a Sources view refetches while a stage that feeds it runs. */
export const LIVE_REFETCH_MS = 5_000;

/**
 * The stages running now: those whose latest frame is `started`, while the
 * run itself is running (a paused run is waiting on a person, so nothing is
 * arriving and nothing pulses).
 *
 * Args:
 *   stream: The task's run stream (its run and stage frames).
 *
 * Returns:
 *   The keys of the stages in progress; empty when no run is running.
 */
export function liveStages(stream: {
  run: { status: string } | null;
  stages: ReadonlyArray<{ stage: string; status: string }>;
}): ReadonlySet<string> {
  if (stream.run?.status !== "running") return new Set();
  const latest = new Map<string, string>();
  for (const entry of stream.stages) latest.set(entry.stage, entry.status);
  return new Set([...latest].filter(([, status]) => status === "started").map(([stage]) => stage));
}

/** Whether a stage that feeds the Sources tab is running. */
export function feedsSources(live: ReadonlySet<string>): boolean {
  return [...live].some((stage) => FEEDS_SOURCES.has(stage));
}

/** Which of a source's cells are waiting on a stage that runs now. */
export type CellPulses = { relevant: boolean; type: boolean; strength: boolean; status: boolean };

/**
 * The cells of one source that show a pulsing placeholder (owner, round 8):
 * only where the value is absent, and only while the stage that fills it
 * runs. Screening fills Relevant for every source; classifying fills the
 * evidence type and strength of the relevant ones; reading the full texts
 * decides the Status of the relevant ones not yet read. Once the stage ends
 * nothing pulses, whatever the cell holds.
 *
 * Args:
 *   item: The source's row.
 *   live: The stages running now (`liveStages`).
 *
 * Returns:
 *   One flag per cell that may pulse.
 */
export function cellPulses(
  item: Pick<EvidenceItem, "screen_status" | "evidence_type" | "appraisal_tier" | "read_in_full" | "status">,
  live: ReadonlySet<string>,
): CellPulses {
  const relevant = item.screen_status === "relevant";
  const classifying = live.has("classify") || live.has("appraise");
  return {
    relevant: live.has("screen") && item.screen_status == null,
    type: classifying && relevant && !item.evidence_type,
    strength: classifying && relevant && !item.appraisal_tier,
    status: live.has("ingest") && relevant && !item.read_in_full && item.status !== "unavailable",
  };
}

/** The stages running now on the task's one run stream (`liveStages`). */
export function useLiveStages(taskId: string): ReadonlySet<string> {
  return liveStages(useRunStream(taskId));
}

/**
 * Refetch a view's reads every `LIVE_REFETCH_MS` while `active` (a stage
 * that feeds the view runs), so the placeholders give way to values as they
 * land; the interval stops when the stage ends.
 *
 * Args:
 *   active: Whether a stage that feeds the view is running.
 *   refetch: Refetches the view's reads.
 */
export function useLiveRefetch(active: boolean, refetch: () => void): void {
  const latest = useRef(refetch);
  useEffect(() => {
    latest.current = refetch;
  });
  useEffect(() => {
    if (!active) return undefined;
    const id = window.setInterval(() => latest.current(), LIVE_REFETCH_MS);
    return () => window.clearInterval(id);
  }, [active]);
}

/** What landed in the table since the page showed it: the rows that were not
 *  there before, and per row the cells whose placeholder gave way to a value. */
export type Landed = { rows: ReadonlySet<string>; cells: ReadonlyMap<string, Partial<CellPulses>> };

const NOTHING_LANDED: Landed = { rows: new Set(), cells: new Map() };

/**
 * The rows and values that landed while a stage that feeds the table runs
 * (task 058, round 9; the animation sweep's entry 7): a row whose source was
 * not on the page before, and a cell that pulsed on the last render and now
 * does not. They fade in once (opacity only: the table must not shift) and
 * keep their mark after, so a refetch never replays the fade. A change of
 * view (`viewKey`: filters, sort, page) starts afresh with nothing landed,
 * and nothing lands while no stage runs.
 *
 * Args:
 *   items: The page's sources: their ids and their cells' pulses now.
 *   viewKey: The view's identity (the task and its query string).
 *   active: True while a stage that feeds the table runs.
 *
 * Returns:
 *   The landed rows and cells.
 */
export function useLandedSources(
  items: ReadonlyArray<{ id: string; pulses: CellPulses }>,
  viewKey: string,
  active: boolean,
): Landed {
  const signature = items
    .map(({ id, pulses }) => `${id}:${+pulses.relevant}${+pulses.type}${+pulses.strength}${+pulses.status}`)
    .join("|");
  const [track, setTrack] = useState<{
    viewKey: string;
    signature: string;
    pulses: ReadonlyMap<string, CellPulses> | null;
    landed: Landed;
  }>(() => ({
    viewKey,
    signature,
    pulses: items.length === 0 ? null : new Map(items.map(({ id, pulses }) => [id, pulses])),
    landed: NOTHING_LANDED,
  }));
  if (track.viewKey !== viewKey || track.signature !== signature) {
    const fresh = track.viewKey !== viewKey;
    const before = fresh ? null : track.pulses;
    // A new view's first page is its opening; it lands nothing.
    // The first page a view shows (no rows before) is its opening: nothing lands.
    const opening = before === null || before.size === 0;
    const rows = new Set(fresh ? [] : track.landed.rows);
    const cells = new Map(fresh ? [] : track.landed.cells);
    if (active && !opening && before !== null) {
      for (const { id, pulses } of items) {
        const was = before.get(id);
        if (was === undefined) {
          rows.add(id);
          continue;
        }
        const keys = (Object.keys(pulses) as (keyof CellPulses)[]).filter((key) => was[key] && !pulses[key]);
        if (keys.length > 0) cells.set(id, { ...cells.get(id), ...Object.fromEntries(keys.map((key) => [key, true])) });
      }
    }
    const landed = { rows, cells };
    setTrack({
      viewKey,
      signature,
      pulses: items.length === 0 && before === null ? null : new Map(items.map(({ id, pulses }) => [id, pulses])),
      landed,
    });
    return landed;
  }
  return track.landed;
}

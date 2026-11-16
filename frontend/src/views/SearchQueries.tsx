import { useId, useState } from "react";
import { Link } from "react-router";

import type { components } from "../api/gen/types";
import { Figures } from "../lib/figures";
import { scrub } from "../lib/scrub";
import type { LiveSearchQuery } from "../store";
import { cn } from "../ui/brand/cn";
import { Collapse } from "../ui/motion/Collapse";
import { TABLE_HEADER_TEXT_CLASS } from "./sourcesPresentation";
import { CAPTION_LABEL_CLASS, PANE_LABEL_CLASS } from "../ui/brand/label";
import { formatCount } from "../lib/format";
import { DisclosureChevron } from "../ui/brand/Disclosure";

/** The block's heading, live and finished (owner, round 12: plain). */
export const SEARCH_QUERIES_TITLE = "Search queries";

/** One row of the block, from the stream or the committed coverage. */
export type QueryRow = {
  backend: string;
  query: string;
  /** A citation pass or an id lookup: its description reads in grey. */
  muted: boolean;
  /** Which pass a muted row is: following citations, or looking works up. */
  pass: "citations" | "lookup" | null;
  /** Null until the query returns. */
  results: number | null;
  /** The key the table filters on (`?query=`, the coverage row's
   *  `query_id`, round 12); null on a live row while the stream carries
   *  none, which then reads as plain words. */
  queryId: string | null;
};

/** A row's `query_id` as the URL carries it. The coverage read always has
 *  one; a live row has one only once the stream sends it. */
function queryIdOf(item: object): string | null {
  const id = (item as { query_id?: number | string | null }).query_id;
  return (typeof id === "number" && Number.isInteger(id)) || (typeof id === "string" && id !== "") ? String(id) : null;
}

/** The block's rows grouped by backend, Overton first, then OpenAlex, then
 *  any other in the order it first appears (owner, 2026-11-09); within a
 *  group, in the order the queries went out. */
export type QueryGroup = { backend: string; rows: QueryRow[] };

/** The search backends' public names (the stream sends their keys; the
 *  committed coverage already says "OpenAlex"). */
const BACKEND_NAMES: Record<string, string> = { openalex: "OpenAlex", overton: "Overton" };

/** The groups' order: the policy database first (owner, 2026-11-09). */
const BACKEND_ORDER = ["Overton", "OpenAlex"];

function backendRank(backend: string): number {
  const rank = BACKEND_ORDER.indexOf(backend);
  return rank === -1 ? BACKEND_ORDER.length : rank;
}

function backendName(backend: string): string {
  return BACKEND_NAMES[backend.toLowerCase()] ?? backend;
}

/** A live pass's description once the search has ended, in the past tense
 *  ("Followed citations from 40 sources", "Looked up 12 cited works"): the
 *  stream names it as it goes out, in the present. The saved coverage
 *  already words its passes for a finished search. */
export function settledPassWords(query: string): string {
  return query.replace(/^Following /, "Followed ").replace(/^Looking up /, "Looked up ");
}

/**
 * The rows the block shows (task 058, owner round 9): while the search runs,
 * the queries as they go out; once it has ended, the committed coverage's
 * queries when the read has them (they replace the live rows in place),
 * else the live rows still (their passes reworded in the past tense). The
 * committed coverage lists each backend's written queries, then its passes
 * in the order they ran, already worded for a finished search (round 11:
 * "a citation pass as its own row").
 *
 * Args:
 *   live: The stream's queries, if any.
 *   committed: The coverage read's per-backend detail, if any.
 *   searching: True while the search stage runs.
 *
 * Returns:
 *   The groups, empty when there is nothing to show.
 */
export function queryGroups(
  live: readonly LiveSearchQuery[] | undefined,
  committed: readonly components["schemas"]["CoverageBackendDetailOut"][] | undefined,
  searching: boolean,
): QueryGroup[] {
  const committedRows: QueryRow[] = (committed ?? []).flatMap((detail) => [
    ...(detail.queries ?? []).map((item) => ({
      backend: backendName(detail.backend),
      query: item.query,
      muted: false,
      pass: null,
      results: item.results,
      queryId: queryIdOf(item),
    })),
    ...(detail.passes ?? []).map((item) => ({
      backend: backendName(detail.backend),
      query: item.query,
      muted: true,
      pass: item.pass,
      results: item.results,
      queryId: queryIdOf(item),
    })),
  ]);
  const liveRows: QueryRow[] = (live ?? []).map((item) => {
    const pass = item.kind === "citations" || item.kind === "lookup" ? item.kind : null;
    return {
      backend: backendName(item.backend),
      query: pass !== null && !searching ? settledPassWords(item.query) : item.query,
      muted: pass !== null,
      pass,
      results: item.results,
      queryId: queryIdOf(item),
    };
  });
  const rows = searching || committedRows.length === 0 ? liveRows : committedRows;
  const groups: QueryGroup[] = [];
  for (const row of rows) {
    const group = groups.find((candidate) => candidate.backend === row.backend);
    if (group === undefined) groups.push({ backend: row.backend, rows: [row] });
    else group.rows.push(row);
  }
  // A stable sort: groups of the same rank keep their order of appearance.
  return groups.sort((a, b) => backendRank(a.backend) - backendRank(b.backend));
}

/** "Found with 12 queries and 3 citation passes": the folded line's words
 *  (round 11). A pass that looks cited works up counts as a citation pass. */
export function queryTotals(groups: readonly QueryGroup[]): string {
  const rows = groups.flatMap((group) => group.rows);
  const passes = rows.filter((row) => row.pass !== null).length;
  const queries = rows.length - passes;
  const words = [
    queries > 0 ? `${formatCount(queries)} ${queries === 1 ? "query" : "queries"}` : null,
    passes > 0 ? `${formatCount(passes)} citation ${passes === 1 ? "pass" : "passes"}` : null,
  ].filter((part) => part !== null);
  return `Found with ${words.join(" and ")}`;
}

/** The row a `?query=` value names, if the block holds it. */
export function findQueryRow(groups: readonly QueryGroup[], param: string): QueryRow | undefined {
  return groups.flatMap((group) => group.rows).find((row) => row.queryId === param);
}

/** The applied query filter's words: "Query: " and the first 40 characters,
 *  an ellipsis when cut (round 12, as the Country chip reads). */
export function queryChipLabel(text: string): string {
  const words = text.trim();
  return words.length > 40 ? `${words.slice(0, 40).trimEnd()}…` : words;
}

/** The query or pass as a prose link that filters the table to the records
 *  it returned (round 12): the row's colour over a Line 2 underline, Electric
 *  Blue on hover. A row without a key reads as plain words. */
function QueryLink({ row, hrefFor }: { row: QueryRow; hrefFor: (param: string) => string }) {
  if (row.queryId === null) return <>{scrub(row.query)}</>;
  return (
    <Link
      to={hrefFor(row.queryId)}
      className="underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 hover:text-blue hover:decoration-blue"
    >
      {scrub(row.query)}
    </Link>
  );
}

/** A count on its way: the Sources tab's placeholder bar, right-aligned. */
function ResultsPulse() {
  return (
    <span aria-hidden="true" data-testid="query-results-pulse" className="flex h-[1lh] items-center justify-end">
      <span className="placeholder-bar h-2.5 w-8" />
    </span>
  );
}

/**
 * The search queries at the top of All sources while the search runs (task
 * 058, owner round 9): open under the heading "Search queries", one row per
 * query as it goes out: the backend once per group as a small grey label,
 * the query (a citation pass's or lookup's description in grey), and in the
 * Results column a pulsing bar until the count returns, then the count in
 * tabular figures, right-aligned (the owner: good as it is). Each query is a
 * link that filters the table to what it returned (round 12). When the
 * search ends the block folds over 200 ms and `QueriesSummary` takes over in
 * the count row.
 */
export function SearchQueries({
  groups,
  searching,
  hrefFor,
}: {
  groups: readonly QueryGroup[];
  searching: boolean;
  hrefFor: (param: string) => string;
}) {
  if (groups.length === 0) return null;
  return (
    <section aria-label={searching ? SEARCH_QUERIES_TITLE : undefined} data-testid="search-queries" className={searching ? "mb-6" : undefined}>
      {searching && (
        <h2 className="text-lead font-semibold text-navy">
          {SEARCH_QUERIES_TITLE}
        </h2>
      )}
      <Collapse show={searching} durationMs={200}>
        <div className="pt-3">
          <QueriesTable groups={groups} hrefFor={hrefFor} live className="border-y" />
        </div>
      </Collapse>
    </section>
  );
}

/**
 * The one queries table, live and finished (owner, 2026-11-09: the finished
 * block had its own layout, a Database column and no group labels; one
 * layout now, the live one). Hairline rows at Meta size, the Query and
 * Results columns headed in the table-header label style, each backend once
 * per group as a row-group label (Label treatment at Caption size, Grey),
 * the query in Navy (a pass's description in Grey), the results count
 * right-aligned in tabular figures, a placeholder bar until it returns.
 *
 * Args:
 *   groups: The rows by backend.
 *   hrefFor: The filter link for a row's key.
 *   live: True while the search runs: a row that goes out fades in.
 *   className: The frame's rules (`border-y` under its own heading,
 *     `border-b` under a disclosure line that already draws the top one).
 */
function QueriesTable({
  groups,
  hrefFor,
  live = false,
  className,
}: {
  groups: readonly QueryGroup[];
  hrefFor: (param: string) => string;
  live?: boolean;
  className?: string;
}) {
  return (
    <table className={cn("w-full table-fixed border-line text-left text-meta", className)}>
      <thead className={cn("border-b border-line", TABLE_HEADER_TEXT_CLASS)}>
        <tr>
          <th scope="col" className="py-2 pr-4">
            Query
          </th>
          <th scope="col" className="w-24 py-2 text-right max-md:w-16">
            Results
          </th>
        </tr>
      </thead>
      {groups.map((group) => (
        <tbody key={group.backend} className="border-b border-line last:border-b-0">
          <tr>
            <th scope="rowgroup" colSpan={2} className={cn(CAPTION_LABEL_CLASS, "pt-3 pb-1")}>
              {scrub(group.backend)}
            </th>
          </tr>
          {group.rows.map((row, rowIndex) => (
            <tr key={`${row.query}:${rowIndex}`} className={cn(rowIndex > 0 && "border-t border-line", live && "anim-swap-in")}>
              <td className={cn("py-2 pr-4 break-words leading-[1.5]", row.muted ? "text-grey" : "text-navy")}>
                <QueryLink row={row} hrefFor={hrefFor} />
              </td>
              <td className="py-2 text-right tabular-nums text-navy">
                {row.results === null ? <ResultsPulse /> : formatCount(row.results)}
              </td>
            </tr>
          ))}
        </tbody>
      ))}
    </table>
  );
}

/**
 * The finished search as a section of its own above the filter bar (owner,
 * round 12: the search came before the filtering). One line in the
 * Landscape's section pattern: the Label-style heading "Search queries" at
 * the left and, right-aligned on the same line, the Body sentence
 * in Ink "Found with 12 queries and 3 citation passes · Show", "Show" the
 * quiet control with the disclosure chevron ("Hide" when open); on phones the
 * sentence wraps under the heading. The hairline runs under that line; open,
 * the same table the live block shows (`QueriesTable`; owner, 2026-11-09:
 * one layout), each query a link that filters the table (round 12). Hidden
 * while the live list shows.
 */
export function QueriesSummary({
  groups,
  hrefFor,
}: {
  groups: readonly QueryGroup[];
  hrefFor: (param: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const tableId = useId();
  if (groups.length === 0) return null;
  return (
    <section aria-label={SEARCH_QUERIES_TITLE} data-testid="search-queries-summary" className="min-w-0">
      {/* The whole line is the disclosure (owner, round 14): one button
          spanning the Landscape section's heading row (LandscapeSection, its
          content padding left out so the section ends at its hairline when
          shut), the Label heading at the left, the sentence and Show / Hide
          at the right. */}
      <h2 className="m-0">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={open ? tableId : undefined}
          // The name carries the visible words, heading first (lead, round
          // 14: Label in Name); the visible separator holds with a no-break
          // space, the name keeps plain spaces.
          aria-label={`${SEARCH_QUERIES_TITLE}: ${queryTotals(groups)} · ${open ? "Hide" : "Show"}`}
          onClick={() => setOpen((value) => !value)}
          className="group flex w-full cursor-pointer flex-wrap items-center justify-between gap-x-4 gap-y-0.5 border-b border-line pt-3.5 pb-2 text-left"
        >
          <span className={PANE_LABEL_CLASS}>{SEARCH_QUERIES_TITLE}</span>
          <span className="text-body text-ink">
            <Figures text={queryTotals(groups)} />
            {/* The dot holds to the sentence's last word, so a wrapped line
                starts with the control, never with the dot. */}
            {"\u00a0· "}
            <span className="inline-flex items-baseline gap-1 whitespace-nowrap">
              <DisclosureChevron open={open} className="self-center" />
              <span className="font-semibold text-grey underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 group-hover:text-navy group-hover:decoration-navy">
                {open ? "Hide" : "Show"}
              </span>
            </span>
          </span>
        </button>
      </h2>
      <Collapse show={open} durationMs={200}>
        <div id={tableId}>
          <QueriesTable groups={groups} hrefFor={hrefFor} className="border-b" />
        </div>
      </Collapse>
    </section>
  );
}

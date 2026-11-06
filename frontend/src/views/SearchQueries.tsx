import { useId, useState } from "react";

import type { components } from "../api/gen/types";
import { Figures } from "../lib/figures";
import { scrub } from "../lib/scrub";
import type { LiveSearchQuery } from "../store";
import { cn } from "../ui/brand/cn";
import { Collapse } from "../ui/motion/Collapse";
import { ChevronIcon } from "../ui/brand/icons";
import { TABLE_HEADER_TEXT_CLASS } from "./sourcesPresentation";
import { CAPTION_LABEL_CLASS } from "../ui/brand/label";

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
};

/** The block's rows grouped by backend, in the order each backend first
 *  appears; within a group, in the order the queries went out. */
export type QueryGroup = { backend: string; rows: QueryRow[] };

/** The search backends' public names (the stream sends their keys; the
 *  committed coverage already says "OpenAlex"). */
const BACKEND_NAMES: Record<string, string> = { openalex: "OpenAlex", overton: "Overton" };

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
    })),
    ...(detail.passes ?? []).map((item) => ({
      backend: backendName(detail.backend),
      query: item.query,
      muted: true,
      pass: item.pass,
      results: item.results,
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
    };
  });
  const rows = searching || committedRows.length === 0 ? liveRows : committedRows;
  const groups: QueryGroup[] = [];
  for (const row of rows) {
    const group = groups.find((candidate) => candidate.backend === row.backend);
    if (group === undefined) groups.push({ backend: row.backend, rows: [row] });
    else group.rows.push(row);
  }
  return groups;
}

/** "Found with 12 queries and 3 citation passes": the folded line's words
 *  (round 11). A pass that looks cited works up counts as a citation pass. */
export function queryTotals(groups: readonly QueryGroup[]): string {
  const rows = groups.flatMap((group) => group.rows);
  const passes = rows.filter((row) => row.pass !== null).length;
  const queries = rows.length - passes;
  const words = [
    queries > 0 ? `${queries.toLocaleString("en-GB")} ${queries === 1 ? "query" : "queries"}` : null,
    passes > 0 ? `${passes.toLocaleString("en-GB")} citation ${passes === 1 ? "pass" : "passes"}` : null,
  ].filter((part) => part !== null);
  return `Found with ${words.join(" and ")}`;
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
 * The search queries at the top of All sources (task 058, owner round 9).
 * While the search runs it is open under the heading "Search queries", one
 * row per query as it goes out: the backend once per group as a small grey
 * label, the query (a citation pass's or lookup's description in grey), and
 * in the Results column a pulsing bar until the count returns, then the
 * count in tabular figures, right-aligned (the owner: good as it is).
 *
 * Once the search has ended (round 11) it is no box: one Meta Grey line in
 * the filter bar's column, "Found with 12 queries and 3 citation passes ·
 * Show", with the app's one disclosure (the chevron, Show / Hide). Open, the
 * queries are ruled rows at the sources table's Meta size and full width:
 * the query in Navy (a pass's description in Grey, as its own row), the
 * database it went to in Grey, and the results count right-aligned.
 */
export function SearchQueries({ groups, searching }: { groups: readonly QueryGroup[]; searching: boolean }) {
  const [open, setOpen] = useState(false);
  const tableId = useId();
  const headingId = useId();
  if (groups.length === 0) return null;
  const rows = groups.flatMap((group) => group.rows);
  return (
    <section aria-labelledby={headingId} data-testid="search-queries" className={searching ? "mb-6" : "mb-3"}>
      {searching ? (
        <h2 id={headingId} className="text-lead font-semibold text-navy">
          Search queries
        </h2>
      ) : (
        <h2 id={headingId} className="text-meta">
          <button
            type="button"
            aria-expanded={open}
            aria-controls={open ? tableId : undefined}
            onClick={() => setOpen((value) => !value)}
            className="group inline-flex min-h-6 cursor-pointer items-center gap-1 text-left text-grey"
          >
            <ChevronIcon
              size={12}
              className={cn(
                "-ml-0.5 shrink-0 transition-transform duration-200 ease-[var(--ease-out-strong)]",
                open && "rotate-90",
              )}
            />
            <span>
              <Figures text={queryTotals(groups)} />
              {" · "}
              <span className="font-semibold underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 group-hover:text-navy group-hover:decoration-navy">
                {open ? "Hide" : "Show"}
              </span>
            </span>
          </button>
        </h2>
      )}
      {/* The block folds to its line when the search ends. */}
      <Collapse show={searching || open} durationMs={200}>
        {searching ? (
          <div id={tableId} className="pt-3">
            <table className="w-full table-fixed border-y border-line text-left text-meta">
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
                  {group.rows.map((row, index) => (
                    // A query that goes out while the reader watches fades in.
                    <tr key={`${row.query}:${index}`} className={cn(index > 0 && "border-t border-line", "anim-swap-in")}>
                      <td className={cn("py-2 pr-4 break-words leading-[1.5]", row.muted ? "text-grey" : "text-navy")}>
                        {scrub(row.query)}
                      </td>
                      <td className="py-2 text-right tabular-nums text-navy">
                        {row.results === null ? <ResultsPulse /> : row.results.toLocaleString("en-GB")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              ))}
            </table>
          </div>
        ) : (
          <div id={tableId} className="pt-2 pb-3">
            <table className="w-full table-fixed text-left text-meta">
              <colgroup>
                <col />
                <col className="w-28 max-md:w-24" />
                <col className="w-16" />
              </colgroup>
              <thead className="sr-only">
                <tr>
                  <th scope="col">Query</th>
                  <th scope="col">Database</th>
                  <th scope="col">Results</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${row.backend}:${row.query}:${index}`} className="border-b border-line first:border-t">
                    <td className={cn("py-2 pr-4 break-words leading-[1.5]", row.muted ? "text-grey" : "text-navy")}>
                      {scrub(row.query)}
                    </td>
                    <td className="py-2 pr-4 align-top text-grey">{scrub(row.backend)}</td>
                    <td className="py-2 text-right align-top tabular-nums text-navy">
                      {row.results === null ? <ResultsPulse /> : row.results.toLocaleString("en-GB")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Collapse>
    </section>
  );
}

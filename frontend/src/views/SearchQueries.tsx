import { useId, useState } from "react";

import type { components } from "../api/gen/types";
import { Figures } from "../lib/figures";
import { scrub } from "../lib/scrub";
import type { LiveSearchQuery } from "../store";
import { cn } from "../ui/brand/cn";
import { Collapse } from "../ui/motion/Collapse";
import { ChevronIcon } from "./workspace/chat/icons";
import { TABLE_HEADER_TEXT_CLASS } from "./sourcesPresentation";

/** One row of the block, from the stream or the committed coverage. */
export type QueryRow = {
  backend: string;
  query: string;
  /** A citation pass or an id lookup: its description reads in grey. */
  muted: boolean;
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

/**
 * The rows the block shows (task 058, owner round 9): while the search runs,
 * the queries as they go out; once it has ended, the committed coverage's
 * queries when the read has them (they replace the live rows in place),
 * else the live rows still.
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
  const committedRows: QueryRow[] = (committed ?? []).flatMap((detail) =>
    (detail.queries ?? []).map((item) => ({
      backend: backendName(detail.backend),
      query: item.query,
      muted: false,
      results: item.results,
    })),
  );
  const liveRows: QueryRow[] = (live ?? []).map((item) => ({
    backend: backendName(item.backend),
    query: item.query,
    muted: item.kind === "citations" || item.kind === "lookup",
    results: item.results,
  }));
  const rows = searching || committedRows.length === 0 ? liveRows : committedRows;
  const groups: QueryGroup[] = [];
  for (const row of rows) {
    const group = groups.find((candidate) => candidate.backend === row.backend);
    if (group === undefined) groups.push({ backend: row.backend, rows: [row] });
    else group.rows.push(row);
  }
  return groups;
}

/** "12 search queries · 312 results": the folded line's words. */
export function queryTotals(groups: readonly QueryGroup[]): string {
  const rows = groups.flatMap((group) => group.rows);
  const results = rows.reduce((sum, row) => sum + (row.results ?? 0), 0);
  const queries = rows.length === 1 ? "1 search query" : `${rows.length.toLocaleString("en-GB")} search queries`;
  const found = results === 1 ? "1 result" : `${results.toLocaleString("en-GB")} results`;
  return `${queries} · ${found}`;
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
 * count in tabular figures, right-aligned. Once the search has ended it
 * folds to one line ("12 search queries · 312 results · Show") whose
 * chevron opens the table. One table at Meta size with hairline rows;
 * queries wrap on words.
 */
export function SearchQueries({ groups, searching }: { groups: readonly QueryGroup[]; searching: boolean }) {
  const [open, setOpen] = useState(false);
  const tableId = useId();
  const headingId = useId();
  if (groups.length === 0) return null;
  const shown = searching || open;
  return (
    <section aria-labelledby={headingId} data-testid="search-queries" className="mb-6">
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
            className="group inline-flex cursor-pointer items-center gap-1 text-left text-grey focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
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
      <Collapse show={shown} durationMs={200}>
        <div id={tableId} className="pt-3">
          <table className="w-full table-fixed border-y border-line text-left text-meta">
            <thead className={cn("border-b border-line", TABLE_HEADER_TEXT_CLASS)}>
              <tr>
                <th scope="col" className="py-2 pr-4 font-extrabold">
                  Query
                </th>
                <th scope="col" className="w-24 py-2 text-right font-extrabold max-md:w-16">
                  Results
                </th>
              </tr>
            </thead>
            {groups.map((group) => (
              <tbody key={group.backend} className="border-b border-line last:border-b-0">
                <tr>
                  <th
                    scope="rowgroup"
                    colSpan={2}
                    className="pt-3 pb-1 text-caption font-bold uppercase tracking-label text-grey"
                  >
                    {scrub(group.backend)}
                  </th>
                </tr>
                {group.rows.map((row, index) => (
                  // A query that goes out while the reader watches fades in.
                  <tr
                    key={`${row.query}:${index}`}
                    className={cn(index > 0 && "border-t border-line", searching && "anim-swap-in")}
                  >
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
      </Collapse>
    </section>
  );
}

import type { HTMLAttributes, ReactNode } from "react";

import { Figures } from "../../../lib/figures";
import { formatCount } from "../../../lib/format";
import { Button } from "../Button";
import { cn } from "../cn";

/*
 * A list's foot (task 058, consolidation batch B): the one line under a list
 * or a table, "Show more" or the page controls at its left and what the page
 * keeps at its right (the archived toggle; the Sources table's page size,
 * range and pages). The Tasks and Projects lists, the Sources table and the
 * Findings table use it.
 */

/** The outline button at the 40 px control height (Show more, Previous, Next). */
const FOOT_BUTTON_CLASS = "h-10 py-0";

/**
 * The list's foot row (round 10, round 11): its start at the list's left
 * edge, and at the right what the page puts there, alone when the other is
 * absent, the right end's items in one row. 40 px, 16 px under the frame;
 * nothing when both are absent.
 *
 * Args:
 *   start: The left end (Show more, Download CSV, the page controls).
 *   end: The right end (the archived toggle; a table's range and pages).
 */
export function ListFootRow({
  start,
  end,
  className,
  ...props
}: { start?: ReactNode; end?: ReactNode } & Omit<HTMLAttributes<HTMLDivElement>, "children">) {
  const hasStart = start != null && start !== false;
  const hasEnd = end != null && end !== false;
  if (!hasStart && !hasEnd) return null;
  return (
    <div className={cn("mt-4 flex min-h-10 flex-wrap items-center gap-x-4 gap-y-2", className)} {...props}>
      {start}
      {hasEnd && <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-2">{end}</div>}
    </div>
  );
}

/**
 * "Show more" (round 10): the outline button pagination uses. It holds its
 * place, disabled, while the next page is on its way.
 *
 * Args:
 *   loading: The next page is on its way.
 *   onShowMore: Asks for the next page.
 */
export function ShowMore({ loading, onShowMore }: { loading: boolean; onShowMore: () => void }) {
  return (
    <Button
      variant="outline"
      className={FOOT_BUTTON_CLASS}
      disabled={loading}
      aria-busy={loading || undefined}
      onClick={onShowMore}
    >
      Show more
    </Button>
  );
}

/**
 * Previous and Next under a paged table (All sources, Findings): outline
 * buttons at the 40 px control height and "Page 1 of 2" between them at Meta
 * size in tabular figures (task 058, round 10). The caller moves the reader
 * to the top of the new page, and places it on the foot row.
 *
 * Args:
 *   page: The page shown, from 1.
 *   totalPages: How many pages there are.
 *   onPage: Called with the page to show.
 */
export function Pagination({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (page: number) => void;
}) {
  return (
    <nav aria-label="Pages" className="flex items-center gap-3">
      <Button variant="outline" className={FOOT_BUTTON_CLASS} disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span className="text-meta text-grey">
        <Figures text={`Page ${formatCount(page)} of ${formatCount(totalPages)}`} />
      </span>
      <Button
        variant="outline"
        className={FOOT_BUTTON_CLASS}
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
      >
        Next
      </Button>
    </nav>
  );
}

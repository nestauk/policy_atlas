import type { ReactNode } from "react";

import { Tooltip } from "../radix/Tooltip";
import { cn } from "./cn";
import { CAPTION_LABEL_CLASS } from "./label";

/*
 * The sortable table header (task 058, round 10; moved here from the Sources
 * view in task 054 phase 7 so the theory of change's assumptions table sorts
 * with the same arrow). DESIGN.md § Tables: headers are the Label style at
 * Caption size, one line, bottom-aligned; a sortable header always keeps its
 * arrow's slot, so labels share one baseline.
 */

/** A sort's direction. */
export type SortOrder = "asc" | "desc";

/** A table header's words: the Label style at Caption size, on one line. */
export const COLUMN_HEADER_TEXT_CLASS = `${CAPTION_LABEL_CLASS} whitespace-nowrap`;

/** The sort mark: a 12 px arrow at the funnel's 2 px stroke. Its slot is
 *  always reserved, so a label never shifts as sorting changes. */
export function SortArrow({ order }: { order: SortOrder | null }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      data-testid="sort-arrow"
      className={cn(
        "h-3 w-3 shrink-0",
        order === null
          ? "text-line-2 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"
          : "text-navy",
        order === "asc" && "rotate-180",
      )}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 4v16M6 14l6 6 6-6" />
    </svg>
  );
}

/** One sortable `<th>`: a real button (accessible name "Sort by <label>"),
 *  `aria-sort` on the header itself, and the arrow once this column is the
 *  active sort (Line 2 on hover and focus otherwise). The caller owns the
 *  sort: a click hands it the column's key, and it decides the direction.
 *  The surface sets the cell's spacing through `className`. */
export function SortableColumnHeader<K extends string>({
  column,
  activeSort,
  activeOrder,
  onSort,
  align = "start",
  className,
  hint,
}: {
  column: { key: K; label: string };
  /** A legend shown on hover and focus (the strength's tones, round 12). */
  hint?: ReactNode;
  activeSort: K | null;
  activeOrder: SortOrder | null;
  onSort: (key: K) => void;
  align?: "start" | "end";
  className?: string;
}) {
  const order = activeSort === column.key ? activeOrder : null;
  const ariaSort = order === "asc" ? "ascending" : order === "desc" ? "descending" : "none";
  const button = (
    <button
      type="button"
      aria-label={`Sort by ${column.label.toLowerCase()}`}
      onClick={() => onSort(column.key)}
      className={cn(
        "group inline-flex min-h-6 cursor-pointer items-center gap-1 py-1 transition-colors duration-150 hover:text-navy",
        COLUMN_HEADER_TEXT_CLASS,
        order !== null && "text-navy",
        align === "end" && "flex-row-reverse",
      )}
    >
      {column.label}
      <SortArrow order={order} />
    </button>
  );
  return (
    <th role="columnheader" scope="col" className={cn(align === "end" && "text-right", className)} aria-sort={ariaSort}>
      {hint === undefined ? button : <Tooltip content={hint}>{button}</Tooltip>}
    </th>
  );
}

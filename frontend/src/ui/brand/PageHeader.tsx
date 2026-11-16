import type { ReactNode } from "react";
import { Link } from "react-router";

import { buttonVariants } from "./Button";
import { cn } from "./cn";

/*
 * The list-page header (task 058, lists polish; lead rulings 2026-11-05).
 *
 * Tasks, Projects and a Project page share one header with fixed slots, so
 * nothing in it moves when you go from one page to the next:
 *
 *   md and up                         below md
 *   ┌────────────────────────────┐    ┌──────────────────────┐
 *   │ context (24 px)            │    │ context (24 px)      │
 *   │ Title            [actions] │    │            [actions] │  52 px
 *   │ filters (40 px)    aside   │    │ Title (wraps)        │
 *   └────────────────────────────┘    │ filters (40 px)      │
 *                                     └──────────────────────┘
 *
 * - The context row is always there (the back link on a project, empty on
 *   the lists), so the title row starts at the same height on every page.
 * - The actions sit in a 52 px row of their own height; they never follow
 *   the title's height. Below md they sit above the title (the platform's
 *   large-title pattern), so the primary keeps its place even when a long
 *   project name wraps.
 * - The filters row is always reserved at 40 px (lead ruling P5), so the
 *   list starts at the same height on every page, filters or not.
 * - The title keeps one line box while its text is on its way (a project
 *   name still loading), so nothing shifts when it lands.
 */

/** Page column for Tasks, Projects and a Project page: 24 px gutters from
 *  md up, 16 px below (the New task page's and the report's gutter). */
export const PAGE_COLUMN_CLASS =
  "mx-auto w-full max-w-[1180px] px-6 pb-10 pt-2 max-md:px-4";

/** The page title: Display, Title below md (DESIGN.md § Hierarchy). */
export const PAGE_TITLE_CLASS =
  "min-h-[1lh] text-display font-extrabold tracking-[-0.5px] text-navy text-pretty max-md:text-title";

/** Every header control that is not the primary: 40 px, Body Semibold, the
 *  primary's label size so the two read as one row (lead ruling, task 058
 *  consistency pass). Pair with `<Button variant="ghost">` (its grey, its
 *  navy hover, its press); the ghost elsewhere stays Meta. */
export const PAGE_CONTROL_CLASS = "h-10 whitespace-nowrap px-3 py-0 text-body";

/*
 * The page's one primary: the Button's primary at the entry size (52 px tall,
 * at least 144 px wide, never wrapped, the cut corner, the inset white focus
 * ring), built from the same classes whether it is a link or a button.
 */
const PAGE_PRIMARY_CLASS = buttonVariants({ variant: "primary", size: "entry" });

type PagePrimaryProps = {
  children: ReactNode;
} & (
  | { to: string; onClick?: never; disabled?: never }
  | { to?: never; onClick: () => void; disabled?: boolean }
);

/** The header's primary action: a link ("New task") or a button ("New project"). */
export function PagePrimary({ children, to, onClick, disabled }: PagePrimaryProps) {
  if (to !== undefined) {
    return (
      <Link to={to} className={PAGE_PRIMARY_CLASS}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" className={PAGE_PRIMARY_CLASS} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

/** The context row's way back ("← Projects"): a 40 px target drawn in the
 *  24 px row, flush with the column's left edge. */
export function PageBackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className={cn(
        "-my-2 inline-flex h-10 items-center whitespace-nowrap text-meta font-semibold text-grey no-underline",
        "transition-colors duration-150 ease-[ease] hover:text-navy",
      )}
    >
      {children}
    </Link>
  );
}

type PageHeaderProps = {
  /** The h1. Pass an empty string while it loads; its line box is kept. */
  title: ReactNode;
  /** The context row's content (the back link on a project page). */
  context?: ReactNode;
  /** The action cluster, right-aligned: secondary controls, then the primary last. */
  actions: ReactNode;
  /** The filters row's left side (the Mine / Organisation switcher, a description). */
  filters?: ReactNode;
  /** The filters row's right side (Make private, the admin's wider-list note). */
  aside?: ReactNode;
  className?: string;
};

/** The shared list-page header with fixed slots (see the file comment). */
export function PageHeader({ title, context, actions, filters, aside, className }: PageHeaderProps) {
  return (
    <header
      data-page-header=""
      className={cn("grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4", className)}
    >
      <div data-slot="context" className="col-span-2 row-start-1 mb-2 flex h-6 items-center">
        {context}
      </div>
      <h1
        className={cn(
          PAGE_TITLE_CLASS,
          "col-span-2 row-start-3 mt-4 md:col-span-1 md:col-start-1 md:row-start-2 md:mt-0",
        )}
      >
        {title}
      </h1>
      <div
        data-slot="actions"
        className="col-span-2 row-start-2 flex h-13 items-center justify-end gap-4 md:col-span-1 md:col-start-2"
      >
        {actions}
      </div>
      <div
        data-slot="filters"
        className="col-span-2 row-start-4 mt-4 flex min-h-10 flex-wrap items-center justify-between gap-x-4 gap-y-2 md:row-start-3"
      >
        <div className="min-w-0">{filters}</div>
        {aside != null && aside !== false && <div className="ml-auto">{aside}</div>}
      </div>
    </header>
  );
}

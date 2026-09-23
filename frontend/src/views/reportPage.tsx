import type { ReactNode } from "react";
import { Link } from "react-router";

import { scrub } from "../lib/scrub";
import { ContentsSidebar, type SidebarEntry } from "./ArtefactOutline";
import { READING_COLUMN_MAX_W } from "./listPageChrome";

/*
 * The report's page chrome, shared by the Evidence search report and the
 * options-scoping surfaces (longlist, option card) so a scoping task reads
 * like the rest of the Result tab: the contents sidebar, the A4 paper, the
 * kind row above the title, and the bordered snapshot cells.
 */

/** The paper: reading column, white, hairline ring; flat on small screens. */
export const REPORT_PAGE_CLASS =
  `artefact-page anim-rise my-8 min-w-0 ${READING_COLUMN_MAX_W} flex-1 bg-paper px-10 py-9 shadow-sm ring-1 ring-line ` +
  "max-md:my-0 max-md:px-4 max-md:py-6 max-md:shadow-none max-md:ring-0";

/** Sidebar + paper, side by side from md up, stacked below. */
export function ReportPage({
  entries,
  className,
  children,
  ...props
}: {
  entries?: SidebarEntry[];
  className?: string;
  children: ReactNode;
} & Omit<React.HTMLAttributes<HTMLElement>, "className" | "children">) {
  return (
    <div className="mx-auto flex w-full flex-col justify-center gap-6 px-6 max-md:gap-0 max-md:px-0 md:flex-row">
      {entries !== undefined && entries.length > 0 && <ContentsSidebar entries={entries} />}
      <main className={className === undefined ? REPORT_PAGE_CLASS : `${REPORT_PAGE_CLASS} ${className}`} {...props}>
        {children}
      </main>
    </div>
  );
}

/** The kind-of-artefact label ("Report", "Baseline", "Longlist", "Option")
 *  with the page's one control at the right (Download, a view switch, the
 *  option's action). */
export function ReportKindRow({ kind, tag, children }: { kind: string; tag?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <p className="flex items-center gap-2.5 text-meta font-extrabold uppercase tracking-[0.06em] text-grey">
        <span>{kind}</span>
        {tag !== undefined && <span className="normal-case tracking-normal">{tag}</span>}
      </p>
      {children}
    </div>
  );
}

/** The page title under the kind row. */
export const REPORT_TITLE_CLASS =
  "mt-1 text-display font-extrabold leading-tight tracking-[-0.5px] text-navy max-md:text-title";

export type SnapshotCell = [label: string, value: string, href: string | null];

/** The bordered facts strip under a report title: label over value, a cell
 *  links when it has somewhere to go. */
export function SnapshotCells({ cells }: { cells: SnapshotCell[] }) {
  if (cells.length === 0) return null;
  return (
    <div className="mt-4 grid grid-cols-2 border border-line sm:grid-cols-4">
      {cells.map(([label, value, href]) => {
        const content = (
          <>
            <p className="text-meta font-bold uppercase tracking-[0.06em] text-grey">{label}</p>
            <p className="mt-1 text-body font-medium leading-snug text-navy">{scrub(value)}</p>
          </>
        );
        return href !== null ? (
          <Link key={label} to={href} className="border-r border-line p-3 last:border-r-0 hover:underline">
            {content}
          </Link>
        ) : (
          <div key={label} className="border-r border-line p-3 last:border-r-0">
            {content}
          </div>
        );
      })}
    </div>
  );
}

import { Children, isValidElement, type ReactNode } from "react";
import { Link } from "react-router";

import { scrub } from "../lib/scrub";
import { ContentsSidebar, MobileContents, requestOpenSection, type SidebarEntry } from "./ArtefactOutline";
import { READING_COLUMN_MAX_W } from "./listPageChrome";
import { PANE_LABEL_CLASS } from "../ui/brand/label";
import { PROSE_LINK_CLASS } from "../ui/brand/inlineActions";
import { cn } from "../ui/brand/cn";

/*
 * The report's page chrome, shared by the Evidence search report and the
 * options-scoping surfaces (longlist, option card) so a scoping task reads
 * like the rest of the Result tab: the contents (a sidebar from md up, a
 * closed "Contents" disclosure under the title block below), the A4 paper,
 * the kind row above the title, and the facts line under it.
 */

/** The paper: reading column, white, hairline ring, the Card's navy ambient
 *  shadow (task 058, N8); flat on small screens. */
export const REPORT_PAGE_CLASS =
  `artefact-page anim-rise my-8 min-w-0 ${READING_COLUMN_MAX_W} flex-1 bg-paper px-10 py-9 shadow-paper ring-1 ring-line ` +
  "max-md:my-0 max-md:px-4 max-md:py-6 max-md:shadow-none max-md:ring-0";

/**
 * The page's children with the phone's contents disclosure after the title
 * block: after the first `<header>` child, or first when there is none.
 * Every page that shares `ReportPage` heads itself with a `<header>`, so
 * the contents land under the title on all of them without each page
 * placing it (task 058, round 10, D3).
 */
function withMobileContents(children: ReactNode, entries: SidebarEntry[]): ReactNode {
  const nodes = Children.toArray(children);
  const at = nodes.findIndex((node) => isValidElement(node) && node.type === "header");
  const contents = <MobileContents key="mobile-contents" entries={entries} />;
  return at === -1 ? [contents, ...nodes] : [...nodes.slice(0, at + 1), contents, ...nodes.slice(at + 1)];
}

/** Sidebar + paper, side by side from md up; below md the contents fold
 *  into a closed disclosure under the title block. */
export function ReportPage({
  entries,
  className,
  children,
}: {
  entries?: SidebarEntry[];
  className?: string;
  children: ReactNode;
}) {
  const hasContents = entries !== undefined && entries.length > 0;
  return (
    <div className="mx-auto flex w-full flex-col justify-center gap-6 px-6 max-md:gap-0 max-md:px-0 md:flex-row">
      {hasContents && <ContentsSidebar entries={entries} />}
      <main className={className === undefined ? REPORT_PAGE_CLASS : `${REPORT_PAGE_CLASS} ${className}`}>
        {hasContents ? withMobileContents(children, entries) : children}
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
      <p className={cn(PANE_LABEL_CLASS, "flex items-center gap-2.5")}>
        <span>{kind}</span>
        {tag !== undefined && <span className="normal-case tracking-normal">{tag}</span>}
      </p>
      {children}
    </div>
  );
}

/** The page title under the kind row. */
export const REPORT_TITLE_CLASS =
  "mt-1 text-display font-extrabold tracking-[-0.5px] text-navy max-md:text-title";

/** The report's date on its own line under the title, Meta Grey (owner,
 *  round 11: "Last updated 5 November 2026" left the facts line). */
export const REPORT_DATELINE_CLASS = "mt-1 text-meta text-grey";

/** The title's actions on one line ("See the plan", "Ask about this
 *  analysis"), before the facts line (round 10, finding 9). */
export const REPORT_ACTIONS_CLASS = "print-hide mt-2 flex flex-wrap items-baseline gap-x-5 gap-y-1";

export type ReportFact = [label: string, value: string, href: string | null];

/**
 * The report's facts under its title (round 10, finding 2): one line of
 * label and value pairs at Meta size, the label in Grey and the value in
 * Navy, wrapping onto a second line on a phone. A value with somewhere to
 * go is a link: a route, or a part of this page ("#references", owner,
 * round 11), which opens that part as the contents do. Not a row of tiles
 * (DESIGN.md: no KPI tiles).
 */
export function ReportFacts({ facts }: { facts: ReportFact[] }) {
  if (facts.length === 0) return null;
  return (
    <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-meta">
      {facts.map(([label, value, href]) => (
        <div key={label} className="flex gap-1.5">
          <dt className="text-grey">{label}</dt>
          <dd className="text-navy">
            {href !== null && href.startsWith("#") ? (
              <a
                href={href}
                onClick={(event) => {
                  event.preventDefault();
                  requestOpenSection(href.slice(1));
                }}
                className={PROSE_LINK_CLASS}
              >
                {scrub(value)}
              </a>
            ) : href !== null ? (
              <Link to={href} className={PROSE_LINK_CLASS}>
                {scrub(value)}
              </Link>
            ) : (
              scrub(value)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

import { NavLink, Outlet, useParams } from "react-router";

import { useFunnel } from "../api/queries";
import { cn } from "../ui/brand/cn";
import { SOURCES_LABELS } from "../lib/vocabulary";
import { WIDE_PAGE_CLASS } from "./listPageChrome";
import { GROWING_RULE_ACTIVE_CLASS, GROWING_RULE_CLASS } from "../ui/brand/Nav";
import { rememberSourcesSubtab, type SourcesSubtab } from "./sourcesSubtab";

/**
 * Sources layout: Themes, Landscape and All sources always render; Findings
 * is a fourth tab present ONLY when the funnel reports a nonzero findings
 * count (rubric 24) — an analysis that never ran deep enough to extract
 * findings gets no tab to click into, not a disabled or empty one.
 *
 * Read-model freshness while a run is in progress comes from the
 * shell-owned `RunStreamProvider`, not a per-layout stream mount.
 */
export function SourcesLayout() {
  const { taskId = "" } = useParams();
  const funnel = useFunnel(taskId);
  const base = `/tasks/${taskId}/sources`;
  const hasFindings = typeof funnel.data?.findings === "number" && funnel.data.findings > 0;

  const tabs: Array<{ label: string; subtab: SourcesSubtab; end: boolean }> = [
    { label: SOURCES_LABELS.themes, subtab: "", end: true },
    { label: SOURCES_LABELS.landscape, subtab: "/landscape", end: false },
    { label: SOURCES_LABELS.all, subtab: "/all", end: false },
    ...(hasFindings ? [{ label: SOURCES_LABELS.findings, subtab: "/findings" as const, end: false }] : []),
  ];

  return (
    <div className={`${WIDE_PAGE_CLASS} min-h-full py-8`}>
      <div className="bg-paper">
        {/* DESIGN.md § Navigation: Meta Semibold Grey, the active tab
            Extrabold Navy over the growing 3px Electric Blue rule, a Line
            hairline under the row (an inset shadow, so the rule sits on it
            without overflowing the scroller); one line, scrolling sideways
            when it does not fit (task 058, landscape polish entry 16). */}
        <nav
          aria-label="Sources"
          className="flex overflow-x-auto shadow-[inset_0_-1px_0_var(--color-line)] [scrollbar-width:none]"
        >
          {tabs.map((tab) => (
            <NavLink
              key={tab.label}
              to={`${base}${tab.subtab}`}
              end={tab.end}
              // The reader's choice wins over the stage-driven landing from
              // now on, on this task (owner, round 10).
              onClick={() => rememberSourcesSubtab(taskId, tab.subtab)}
              className={({ isActive }) =>
                cn(
                  "flex-1 shrink-0 whitespace-nowrap border-b-[3px] border-transparent px-4 py-2.5 text-center text-meta no-underline max-md:px-2.5",
                  "transition-colors duration-150 ease-[ease] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue",
                  // The tab language of the whole app (owner, consistency
                  // pass): the rule grows from the left edge to the centre
                  // on hover and focus, and runs full width when active.
                  GROWING_RULE_CLASS,
                  isActive
                    ? cn(GROWING_RULE_ACTIVE_CLASS, "font-extrabold text-navy")
                    : "font-semibold text-grey hover:text-navy",
                )
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-6">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

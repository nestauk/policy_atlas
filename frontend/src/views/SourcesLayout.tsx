import { Navigate, NavLink, Outlet, useParams } from "react-router";

import { useFunnel, useTask } from "../api/queries";
import { cn } from "../ui/brand/cn";
import { SOURCES_LABELS } from "../lib/vocabulary";
import { WIDE_PAGE_CLASS } from "./listPageChrome";
import { isToc } from "./scopingActivity";
import { ThemesView } from "./ThemesView";

/**
 * The Sources tab's first page: Themes, or (for a theory of change, which has
 * no themes; task 054) a redirect to All sources. Nothing until the task is
 * known, so Themes never flashes first.
 */
export function SourcesIndex() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  if (task.isPending) return null;
  return isToc(task.data) ? <Navigate to="all" replace /> : <ThemesView />;
}

/**
 * Sources layout: Themes, Landscape and All sources always render (a theory
 * of change has no Themes tab: All sources is its first page); Findings
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
  const task = useTask(taskId);
  const base = `/tasks/${taskId}/sources`;
  const hasFindings = typeof funnel.data?.findings === "number" && funnel.data.findings > 0;

  const tabs = [
    ...(isToc(task.data) ? [] : [{ label: SOURCES_LABELS.themes, to: base, end: true }]),
    { label: SOURCES_LABELS.landscape, to: `${base}/landscape`, end: false },
    { label: SOURCES_LABELS.all, to: `${base}/all`, end: false },
    ...(hasFindings ? [{ label: SOURCES_LABELS.findings, to: `${base}/findings`, end: false }] : []),
  ];

  return (
    <div className={`${WIDE_PAGE_CLASS} min-h-full py-6`}>
      <div className="bg-paper">
        <nav aria-label="Sources" className="flex border-b border-line">
          {tabs.map((tab, index) => (
            <NavLink
              key={tab.label}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                cn(
                  "flex-1 px-4 py-2.5 text-center text-meta font-extrabold uppercase tracking-[0.06em] no-underline max-md:px-2 max-md:text-caption",
                  index > 0 && "border-l border-line",
                  isActive ? "bg-navy text-white" : "text-grey hover:text-navy",
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

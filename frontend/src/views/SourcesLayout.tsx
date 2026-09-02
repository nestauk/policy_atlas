import { NavLink, Outlet, useParams } from "react-router";

import { useFunnel } from "../api/queries";
import { cn } from "../ui/brand/cn";
import { SOURCES_LABELS } from "../lib/vocabulary";
import { WIDE_PAGE_CLASS } from "./listPageChrome";

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
  const { projectId = "" } = useParams();
  const funnel = useFunnel(projectId);
  const base = `/projects/${projectId}/sources`;
  const hasFindings = typeof funnel.data?.findings === "number" && funnel.data.findings > 0;

  const tabs = [
    { label: SOURCES_LABELS.themes, to: base, end: true },
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
                  "flex-1 px-4 py-2.5 text-center text-meta font-extrabold uppercase tracking-[0.06em] no-underline",
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

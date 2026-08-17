import { NavLink, Outlet, useParams } from "react-router";

import { useFunnel } from "../api/queries";
import { cn } from "../ui/brand/cn";
import { SOURCES_LABELS } from "../lib/vocabulary";

/**
 * Sources layout: Themes, Landscape and All sources always render; Findings
 * is a fourth tab present ONLY when the funnel reports a nonzero findings
 * count (rubric 24) — an analysis that never ran deep enough to extract
 * findings gets no tab to click into, not a disabled or empty one.
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
    <div>
      <nav aria-label="Sources" className="border-b border-line px-6 pt-6">
        <div className="flex items-center gap-5 pb-3">
          {tabs.map((tab) => (
            <NavLink
              key={tab.label}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                cn(
                  "nav-underline text-meta font-semibold text-grey no-underline hover:text-navy",
                  isActive && "nav-underline-on font-extrabold text-navy",
                )
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <Outlet />
    </div>
  );
}

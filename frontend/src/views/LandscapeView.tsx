import { useParams } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";

import { useFunnel, useGroups, useLandscape, useProject } from "../api/queries";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Card, Divider, PaneHeading } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import {
  EvidenceDistributionChart,
  normaliseGeographies,
  PublicationYearsChart,
} from "../ui/charts/EvidenceDistributionChart";

const FUNNEL_ORDER = [
  ["found", "Found"],
  ["relevant", "Relevant"],
  ["quality_checked", "Quality-checked"],
  ["read_in_full", "Read in full"],
  ["selected", "Shortlisted"],
  ["findings", "Findings"],
  ["cited", "Cited"],
] as const;

const CHART_TOKENS = {
  grid: "var(--color-line)",
  text: "var(--color-grey)",
  navy: "var(--color-navy)",
  blue: "var(--color-blue)",
} as const;

/**
 * Landscape: distributions over the screened-in set ONLY (the funnel is the
 * one surface spanning the full flow). Surfaces without data are hidden,
 * never faked.
 */
export function LandscapeView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  useDocumentTitle(project.data?.name, "Landscape");
  const landscape = useLandscape(projectId);
  const funnel = useFunnel(projectId);
  const groups = useGroups(projectId);

  const funnelRows = FUNNEL_ORDER.flatMap(([key, label]) => {
    const count = funnel.data?.[key];
    return typeof count === "number" ? [{ label: label as string, count }] : [];
  });

  const noData =
    !landscape.isPending &&
    !funnel.isPending &&
    funnelRows.length === 0 &&
    Object.keys(landscape.data?.evidence_types ?? {}).length === 0;

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <h1 className="mb-1 font-display text-xl font-extrabold text-navy">
        Evidence landscape
      </h1>
      <p className="mb-5 text-[12.5px] text-grey">
        Distributions describe the screened-in sources only; the funnel spans the whole
        flow.
      </p>

      {(landscape.isPending || funnel.isPending) && (
        <div aria-busy="true" aria-label="Loading the landscape" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-72 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {noData && (
        <Card role="status" className="p-8 text-center text-[13px] text-grey">
          The landscape appears once screening has run.
        </Card>
      )}

      <div className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-2">
        {funnelRows.length > 0 && (
          <Card>
            <PaneHeading>From search to citation</PaneHeading>
            <Divider />
            <div className="h-64 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={funnelRows} layout="vertical" margin={{ left: 8, right: 24 }}>
                  <CartesianGrid horizontal={false} stroke={CHART_TOKENS.grid} />
                  <XAxis
                    type="number"
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: CHART_TOKENS.text }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={120}
                    tick={{ fontSize: 11, fill: CHART_TOKENS.navy }}
                  />
                  <Bar dataKey="count" fill={CHART_TOKENS.navy} isAnimationActive={false} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}

        {landscape.data !== undefined &&
          Object.keys(landscape.data.evidence_types ?? {}).length > 0 && (
            <Card className="min-w-0">
              <PaneHeading>Evidence types</PaneHeading>
              <Divider />
              <div className="min-w-0 p-4">
                <EvidenceDistributionChart data={landscape.data.evidence_types ?? {}} />
              </div>
            </Card>
          )}

        {landscape.data !== undefined && Object.keys(landscape.data.years ?? {}).length > 0 && (
          <Card className="min-w-0">
            <PaneHeading>Publication years</PaneHeading>
            <Divider />
            <div className="min-w-0 p-4">
              <PublicationYearsChart data={landscape.data.years ?? {}} />
            </div>
          </Card>
        )}

        {landscape.data?.geographies !== null &&
          landscape.data?.geographies !== undefined &&
          Object.keys(landscape.data.geographies).length > 0 && (
            <div className="min-w-0 lg:col-span-2">
              <Card className="min-w-0">
                <PaneHeading>Where sources were published</PaneHeading>
                <Divider />
                <div className="min-w-0 p-4">
                  <EvidenceDistributionChart data={normaliseGeographies(landscape.data.geographies ?? {})} />
                </div>
              </Card>
              <p className="mt-2 text-[11.5px] text-grey">Where sources were published, not where the studies were conducted.</p>
            </div>
          )}
      </div>

      {landscape.data !== undefined && (landscape.data.themes ?? []).length > 0 && (
        <Card className="mt-4">
          <PaneHeading>Themes in the evidence</PaneHeading>
          <Divider />
          <ul role="list" className="space-y-2.5 p-4">
            {(landscape.data.themes ?? []).map((theme) => (
              <li key={theme.name} className="flex items-baseline gap-2.5">
                <Chip tone="blue">{theme.size}</Chip>
                <div>
                  <p className="text-[13px] font-semibold text-navy">{scrub(theme.name)}</p>
                  <p className="text-[12px] text-grey">{scrub(theme.description)}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {groups.data !== undefined && (groups.data.facets ?? []).length > 0 && (
        <Card className="mt-4">
          <PaneHeading>Finding groups</PaneHeading>
          <Divider />
          <div className="space-y-4 p-4">
            {(groups.data.facets ?? []).map((facet) => (
              <div key={facet.facet}>
                <p className="text-[12px] font-bold uppercase tracking-wide text-grey">
                  {scrub(facet.facet)}
                </p>
                <ul role="list" className="mt-1.5 flex flex-wrap gap-1.5">
                  {(facet.groups ?? []).map((group) => (
                    <li key={group.label}>
                      <Chip tone="soft">
                        {scrub(group.label)} · {group.size}
                      </Chip>
                    </li>
                  ))}
                  {facet.ungrouped > 0 && (
                    <li>
                      <Chip tone="default">Ungrouped · {facet.ungrouped}</Chip>
                    </li>
                  )}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}
    </main>
  );
}

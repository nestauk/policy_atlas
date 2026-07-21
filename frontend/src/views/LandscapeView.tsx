import { useParams } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";

import { useFunnel, useGroups, useLandscape } from "../api/queries";
import { scrub } from "../lib/scrub";
import { Card, Divider, PaneHeading } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";

const FUNNEL_ORDER = [
  ["found", "Found"],
  ["relevant", "Relevant"],
  ["quality_checked", "Quality-checked"],
  ["read_in_full", "Read in full"],
  ["selected", "Shortlisted"],
  ["findings", "Findings"],
  ["cited", "Cited"],
] as const;

function DistributionChart({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const rows = Object.entries(data)
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);
  if (rows.length === 0) return null;
  return (
    <Card>
      <PaneHeading>{title}</PaneHeading>
      <Divider />
      <div className="h-64 p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24 }}>
            <CartesianGrid horizontal={false} stroke="#e4e4e7" />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#646363" }} />
            <YAxis
              type="category"
              dataKey="label"
              width={150}
              tick={{ fontSize: 11, fill: "#0f294a" }}
            />
            <Bar dataKey="count" fill="#0000FF" isAnimationActive={false} barSize={14} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

/**
 * Landscape: distributions over the screened-in set ONLY (the funnel is the
 * one surface spanning the full flow). Surfaces without data are hidden,
 * never faked.
 */
export function LandscapeView() {
  const { projectId = "" } = useParams();
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {funnelRows.length > 0 && (
          <Card>
            <PaneHeading>From search to citation</PaneHeading>
            <Divider />
            <div className="h-64 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={funnelRows} layout="vertical" margin={{ left: 8, right: 24 }}>
                  <CartesianGrid horizontal={false} stroke="#e4e4e7" />
                  <XAxis
                    type="number"
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: "#646363" }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={120}
                    tick={{ fontSize: 11, fill: "#0f294a" }}
                  />
                  <Bar dataKey="count" fill="#0F294A" isAnimationActive={false} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}

        {landscape.data !== undefined &&
          Object.keys(landscape.data.evidence_types ?? {}).length > 0 && (
            <DistributionChart title="Evidence types" data={landscape.data.evidence_types ?? {}} />
          )}

        {landscape.data !== undefined && Object.keys(landscape.data.years ?? {}).length > 0 && (
          <DistributionChart title="Publication years" data={landscape.data.years ?? {}} />
        )}

        {landscape.data?.geographies !== null &&
          landscape.data?.geographies !== undefined &&
          Object.keys(landscape.data.geographies).length > 0 && (
            <div className="lg:col-span-2">
              <DistributionChart
                title="Where published (not where conducted)"
                data={landscape.data.geographies ?? {}}
              />
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

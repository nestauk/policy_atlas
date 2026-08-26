import { useParams } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useFunnel, useGroups, useLandscape, useProject } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Card, Divider, PaneHeading } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import {
  CHART_TICK_FONT_SIZE,
  DistributionChartTooltip,
  EvidenceDistributionChart,
  normaliseGeographies,
  PublicationYearsChart,
} from "../ui/charts/EvidenceDistributionChart";
import { ReauthRedirect } from "../ui/feedback";

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
  blueTint: "var(--color-blue-tint)",
} as const;

/** One centred plot per row so classification labels stay readable. */
const LANDSCAPE_PLOT_CLASS = "mx-auto w-full max-w-3xl";

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

  // `not_found` is the server's honest shape for "no landscape/funnel yet"
  // (screening hasn't run) — that's the expected empty state below, not a
  // failure to surface as an error.
  const landscapeErrorCode = landscape.isError ? errorCode(landscape.error) : null;
  const funnelErrorCode = funnel.isError ? errorCode(funnel.error) : null;
  const isUnauthenticated =
    landscapeErrorCode === "unauthenticated" || funnelErrorCode === "unauthenticated";
  const isError =
    (landscape.isError && landscapeErrorCode !== "not_found") ||
    (funnel.isError && funnelErrorCode !== "not_found");

  const noData =
    !landscape.isPending &&
    !funnel.isPending &&
    !isError &&
    funnelRows.length === 0 &&
    Object.keys(landscape.data?.evidence_types ?? {}).length === 0;

  return (
    <main className="py-8">
      {(landscape.isPending || funnel.isPending) && (
        <div aria-busy="true" aria-label="Loading the landscape" className="flex flex-col gap-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className={`${LANDSCAPE_PLOT_CLASS} h-72 animate-pulse border border-line bg-paper-2`} />
          ))}
        </div>
      )}

      {isError &&
        (isUnauthenticated ? (
          <ReauthRedirect />
        ) : (
          <Card role="alert" className="p-8 text-center text-body text-navy">
            The landscape couldn't be loaded.{" "}
            <button
              type="button"
              className="cursor-pointer font-bold text-blue hover:underline"
              onClick={() => {
                void landscape.refetch();
                void funnel.refetch();
              }}
            >
              Retry
            </button>
          </Card>
        ))}

      {noData && (
        <Card role="status" className="p-8 text-center text-body text-grey">
          The landscape appears once screening has run.
        </Card>
      )}

      <div className="flex flex-col gap-4">
        {funnelRows.length > 0 && (
          <Card className={LANDSCAPE_PLOT_CLASS}>
            <PaneHeading>From search to citation</PaneHeading>
            <Divider />
            <div className="h-64 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={funnelRows} layout="vertical" margin={{ left: 8, right: 24 }}>
                  <CartesianGrid horizontal={false} stroke={CHART_TOKENS.grid} />
                  <XAxis
                    type="number"
                    allowDecimals={false}
                    tick={{ fontSize: CHART_TICK_FONT_SIZE, fill: CHART_TOKENS.text }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={140}
                    tick={{ fontSize: CHART_TICK_FONT_SIZE, fill: CHART_TOKENS.navy }}
                  />
                  <Tooltip cursor={{ fill: CHART_TOKENS.blueTint }} content={<DistributionChartTooltip />} />
                  <Bar dataKey="count" fill={CHART_TOKENS.navy} isAnimationActive={false} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}

        {landscape.data !== undefined &&
          Object.keys(landscape.data.evidence_types ?? {}).length > 0 && (
            <Card className={`min-w-0 ${LANDSCAPE_PLOT_CLASS}`}>
              <PaneHeading>Evidence types</PaneHeading>
              <Divider />
              <div className="min-w-0 p-4">
                <EvidenceDistributionChart data={landscape.data.evidence_types ?? {}} />
              </div>
            </Card>
          )}

        {landscape.data !== undefined && Object.keys(landscape.data.years ?? {}).length > 0 && (
          <Card className={`min-w-0 ${LANDSCAPE_PLOT_CLASS}`}>
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
            <Card className={`min-w-0 ${LANDSCAPE_PLOT_CLASS}`}>
              <PaneHeading>Where sources were published</PaneHeading>
              <Divider />
              <div className="min-w-0 p-4">
                {/* Task 031: publisher country only — never the authors'
                    countries, which answer a different question. */}
                <p className="mb-3 break-words text-body text-grey">
                  The country of the publishing venue, when the database reports it. Sources
                  without one are counted as “Not reported”.
                </p>
                <EvidenceDistributionChart data={normaliseGeographies(landscape.data.geographies ?? {})} />
              </div>
            </Card>
          )}
      </div>

      {groups.data !== undefined && (groups.data.facets ?? []).length > 0 && (
        <Card className={`mt-4 ${LANDSCAPE_PLOT_CLASS}`}>
          <PaneHeading>Finding groups</PaneHeading>
          <Divider />
          <div className="space-y-4 p-4">
            {(groups.data.facets ?? []).map((facet) => (
              <div key={facet.facet}>
                <p className="text-meta font-bold uppercase tracking-[0.06em] text-grey">
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

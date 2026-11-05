import { useParams } from "react-router";

import { useFunnel, useGroups, useLandscape, useTask } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { useRunStream } from "../store";
import { ReauthRedirect } from "../ui/feedback";
import {
  evidenceTypeRows,
  facetRows,
  fewYearsSentence,
  funnelRows,
  geographyRows,
  LandscapeSection,
  onlyNotReported,
  population,
  PublicationYears,
  RankedBars,
  singleTypeSentence,
} from "./LandscapeViewCharts";
import { LandscapeSkeleton } from "./LandscapeViewSkeleton";
import { feedsSources, liveStages, useLiveRefetch } from "./sourcesPresentation";
import { CAPTION_LABEL_CLASS } from "../ui/brand/label";
import { cn } from "../ui/brand/cn";
import { RetryCard } from "../ui/feedback/RetryCard";

const TITLES = {
  funnel: "From search to citation",
  types: "Evidence types",
  years: "Publication years",
  geographies: "Where sources were published",
  groups: "Finding groups",
} as const;

const sum = (data: Record<string, number>) => Object.values(data).reduce((total, count) => total + count, 0);

/**
 * Landscape: distributions over the screened-in set ONLY (the funnel is the
 * one surface spanning the full flow). Surfaces without data are hidden,
 * never faked. Task 058 landscape polish (lead rulings 2026-11-05): the
 * sections sit uncarded on the Sources panel, the bar charts are ranked-bar
 * tables in Navy with their values at the bar ends, each heading carries the
 * population it counts, and a one-value chart is a sentence instead.
 */
export function LandscapeView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  useDocumentTitle(task.data?.name, "Landscape");
  const landscape = useLandscape(taskId);
  const funnel = useFunnel(taskId);
  const groups = useGroups(taskId);
  // While a stage that feeds the landscape runs, its reads refetch every
  // 5 s and the rows it will fill breathe a placeholder (owner, round 8).
  const stream = useRunStream(taskId);
  const live = liveStages(stream);
  const runLive = stream.run?.status === "running" || stream.run?.status === "paused";
  const classifying = live.has("classify") || live.has("appraise");
  useLiveRefetch(feedsSources(live), () => {
    void landscape.refetch();
    void funnel.refetch();
  });

  const evidenceTypes = landscape.data?.evidence_types ?? {};
  const years = landscape.data?.years ?? {};
  const geographies = landscape.data?.geographies ?? {};
  const facets = groups.data?.facets ?? [];
  const relevant = typeof funnel.data?.relevant === "number" ? funnel.data.relevant : null;
  const findings = typeof funnel.data?.findings === "number" ? funnel.data.findings : null;
  const relevantFigure = relevant !== null ? population.relevant(relevant) : null;

  const funnelTable = funnelRows(funnel.data, runLive, live);
  const typeRows = evidenceTypeRows(evidenceTypes, classifying);
  const showTypes = classifying || Object.values(evidenceTypes).some((count) => count > 0);
  const typeSentence = classifying ? null : singleTypeSentence(typeRows);
  const withYear = sum(years);
  // The relevant count is said once, at the top of the page; a heading
  // carries a count only when it differs from it (owner, consistency pass).
  const yearsFigure = relevant !== null && withYear < relevant ? population.withYear(withYear) : null;
  const allSources = `/tasks/${taskId}/sources/all`;
  const typeHref = (label: string) => `${allSources}?${new URLSearchParams({ type: label }).toString()}`;
  const yearHref = (year: string) => `${allSources}?${new URLSearchParams({ year_from: year, year_to: year }).toString()}`;
  const groupHref = (facet: string, group: string) =>
    `/tasks/${taskId}/sources/findings?${new URLSearchParams({ facet, group }).toString()}`;
  // A row leads somewhere only when it has sources to show.
  const linkTypes = typeRows.map((row) => (row.count ? { ...row, href: typeHref(row.key) } : row));

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
  const isPending = landscape.isPending || funnel.isPending;

  const noData = !showTypes && !isPending && !isError && funnelTable.length === 0;

  return (
    <main className="py-8">
      {isPending && <LandscapeSkeleton />}

      {isError &&
        (isUnauthenticated ? (
          <ReauthRedirect />
        ) : (
          <RetryCard className="mx-auto mt-8 max-w-3xl" copy="The landscape couldn't be loaded." onRetry={() => {
                void landscape.refetch();
                void funnel.refetch();
              }} />
        ))}

      {noData && (
        <p role="status" className="mx-auto max-w-3xl py-8 text-center text-body text-grey">
          The landscape appears once screening has run.
        </p>
      )}

      {!isPending && (
        <div className="mx-auto w-full max-w-3xl">
          {relevantFigure !== null && !noData && (
            <p className="text-meta text-grey" data-testid="landscape-population">
              {relevantFigure}
            </p>
          )}
          {funnelTable.length > 0 && (
            <LandscapeSection title={TITLES.funnel}>
              <RankedBars caption={TITLES.funnel} rows={funnelTable} busy={funnelTable.some((row) => row.pending)} />
            </LandscapeSection>
          )}

          {showTypes && (
            <LandscapeSection title={TITLES.types}>
              {classifying && relevant !== null && (
                <p className="mb-3 text-meta text-grey" data-testid="classified-so-far">
                  {population.classifiedSoFar(sum(evidenceTypes), relevant)}
                </p>
              )}
              {typeSentence !== null ? (
                <p className="text-meta text-navy">{typeSentence}</p>
              ) : (
                <RankedBars caption={TITLES.types} rows={linkTypes} busy={classifying} />
              )}
            </LandscapeSection>
          )}

          {withYear > 0 && (
            <LandscapeSection title={TITLES.years} figure={yearsFigure}>
              {fewYearsSentence(years) ?? <PublicationYears data={years} caption={TITLES.years} yearHref={yearHref} />}
            </LandscapeSection>
          )}

          {Object.keys(geographies).length > 0 && (
            <LandscapeSection title={TITLES.geographies}>
              {onlyNotReported(geographies) ? (
                <p className="text-meta text-navy">No publisher country was reported for these sources.</p>
              ) : (
                <>
                  {/* Task 031: publisher country only — never the authors'
                      countries, which answer a different question. */}
                  <p className="mb-4 max-w-[44em] break-words text-body text-grey">
                    The country of the publishing venue, when the database reports it. Sources
                    without one are counted as “Not reported”.
                  </p>
                  <RankedBars caption={TITLES.geographies} rows={geographyRows(geographies)} />
                </>
              )}
            </LandscapeSection>
          )}

          {facets.length > 0 && (
            <LandscapeSection title={TITLES.groups} figure={findings !== null ? population.findings(findings) : null}>
              <div className="flex flex-col gap-6">
                {facets.map((facet) => (
                  <div key={facet.facet}>
                    <h3 className={cn(CAPTION_LABEL_CLASS, "mb-2")}>
                      {scrub(facet.facet)}
                    </h3>
                    <RankedBars
                      caption={scrub(facet.facet)}
                      rows={facetRows(facet.groups ?? [], facet.ungrouped).map((row) =>
                        row.key !== "ungrouped" && row.count ? { ...row, href: groupHref(facet.facet, row.key) } : row,
                      )}
                    />
                  </div>
                ))}
              </div>
            </LandscapeSection>
          )}
        </div>
      )}
    </main>
  );
}

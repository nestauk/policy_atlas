import { lazy, Suspense, useState } from "react";
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
import { normaliseGeographies } from "../ui/charts/EvidenceDistributionChart";

/** The publisher map, loaded only when the reader asks for it (round 11),
 *  so the Landscape page does not carry the atlas. */
const PublisherMap = lazy(() => import("./LandscapeViewMap"));

const GEOGRAPHY_VIEWS = [
  { key: "list", label: "List" },
  { key: "map", label: "Map" },
] as const;
import { LandscapeSkeleton } from "./LandscapeViewSkeleton";
import { feedsSources, liveStages, useLiveRefetch, NO_COUNTRY } from "./sourcesPresentation";
import { CAPTION_LABEL_CLASS } from "../ui/brand/label";
import { cn } from "../ui/brand/cn";
import { RetryCard } from "../ui/feedback/RetryCard";
import { OutlineSwitch } from "../ui/brand/OutlineSwitch";
import { InfoHint } from "../ui/brand/InfoHint";

const TITLES = {
  funnel: "From search to citation",
  types: "Evidence types",
  years: "Publication years",
  geographies: "Where sources were published",
  groups: "Finding groups",
} as const;

const sum = (data: Record<string, number>) => Object.values(data).reduce((total, count) => total + count, 0);

/** What "Where sources were published" counts (owner, round 13: on hover). */
const GEOGRAPHY_NOTE = [
  "The country of the publishing venue, when the database reports it. Sources without one are counted as “Not reported”.",
  "This is not necessarily where the study took place.",
] as const;

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
  const [geographyView, setGeographyView] = useState<"list" | "map">("list");
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

  // Each funnel row leads to the table filtered to its set, when the table
  // can filter to it (rounds 11 and 13): Found to every source, Relevant to
  // the screened-in set, Appraised and Full text accessed to theirs (the
  // evidence read's `appraised` and `depth` filters), Cited to the cited
  // sources. Shortlisted has no filter on the table, so it leads nowhere.
  const allSources = `/tasks/${taskId}/sources/all`;
  const funnelHref = (key: string): string | undefined =>
    key === "found"
      ? `${allSources}?status=all`
      : key === "relevant"
        ? `${allSources}?status=Included`
        : key === "quality_checked"
          ? `${allSources}?appraised=true`
          : key === "read_in_full"
            ? `${allSources}?depth=full_text`
            : key === "cited"
              ? `${allSources}?cited=true`
              : undefined;
  const funnelTable = funnelRows(funnel.data, runLive, live).map((row) => {
    const href = row.count ? funnelHref(row.key) : undefined;
    return href !== undefined ? { ...row, href } : row;
  });
  const typeRows = evidenceTypeRows(evidenceTypes, classifying);
  const showTypes = classifying || Object.values(evidenceTypes).some((count) => count > 0);
  const typeSentence = classifying ? null : singleTypeSentence(typeRows);
  const withYear = sum(years);
  // The relevant count is not restated at the top (round 11: the funnel
  // says it); a heading carries a count only when it differs from it.
  const yearsFigure = relevant !== null && withYear < relevant ? population.withYear(withYear) : null;
  const typeHref = (label: string) => `${allSources}?${new URLSearchParams({ type: label }).toString()}`;
  const rangeHref = (from: string, to: string) =>
    `${allSources}?${new URLSearchParams({ year_from: from, year_to: to }).toString()}`;
  const countryHref = (country: string) => `${allSources}?${new URLSearchParams({ country }).toString()}`;
  const groupHref = (facet: string, group: string) =>
    `/tasks/${taskId}/sources/findings?${new URLSearchParams({ facet, group }).toString()}`;
  // A row leads somewhere only when it has sources to show.
  const linkTypes = typeRows.map((row) => (row.count ? { ...row, href: typeHref(row.key) } : row));
  // A country leads to All sources filtered to it (`country=`, round 10);
  // "Not reported" to the sources without one (`country=none`, the evidence
  // read's sentinel, round 14); the folded tail leads nowhere.
  const linkCountries = geographyRows(geographies).map((row) =>
    !row.count
      ? row
      : row.key === "Not reported"
        ? { ...row, href: countryHref(NO_COUNTRY) }
        : row.tone !== "grey"
          ? { ...row, href: countryHref(row.key) }
          : row,
  );

  // The map draws every country (no folded tail); "Not reported" is no place.
  const mapCountries = Object.entries(normaliseGeographies(geographies))
    .filter(([country, count]) => country !== "Not reported" && count > 0)
    .map(([country, count]) => ({ country, count }));

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
              {fewYearsSentence(years) ?? <PublicationYears data={years} caption={TITLES.years} rangeHref={rangeHref} />}
            </LandscapeSection>
          )}

          {Object.keys(geographies).length > 0 && (
            <LandscapeSection
              title={TITLES.geographies}
              // What the section counts, on hover (owner, round 13): it left
              // the page. Task 031: publisher country only, never the
              // authors' countries, which answer a different question.
              hint={<InfoHint label="About where sources were published" note={GEOGRAPHY_NOTE} />}
              control={
                onlyNotReported(geographies) ? null : (
                  <OutlineSwitch label="Show as" choices={GEOGRAPHY_VIEWS} value={geographyView} onChange={setGeographyView} height={32} />
                )
              }
            >
              {onlyNotReported(geographies) ? (
                <p className="text-meta text-navy">No publisher country was reported for these sources.</p>
              ) : (
                <>
                  {geographyView === "map" ? (
                    // The list stays the keyboard's path (round 11): the map
                    // is for the eye and its countries take no focus.
                    <Suspense fallback={<div aria-hidden="true" className="publisher-map__placeholder" />}>
                      <PublisherMap
                        countries={mapCountries}
                        caption={TITLES.geographies}
                        hrefFor={(country) => countryHref(country)}
                      />
                    </Suspense>
                  ) : (
                    <RankedBars caption={TITLES.geographies} rows={linkCountries} />
                  )}
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

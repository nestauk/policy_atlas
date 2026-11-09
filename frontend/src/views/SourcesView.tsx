import { forwardRef, useRef, useState, type ComponentPropsWithoutRef, type ReactNode } from "react";
import { useParams, useSearchParams } from "react-router";

import { useApiClient, useCoverage, useLonglist, useEvidence, useFindings, useLandscape, useTask, useSourceDossier, useSourceRecords } from "../api/queries";
import type { components } from "../api/gen/types";
import { errorCode } from "../lib/errors";
import { Figures } from "../lib/figures";
import { safeHref } from "../lib/safeHref";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { useRunStream } from "../store";
import { Button, buttonVariants } from "../ui/brand/Button";
import { Select } from "../ui/brand/Select";
import { APPLIED_CHIP_CLASS, APPLIED_CHIP_PART_CLASS } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { cn } from "../ui/brand/cn";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { Sheet, SheetContent } from "../ui/radix/Sheet";
import { Tooltip } from "../ui/radix/Tooltip";
import { CloseIcon, DownloadIcon } from "../ui/brand/icons";
import { Arrival, ArrivalProvider, useFirstPaintDone } from "../ui/motion/arrivals";
import { findQueryRow, queryChipLabel, queryGroups, QueriesSummary, SearchQueries } from "./SearchQueries";
import {
  abstractSourceLabel,
  cellPulses,
  feedsSources,
  liveStages,
  nextEvidenceSort,
  screeningDetails,
  sourceStatusLabel,
  yearRangeLabel,
  DEFAULT_SOURCES_PAGE_SIZE,
  FACET_PARAMS,
  NO_COUNTRY,
  ORIGIN_FILTER_OPTIONS,
  sourcesPageSizeChoice,
  SOURCES_PAGE_SIZES,
  sourcesPageSize,
  STATUS_COLUMN_HEADER,
  PHONE_SORT_OPTIONS,
  SOURCE_SORT_COLUMNS,
  TABLE_HEADER_TEXT_CLASS,
  FILTER_CONTROL_IDLE,
  switchChoiceClass,
  type CellPulses,
  type EvidenceSortField,
  type SortOrder,
  useLandedSources,
  useLiveRefetch,
} from "./sourcesPresentation";
import {
  evidenceTypeLabel,
  readDepthColour,
  readDepthHint,
  readDepthLabel,
  strengthHint,
  STRENGTH_LEGEND,
  STRENGTH_TIERS,
  type ReadDepth,
} from "../ui/brand/evidence";
import { DepthMark, StrengthMark, ToneSquare } from "../ui/brand/EvidenceMarks";
import { numberedAuthorships } from "./artefactPresentation";
import { displayUrl, referenceParts } from "../ui/brand/reference";
import { isScoping } from "./scopingActivity";
import { isFinished } from "./workspace/runProgress";
import { Pagination } from "./Pagination";
import { normaliseGeographies } from "../ui/charts/EvidenceDistributionChart";
import "./sources.css";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  // The API's value stays "Included"; the set is named Relevant, as the
  // funnel names it (owner, round 13).
  { key: "Included", label: "Relevant" },
  { key: "screened_out", label: "Screened out" },
] as const;


type EvidenceItem = components["schemas"]["EvidenceItemOut"];
type EvidenceQuery = NonNullable<Parameters<typeof useEvidence>[1]>;


/** The 40 px ghost inside the table's frame (the list pages' `ListError`
 *  control): Try again, Clear filters. */
const FRAME_CONTROL_CLASS = "h-10 whitespace-nowrap px-3 py-0 text-meta";

/** Sources: collection-true server filters and a URL-addressable source dossier. */
export function SourcesView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const landscape = useLandscape(taskId);
  const coverage = useCoverage(taskId);
  useDocumentTitle(task.data?.name, "Sources");
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedStatus = searchParams.get("status");
  const stream = useRunStream(taskId);
  // No explicit status → Included (the screened-in set), the owner default,
  // once screening has finished. Before that the screened-in set is empty or
  // partial, so the default is All (task 058, N16).
  const screened = stream.run !== null
    ? isFinished(stream.run.status) ||
      stream.stages.some((entry) => entry.stage === "screen" && entry.status === "completed")
    : task.data?.latest_run?.status !== "running" && task.data?.latest_run?.status !== "paused";
  const statusFilter =
    STATUS_FILTERS.find((filter) => filter.key === requestedStatus)?.key ??
    (screened || isScoping(task.data) ? "Included" : "all");
  const citedFilter = searchParams.get("cited") === "true";
  // The funnel's Appraised and Full text accessed sets (round 13): the
  // evidence read's `appraised` and `depth` filters.
  const appraisedFilter = searchParams.get("appraised") === "true";
  const fullTextFilter = searchParams.get("depth") === "full_text";
  const originFilter = ORIGIN_FILTER_OPTIONS.find((value) => value === searchParams.get("origin"));
  const typeFilter = searchParams.get("type") ?? undefined;
  const strengthFilter = STRENGTH_TIERS.find(
    (value) => value === searchParams.get("strength"),
  );
  const countryFilter = searchParams.get("country") ?? undefined;
  // One search query's results (round 12): the coverage row's `query_id`.
  const rawQuery = searchParams.get("query");
  const queryFilter = rawQuery !== null && /^\d+$/.test(rawQuery) ? rawQuery : undefined;
  const yearFrom = parseYearParam(searchParams.get("year_from"));
  const yearTo = parseYearParam(searchParams.get("year_to"));
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
  // 25 a page unless the reader chose more (round 12): the URL names a size
  // other than 25; otherwise the size they last chose on this task.
  const requestedPageSize =
    sourcesPageSize(searchParams.get("page_size")) ?? sourcesPageSizeChoice.read(taskId) ?? DEFAULT_SOURCES_PAGE_SIZE;
  const sourceId = searchParams.get("source");
  // Task 046, amendment 3 (R67): an option card's document link adds the
  // option, so the dossier's slot reads "In this option"; a row here opens
  // the document with no option (its records under every option).
  const optionId = searchParams.get("option");
  const requestedSort = searchParams.get("sort");
  const sortField = SOURCE_SORT_COLUMNS.find((column) => column.key === requestedSort)?.key ?? null;
  const requestedOrder = searchParams.get("order");
  const sortOrder: SortOrder | null =
    sortField !== null && (requestedOrder === "asc" || requestedOrder === "desc") ? requestedOrder : null;
  const themeFilter = searchParams.get("theme") ?? undefined;
  // Themes without a stable id predate 028 strand 8 and can't be filtered
  // on (the `theme` param binds to `ThemeOut.theme_id`) — omit them rather
  // than offer a selection that can never round-trip.
  // An options-scoping task's themes are the longlist's option clusters
  // (round 14): the evidence read takes their ids, and the filter names them.
  const scoping = isScoping(task.data);
  const longlist = useLonglist(scoping ? taskId : "");
  const landscapeThemeOptions = (landscape.data?.themes ?? []).filter(
    (theme): theme is typeof theme & { theme_id: string } => Boolean(theme.theme_id),
  );
  const themeOptions = scoping
    ? (longlist.data?.themes ?? []).map((theme) => ({ value: theme.theme_id, label: scrub(theme.name) }))
    : landscapeThemeOptions.map((theme) => ({ value: theme.theme_id, label: scrub(theme.name) }));
  // Evidence-type filter options come from the landscape distribution — the
  // same closed set the classification wrote for this task.
  const evidenceTypeOptions = Object.keys(landscape.data?.evidence_types ?? {}).sort();
  // Publisher countries as the Landscape names them (aliases folded), so a
  // geography row's link lands on a value this select shows.
  const countryOptions = Object.keys(normaliseGeographies(landscape.data?.geographies ?? {}))
    .filter((country) => country !== "Not reported")
    .sort();
  const notReportedCount = normaliseGeographies(landscape.data?.geographies ?? {})["Not reported"] ?? 0;
  // No explicit sort → the relevance spectrum, descending (owner default:
  // confidently relevant → uncertain → confidently irrelevant).
  const effectiveSort = sortField ?? "relevance";
  const effectiveOrder = sortField !== null ? sortOrder : "desc";
  // A filter besides the screening toggles narrows the view; "Clear
  // filters" removes them all and keeps the screening choice.
  const filtered = FACET_PARAMS.some((key) => searchParams.has(key));
  const evidence = useEvidence(taskId, {
    page,
    page_size: requestedPageSize,
    status: statusFilter === "all" ? undefined : [statusFilter],
    cited: citedFilter || undefined,
    sort: effectiveSort,
    order: effectiveOrder ?? undefined,
    theme: themeFilter,
    origin: originFilter,
    evidence_type: typeFilter,
    strength: strengthFilter,
    year_from: yearFrom,
    year_to: yearTo,
    country: countryFilter,
    query: queryFilter !== undefined ? Number(queryFilter) : undefined,
    appraised: appraisedFilter || undefined,
    depth: fullTextFilter ? "full_text" : undefined,
  });
  const dossier = useSourceDossier(taskId, sourceId);
  const findings = useFindings(taskId, sourceId ? { page_size: 200, source_id: sourceId } : undefined);
  // While a stage that feeds this table runs, the table refetches every 5 s
  // and the cells it will fill pulse until their values land (owner, round 8).
  const live = liveStages(stream);
  // The search queries, live as they go out (owner, round 9).
  const searching = live.has("acquire");
  const groups = queryGroups(stream.liveSearchQueries, coverage.data?.backends_detail, searching);
  const appliedQuery = queryFilter !== undefined ? findQueryRow(groups, queryFilter) : undefined;
  // A query's link shows every record it returned: the screening choice
  // opens to All, and the other filters stay as they are.
  const queryHref = (param: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("query", param);
    next.set("status", "all");
    next.delete("page");
    next.delete("source");
    return `?${next.toString()}`;
  };
  // Rows and values that land while a stage runs fade in (the animation
  // sweep's entry 7); a filter, a sort or a page change holds still.
  const viewKey = searchParams.toString();
  const landing = useLandedSources(
    (evidence.data?.data ?? []).map((item) => ({ id: item.source_id, pulses: cellPulses(item, live) })),
    `${taskId}?${viewKey}`,
    feedsSources(live),
  );
  const firstPaintDone = useFirstPaintDone(evidence.data !== undefined, `${taskId}?${viewKey}`);
  useLiveRefetch(feedsSources(live), () => {
    void evidence.refetch();
    void landscape.refetch();
  });
  const results = useRef<HTMLDivElement>(null);
  const totalItems = evidence.data?.pagination.total_items ?? 0;
  const pageSize = evidence.data?.pagination.page_size ?? requestedPageSize;
  const totalPages = evidence.data === undefined ? 0 : Math.ceil(totalItems / pageSize);

  const updateParams = (update: (next: URLSearchParams) => void) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      update(next);
      return next;
    });
  };
  const choosePageSize = (value: string) => {
    const size = sourcesPageSize(value) ?? DEFAULT_SOURCES_PAGE_SIZE;
    sourcesPageSizeChoice.remember(taskId, size);
    updateParams((next) => {
      if (size === DEFAULT_SOURCES_PAGE_SIZE) next.delete("page_size");
      else next.set("page_size", String(size));
      next.delete("page");
    });
  };
  const setFacet = (key: string, value: string | undefined) =>
    updateParams((next) => {
      if (value) next.set(key, value);
      else next.delete(key);
      next.delete("page");
    });
  const clearFilters = () =>
    updateParams((next) => {
      for (const key of FACET_PARAMS) next.delete(key);
      next.delete("page");
    });

  const handleSort = (field: EvidenceSortField) => {
    const next = nextEvidenceSort({ sort: sortField, order: sortOrder }, field);
    updateParams((params) => {
      if (next.sort === null || next.order === null) {
        params.delete("sort");
        params.delete("order");
      } else {
        params.set("sort", next.sort);
        params.set("order", next.order);
      }
      params.delete("page");
    });
  };
  const goToPage = (target: number) => {
    updateParams((next) => next.set("page", String(target)));
    // The reader starts the new page at its first row, not mid-table.
    results.current?.scrollIntoView?.({ block: "start" });
  };

  const header = (
    <SourcesHeaderRow activeSort={effectiveSort} activeOrder={effectiveOrder} onSort={handleSort} />
  );
  const rows = evidence.data?.data ?? [];
  const firstRow = (page - 1) * pageSize + 1;
  const countLine =
    totalItems > pageSize
      ? `${firstRow.toLocaleString("en-GB")}–${(firstRow + rows.length - 1).toLocaleString("en-GB")} of ${totalItems.toLocaleString("en-GB")} sources`
      : `${totalItems.toLocaleString("en-GB")} ${totalItems === 1 ? "source" : "sources"}`;

  // While the search runs and nothing has landed, the queries are the page:
  // the table waits for the first results (owner, round 9), and the filter
  // bar waits with it (round 12). A filter the reader set keeps the bar, so
  // it can always be cleared.
  // A search from before queries were linked to their results keeps no
  // records (the server's rule): a query that returned some, filtered on
  // alone over every screening choice, that comes back empty is one.
  const preChangeQuery =
    queryFilter !== undefined &&
    evidence.data !== undefined &&
    rows.length === 0 &&
    (appliedQuery?.results ?? 0) > 0 &&
    statusFilter === "all" &&
    FACET_PARAMS.every((key) => key === "query" || !searchParams.has(key));
  const waiting =
    searching && !filtered && requestedStatus === null && (evidence.isPending || (evidence.data !== undefined && rows.length === 0));

  return (
    // The column is the table's container: its widths and the stacked row
    // follow the column, not the window, so the source stays readable when
    // the sidebar narrows the page (round 12).
    <main className="@container/sources py-8">
      <SearchQueries groups={groups} searching={searching} hrefFor={queryHref} />
      {/* The finished search as its own one-line section above the filter
          bar (owner, round 12: the search came before the filtering), 24 px
          clear of the bar, so the bar reads as the table's own head; hidden
          while the live list shows. */}
      {!searching && groups.length > 0 && (
        <div className="mb-6">
          <QueriesSummary groups={groups} hrefFor={queryHref} />
        </div>
      )}
      {/* The filter bar (task 058, rounds 11 and 12): filters only, one row
          above the table it scopes, every control a 32 px outline box at
          Meta size on one baseline, 12 px apart on every line when it wraps;
          an applied filter a filled Navy chip with its ×. */}
      {!waiting && (
      <div
        role="group"
        aria-label="Filter sources"
        className={cn("mb-4 flex flex-col items-start gap-2", groups.length > 0 && searching && "mt-8")}
      >
        {/* Two rows (round 12): the screening switch alone, then the facets
            wrapping as they must, 8 px between the rows, nothing squeezed. */}
        <div role="group" aria-label="Screening" className="flex">
          {STATUS_FILTERS.map((filter, index) => (
            <button
              key={filter.key}
              type="button"
              aria-pressed={statusFilter === filter.key}
              onClick={() => updateParams((next) => {
                next.set("status", filter.key);
                next.delete("page");
              })}
              className={cn(switchChoiceClass(statusFilter === filter.key), index > 0 && "-ml-px")}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <div data-testid="sources-facets" className="flex flex-wrap items-center gap-3">
        {citedFilter ? (
          <span className={APPLIED_CHIP_CLASS}>
            <button
              type="button"
              aria-pressed
              onClick={() => setFacet("cited", undefined)}
              className={cn(APPLIED_CHIP_PART_CLASS, "pl-2.5 pr-2")}
            >
              Cited
              <CloseIcon size={12} />
            </button>
          </span>
        ) : (
          <button type="button" aria-pressed={false} onClick={() => setFacet("cited", "true")} className={FILTER_CONTROL_IDLE}>
            Cited
          </button>
        )}
        <FilterSelect
          label={scoping ? "Theme" : "Key theme"}
          allLabel="All themes"
          value={themeFilter ?? ""}
          options={themeOptions}
          onChange={(value) => setFacet("theme", value)}
        />
        <FilterSelect
          label="Origin"
          allLabel="All"
          value={originFilter ?? ""}
          options={ORIGIN_FILTER_OPTIONS.map((value) => ({ value, label: value }))}
          onChange={(value) => setFacet("origin", value)}
        />
        <FilterSelect
          label="Evidence type"
          allLabel="All"
          value={typeFilter ?? ""}
          options={evidenceTypeOptions.map((value) => ({ value, label: evidenceTypeLabel(scrub(value)) }))}
          onChange={(value) => setFacet("type", value)}
        />
        <FilterSelect
          label="Strength"
          allLabel="All"
          value={strengthFilter ?? ""}
          options={STRENGTH_TIERS.map((value) => ({ value, label: value }))}
          onChange={(value) => setFacet("strength", value)}
        />
        <FilterSelect
          label="Country"
          allLabel="All"
          value={countryFilter ?? ""}
          options={[
            ...[...new Set([...countryOptions, ...(countryFilter && countryFilter !== NO_COUNTRY ? [countryFilter] : [])])].map((value) => ({ value, label: scrub(value) })),
            // The sources with no publisher country (round 14), last, as the
            // Landscape pins them.
            ...(notReportedCount > 0 || countryFilter === NO_COUNTRY ? [{ value: NO_COUNTRY, label: "Not reported" }] : []),
          ]}
          onChange={(value) => setFacet("country", value)}
        />
        <YearFilter
          from={yearFrom}
          to={yearTo}
          onChange={(from, to) => updateParams((next) => {
            if (from !== undefined) next.set("year_from", String(from));
            else next.delete("year_from");
            if (to !== undefined) next.set("year_to", String(to));
            else next.delete("year_to");
            next.delete("page");
          })}
        />
        {/* One search query's results (round 12): set from the query's link,
            shown as the Country chip is, its × clearing it. */}
        {queryFilter !== undefined && (
          <span className={APPLIED_CHIP_CLASS}>
            <span className={cn(APPLIED_CHIP_PART_CLASS, "cursor-default pl-2.5 pr-2 hover:bg-transparent")}>
              <span className="truncate max-md:max-w-52">
                {`Query: ${appliedQuery !== undefined ? queryChipLabel(scrub(appliedQuery.query)) : "…"}`}
              </span>
            </span>
            <button
              type="button"
              aria-label="Clear the query filter"
              onClick={() => setFacet("query", undefined)}
              className={cn(APPLIED_CHIP_PART_CLASS, "border-l border-navy-line px-2")}
            >
              <CloseIcon size={12} />
            </button>
          </span>
        )}
        {/* The funnel's sets (round 13), set from its rows, each a chip whose
            × clears it. */}
        {appraisedFilter && <SetChip words="Appraised" onClear={() => setFacet("appraised", undefined)} />}
        {fullTextFilter && <SetChip words="Full text accessed" onClear={() => setFacet("depth", undefined)} />}
        {/* When the table stacks the headers hide, so sorting moves here. */}
        <FilterSelect
          className="@min-[54rem]/sources:hidden"
          label="Sort"
          value={`${effectiveSort}:${effectiveOrder ?? "desc"}`}
          options={PHONE_SORT_OPTIONS}
          onChange={(value) => {
            const [sort, order] = value.split(":");
            updateParams((next) => {
              if (sort === "relevance" && order === "desc") {
                next.delete("sort");
                next.delete("order");
              } else {
                next.set("sort", sort);
                next.set("order", order);
              }
              next.delete("page");
            });
          }}
        />
        {filtered && (
          <Button variant="ghost" className="h-8 px-2 py-0" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
        </div>
      </div>
      )}

      <div ref={results} className="scroll-mt-4">
        {evidence.isPending && !waiting && <SourcesLoading header={header} />}

        {evidence.isError &&
          (errorCode(evidence.error) === "unauthenticated" ? (
            <ReauthRedirect />
          ) : (
            <div role="alert" className="sources-frame flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-4 pl-4 pr-1">
              <p className="text-body text-navy">Sources couldn't be loaded.</p>
              <Button variant="ghost" className={FRAME_CONTROL_CLASS} onClick={() => void evidence.refetch()}>
                Try again
              </Button>
            </div>
          ))}

        {/* A search that ran before queries were linked to their results
            cannot filter: the table's empty state says so (round 12). */}
        {preChangeQuery && (
          <SourcesEmpty
            label="No sources match"
            action={
              <Button variant="ghost" className={FRAME_CONTROL_CLASS} onClick={clearFilters}>
                Clear filters
              </Button>
            }
          >
            This search ran before queries were linked to their results.
          </SourcesEmpty>
        )}

        {!preChangeQuery && evidence.data !== undefined && rows.length === 0 && !waiting && (
          filtered ? (
            <SourcesNoMatch
              taskId={taskId}
              status={statusFilter === "all" ? undefined : [statusFilter]}
              onClear={clearFilters}
            />
          ) : (
            <SourcesEmpty label={statusFilter === "all" ? "No sources yet" : "No sources match"}>
              {statusFilter === "all" ? "They appear here as the search finds them." : null}
            </SourcesEmpty>
          )
        )}

        {evidence.data !== undefined && rows.length > 0 && (
          // The table and its count appear together, rising in, when the
          // first results land after the page opened.
          <ArrivalProvider settled={firstPaintDone} scopeKey={`${taskId}?${viewKey}`}>
          <Arrival arrivalId="sources-table">
            <div className="sources-frame">
              <table role="table" className="sources-table">
                <SourcesColumns />
                {header}
                <tbody role="rowgroup">
                  {rows.map((item) => (
                    <SourceRow
                      key={item.source_id}
                      item={item}
                      pulses={cellPulses(item, live)}
                      landedRow={landing.rows.has(item.source_id)}
                      landedCells={landing.cells.get(item.source_id)}
                      onOpen={() => updateParams((next) => { next.set("source", item.source_id); next.delete("option"); })}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            {/* The line under the table (owner, round 12): Download CSV at the
                left; at the right the page size, the range, then the page
                controls. */}
            <div data-testid="sources-foot" className="mt-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
              <DownloadSourcesButton taskId={taskId} taskName={task.data?.name} />
              <div className="flex flex-wrap items-center gap-x-4 gap-y-3 [&>nav]:mt-0">
                {totalItems > DEFAULT_SOURCES_PAGE_SIZE && (
                  <Select
                    label="Sources per page"
                    size={32}
                    // The size the page asked for (a server may echo another).
                    value={String(requestedPageSize)}
                    options={SOURCES_PAGE_SIZES.map((size) => ({ value: String(size), label: `${size} per page` }))}
                    onChange={choosePageSize}
                    className="w-36"
                  />
                )}
                <p className="text-meta text-grey" role="status">
                  <Figures text={countLine} />
                </p>
                {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPage={goToPage} />}
              </div>
            </div>
          </Arrival>
          </ArrivalProvider>
        )}

        {/* A page past the end shows its controls alone, the way back. */}
        {evidence.data !== undefined && rows.length === 0 && totalPages > 1 && (
          <Pagination page={page} totalPages={totalPages} onPage={goToPage} />
        )}
      </div>

      <SourceDossier
        taskId={taskId}
        sourceId={sourceId}
        optionId={optionId}
        source={dossier.data}
        isPending={dossier.isPending}
        isError={dossier.isError}
        findings={findings.data?.data}
        findingsPending={findings.isPending}
        onClose={() => updateParams((next) => { next.delete("source"); next.delete("option"); })}
      />
    </main>
  );
}

/** The table's fixed column widths (`sources.css`): the source takes what
 *  the value columns leave, so a filter or a page never moves a column. */
function SourcesColumns() {
  return (
    <colgroup>
      <col className="sources-col-source" />
      <col className="sources-col-year" />
      <col className="sources-col-type" />
      <col className="sources-col-strength" />
      <col className="sources-col-relevant" />
      <col className="sources-col-status" />
    </colgroup>
  );
}

/** The header row: every column sorts, the labels on one line at the
 *  Caption label size, the Relevant figure's header right-aligned over it. */
function SourcesHeaderRow({
  activeSort,
  activeOrder,
  onSort,
}: {
  activeSort: EvidenceSortField;
  activeOrder: SortOrder | null;
  onSort: (field: EvidenceSortField) => void;
}) {
  const column = (key: EvidenceSortField) => SOURCE_SORT_COLUMNS.find((candidate) => candidate.key === key) ?? SOURCE_SORT_COLUMNS[0];
  const props = { activeSort, activeOrder, onSort };
  return (
    <thead role="rowgroup" className="sources-head">
      <tr role="row">
        <SortableColumnHeader column={column("title")} className="pl-4" {...props} />
        <SortableColumnHeader column={column("year")} {...props} />
        <SortableColumnHeader column={column("type")} {...props} />
        <SortableColumnHeader column={column("strength")} hint={<StrengthLegend />} {...props} />
        <SortableColumnHeader column={column("relevance")} align="end" {...props} />
        <SortableColumnHeader column={column("status")} {...props} />
      </tr>
    </thead>
  );
}

/**
 * One source. From `md` up a table row: the title (the way into the
 * dossier) over a Meta Grey line, "Venue · Origin" and the green "Cited"
 * chip; then Year, the evidence type and strength, the Relevant figure and
 * the text depth, plain Meta text in fixed columns. Below `lg` the same
 * markup stacks (`sources.css`): the title, "Venue · Year · Origin", then
 * the values in column order joined by " · ", each placeholder in its slot.
 * The cells' hover reasons stay out of the tab order (lead, round 10); the
 * title is the keyboard's way to the same words in the dossier.
 */
function SourceRow({
  item,
  pulses,
  landedRow,
  landedCells,
  onOpen,
}: {
  item: EvidenceItem;
  pulses: CellPulses;
  landedRow: boolean;
  landedCells: Partial<CellPulses> | undefined;
  onOpen: () => void;
}) {
  const fade = (cell: keyof CellPulses) => (landedCells?.[cell] ? "anim-swap-in" : undefined);
  const depth = readDepthLabel(item);
  const type = item.evidence_type ? evidenceTypeLabel(scrub(item.evidence_type)) : null;
  return (
    <tr role="row" className={cn("sources-row", landedRow && "anim-swap-in")}>
      <td role="cell" className="sources-cell sources-cell-source">
        <TitleWithDescription item={item} onOpen={onOpen} />
        <SourceMetaLine item={item} />
      </td>
      <td role="cell" className="sources-cell sources-cell-year">{item.year ?? ""}</td>
      <td role="cell" className="sources-cell sources-value sources-cell-type">
        {pulses.type && <CellPulse width="w-20" />}
        {type !== null && (
          <span className={cn("sources-type", fade("type"))}>
            {item.classification_reason ? (
              <Tooltip content={<p>{scrub(item.classification_reason)}</p>}>
                <button type="button" tabIndex={-1} aria-label={`${type}: why this type`} className="sources-hint">
                  <span className="reason-word">{type}</span>
                </button>
              </Tooltip>
            ) : (
              type
            )}
          </span>
        )}
      </td>
      <td role="cell" className="sources-cell sources-value">
        {pulses.strength && <CellPulse width="w-14" />}
        {item.appraisal_tier && (
          <span className={cn("sources-nowrap", fade("strength"))}>
            <Tooltip content={<p>{scrub(strengthHint(item.appraisal_tier, item.evidence_type))}</p>}>
              <button type="button" tabIndex={-1} aria-label={`${item.appraisal_tier}: how strength is appraised`} className="sources-hint">
                {/* The strength's tone square and word, the shared mark. */}
                <StrengthMark tier={item.appraisal_tier} squareClassName="sources-tone" wordClassName="reason-word" />
              </button>
            </Tooltip>
          </span>
        )}
      </td>
      <td role="cell" className="sources-cell sources-value sources-cell-relevant">
        {pulses.relevant ? <CellPulse width="w-10" /> : (
          item.screen_status != null && <span className={fade("relevant")}><RelevantCell item={item} /></span>
        )}
      </td>
      <td role="cell" className="sources-cell sources-value sources-cell-status">
        {/* While the full texts are collected a source not yet read says so
            (owner, round 14), settling to its depth when the fetch ends. */}
        {pulses.status && <Collecting />}
        {!pulses.status && depth !== null && (
          <span className={cn("sources-nowrap", fade("status"))}>
            <DepthValue item={item} depth={depth} />
          </span>
        )}
        {item.cited && <CitedMark />}
      </td>
    </tr>
  );
}

/** Shown only while the table stacks (its column narrower than 54 rem):
 *  the year joins the source's line when its column hides. */
const STACKED_ONLY = "@min-[54rem]/sources:hidden";

/**
 * The Status cell's word (round 12): the tone square (green full text,
 * yellow abstract, red neither) and the word. "Full text" links to the
 * document's own address when the text was collected and the row carries it,
 * opening in a new tab as the report's addresses do; "Abstract only" and
 * "Title only" carry their reason on hover, out of the tab order.
 */
function DepthValue({ item, depth }: { item: EvidenceItem; depth: ReadDepth }) {
  const mark = <ToneSquare colour={readDepthColour(depth)} className="sources-tone" testId="status-mark" />;
  if (item.read_in_full) {
    const href = item.full_text_url ? safeHref(item.full_text_url) : undefined;
    return (
      <span className="text-navy">
        {mark}
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${depth} (opens the document in a new tab)`}
            className="sources-text-link"
          >
            {depth}
          </a>
        ) : (
          depth
        )}
      </span>
    );
  }
  return (
    <Tooltip content={<p>{scrub(readDepthHint(item) ?? "")}</p>}>
      <button type="button" tabIndex={-1} aria-label={`${depth}: why`} className="sources-hint text-grey">
        {mark}
        <span className="reason-word">{depth}</span>
      </button>
    </Tooltip>
  );
}

/** A set the funnel opened the table on (round 13): the applied Navy chip,
 *  its × clearing it, as Cited is. */
function SetChip({ words, onClear }: { words: string; onClear: () => void }) {
  return (
    <span className={APPLIED_CHIP_CLASS}>
      <button type="button" aria-pressed onClick={onClear} className={cn(APPLIED_CHIP_PART_CLASS, "pl-2.5 pr-2")}>
        {words}
        <CloseIcon size={12} />
      </button>
    </span>
  );
}

/** The Status of a source whose full text is being collected (round 14):
 *  "Collecting…" in Grey on the soft breathe, a Line 2 square in the tone
 *  square's slot, one rhythm; still under reduced motion. */
function Collecting() {
  return (
    <span data-testid="status-collecting" className="sources-nowrap anim-breathe-soft text-grey">
      <span aria-hidden="true" data-tone="pending" className="sources-tone inline-block size-1.5 shrink-0 bg-line-2" />
      Collecting…
    </span>
  );
}

/** A cited source, under its Status (round 12, in place of the chip): a
 *  12 px Green tick and the word, Meta Ink. */
function CitedMark() {
  return (
    <span className="sources-cited">
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="h-3 w-3 shrink-0 text-green"
        fill="none"
        stroke="currentColor"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 12.5l5 5L20 6.5" />
      </svg>
      Cited
    </span>
  );
}

/** The title's second line: "Venue · Origin" (lead, round 10: Origin folds
 *  in here). While the table stacks the year joins it after the venue, its
 *  column hidden. */
function SourceMetaLine({ item }: { item: EvidenceItem }) {
  const pieces: Array<{ key: string; text: string; phoneOnly: boolean }> = [];
  if (item.venue) pieces.push({ key: "venue", text: scrub(item.venue), phoneOnly: false });
  if (item.year != null) pieces.push({ key: "year", text: String(item.year), phoneOnly: true });
  if (item.origin) pieces.push({ key: "origin", text: scrub(item.origin), phoneOnly: false });
  if (pieces.length === 0) return null;
  return (
    <p className="sources-meta">
      {pieces.map((piece, index) => {
        // A separator next to the phone-only year shows on phones only,
        // unless it stands between two pieces shown at every width.
        const before = pieces[index - 1];
        const sepPhoneOnly = piece.phoneOnly || (before?.phoneOnly === true && index - 1 === 0);
        return (
          <span key={piece.key}>
            {index > 0 && <span className={sepPhoneOnly ? STACKED_ONLY : undefined}>{" · "}</span>}
            <span className={piece.phoneOnly ? STACKED_ONLY : undefined}>{piece.text}</span>
          </span>
        );
      })}
    </p>
  );
}

/** The list's loading state in the table's own frame: the real header row
 *  and six rows at about the real row height, a placeholder bar where the
 *  title and its line will sit and one in every value column, each sized to
 *  its column (owner, round 13: Relevant and Status were blank). They breathe
 *  together, and hold still under reduced motion. */
function SourcesLoading({ header }: { header: ReactNode }) {
  return (
    <div className="sources-frame" aria-busy="true" aria-label="Loading sources" role="status">
      <table role="presentation" className="sources-table">
        <SourcesColumns />
        {header}
        <tbody>
          {Array.from({ length: 6 }).map((_, index) => (
            <tr key={index} aria-hidden="true" className="sources-row sources-row-skeleton">
              <td className="sources-cell sources-cell-source">
                <span className="placeholder-bar h-3 w-3/5" />
                <span className="placeholder-bar mt-3 h-2.5 w-2/5" />
              </td>
              <td className="sources-cell sources-cell-year"><span className="placeholder-bar h-2.5 w-10" /></td>
              <td className="sources-cell sources-value sources-cell-type"><span className="placeholder-bar h-2.5 w-24" /></td>
              <td className="sources-cell sources-value"><span className="placeholder-bar h-2.5 w-16" /></td>
              {/* Relevant's figure sits at the right, so its bar does too. */}
              <td className="sources-cell sources-value sources-cell-relevant"><span className="placeholder-bar ml-auto h-2.5 w-10" /></td>
              <td className="sources-cell sources-value sources-cell-status"><span className="placeholder-bar h-2.5 w-16" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** An empty table: its frame with a label and, when there is one, one plain
 *  sentence, left-aligned at the table's edge (the list pages' pattern). */
function SourcesEmpty({ label, children, action }: { label: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div role="status" className="sources-frame flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-5 pl-4 pr-1">
      <div>
        <p className="text-body font-semibold text-navy">{label}</p>
        {children != null && <p className="mt-1 text-body text-grey">{children}</p>}
      </div>
      {action}
    </div>
  );
}

/** Nothing matches the filters: say how many the screening view holds
 *  without them, and offer to clear them. Asks for that total only here. */
function SourcesNoMatch({
  taskId,
  status,
  onClear,
}: {
  taskId: string;
  status: EvidenceQuery["status"];
  onClear: () => void;
}) {
  const unfiltered = useEvidence(taskId, { page: 1, page_size: 1, status });
  const total = unfiltered.data?.pagination.total_items ?? 0;
  return (
    <SourcesEmpty
      label="No sources match"
      action={
        <Button variant="ghost" className={FRAME_CONTROL_CLASS} onClick={onClear}>
          Clear filters
        </Button>
      }
    >
      {total > 0 ? `Clear the filters to see all ${total.toLocaleString("en-GB")}.` : null}
    </SourcesEmpty>
  );
}

/** The title cell's button: opens the dossier on click and, when the source
 *  carries a description, previews it (clamped) on hover. */
function TitleWithDescription({ item, onOpen }: { item: Parameters<typeof screeningDetails>[0] & { title: string; abstract?: string | null; abstract_source?: string | null }; onOpen: () => void }) {
  const button = (
    <button
      type="button"
      onClick={onOpen}
      className="cursor-pointer text-left text-body font-semibold leading-snug text-navy hover:text-blue hover:underline hover:underline-offset-[3px]"
    >
      {scrub(item.title)}
    </button>
  );
  if (!item.abstract) return button;
  const clamped = item.abstract.length > 300 ? `${item.abstract.slice(0, 300)}…` : item.abstract;
  return (
    <Tooltip
      content={
        <p className="max-w-prose-measure">
          {item.abstract_source === "llm_description" && <span className="font-semibold">AI description — </span>}
          {scrub(clamped)}
        </p>
      }
    >
      {button}
    </Tooltip>
  );
}

/** A CSV cell: quoted/escaped, and defused against spreadsheet formula
 *  injection — titles and venues arrive from external sources. */
function csvCell(value: string | number | boolean | null | undefined): string {
  let text = value === null || value === undefined ? "" : String(value);
  // Also defuse markers behind leading whitespace ("\t=SUM…").
  if (/^\s*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

/** Downloads the whole source list (every page, no filters) as a CSV file.
 *  An outline control at the filter bar's right end (round 11): the table
 *  has no single forward action, so nothing here takes the blue primary
 *  (lead, round 10). */
function DownloadSourcesButton({ taskId, taskName }: { taskId: string; taskName?: string }) {
  const client = useApiClient();
  const [downloading, setDownloading] = useState(false);
  const [failed, setFailed] = useState(false);

  const download = async () => {
    setDownloading(true);
    setFailed(false);
    try {
      const rows = [];
      // ponytail: offset pagination, no snapshot — a source arriving mid-download
      // can shift pages; add a cursor if downloads during active runs matter.
      for (let page = 1; ; page += 1) {
        const { data, error } = await client.GET("/api/v1/tasks/{task_id}/evidence", {
          params: { path: { task_id: taskId }, query: { page, page_size: 200 } },
        });
        if (data === undefined) throw error;
        rows.push(...data.data);
        if (page * data.pagination.page_size >= data.pagination.total_items) break;
      }
      const header = ["Title", "Venue", "Year", "Origin", "Status", "Status reason", "Evidence type", "Evidence type reason", "Strength", "Screening", "Screening confidence", "Screening reason", "Full text", "Cited", "URL", "Description", "Description source"];
      const csv = [
        header.map(csvCell).join(","),
        ...rows.map((item) => [
          item.title,
          item.venue,
          item.year,
          item.origin,
          item.status,
          item.status_reason,
          item.evidence_type,
          item.classification_reason,
          item.appraisal_tier,
          item.screen_status,
          item.screen_confidence,
          item.screen_reason,
          item.read_in_full,
          item.cited,
          item.url,
          item.abstract,
          item.abstract_source === "llm_description" ? "AI description" : item.abstract_source,
        ].map(csvCell).join(",")),
      ].join("\r\n");
      // UTF-8 BOM so spreadsheet apps decode non-ASCII source text correctly.
      const url = URL.createObjectURL(new Blob(["﻿", csv], { type: "text/csv;charset=utf-8" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${(taskName ?? "Task").replaceAll(/[\\/]/g, "-")} - sources.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setFailed(true);
    } finally {
      setDownloading(false);
    }
  };

  // The quiet control with the download glyph (round 12: the outline box
  // read as one more filter), at the end of the line under the table.
  return (
    <span className="flex items-center gap-3">
      {failed && <span role="alert" className="text-meta text-red">The download failed. Try again.</span>}
      <button
        type="button"
        disabled={downloading}
        onClick={() => void download()}
        className="group inline-flex h-8 cursor-pointer items-center gap-1.5 whitespace-nowrap text-meta font-semibold text-grey transition-colors duration-150 hover:text-navy disabled:cursor-default disabled:hover:text-grey"
      >
        <DownloadIcon className="shrink-0" />
        <span className="underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 group-hover:decoration-navy group-disabled:no-underline">
          {downloading ? "Preparing…" : "Download CSV"}
        </span>
      </button>
    </span>
  );
}

/** The strength column's legend (round 12): each tone square beside the
 *  tiers it marks, in the sort's order. */
function StrengthLegend() {
  return (
    <ul aria-label="Evidence strength tones" className="space-y-1">
      {STRENGTH_LEGEND.map(({ colour, tiers }) => (
        <li key={colour} className="flex items-center gap-2">
          <ToneSquare colour={colour} />
          {tiers}
        </li>
      ))}
    </ul>
  );
}

/** The sort mark: a 12 px arrow at the funnel's 2 px stroke. Its slot is
 *  always reserved, so a label never shifts as sorting changes. */
function SortArrow({ order }: { order: SortOrder | null }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      data-testid="sort-arrow"
      className={cn(
        "h-3 w-3 shrink-0",
        order === null
          ? "text-line-2 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"
          : "text-navy",
        order === "asc" && "rotate-180",
      )}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 4v16M6 14l6 6 6-6" />
    </svg>
  );
}

/** One sortable `<th>` in the sources table: a real button (accessible name
 *  "Sort by <label>"), `aria-sort` on the header itself, and the arrow once
 *  this column is the active sort (Line 2 on hover and focus otherwise).
 *  Clicking cycles none → the column's default direction → the opposite →
 *  none, and the caller re-derives `sort`/`order` URL params from that (no
 *  client-side sort of the page — the 025 filters pattern). Every header is
 *  one line and bottom-aligned, so the labels and arrows share a baseline. */
function SortableColumnHeader({
  column,
  activeSort,
  activeOrder,
  onSort,
  align = "start",
  className,
  hint,
}: {
  column: (typeof SOURCE_SORT_COLUMNS)[number];
  /** A legend shown on hover and focus (the strength's tones, round 12). */
  hint?: ReactNode;
  activeSort: EvidenceSortField | null;
  activeOrder: SortOrder | null;
  onSort: (field: EvidenceSortField) => void;
  align?: "start" | "end";
  className?: string;
}) {
  const order = activeSort === column.key ? activeOrder : null;
  const ariaSort = order === "asc" ? "ascending" : order === "desc" ? "descending" : "none";
  const button = (
    <button
      type="button"
      aria-label={`Sort by ${column.label.toLowerCase()}`}
      onClick={() => onSort(column.key)}
      className={cn(
        "group inline-flex min-h-6 cursor-pointer items-center gap-1 py-1 transition-colors duration-150 hover:text-navy",
        TABLE_HEADER_TEXT_CLASS,
        order !== null && "text-navy",
        align === "end" && "flex-row-reverse",
      )}
    >
      {column.label}
      <SortArrow order={order} />
    </button>
  );
  return (
    <th role="columnheader" scope="col" className={cn("sources-th", align === "end" && "text-right", className)} aria-sort={ariaSort}>
      {hint === undefined ? button : <Tooltip content={hint}>{button}</Tooltip>}
    </th>
  );
}

function parseYearParam(value: string | null): number | undefined {
  const year = Number(value);
  return value !== null && Number.isInteger(year) && year >= 1000 && year <= 3000
    ? year
    : undefined;
}

/** A filter control's chevron: 12 px, the trigger's colour. */
function SelectChevron() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="h-3 w-3 shrink-0 opacity-70"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

/**
 * A filter's trigger in the filter bar (round 11). Idle, the outline box
 * with the facet's name and a chevron ("Evidence type"); applied, the
 * filled Navy chip with the facet and its value ("Strength: Moderate") and
 * a × that clears it. The words open the choices either way.
 */
const FilterTrigger = forwardRef<
  HTMLButtonElement,
  {
    label: string;
    /** The chosen value in words; `null` when the filter is idle. */
    shown: string | null;
    name: string;
    onClear?: () => void;
    clearName?: string;
  } & ComponentPropsWithoutRef<"button">
>(function FilterTrigger({ label, shown: value, name, onClear, clearName, className, ...props }, ref) {
  if (value === null || onClear === undefined) {
    return (
      <button ref={ref} type="button" aria-label={name} className={cn(FILTER_CONTROL_IDLE, className)} {...props}>
        <span className="truncate">{value === null ? label : <Figures text={`${label}: ${value}`} />}</span>
        <SelectChevron />
      </button>
    );
  }
  return (
    <span className={cn(APPLIED_CHIP_CLASS, className)}>
      <button ref={ref} type="button" aria-label={name} className={cn(APPLIED_CHIP_PART_CLASS, "pl-2.5 pr-2")} {...props}>
        <span className="truncate max-md:max-w-52">
          <Figures text={`${label}: ${value}`} />
        </span>
      </button>
      <button
        type="button"
        aria-label={clearName ?? `Clear the ${label.toLowerCase()} filter`}
        onClick={onClear}
        className={cn(APPLIED_CHIP_PART_CLASS, "border-l border-navy-line px-2")}
      >
        <CloseIcon size={12} />
      </button>
    </span>
  );
});

/** The Year filter in the filter bar: "Year" idle, "Year: 2015 to 2020" as
 *  the applied chip; a popover of two four-digit fields that apply on
 *  leaving a field or on Enter. */
function YearFilter({
  from,
  to,
  onChange,
}: {
  from: number | undefined;
  to: number | undefined;
  onChange: (from: number | undefined, to: number | undefined) => void;
}) {
  const range = yearRangeLabel(from, to);
  const field = "mt-1 h-10 w-full border border-line-2 bg-paper px-3 text-meta font-normal text-navy";
  return (
    <Popover>
      <PopoverTrigger asChild>
        <FilterTrigger
          label="Year"
          shown={range}
          name={`Filter by year: ${range === null ? "any" : range}`}
          onClear={() => onChange(undefined, undefined)}
          clearName="Clear the year filter"
        />
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 max-w-[calc(100vw-2rem)] p-4">
        {/* Uncontrolled + apply-on-blur/Enter so partial typing ("20…")
            never gets clobbered by a controlled reset. */}
        <div className="flex items-start gap-3">
          <label className="flex-1 text-meta font-semibold text-grey">
            From
            <input
              key={`from-${from ?? "any"}`}
              type="text"
              inputMode="numeric"
              pattern="[0-9]{4}"
              maxLength={4}
              defaultValue={from ?? ""}
              onBlur={(event) => onChange(parseYearParam(event.target.value || null), to)}
              onKeyDown={(event) => {
                if (event.key === "Enter") event.currentTarget.blur();
              }}
              placeholder="Any"
              className={field}
            />
          </label>
          <label className="flex-1 text-meta font-semibold text-grey">
            To
            <input
              key={`to-${to ?? "any"}`}
              type="text"
              inputMode="numeric"
              pattern="[0-9]{4}"
              maxLength={4}
              defaultValue={to ?? ""}
              onBlur={(event) => onChange(from, parseYearParam(event.target.value || null))}
              onKeyDown={(event) => {
                if (event.key === "Enter") event.currentTarget.blur();
              }}
              placeholder="Any"
              className={field}
            />
          </label>
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** One facet dropdown in the sources filter bar: the app's one dropdown
 *  (`Select`, round 12) with the bar's own trigger. With `allLabel` the list
 *  opens on an "all" choice (value "") and a chosen value turns the control
 *  into the applied chip; without it (Sort) every choice is one of
 *  `options` and the control stays an outline box naming its value. */
function FilterSelect({
  label,
  allLabel,
  value,
  options,
  onChange,
  className,
}: {
  label: string;
  allLabel?: string;
  value: string;
  options: ReadonlyArray<{ value: string; label: string }>;
  onChange: (value: string) => void;
  className?: string;
}) {
  const facet = allLabel !== undefined;
  const choices = facet ? [{ value: "", label: allLabel }, ...options] : options;
  return (
    <Select
      label={label}
      value={value}
      options={choices}
      onChange={onChange}
      // Long theme names wrap in the list rather than size the closed control.
      contentClassName="w-72"
      renderTrigger={({ open, chosen }) => (
        <FilterTrigger
          label={label}
          shown={facet ? (value === "" ? null : (chosen?.label ?? value)) : (chosen?.label ?? null)}
          name={`${label}: ${chosen?.label ?? allLabel ?? ""}`}
          onClear={facet ? () => onChange("") : undefined}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={className}
        />
      )}
    />
  );
}

/** A value on its way (owner, round 8): a short grey bar, breathing on the
 *  status mark's 1.6 s rhythm, in the cell the running stage will fill. It
 *  sits where the value will, and holds still under reduced motion. */
function CellPulse({ width }: { width: string }) {
  return (
    <span aria-hidden="true" data-testid="cell-pulse" className="sources-pulse">
      <span className={`placeholder-bar h-2.5 ${width}`} />
    </span>
  );
}

/** A 12 px tick or cross at the 2 px stroke, before the screening figure. */
function VerdictMark({ relevant }: { relevant: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={cn("h-3 w-3 shrink-0", relevant ? "text-green" : "text-red")}
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {relevant ? <path d="M4 12.5l5 5L20 6.5" /> : <path d="M6 6l12 12M18 6L6 18" />}
    </svg>
  );
}

/** The screening verdict: the mark and the confidence figure, right-aligned
 *  in tabular figures (the default sort key reads as a ranked figure); the
 *  LLM's reasoning on hover, out of the tab order. Its name carries the
 *  figure ("Relevant, 99% confidence: screening details"). */
function RelevantCell({ item }: { item: Parameters<typeof screeningDetails>[0] }) {
  if (item.screen_status === null || item.screen_status === undefined) return null;
  const retracted = item.screen_status === "excluded_retracted";
  const relevant = item.screen_status === "relevant";
  const verdict = retracted ? "Excluded — retracted" : relevant ? "Relevant" : "Not relevant";
  const figure =
    !retracted && item.screen_confidence !== null && item.screen_confidence !== undefined
      ? `${Math.round(item.screen_confidence * 100)}%`
      : null;
  const name = figure !== null ? `${verdict}, ${figure} confidence: screening details` : `${verdict}: screening details`;
  const content = (
    <p>
      {retracted
        ? "The record was retracted, so it is excluded regardless of relevance."
        : item.screen_reason
          ? scrub(item.screen_reason)
          : "No screening reasoning was recorded."}
    </p>
  );
  return (
    <Tooltip content={content}>
      <button type="button" tabIndex={-1} aria-label={name} className="sources-hint">
        <VerdictMark relevant={relevant} />
        {figure !== null && <span className="reason-word tabular-nums text-navy">{figure}</span>}
        {retracted && <span className="reason-word text-red">retracted</span>}
      </button>
    </Tooltip>
  );
}

function SourceDossier({
  taskId,
  sourceId,
  optionId,
  source,
  isPending,
  isError,
  findings,
  findingsPending,
  onClose,
}: {
  taskId: string;
  sourceId: string | null;
  optionId: string | null;
  source: components["schemas"]["SourceDossierOut"] | undefined;
  isPending: boolean;
  isError: boolean;
  findings: components["schemas"]["FindingOut"][] | undefined;
  findingsPending: boolean;
  onClose: () => void;
}) {
  const records = useDossierRecords(taskId, sourceId, optionId);
  if (!sourceId) return null;
  return (
    <Sheet open onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent title={source ? scrub(source.title) : "Source dossier"}>
        {isPending && <p role="status" className="anim-breathe-soft text-body text-grey">{DOSSIER_LOADING_LINE}</p>}
        {isError && <p role="alert" className="text-body text-navy">This source dossier couldn't be loaded.</p>}
        {source && (
          <SourceDossierBody
            records={records}
            source={source}
            findings={findings}
            findingsPending={findingsPending}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

/** The authors line with superscript affiliation markers (042 D5). Renders
 *  nothing when the source carries no authors (honest absence). Shared by the
 *  dossier header and the citation block in ArtefactView. */
export function AuthorsLine({
  authorships,
  className,
}: {
  authorships: components["schemas"]["AuthorshipOut"][] | undefined;
  className?: string;
}) {
  const numbered = numberedAuthorships(authorships);
  if (numbered.authors.length === 0) return null;
  return (
    <p className={className}>
      {numbered.authors.map((author, index) => (
        <span key={`${author.name}-${index}`}>
          {index > 0 && ", "}
          {scrub(author.name)}
          {author.markers.length > 0 && <sup>{author.markers.join(",")}</sup>}
        </span>
      ))}
    </p>
  );
}

/** The numbered institutions under the year line (042 D5): deduped, ordered
 *  by first appearance, numbers matching the AuthorsLine markers. */
export function InstitutionsLine({
  authorships,
  className,
}: {
  authorships: components["schemas"]["AuthorshipOut"][] | undefined;
  className?: string;
}) {
  const numbered = numberedAuthorships(authorships);
  if (numbered.institutions.length === 0) return null;
  return (
    <p className={className}>
      {numbered.institutions.map((institution, index) => (
        <span key={institution}>
          {index > 0 && " · "}
          <sup>{index + 1}</sup> {scrub(institution)}
        </span>
      ))}
    </p>
  );
}

/** The labelled lines of one intervention profile record, in its own words
 *  (task 046, amendment 3, R67). A field the record does not state is left out. */
const RECORD_LINES = [
  ["Intervention", "intervention"],
  ["Setting", "setting"],
  ["Tried on", "unit"],
  ["Outcomes measured", "outcome"],
  ["Where", "study_geography"],
  ["Role", "role"],
] as const;

function RecordEntry({
  record,
  withOption,
}: {
  record: components["schemas"]["OptionRecordOut"];
  withOption: boolean;
}) {
  return (
    <div className="border-b border-line py-3 first:border-t">
      {withOption && <p className="text-body text-navy">{scrub(record.option_name)}</p>}
      <dl className="mt-1 space-y-1">
        {RECORD_LINES.map(([label, key]) => {
          const value = record[key];
          if (value === null || value === undefined || value.trim() === "") return null;
          return (
            <div key={key} className="flex gap-3">
              <dt className="w-36 shrink-0 text-grey">{label}</dt>
              <dd className="text-navy">{scrub(value)}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

/** A dossier's option records on an options-scoping task (none otherwise),
 *  and whether it was opened from an option card. */
export type DossierRecords = {
  records: components["schemas"]["OptionRecordOut"][] | undefined;
  pending: boolean;
  fromOption: boolean;
};

/** The source dossier sheet's records read, shared by both sheets. */
export function useDossierRecords(
  taskId: string,
  sourceId: string | null,
  optionId: string | null | undefined,
): DossierRecords {
  const task = useTask(taskId);
  const scoping = isScoping(task.data);
  const query = useSourceRecords(taskId, sourceId, optionId, { enabled: scoping });
  return {
    records: scoping ? query.data?.records : undefined,
    pending: scoping && query.isPending,
    fromOption: optionId !== null,
  };
}

/** The source sheet's loading line, one copy for every route into it (the
 *  report, the Sources table, the option card; owner, round 13). */
export const DOSSIER_LOADING_LINE = "Loading source details…";

/** Full source provenance, used by every route into the source dossier sheet.
 *
 *  On an options-scoping task the sheet passes the document's intervention
 *  profile records; when there are any they fill the findings slot, under "In this
 *  option" when the dossier was opened from an option card (`optionId`) or
 *  "Records" otherwise, one per option. With none, the slot shows the
 *  findings as on an Evidence search task (task 046, amendment 3, R67). */
export function SourceDossierBody({
  records: dossierRecords,
  source,
  findings,
  findingsPending,
}: {
  /** From `useDossierRecords`, called by the sheet so the read starts with
   *  the dossier's own. */
  records?: DossierRecords;
  source: components["schemas"]["SourceDossierOut"];
  findings: components["schemas"]["FindingOut"][] | undefined;
  findingsPending: boolean;
}) {
  const records = dossierRecords?.records;
  const recordsPending = dossierRecords?.pending ?? false;
  const fromOption = dossierRecords?.fromOption ?? false;
  const byAsserter = new Map<string, NonNullable<typeof source.tags>>();
  for (const tag of source.tags ?? []) {
    byAsserter.set(tag.asserted_by, [...(byAsserter.get(tag.asserted_by) ?? []), tag]);
  }
  const statusLabel = sourceStatusLabel(source);
  const href = source.url ? safeHref(source.url) : undefined;
  const reference = referenceParts(source);
  const depth = readDepthLabel(source);
  const details = [
    ["Publisher", source.publisher],
    ["Record type", source.record_type],
    ["Language", source.language],
    ["DOI", source.doi],
    ["Cited by", source.cited_by_count],
    ["Field-weighted citation impact", source.fwci],
  ] as const;
  const hasAuthors = numberedAuthorships(source.authorships).authors.length > 0;
  const hasInstitutions = numberedAuthorships(source.authorships).institutions.length > 0;
  const shownDetails = details.filter(([, value]) => value !== null && value !== undefined);
  return (
    // One type scale (round 12): the sheet's title, Body for the reference
    // line and every sentence, Meta for the labels and the facts. No chips
    // and no bold below the title; the facts are ruled lists with their
    // labels at Meta Grey; the actions at the foot.
    <div className="space-y-6 text-meta text-ink">
      {/* The reference line as the report's References read it (the sheet
          header holds the title): authors (year), the venue, the address. */}
      {(reference.lead !== null || reference.venue !== null || reference.url !== null) && (
        <p data-testid="dossier-reference" className="text-body text-ink [overflow-wrap:anywhere]">
          {reference.lead !== null && <span>{scrub(reference.lead)}</span>}
          {reference.venue !== null && <span className="text-grey">{scrub(reference.venue)}</span>}
          {reference.url !== null && href !== undefined && (
            <>
              {" "}
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-grey underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 hover:text-navy hover:decoration-navy"
              >
                {displayUrl(reference.url)}
              </a>
            </>
          )}
        </p>
      )}
      <dl aria-label="About this source" className="border-t border-line">
        {source.evidence_type && <DetailRow label="Evidence type" value={evidenceTypeLabel(source.evidence_type)} />}
        {source.classification_reason && <DetailRow label="Why this type" value={source.classification_reason} prose />}
        {source.appraisal_tier && (
          <DetailRow label="Strength">
            <StrengthMark tier={source.appraisal_tier} squareClassName="sources-tone" />
          </DetailRow>
        )}
        {depth !== null && (
          <DetailRow label={STATUS_COLUMN_HEADER}>
            <DepthMark depth={depth} squareClassName="sources-tone" />
            {source.cited && <CitedMark />}
          </DetailRow>
        )}
        {source.year != null && <DetailRow label="Year" value={String(source.year)} />}
        <DetailRow label="Origin" value={source.origin} />
      </dl>
      {source.abstract && (
        <DossierSection title={abstractSourceLabel(source.abstract_source) ? "About · AI description" : "About"}>
          <p className="max-w-prose-measure text-body text-ink">{scrub(source.abstract)}</p>
        </DossierSection>
      )}
      {statusLabel && (
        <DossierSection title="What happened to it">
          <dl className="border-t border-line">
            <DetailRow label="Stage" value={statusLabel} />
            {screeningDetails(source).map(([label, value]) => (
              <DetailRow key={label} label={label} value={value} prose={label === "Reasoning" || label === "Reason"} />
            ))}
          </dl>
        </DossierSection>
      )}
      {(hasAuthors || shownDetails.length > 0) && (
        <DossierSection title="Details">
          <dl className="border-t border-line">
            {hasAuthors && (
              <DetailRow label="Authors">
                <AuthorsLine authorships={source.authorships} />
              </DetailRow>
            )}
            {hasInstitutions && (
              <DetailRow label="Institutions">
                <InstitutionsLine authorships={source.authorships} />
              </DetailRow>
            )}
            {shownDetails.map(([label, value]) => <DetailRow key={label} label={label} value={String(value)} />)}
          </dl>
        </DossierSection>
      )}
      {byAsserter.size > 0 && (
        <DossierSection title="Tags">
          <dl className="border-t border-line">
            {[...byAsserter.entries()].map(([asserter, tags]) => (
              <DetailRow key={asserter} label={`Asserted by ${scrub(asserter)}`} value={tags.map((tag) => tag.tag).join(", ")} />
            ))}
          </dl>
        </DossierSection>
      )}
      {(source.cited_in ?? []).length > 0 && (
        <DossierSection title="Cited in the report">
          <ul className="border-t border-line">
            {source.cited_in?.map((citation, index) => (
              <li key={`${citation.section_title}-${index}`} className="border-b border-line py-3">
                <p className="text-body text-navy">{scrub(citation.claim)}</p>
                <p className="mt-1 text-body italic text-grey">“{scrub(citation.quote)}”</p>
                <p className="mt-1 text-meta text-grey">{scrub(citation.section_title)}</p>
              </li>
            ))}
          </ul>
        </DossierSection>
      )}
      {records !== undefined && records.length > 0 ? (
        <DossierSection title={fromOption ? "In this option" : "Records"}>
          <div>
            {records.map((record) => (
              <RecordEntry key={`${record.option_id}-${record.record_id}`} record={record} withOption={!fromOption} />
            ))}
          </div>
        </DossierSection>
      ) : (
        <DossierSection title="Findings from this source">
          {(findingsPending || recordsPending) && <p className="text-body text-grey">Loading findings…</p>}
          {!findingsPending && !recordsPending && (!findings || findings.length === 0) && (
            <p className="text-body text-grey">No findings extracted from this source.</p>
          )}
          {!recordsPending && findings && findings.length > 0 && (
            <ul className="border-t border-line">
              {findings.map((finding) => (
                <li key={finding.finding_id} className="border-b border-line py-3">
                  <p className="text-meta text-grey">{finding.profile === "iof" ? "Intervention–outcome" : "Implementation context"}</p>
                  <p className="mt-1 text-body text-navy">{scrub(finding.statement)}</p>
                </li>
              ))}
            </ul>
          )}
        </DossierSection>
      )}
      {href && (
        <footer className="border-t border-line pt-4">
          <a href={href} target="_blank" rel="noopener noreferrer" className={buttonVariants({ variant: "outline", size: "sm" })}>
            Open original
          </a>
        </footer>
      )}
    </div>
  );
}

/** A dossier block under its label: Meta Grey, sentence case, no rule of
 *  its own (the list under it carries the rules). */
function DossierSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-meta text-grey">{title}</h3>
      {children}
    </section>
  );
}

/** One ruled fact: the label at Meta Grey in a fixed column, the value at
 *  Meta Ink (a sentence at Body, the floor for prose). */
function DetailRow({ label, value, prose = false, children }: { label: string; value?: string; prose?: boolean; children?: ReactNode }) {
  return (
    <div className="grid grid-cols-[9rem_minmax(0,1fr)] gap-4 border-b border-line py-2 max-md:grid-cols-[6.5rem_minmax(0,1fr)] max-md:gap-3">
      <dt className="text-grey">{label}</dt>
      <dd className={cn("[overflow-wrap:anywhere]", prose ? "text-body text-ink" : "text-ink")}>
        {children ?? scrub(value ?? "")}
      </dd>
    </div>
  );
}

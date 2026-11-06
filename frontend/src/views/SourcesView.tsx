import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useParams, useSearchParams } from "react-router";

import { useApiClient, useCoverage, useEvidence, useFindings, useLandscape, useTask, useSourceDossier, useSourceRecords } from "../api/queries";
import type { components } from "../api/gen/types";
import { errorCode } from "../lib/errors";
import { Figures } from "../lib/figures";
import { safeHref } from "../lib/safeHref";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { useRunStream } from "../store";
import { Button } from "../ui/brand/Button";
import { Divider, PaneHeading } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { cn } from "../ui/brand/cn";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { Sheet, SheetContent } from "../ui/radix/Sheet";
import { Tooltip } from "../ui/radix/Tooltip";
import { Arrival, ArrivalProvider, useFirstPaintDone } from "../ui/motion/arrivals";
import { queryGroups, SearchQueries } from "./SearchQueries";
import {
  abstractSourceLabel,
  cellPulses,
  evidenceTypeLabel,
  feedsSources,
  liveStages,
  nextEvidenceSort,
  readDepthHint,
  readDepthLabel,
  screeningDetails,
  sourceStatusLabel,
  strengthHint,
  yearRangeLabel,
  FACET_PARAMS,
  ORIGIN_FILTER_OPTIONS,
  PHONE_SORT_OPTIONS,
  SOURCE_SORT_COLUMNS,
  STRENGTH_FILTER_OPTIONS,
  TABLE_HEADER_TEXT_CLASS,
  filterChipClass,
  type CellPulses,
  type EvidenceSortField,
  type SortOrder,
  useLandedSources,
  useLiveRefetch,
} from "./sourcesPresentation";
import { numberedAuthorships } from "./artefactPresentation";
import { isScoping } from "./scopingActivity";
import { isFinished } from "./workspace/runProgress";
import { PANE_LABEL_CLASS } from "../ui/brand/label";
import { Pagination } from "./Pagination";
import { normaliseGeographies } from "../ui/charts/EvidenceDistributionChart";
import "./sources.css";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "Included", label: "Included" },
  { key: "screened_out", label: "Screened out" },
] as const;

const PAGE_SIZE = 50;

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
  const originFilter = ORIGIN_FILTER_OPTIONS.find((value) => value === searchParams.get("origin"));
  const typeFilter = searchParams.get("type") ?? undefined;
  const strengthFilter = STRENGTH_FILTER_OPTIONS.find(
    (value) => value === searchParams.get("strength"),
  );
  const countryFilter = searchParams.get("country") ?? undefined;
  const yearFrom = parseYearParam(searchParams.get("year_from"));
  const yearTo = parseYearParam(searchParams.get("year_to"));
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
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
  const themeOptions = (landscape.data?.themes ?? []).filter(
    (theme): theme is typeof theme & { theme_id: string } => Boolean(theme.theme_id),
  );
  // Evidence-type filter options come from the landscape distribution — the
  // same closed set the classification wrote for this task.
  const evidenceTypeOptions = Object.keys(landscape.data?.evidence_types ?? {}).sort();
  // Publisher countries as the Landscape names them (aliases folded), so a
  // geography row's link lands on a value this select shows.
  const countryOptions = Object.keys(normaliseGeographies(landscape.data?.geographies ?? {}))
    .filter((country) => country !== "Not reported")
    .sort();
  // No explicit sort → the relevance spectrum, descending (owner default:
  // confidently relevant → uncertain → confidently irrelevant).
  const effectiveSort = sortField ?? "relevance";
  const effectiveOrder = sortField !== null ? sortOrder : "desc";
  // A filter besides the screening toggles narrows the view; "Clear
  // filters" removes them all and keeps the screening choice.
  const filtered = FACET_PARAMS.some((key) => searchParams.has(key));
  const evidence = useEvidence(taskId, {
    page,
    page_size: PAGE_SIZE,
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
  });
  const dossier = useSourceDossier(taskId, sourceId);
  const findings = useFindings(taskId, sourceId ? { page_size: 200, source_id: sourceId } : undefined);
  // While a stage that feeds this table runs, the table refetches every 5 s
  // and the cells it will fill pulse until their values land (owner, round 8).
  const live = liveStages(stream);
  // The search queries, live as they go out (owner, round 9).
  const searching = live.has("acquire");
  const groups = queryGroups(stream.liveSearchQueries, coverage.data?.backends_detail, searching);
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
  const pageSize = evidence.data?.pagination.page_size ?? PAGE_SIZE;
  const totalPages = evidence.data === undefined ? 0 : Math.ceil(totalItems / pageSize);

  const updateParams = (update: (next: URLSearchParams) => void) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      update(next);
      return next;
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

  return (
    <main className="py-8">
      <SearchQueries groups={groups} searching={searching} />
      {/* One row of filters above the table they scope (task 058, round 10):
          the screening toggles as a group, Cited, the selects, and "Clear
          filters" once any narrows the view. The queries block above keeps
          32 px of air (its own 24 px margin collapses into this one). */}
      <div
        role="group"
        aria-label="Filter sources"
        className={cn("mb-4 flex flex-wrap items-center gap-x-4 gap-y-2", groups.length > 0 && "mt-8")}
      >
        <div role="group" aria-label="Screening" className="flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.key}
              type="button"
              aria-pressed={statusFilter === filter.key}
              onClick={() => updateParams((next) => {
                next.set("status", filter.key);
                next.delete("page");
              })}
              className={filterChipClass(statusFilter === filter.key)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          aria-pressed={citedFilter}
          onClick={() => setFacet("cited", citedFilter ? undefined : "true")}
          className={filterChipClass(citedFilter)}
        >
          Cited
        </button>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <FilterSelect
          label="Key theme"
          allLabel="All themes"
          value={themeFilter ?? ""}
          options={themeOptions.map((theme) => ({ value: theme.theme_id, label: scrub(theme.name) }))}
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
          options={STRENGTH_FILTER_OPTIONS.map((value) => ({ value, label: value }))}
          onChange={(value) => setFacet("strength", value)}
        />
        <FilterSelect
          label="Country"
          allLabel="All"
          value={countryFilter ?? ""}
          options={[...new Set([...countryOptions, ...(countryFilter ? [countryFilter] : [])])].map((value) => ({ value, label: scrub(value) }))}
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
        </div>
        {/* Below lg the headers are hidden, so sorting moves here. */}
        <FilterSelect
          className="lg:hidden"
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
          <Button variant="ghost" className="px-2" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
      </div>

      <div ref={results} className="scroll-mt-4">
        {evidence.isPending && <SourcesLoading header={header} />}

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

        {/* While the search runs and nothing has landed, the queries above are
            the page: the table waits for the first results (owner, round 9). */}
        {evidence.data !== undefined && rows.length === 0 && !searching && (
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
          // The count line and the table appear together, rising in, when the
          // first results land after the page opened.
          <ArrivalProvider settled={firstPaintDone} scopeKey={`${taskId}?${viewKey}`}>
          <Arrival arrivalId="sources-table">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <p className="text-meta text-grey" role="status">
                <Figures text={countLine} />
              </p>
              <DownloadSourcesButton taskId={taskId} taskName={task.data?.name} />
            </div>
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
          </Arrival>
          </ArrivalProvider>
        )}

        {evidence.data !== undefined && totalPages > 1 && (
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
        <SortableColumnHeader column={column("strength")} {...props} />
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
      <td role="cell" className="sources-cell sources-value">
        {pulses.type && <CellPulse width="w-20" />}
        {type !== null && (
          <span className={cn("sources-nowrap", fade("type"))}>
            {item.classification_reason ? (
              <Tooltip content={<p>{scrub(item.classification_reason)}</p>}>
                <button type="button" tabIndex={-1} aria-label={`${type}: why this type`} className="sources-hint">
                  {type}
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
            <Tooltip content={<p>{scrub(strengthHint(item))}</p>}>
              <button type="button" tabIndex={-1} aria-label={`${item.appraisal_tier}: how strength is appraised`} className="sources-hint">
                {scrub(item.appraisal_tier)}
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
      <td role="cell" className="sources-cell sources-value">
        {pulses.status && <CellPulse width="w-16" />}
        {!pulses.status && depth !== null && (
          <span className={cn("sources-nowrap", fade("status"))}>
            {item.read_in_full ? (
              <span className="text-navy">{depth}</span>
            ) : (
              <Tooltip content={<p>{scrub(readDepthHint(item) ?? "")}</p>}>
                <button type="button" tabIndex={-1} aria-label="Abstract only: why" className="sources-hint sources-hint-dotted text-grey">
                  {depth}
                </button>
              </Tooltip>
            )}
          </span>
        )}
      </td>
    </tr>
  );
}

/** The title's second line: "Venue · Origin" and, for a cited source, the
 *  green "Cited" chip at its end (lead, round 10: Origin and Cited fold in
 *  here). Below `lg` the year joins it after the venue, its column hidden. */
function SourceMetaLine({ item }: { item: EvidenceItem }) {
  const pieces: Array<{ key: string; text: string; phoneOnly: boolean }> = [];
  if (item.venue) pieces.push({ key: "venue", text: scrub(item.venue), phoneOnly: false });
  if (item.year != null) pieces.push({ key: "year", text: String(item.year), phoneOnly: true });
  if (item.origin) pieces.push({ key: "origin", text: scrub(item.origin), phoneOnly: false });
  if (pieces.length === 0 && !item.cited) return null;
  return (
    <p className="sources-meta">
      {pieces.map((piece, index) => {
        // A separator next to the phone-only year shows on phones only,
        // unless it stands between two pieces shown at every width.
        const before = pieces[index - 1];
        const sepPhoneOnly = piece.phoneOnly || (before?.phoneOnly === true && index - 1 === 0);
        return (
          <span key={piece.key}>
            {index > 0 && <span className={sepPhoneOnly ? "lg:hidden" : undefined}>{" · "}</span>}
            <span className={piece.phoneOnly ? "lg:hidden" : undefined}>{piece.text}</span>
          </span>
        );
      })}
      {item.cited && <Chip tone="green" className="sources-cited">Cited</Chip>}
    </p>
  );
}

/** The list's loading state in the table's own frame: the real header row
 *  and six rows at about the real row height, a placeholder bar where the
 *  title and its line will sit and one in Year, type and strength. They
 *  breathe, and hold still under reduced motion. */
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
              <td className="sources-cell sources-value"><span className="placeholder-bar h-2.5 w-14" /></td>
              <td className="sources-cell sources-value"><span className="placeholder-bar h-2.5 w-14" /></td>
              <td className="sources-cell sources-value" />
              <td className="sources-cell sources-value" />
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
 *  An outline control beside the count line: the table has no single
 *  forward action, so nothing here takes the blue primary (lead, round 10). */
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

  return (
    <span className="flex items-center gap-3">
      {failed && <span role="alert" className="text-meta text-red">The download failed. Try again.</span>}
      <Button type="button" variant="outline" size="sm" className="h-10 py-0" disabled={downloading} onClick={() => void download()}>
        {downloading ? "Preparing…" : "Download CSV"}
      </Button>
    </span>
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
}: {
  column: (typeof SOURCE_SORT_COLUMNS)[number];
  activeSort: EvidenceSortField | null;
  activeOrder: SortOrder | null;
  onSort: (field: EvidenceSortField) => void;
  align?: "start" | "end";
  className?: string;
}) {
  const order = activeSort === column.key ? activeOrder : null;
  const ariaSort = order === "asc" ? "ascending" : order === "desc" ? "descending" : "none";
  return (
    <th role="columnheader" scope="col" className={cn("sources-th", align === "end" && "text-right", className)} aria-sort={ariaSort}>
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
    </th>
  );
}

function parseYearParam(value: string | null): number | undefined {
  const year = Number(value);
  return value !== null && Number.isInteger(year) && year >= 1000 && year <= 3000
    ? year
    : undefined;
}

/** The filter row's control: a 1 px Line 2 box on Paper, Meta Semibold
 *  Navy, its chevron Grey; the same box opens a listbox or the year range. */
const SELECT_TRIGGER_CLASS =
  "inline-flex min-h-[34px] min-w-0 cursor-pointer items-center justify-between gap-2 border border-line-2 bg-paper px-2.5 py-1.5 text-meta font-semibold text-navy transition-colors duration-150 hover:border-navy max-md:max-w-52";

function SelectChevron() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="h-3.5 w-3.5 shrink-0 text-grey"
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

/** The Year filter in the filter row: the range in words on the control
 *  ("Any", "2015 to 2020"), a popover of two four-digit fields that apply on
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
  const labelId = useId();
  const range = yearRangeLabel(from, to);
  const field = "mt-1 h-10 w-full border border-line-2 bg-paper px-3 text-meta font-normal text-navy";
  return (
    <span className="flex min-w-0 max-w-full items-center gap-1.5 text-meta font-semibold text-grey">
      <span id={labelId} aria-hidden="true" className="whitespace-nowrap">Year</span>
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={`Filter by year: ${range === null ? "any" : range}`}
            className={SELECT_TRIGGER_CLASS}
          >
            <span className="truncate"><Figures text={range ?? "Any"} /></span>
            <SelectChevron />
          </button>
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
          {range !== null && (
            <button
              type="button"
              onClick={() => onChange(undefined, undefined)}
              className="mt-3 cursor-pointer text-meta font-semibold text-grey underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 hover:text-navy hover:decoration-navy"
            >
              Clear
            </button>
          )}
        </PopoverContent>
      </Popover>
    </span>
  );
}

/** One facet dropdown in the sources filter row. With `allLabel` the list
 *  opens on an "all" choice (value ""); without it (Sort) every choice is
 *  one of `options`. */
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
  // App-styled Popover listbox (the NewTaskView ProjectPicker pattern), not a
  // native <select>: consistent chrome at every width, and long theme names
  // wrap in the menu instead of sizing (and overflowing) the closed control.
  const [open, setOpen] = useState(false);
  const triggerId = useId();
  const labelId = useId();
  const valueId = useId();
  const listRef = useRef<HTMLUListElement>(null);
  const selected = options.find((option) => option.value === value);
  const pick = (next: string) => {
    onChange(next);
    setOpen(false);
  };
  const optionButtons = () =>
    Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? []);
  // The native <select> this replaced gave arrow-key navigation for free;
  // Radix Popover only owns Esc/dismiss/focus-return, so the listbox moves
  // focus itself (040 review finding).
  const onListKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const buttons = optionButtons();
    if (buttons.length === 0) return;
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? buttons.length - 1
          : event.key === "ArrowDown"
            ? Math.min(current + 1, buttons.length - 1)
            : Math.max(current - 1, 0);
    buttons[next]?.focus();
  };
  const optionClass = (active: boolean) =>
    cn(
      "block w-full cursor-pointer px-3 py-2 text-left text-meta font-normal text-navy hover:bg-blue-tint-2 hover:text-blue",
      active && "bg-blue-tint-2 font-semibold",
    );
  const choices = allLabel === undefined ? options : [{ value: "", label: allLabel }, ...options];
  return (
    <span className={cn("flex min-w-0 max-w-full items-center gap-1.5 text-meta font-semibold text-grey", className)}>
      <label id={labelId} htmlFor={triggerId} className="cursor-pointer whitespace-nowrap">
        {label}
      </label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            id={triggerId}
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-labelledby={`${labelId} ${valueId}`}
            className={SELECT_TRIGGER_CLASS}
          >
            <span id={valueId} className="truncate">{selected?.label ?? allLabel ?? ""}</span>
            <SelectChevron />
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-72 max-w-[calc(100vw-2rem)] p-1"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            const buttons = optionButtons();
            (buttons.find((button) => button.getAttribute("aria-selected") === "true") ?? buttons[0])?.focus();
          }}
        >
          <ul
            ref={listRef}
            role="listbox"
            aria-labelledby={labelId}
            onKeyDown={onListKeyDown}
            className="flex max-h-80 flex-col overflow-y-auto"
          >
            {choices.map((option) => (
              <li key={option.value} role="none">
                <button
                  type="button"
                  role="option"
                  aria-selected={value === option.value}
                  onClick={() => pick(option.value)}
                  className={optionClass(value === option.value)}
                >
                  {option.label}
                </button>
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>
    </span>
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
        {figure !== null && <span className="tabular-nums text-navy">{figure}</span>}
        {retracted && <span className="text-red">retracted</span>}
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
        {isPending && <p role="status" className="anim-breathe text-body text-grey">Loading the dossier…</p>}
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
    <div className="border-l-2 border-line-2 pl-3">
      {withOption && <p className="text-body font-semibold text-navy">{scrub(record.option_name)}</p>}
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
  const details = [
    ["Publisher", source.publisher],
    ["Record type", source.record_type],
    ["Language", source.language],
    ["DOI", source.doi],
    ["Cited by", source.cited_by_count],
    ["Field-weighted citation impact", source.fwci],
  ] as const;
  return (
    <div className="space-y-6 text-caption">
      <header>
        {/* The sheet header already shows the title (042 item 4) — the body
            starts at the authors line. */}
        <AuthorsLine authorships={source.authorships} className="text-grey" />
        {(source.year || source.venue) && <p className="mt-1 text-grey">{[source.year, source.venue].filter(Boolean).map(String).map(scrub).join(" · ")}</p>}
        <InstitutionsLine authorships={source.authorships} className="mt-1 text-grey" />
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Chip tone="soft">{scrub(source.origin)}</Chip>
          {source.appraisal_tier && <Chip tone="soft">{scrub(source.appraisal_tier)}</Chip>}
          {href && <a className="border border-blue px-2.5 py-1 text-caption font-semibold text-blue hover:underline" href={href} target="_blank" rel="noreferrer">Open original</a>}
        </div>
      </header>
      {source.abstract && (
        <DossierSection title="About">
          {abstractSourceLabel(source.abstract_source) && <Chip tone="yellow">AI description</Chip>}
          <p className="mt-2 max-w-prose-measure text-body text-grey">{scrub(source.abstract)}</p>
        </DossierSection>
      )}
      {statusLabel && (
        <DossierSection title="What happened to it">
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip tone="soft">{statusLabel}</Chip>
            {readDepthLabel(source) !== null && (
              <Chip tone={source.read_in_full ? "blue" : "yellow"}>{readDepthLabel(source)}</Chip>
            )}
          </div>
          <dl className="mt-3 space-y-1.5">
            {screeningDetails(source).map(([label, value]) => <DetailRow key={label} label={label} value={value} />)}
          </dl>
        </DossierSection>
      )}
      {(source.evidence_type || source.appraisal_tier) && (
        <DossierSection title="Quality">
          <dl className="space-y-1.5">
            {source.evidence_type && <DetailRow label="Evidence type" value={evidenceTypeLabel(source.evidence_type)} />}
            {source.classification_reason && (
              <DetailRow label="Why this type" value={source.classification_reason} />
            )}
            {source.appraisal_tier && <DetailRow label="Appraised strength" value={source.appraisal_tier} />}
          </dl>
        </DossierSection>
      )}
      {details.some(([, value]) => value !== null && value !== undefined) && (
        <DossierSection title="Details">
          <dl className="space-y-1.5">{details.filter(([, value]) => value !== null && value !== undefined).map(([label, value]) => <DetailRow key={label} label={label} value={String(value)} />)}</dl>
        </DossierSection>
      )}
      {byAsserter.size > 0 && (
        <DossierSection title="Tags">
          {[...byAsserter.entries()].map(([asserter, tags]) => (
            <div key={asserter} className="mb-3">
              <p className={cn(PANE_LABEL_CLASS, "mb-1")}>Asserted by {scrub(asserter)}</p>
              <div className="flex flex-wrap gap-1.5">{tags.map((tag) => <Chip key={`${tag.tag_type}-${tag.tag}`} tone="soft">{scrub(tag.tag)}</Chip>)}</div>
            </div>
          ))}
        </DossierSection>
      )}
      {(source.cited_in ?? []).length > 0 && (
        <DossierSection title="Cited in the report">
          <div className="space-y-3">{source.cited_in?.map((citation, index) => (
            <div key={`${citation.section_title}-${index}`} className="border-l-2 border-blue pl-3">
              <p className="text-body leading-snug text-navy">{scrub(citation.claim)}</p>
              <p className="mt-1 text-body italic text-grey">“{scrub(citation.quote)}”</p>
              <p className={cn(PANE_LABEL_CLASS, "mt-1")}>{scrub(citation.section_title)}</p>
            </div>
          ))}</div>
        </DossierSection>
      )}
      {records !== undefined && records.length > 0 ? (
        <DossierSection title={fromOption ? "In this option" : "Records"}>
          <div className="space-y-3">
            {records.map((record) => (
              <RecordEntry key={`${record.option_id}-${record.record_id}`} record={record} withOption={!fromOption} />
            ))}
          </div>
        </DossierSection>
      ) : (
      <DossierSection title="Findings from this source">
        {(findingsPending || recordsPending) && <p className="text-body text-grey">Loading findings…</p>}
        {!findingsPending && !recordsPending && (!findings || findings.length === 0) && <p className="text-body text-grey">No findings extracted from this source.</p>}
        {!recordsPending && findings && findings.length > 0 && <div className="space-y-2">{findings.map((finding) => (
          <div key={finding.finding_id} className="border-l-2 border-line-2 pl-3">
            <Chip tone="soft">{finding.profile === "iof" ? "Intervention–outcome" : "Implementation context"}</Chip>
            <p className="mt-1 text-body leading-snug text-navy">{scrub(finding.statement)}</p>
          </div>
        ))}</div>}
      </DossierSection>
      )}
    </div>
  );
}

function DossierSection({ title, children }: { title: string; children: ReactNode }) {
  return <section><PaneHeading className="px-0 pt-0">{title}</PaneHeading><Divider className="mb-3" />{children}</section>;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between gap-4"><dt className="text-grey">{label}</dt><dd className="text-right text-navy">{scrub(value)}</dd></div>;
}

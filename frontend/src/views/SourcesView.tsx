import type { ReactNode } from "react";
import { useParams, useSearchParams } from "react-router";

import { useEvidence, useFindings, useLandscape, useProject, useSourceDossier } from "../api/queries";
import type { components } from "../api/gen/types";
import { errorCode } from "../lib/errors";
import { safeHref } from "../lib/safeHref";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Card, Divider, PaneHeading } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { Sheet, SheetContent } from "../ui/radix/Sheet";
import { Tooltip } from "../ui/radix/Tooltip";
import {
  abstractSourceLabel,
  nextEvidenceSort,
  readDepthHint,
  readDepthLabel,
  screeningDetails,
  sourceStatusLabel,
  strengthHint,
  ORIGIN_FILTER_OPTIONS,
  SOURCE_SORT_COLUMNS,
  STRENGTH_FILTER_OPTIONS,
  type EvidenceSortField,
  type SortOrder,
} from "./sourcesPresentation";

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "Included", label: "Included" },
  { key: "screened_out", label: "Screened out" },
] as const;

/** Sources: collection-true server filters and a URL-addressable source dossier. */
export function SourcesView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const landscape = useLandscape(projectId);
  useDocumentTitle(project.data?.name, "Sources");
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedStatus = searchParams.get("status");
  const statusFilter =
    STATUS_FILTERS.find((filter) => filter.key === requestedStatus)?.key ?? "all";
  const citedFilter = searchParams.get("cited") === "true";
  const originFilter = ORIGIN_FILTER_OPTIONS.find((value) => value === searchParams.get("origin"));
  const typeFilter = searchParams.get("type") ?? undefined;
  const strengthFilter = STRENGTH_FILTER_OPTIONS.find(
    (value) => value === searchParams.get("strength"),
  );
  const yearFrom = parseYearParam(searchParams.get("year_from"));
  const yearTo = parseYearParam(searchParams.get("year_to"));
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
  const sourceId = searchParams.get("source");
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
  // same closed set the classification wrote for this project.
  const evidenceTypeOptions = Object.keys(landscape.data?.evidence_types ?? {}).sort();
  // No explicit sort → the relevance spectrum, descending (owner default:
  // confidently relevant → uncertain → confidently irrelevant).
  const effectiveSort = sortField ?? "relevance";
  const effectiveOrder = sortField !== null ? sortOrder : "desc";
  const evidence = useEvidence(projectId, {
    page,
    page_size: 50,
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
  });
  const dossier = useSourceDossier(projectId, sourceId);
  const findings = useFindings(projectId, sourceId ? { page_size: 200, source_id: sourceId } : undefined);
  const totalPages = evidence.data === undefined
    ? 0
    : Math.ceil(evidence.data.pagination.total_items / evidence.data.pagination.page_size);

  const updateParams = (update: (next: URLSearchParams) => void) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      update(next);
      return next;
    });
  };

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

  return (
    <main className="py-8">
      <header className="mb-5">
        <div role="group" aria-label="Filter sources" className="flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.key}
              type="button"
              aria-pressed={statusFilter === filter.key}
              onClick={() => updateParams((next) => {
                if (filter.key === "all") next.delete("status");
                else next.set("status", filter.key);
                next.delete("page");
              })}
              className={`cursor-pointer border px-2.5 py-1 text-caption font-semibold focus-visible:outline-2 focus-visible:outline-blue ${
                statusFilter === filter.key
                  ? "border-blue bg-blue-tint text-blue"
                  : "border-line-2 bg-paper text-grey hover:text-navy"
              }`}
            >
              {filter.label}
            </button>
          ))}
          <button
            type="button"
            aria-pressed={citedFilter}
            onClick={() => updateParams((next) => {
              if (citedFilter) next.delete("cited");
              else next.set("cited", "true");
              next.delete("page");
            })}
            className={`cursor-pointer border px-2.5 py-1 text-caption font-semibold focus-visible:outline-2 focus-visible:outline-blue ${
              citedFilter
                ? "border-blue bg-blue-tint text-blue"
                : "border-line-2 bg-paper text-grey hover:text-navy"
            }`}
          >
            Cited
          </button>
          <FilterSelect
            label="Key theme"
            allLabel="All themes"
            value={themeFilter ?? ""}
            options={themeOptions.map((theme) => ({ value: theme.theme_id, label: scrub(theme.name) }))}
            onChange={(value) => updateParams((next) => {
              if (value) next.set("theme", value);
              else next.delete("theme");
              next.delete("page");
            })}
          />
        </div>
      </header>

      {evidence.isPending && <SourceLoading />}

      {evidence.isError &&
        (errorCode(evidence.error) === "unauthenticated" ? (
          <ReauthRedirect />
        ) : (
          <RetryCard copy="Sources couldn't be loaded." onRetry={() => void evidence.refetch()} />
        ))}

      {evidence.data !== undefined && evidence.data.data.length === 0 && (
        <Card role="status" className="p-8 text-center text-body text-grey">
          {statusFilter === "all" && !citedFilter
            ? "No sources yet — they arrive as the analysis searches."
            : "No sources match these filters."}
        </Card>
      )}

      {evidence.data !== undefined && evidence.data.data.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left">
            <thead className="border-b border-line bg-paper-2 text-caption font-extrabold uppercase tracking-[0.06em] text-grey">
              <tr>
                <SortableColumnHeader
                  column={SOURCE_SORT_COLUMNS[0]}
                  className="px-4 py-3"
                  activeSort={effectiveSort}
                  activeOrder={effectiveOrder}
                  onSort={handleSort}
                />
                <SortableColumnHeader
                  column={SOURCE_SORT_COLUMNS[1]}
                  activeSort={effectiveSort}
                  activeOrder={effectiveOrder}
                  onSort={handleSort}
                >
                  <YearRangeFilter
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
                </SortableColumnHeader>
                <th className="px-3 py-3">
                  Origin
                  <HeaderFilter
                    label="Filter by origin"
                    allLabel="All"
                    value={originFilter ?? ""}
                    options={ORIGIN_FILTER_OPTIONS.map((value) => ({ value, label: value }))}
                    onChange={(value) => updateParams((next) => {
                      if (value) next.set("origin", value);
                      else next.delete("origin");
                      next.delete("page");
                    })}
                  />
                </th>
                <SortableColumnHeader
                  column={SOURCE_SORT_COLUMNS[2]}
                  activeSort={effectiveSort}
                  activeOrder={effectiveOrder}
                  onSort={handleSort}
                >
                  <HeaderFilter
                    label="Filter by evidence type"
                    allLabel="All"
                    value={typeFilter ?? ""}
                    options={evidenceTypeOptions.map((value) => ({ value, label: scrub(value) }))}
                    onChange={(value) => updateParams((next) => {
                      if (value) next.set("type", value);
                      else next.delete("type");
                      next.delete("page");
                    })}
                  />
                </SortableColumnHeader>
                <SortableColumnHeader
                  column={SOURCE_SORT_COLUMNS[3]}
                  activeSort={effectiveSort}
                  activeOrder={effectiveOrder}
                  onSort={handleSort}
                >
                  <HeaderFilter
                    label="Filter by evidence strength"
                    allLabel="All"
                    value={strengthFilter ?? ""}
                    options={STRENGTH_FILTER_OPTIONS.map((value) => ({ value, label: value }))}
                    onChange={(value) => updateParams((next) => {
                      if (value) next.set("strength", value);
                      else next.delete("strength");
                      next.delete("page");
                    })}
                  />
                </SortableColumnHeader>
                <SortableColumnHeader
                  column={SOURCE_SORT_COLUMNS[5]}
                  activeSort={effectiveSort}
                  activeOrder={effectiveOrder}
                  onSort={handleSort}
                />
                <SortableColumnHeader
                  column={SOURCE_SORT_COLUMNS[4]}
                  activeSort={effectiveSort}
                  activeOrder={effectiveOrder}
                  onSort={handleSort}
                />
                <th className="px-3 py-3">Cited</th>
              </tr>
            </thead>
            <tbody>
              {evidence.data.data.map((item) => (
                <tr key={item.source_id} className="border-b border-line last:border-b-0">
                  <td className="max-w-md px-4 py-3 align-top">
                    <button
                      type="button"
                      onClick={() => updateParams((next) => next.set("source", item.source_id))}
                      className="cursor-pointer text-left text-body font-semibold leading-snug text-navy hover:text-blue hover:underline focus-visible:outline-2 focus-visible:outline-blue"
                    >
                      {scrub(item.title)}
                    </button>
                    {item.venue && <p className="mt-0.5 text-body text-grey">{scrub(item.venue)}</p>}
                  </td>
                  <td className="px-3 py-3 align-top text-body text-navy">{item.year ?? ""}</td>
                  <td className="px-3 py-3 align-top"><Chip tone="soft">{scrub(item.origin)}</Chip></td>
                  <td className="px-3 py-3 align-top">
                    {item.evidence_type && (
                      item.classification_reason ? (
                        <Tooltip content={<p>{scrub(item.classification_reason)}</p>}>
                          <button type="button" aria-label={`${item.evidence_type}: why this type`} className="cursor-help focus-visible:outline-2 focus-visible:outline-blue">
                            <Chip tone="soft">{scrub(item.evidence_type)}</Chip>
                          </button>
                        </Tooltip>
                      ) : (
                        <Chip tone="soft">{scrub(item.evidence_type)}</Chip>
                      )
                    )}
                  </td>
                  <td className="px-3 py-3 align-top">
                    {item.appraisal_tier && (
                      <Tooltip content={<p>{scrub(strengthHint(item))}</p>}>
                        <button type="button" aria-label={`${item.appraisal_tier}: how strength is appraised`} className="cursor-help focus-visible:outline-2 focus-visible:outline-blue">
                          <Chip tone="soft">{scrub(item.appraisal_tier)}</Chip>
                        </button>
                      </Tooltip>
                    )}
                  </td>
                  <td className="px-3 py-3 align-top"><RelevantCell item={item} /></td>
                  <td className="px-3 py-3 align-top">
                    {readDepthLabel(item) !== null && (
                      item.read_in_full ? (
                        <Chip tone="blue">{readDepthLabel(item)}</Chip>
                      ) : (
                        <Tooltip content={<p>{scrub(readDepthHint(item) ?? "")}</p>}>
                          <button type="button" aria-label="Abstract only: why" className="cursor-help focus-visible:outline-2 focus-visible:outline-blue">
                            <Chip tone="yellow">{readDepthLabel(item)}</Chip>
                          </button>
                        </Tooltip>
                      )
                    )}
                  </td>
                  <td className="px-3 py-3 align-top">
                    {item.cited && <Chip tone="green">Cited</Chip>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {evidence.data !== undefined && evidence.data.data.length > 0 && (
        <p className="mt-2 text-caption text-grey">{evidence.data.pagination.total_items} sources</p>
      )}

      {evidence.data !== undefined && totalPages > 1 && (
        <nav aria-label="Pages" className="mt-5 flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => updateParams((next) => next.set("page", String(page - 1)))}
            className="cursor-pointer border border-line-2 px-3 py-2 text-caption font-semibold text-navy disabled:cursor-default disabled:text-line-2"
          >
            Previous
          </button>
          <span className="text-caption text-grey">Page {page} of {totalPages}</span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => updateParams((next) => next.set("page", String(page + 1)))}
            className="cursor-pointer border border-line-2 px-3 py-2 text-caption font-semibold text-navy disabled:cursor-default disabled:text-line-2"
          >
            Next
          </button>
        </nav>
      )}

      <SourceDossier
        sourceId={sourceId}
        source={dossier.data}
        isPending={dossier.isPending}
        isError={dossier.isError}
        findings={findings.data?.data}
        findingsPending={findings.isPending}
        onClose={() => updateParams((next) => next.delete("source"))}
      />
    </main>
  );
}

function SourceLoading() {
  return (
    <div aria-busy="true" aria-label="Loading sources" className="space-y-2">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="h-14 animate-pulse border border-line bg-paper-2" />
      ))}
    </div>
  );
}

/** One sortable `<th>` in the sources table: a real button (accessible name
 *  "Sort by <label>"), `aria-sort` on the header itself, and a ↑/↓
 *  indicator once this column is the active sort. Clicking cycles
 *  none → the column's default direction → the opposite → none, and the
 *  caller re-derives `sort`/`order` URL params from that (no client-side
 *  sort of the page — the 025 filters pattern). */
function SortableColumnHeader({
  column,
  activeSort,
  activeOrder,
  onSort,
  className = "px-3 py-3",
  children,
}: {
  column: (typeof SOURCE_SORT_COLUMNS)[number];
  activeSort: EvidenceSortField | null;
  activeOrder: SortOrder | null;
  onSort: (field: EvidenceSortField) => void;
  className?: string;
  /** Optional header-mounted filter control, rendered under the label. */
  children?: ReactNode;
}) {
  const order = activeSort === column.key ? activeOrder : null;
  const ariaSort = order === "asc" ? "ascending" : order === "desc" ? "descending" : "none";
  return (
    <th className={className} aria-sort={ariaSort}>
      <span className="flex items-center gap-1">
        <button
          type="button"
          aria-label={`Sort by ${column.label.toLowerCase()}`}
          onClick={() => onSort(column.key)}
          className="flex cursor-pointer items-center gap-1 text-caption font-extrabold uppercase tracking-[0.06em] text-grey hover:text-navy focus-visible:outline-2 focus-visible:outline-blue"
        >
          {column.label}
          {order !== null && <span aria-hidden="true">{order === "asc" ? "↑" : "↓"}</span>}
        </button>
        {children}
      </span>
    </th>
  );
}

function FunnelIcon({ active }: { active: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`h-3.5 w-3.5 ${active ? "text-blue" : "text-grey"}`}
      fill={active ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={2}
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 5h18l-7 8v5l-4 2v-7L3 5Z" />
    </svg>
  );
}

/** A facet filter behind a funnel icon beside the header label: the icon IS
 *  a native select (invisible overlay), so clicking it opens the dropdown. */
function HeaderFilter({
  label,
  allLabel,
  value,
  options,
  onChange,
}: {
  label: string;
  allLabel: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <span className="relative inline-flex h-5 w-5 items-center justify-center">
      <FunnelIcon active={value !== ""} />
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0 focus-visible:outline-2 focus-visible:outline-blue"
      >
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </span>
  );
}

function parseYearParam(value: string | null): number | undefined {
  const year = Number(value);
  return value !== null && Number.isInteger(year) && year >= 1000 && year <= 3000
    ? year
    : undefined;
}

/** The Year column's range filter: a funnel icon opening a two-field popover. */
function YearRangeFilter({
  from,
  to,
  onChange,
}: {
  from: number | undefined;
  to: number | undefined;
  onChange: (from: number | undefined, to: number | undefined) => void;
}) {
  return (
    <Popover>
      <PopoverTrigger
        aria-label="Filter by year range"
        className="inline-flex h-5 w-5 cursor-pointer items-center justify-center focus-visible:outline-2 focus-visible:outline-blue"
      >
        <FunnelIcon active={from !== undefined || to !== undefined} />
      </PopoverTrigger>
      <PopoverContent className="w-56 p-3">
        {/* Uncontrolled + apply-on-blur/Enter so partial typing ("20…")
            never gets clobbered by a controlled reset. */}
        <div className="flex items-center gap-2">
          <label className="flex-1 text-caption font-semibold normal-case tracking-normal text-grey">
            From
            <input
              key={`from-${from ?? "any"}`}
              type="number"
              inputMode="numeric"
              defaultValue={from ?? ""}
              onBlur={(event) => onChange(parseYearParam(event.target.value || null), to)}
              onKeyDown={(event) => {
                if (event.key === "Enter") event.currentTarget.blur();
              }}
              placeholder="Any"
              className="mt-1 w-full border border-line-2 bg-paper px-2 py-1 text-meta font-medium text-navy focus-visible:outline-2 focus-visible:outline-blue"
            />
          </label>
          <label className="flex-1 text-caption font-semibold normal-case tracking-normal text-grey">
            To
            <input
              key={`to-${to ?? "any"}`}
              type="number"
              inputMode="numeric"
              defaultValue={to ?? ""}
              onBlur={(event) => onChange(from, parseYearParam(event.target.value || null))}
              onKeyDown={(event) => {
                if (event.key === "Enter") event.currentTarget.blur();
              }}
              placeholder="Any"
              className="mt-1 w-full border border-line-2 bg-paper px-2 py-1 text-meta font-medium text-navy focus-visible:outline-2 focus-visible:outline-blue"
            />
          </label>
        </div>
        {(from !== undefined || to !== undefined) && (
          <button
            type="button"
            onClick={() => onChange(undefined, undefined)}
            className="mt-2 cursor-pointer text-caption font-semibold normal-case tracking-normal text-blue hover:underline"
          >
            Clear
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}

function RetryCard({ copy, onRetry }: { copy: string; onRetry: () => void }) {
  return (
    <Card role="alert" className="p-8 text-center text-body text-navy">
      {copy} <button type="button" className="cursor-pointer font-bold text-blue hover:underline" onClick={onRetry}>Retry</button>
    </Card>
  );
}

/** One facet dropdown in the sources filter row. */
function FilterSelect({
  label,
  allLabel,
  value,
  options,
  onChange,
}: {
  label: string;
  allLabel: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-1.5 text-caption font-semibold text-grey">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="cursor-pointer border border-line-2 bg-paper px-2 py-1 text-caption font-semibold text-navy focus-visible:outline-2 focus-visible:outline-blue"
      >
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}

/** The screening verdict: tick/cross + confidence, the LLM's reasoning on
 *  hover (just the reasoning — basis and depth live in the Status column). */
function RelevantCell({ item }: { item: Parameters<typeof screeningDetails>[0] }) {
  if (item.screen_status === null || item.screen_status === undefined) return null;
  const retracted = item.screen_status === "excluded_retracted";
  const relevant = item.screen_status === "relevant";
  const label = retracted ? "Excluded — retracted" : relevant ? "Relevant" : "Not relevant";
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
      <button
        type="button"
        aria-label={`${label}: screening details`}
        className="flex cursor-help items-baseline gap-1.5 focus-visible:outline-2 focus-visible:outline-blue"
      >
        <span aria-hidden="true" className={`text-meta font-bold ${relevant ? "text-green" : "text-red"}`}>
          {relevant ? "✓" : "✕"}
        </span>
        {!retracted && item.screen_confidence !== null && item.screen_confidence !== undefined && (
          <span className="text-caption text-grey">{Math.round(item.screen_confidence * 100)}%</span>
        )}
        {retracted && <span className="text-caption text-red">retracted</span>}
      </button>
    </Tooltip>
  );
}

function SourceDossier({
  sourceId,
  source,
  isPending,
  isError,
  findings,
  findingsPending,
  onClose,
}: {
  sourceId: string | null;
  source: components["schemas"]["SourceDossierOut"] | undefined;
  isPending: boolean;
  isError: boolean;
  findings: components["schemas"]["FindingOut"][] | undefined;
  findingsPending: boolean;
  onClose: () => void;
}) {
  if (!sourceId) return null;
  return (
    <Sheet open onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent title={source ? scrub(source.title) : "Source dossier"} description="Source dossier">
        {isPending && <p role="status" className="animate-pulse text-body text-grey">Loading the dossier…</p>}
        {isError && <p role="alert" className="text-body text-navy">This source dossier couldn't be loaded.</p>}
        {source && <SourceDossierBody source={source} findings={findings} findingsPending={findingsPending} />}
      </SheetContent>
    </Sheet>
  );
}

/** Full source provenance, used by every route into the source dossier sheet. */
export function SourceDossierBody({
  source,
  findings,
  findingsPending,
}: {
  source: components["schemas"]["SourceDossierOut"];
  findings: components["schemas"]["FindingOut"][] | undefined;
  findingsPending: boolean;
}) {
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
        <p className="font-display text-body font-bold leading-snug text-navy">{scrub(source.title)}</p>
        {(source.year || source.venue) && <p className="mt-1 text-grey">{[source.year, source.venue].filter(Boolean).map(String).map(scrub).join(" · ")}</p>}
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Chip tone="soft">{scrub(source.origin)}</Chip>
          {source.appraisal_tier && <Chip tone="soft">{scrub(source.appraisal_tier)}</Chip>}
          {href && <a className="border border-blue px-2.5 py-1 text-caption font-semibold text-blue hover:underline" href={href} target="_blank" rel="noreferrer">Open original</a>}
        </div>
      </header>
      {source.abstract && (
        <DossierSection title="About">
          {abstractSourceLabel(source.abstract_source) && <Chip tone="yellow">AI description</Chip>}
          <p className="mt-2 max-w-prose-measure text-body leading-relaxed text-grey">{scrub(source.abstract)}</p>
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
            {source.evidence_type && <DetailRow label="Evidence type" value={source.evidence_type} />}
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
              <p className="mb-1 text-caption font-extrabold uppercase tracking-[0.06em] text-grey">Asserted by {scrub(asserter)}</p>
              <div className="flex flex-wrap gap-1.5">{tags.map((tag) => <Chip key={`${tag.tag_type}-${tag.tag}`} tone="soft">{scrub(tag.tag)}</Chip>)}</div>
            </div>
          ))}
        </DossierSection>
      )}
      {(source.cited_in ?? []).length > 0 && (
        <DossierSection title="Cited in the evidence base">
          <div className="space-y-3">{source.cited_in?.map((citation, index) => (
            <div key={`${citation.section_title}-${index}`} className="border-l-2 border-blue pl-3">
              <p className="text-body leading-snug text-navy">{scrub(citation.claim)}</p>
              <p className="mt-1 text-body italic text-grey">“{scrub(citation.quote)}”</p>
              <p className="mt-1 text-caption font-extrabold uppercase tracking-[0.06em] text-grey">{scrub(citation.section_title)}</p>
            </div>
          ))}</div>
        </DossierSection>
      )}
      <DossierSection title="Findings from this source">
        {findingsPending && <p className="text-body text-grey">Loading findings…</p>}
        {!findingsPending && (!findings || findings.length === 0) && <p className="text-body text-grey">No findings extracted from this source.</p>}
        {findings && findings.length > 0 && <div className="space-y-2">{findings.map((finding) => (
          <div key={finding.finding_id} className="border-l-2 border-line-2 pl-3">
            <Chip tone="soft">{finding.profile === "iof" ? "Intervention–outcome" : "Implementation context"}</Chip>
            <p className="mt-1 text-body leading-snug text-navy">{scrub(finding.statement)}</p>
          </div>
        ))}</div>}
      </DossierSection>
    </div>
  );
}

function DossierSection({ title, children }: { title: string; children: ReactNode }) {
  return <section><PaneHeading className="px-0 pt-0">{title}</PaneHeading><Divider className="mb-3" />{children}</section>;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between gap-4"><dt className="text-grey">{label}</dt><dd className="text-right text-navy">{scrub(value)}</dd></div>;
}

import type { ReactNode } from "react";
import { useParams, useSearchParams } from "react-router";

import { useEvidence, useFindings, useProject, useSourceDossier } from "../api/queries";
import type { components } from "../api/gen/types";
import { errorCode } from "../lib/errors";
import { safeHref } from "../lib/safeHref";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Card, Divider, PaneHeading } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { Sheet, SheetContent } from "../ui/radix/Sheet";
import { Tooltip } from "../ui/radix/Tooltip";
import { abstractSourceLabel, screeningDetails, sourceStatusLabel } from "./sourcesPresentation";

const STATUS_TONE: Record<string, "default" | "blue" | "soft" | "green" | "yellow" | "red"> = {
  found: "soft",
  screened_out: "soft",
  relevant: "blue",
  not_selected: "soft",
  selected: "blue",
  read_in_full: "blue",
  findings_extracted: "green",
  cited: "green",
  unavailable: "yellow",
  excluded_retracted: "red",
};

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "Included", label: "Included" },
  { key: "screened_out", label: "Screened out" },
] as const;

/** Sources: collection-true server filters and a URL-addressable source dossier. */
export function SourcesView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  useDocumentTitle(project.data?.name, "Sources");
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedStatus = searchParams.get("status");
  const statusFilter = STATUS_FILTERS.find((filter) => filter.key === requestedStatus)?.key ?? "all";
  const citedFilter = searchParams.get("cited") === "true";
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
  const sourceId = searchParams.get("source");
  const evidence = useEvidence(projectId, {
    page,
    page_size: 50,
    status: statusFilter === "all" ? undefined : [statusFilter],
    cited: citedFilter || undefined,
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

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-5">
        <h1 className="font-display text-title font-extrabold text-navy">Sources</h1>
        <p className="mt-1 text-caption text-grey">
          Every source the analysis touched — what happened to it, and why.
        </p>
        <div role="group" aria-label="Filter sources" className="mt-4 flex flex-wrap gap-1.5">
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
        <Card role="status" className="p-8 text-center text-meta text-grey">
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
                <th className="px-4 py-3">Source</th>
                <th className="px-3 py-3">Year</th>
                <th className="px-3 py-3">Origin</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Strength</th>
                <th className="px-3 py-3">Cited</th>
              </tr>
            </thead>
            <tbody>
              {evidence.data.data.map((item) => {
                const label = sourceStatusLabel(item);
                return (
                  <tr key={item.source_id} className="border-b border-line last:border-b-0">
                    <td className="max-w-md px-4 py-3 align-top">
                      <button
                        type="button"
                        onClick={() => updateParams((next) => next.set("source", item.source_id))}
                        className="cursor-pointer text-left text-meta font-semibold leading-snug text-navy hover:text-blue hover:underline focus-visible:outline-2 focus-visible:outline-blue"
                      >
                        {scrub(item.title)}
                      </button>
                      {item.venue && <p className="mt-0.5 text-caption text-grey">{scrub(item.venue)}</p>}
                    </td>
                    <td className="px-3 py-3 align-top text-caption text-navy">{item.year ?? ""}</td>
                    <td className="px-3 py-3 align-top"><Chip tone="soft">{scrub(item.origin)}</Chip></td>
                    <td className="px-3 py-3 align-top">
                      {label !== undefined && <ScreeningTooltip item={item} label={label} />}
                    </td>
                    <td className="px-3 py-3 align-top">
                      {item.appraisal_tier && <Chip tone="soft">{scrub(item.appraisal_tier)}</Chip>}
                    </td>
                    <td className="px-3 py-3 align-top">
                      {item.cited && <Chip tone="green">Cited</Chip>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
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

function RetryCard({ copy, onRetry }: { copy: string; onRetry: () => void }) {
  return (
    <Card role="alert" className="p-8 text-center text-meta text-navy">
      {copy} <button type="button" className="cursor-pointer font-bold text-blue hover:underline" onClick={onRetry}>Retry</button>
    </Card>
  );
}

function ScreeningTooltip({
  item,
  label,
}: {
  item: Parameters<typeof screeningDetails>[0] & { status: string };
  label: string;
}) {
  const details = screeningDetails(item);
  const content = details.length === 0 ? <p>No additional screening detail was recorded.</p> : (
    <dl className="space-y-1">
      {details.map(([detailLabel, value]) => (
        <div key={detailLabel} className="flex gap-2">
          <dt className="font-semibold text-grey">{detailLabel}</dt>
          <dd>{scrub(value)}</dd>
        </div>
      ))}
    </dl>
  );
  const confidence = item.screen_status !== "excluded_retracted" ? item.screen_confidence : undefined;
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Tooltip content={content}>
        <button type="button" aria-label={`${label}: screening details`} className="cursor-help focus-visible:outline-2 focus-visible:outline-blue">
          <Chip tone={STATUS_TONE[item.screen_status ?? item.status] ?? "default"}>{label}</Chip>
        </button>
      </Tooltip>
      {confidence !== null && confidence !== undefined && <Chip tone="soft">{Math.round(confidence * 100)}% confidence</Chip>}
    </span>
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
        {isPending && <p role="status" className="animate-pulse text-caption text-grey">Loading the dossier…</p>}
        {isError && <p role="alert" className="text-caption text-navy">This source dossier couldn't be loaded.</p>}
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
          <p className="mt-2 leading-relaxed text-grey">{scrub(source.abstract)}</p>
        </DossierSection>
      )}
      {statusLabel && (
        <DossierSection title="What happened to it">
          <ScreeningTooltip item={source} label={statusLabel} />
          <dl className="mt-3 space-y-1.5">
            {screeningDetails(source).map(([label, value]) => <DetailRow key={label} label={label} value={value} />)}
          </dl>
        </DossierSection>
      )}
      {(source.evidence_type || source.appraisal_tier) && (
        <DossierSection title="Quality">
          <dl className="space-y-1.5">
            {source.evidence_type && <DetailRow label="Evidence type" value={source.evidence_type} />}
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
          <p className="mb-2 text-caption text-grey">Tags remain grouped by who asserted them.</p>
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
              <p className="leading-snug text-navy">{scrub(citation.claim)}</p>
              <p className="mt-1 italic text-grey">“{scrub(citation.quote)}”</p>
              <p className="mt-1 text-caption font-extrabold uppercase tracking-[0.06em] text-grey">{scrub(citation.section_title)}</p>
            </div>
          ))}</div>
        </DossierSection>
      )}
      <DossierSection title="Findings from this source">
        {findingsPending && <p className="text-grey">Loading findings…</p>}
        {!findingsPending && (!findings || findings.length === 0) && <p className="text-grey">No findings extracted from this source.</p>}
        {findings && findings.length > 0 && <div className="space-y-2">{findings.map((finding) => (
          <div key={finding.finding_id} className="border-l-2 border-line-2 pl-3">
            <Chip tone="soft">{finding.profile === "iof" ? "Intervention–outcome" : "Implementation context"}</Chip>
            <p className="mt-1 leading-snug text-navy">{scrub(finding.statement)}</p>
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

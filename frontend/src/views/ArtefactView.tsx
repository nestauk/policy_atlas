import { useMemo } from "react";
import { useParams, useSearchParams } from "react-router";

import type { components } from "../api/gen/types";
import { useApiClient, useArtefact, useCoverage, useEvidence } from "../api/queries";
import { useQuery } from "@tanstack/react-query";
import { scrub } from "../lib/scrub";
import { Card } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { Sheet, SheetContent } from "../ui/radix/Sheet";
import { Tooltip } from "../ui/radix/Tooltip";

type CitationOut = components["schemas"]["CitationOut"];

// Structural view of the artefact's blocks/claims: the generated schema
// renders `span` as `number[]` in the inlined response type, so the view
// accepts the loose shape and guards the two-element invariant itself.
interface ClaimLike {
  claim_id: string;
  claim_type: components["schemas"]["ClaimOut"]["claim_type"];
  text: string;
  span?: number[] | null;
  citations?: CitationOut[];
}
interface BlockLike {
  block_id: string;
  prose: string;
  claims?: ClaimLike[];
}

/** Fetch one citation's clamped chunk context on demand (the click rung). */
function useChunkContext(projectId: string, citationId: string | null) {
  const client = useApiClient();
  return useQuery({
    enabled: citationId !== null,
    queryKey: ["projects", projectId, "chunk-context", citationId],
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/projects/{project_id}/citations/{citation_key}/context",
        { params: { path: { project_id: projectId, citation_key: citationId ?? "" } } },
      );
      if (data === undefined) throw error;
      return data;
    },
  });
}

function CitationMarker({
  projectId,
  citation,
  onOpenDossier,
}: {
  projectId: string;
  citation: CitationOut;
  onOpenDossier: (title: string) => void;
}) {
  return (
    <Popover>
      <Tooltip content={<span className="text-xs">“{scrub(citation.quote)}”</span>}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={`Citation ${citation.n}: ${citation.source_title}`}
            className="mx-0.5 cursor-pointer align-super text-[10.5px] font-bold text-blue hover:underline focus-visible:outline-2 focus-visible:outline-blue"
          >
            [{citation.n}]
          </button>
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent>
        <CitationDetail
          projectId={projectId}
          citation={citation}
          onOpenDossier={onOpenDossier}
        />
      </PopoverContent>
    </Popover>
  );
}

function CitationDetail({
  projectId,
  citation,
  onOpenDossier,
}: {
  projectId: string;
  citation: CitationOut;
  onOpenDossier: (title: string) => void;
}) {
  const context = useChunkContext(projectId, citation.citation_id);
  return (
    <div>
      <p className="text-[12.5px] font-bold text-navy">{scrub(citation.source_title)}</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {citation.grounding_tier !== null && citation.grounding_tier !== undefined && (
          <Chip tone="soft">{scrub(citation.grounding_tier)}</Chip>
        )}
        {citation.appraisal_label !== null && citation.appraisal_label !== undefined && (
          <Chip tone="soft">{scrub(citation.appraisal_label)}</Chip>
        )}
      </div>
      <blockquote className="mt-2 border-l-2 border-l-blue bg-blue-tint-2 px-3 py-2 text-[12.5px] italic leading-relaxed text-ink">
        “{scrub(citation.quote)}”
      </blockquote>
      {context.isPending && (
        <p role="status" className="mt-2 animate-pulse text-[11.5px] text-grey">
          Loading surrounding context…
        </p>
      )}
      {context.data !== undefined && (
        <details className="mt-2">
          <summary className="cursor-pointer text-[11.5px] font-semibold text-blue">
            In its surrounding context{context.data.clamped ? " (excerpt)" : ""}
          </summary>
          <p className="mt-1.5 max-h-52 overflow-y-auto whitespace-pre-wrap text-[11.5px] leading-relaxed text-grey">
            {scrub(context.data.context)}
          </p>
        </details>
      )}
      {context.isError && (
        <p className="mt-2 text-[11.5px] text-grey">
          The source passage couldn't be anchored for a wider excerpt.
        </p>
      )}
      <button
        type="button"
        className="mt-2.5 cursor-pointer text-[11.5px] font-bold text-blue hover:underline"
        onClick={() => onOpenDossier(citation.source_title)}
      >
        Open the source dossier
      </button>
    </div>
  );
}

/**
 * Render a block's prose with its annotation layer IN the text: span-anchored
 * claims wrap their exact prose span; citation claims carry [n] markers; gap
 * claims get the gap chip. No callout cards, no per-block detail footer
 * (RETRO §2.5, ADR 0015).
 */
function AnnotatedProse({
  projectId,
  block,
  onOpenDossier,
}: {
  projectId: string;
  block: BlockLike;
  onOpenDossier: (title: string) => void;
}) {
  const segments = useMemo(() => {
    const prose = block.prose;
    const spanned = (block.claims ?? [])
      .filter(
        (claim): claim is ClaimLike & { span: [number, number] } =>
          claim.span !== null &&
          claim.span !== undefined &&
          claim.span[0] >= 0 &&
          claim.span.length === 2 && claim.span[1] <= prose.length &&
          claim.span[0] < claim.span[1],
      )
      .sort((a, b) => a.span[0] - b.span[0]);
    const parts: Array<
      { kind: "plain"; text: string } | { kind: "claim"; text: string; claim: ClaimLike }
    > = [];
    let cursor = 0;
    for (const claim of spanned) {
      if (claim.span[0] < cursor) continue; // overlapping span — keep the first
      if (claim.span[0] > cursor) {
        parts.push({ kind: "plain", text: prose.slice(cursor, claim.span[0]) });
      }
      parts.push({ kind: "claim", text: prose.slice(claim.span[0], claim.span[1]), claim });
      cursor = claim.span[1];
    }
    if (cursor < prose.length) parts.push({ kind: "plain", text: prose.slice(cursor) });
    return parts;
  }, [block]);

  const unspanned = (block.claims ?? []).filter(
    (claim) => claim.span === null || claim.span === undefined,
  );

  return (
    <div className="text-[14px] leading-[1.75] text-ink">
      <p>
        {segments.map((segment, index) => {
          if (segment.kind === "plain") {
            return <span key={index}>{scrub(segment.text)}</span>;
          }
          const { claim } = segment;
          if (claim.claim_type === "gap") {
            return (
              <span key={index}>
                <span className="border-b border-dashed border-orange">
                  {scrub(segment.text)}
                </span>{" "}
                <Chip tone="yellow">Evidence gap</Chip>
              </span>
            );
          }
          return (
            <span
              key={index}
              className={
                claim.claim_type === "citation"
                  ? "border-b border-dotted border-line-2"
                  : undefined
              }
            >
              {scrub(segment.text)}
              {(claim.citations ?? []).map((citation) => (
                <CitationMarker
                  key={citation.citation_id}
                  projectId={projectId}
                  citation={citation}
                  onOpenDossier={onOpenDossier}
                />
              ))}
            </span>
          );
        })}
      </p>
      {unspanned.map((claim) => (
        <p key={claim.claim_id} className="mt-2 text-[12.5px] text-grey">
          {scrub(claim.text)}
          {(claim.citations ?? []).map((citation) => (
            <CitationMarker
              key={citation.citation_id}
              projectId={projectId}
              citation={citation}
              onOpenDossier={onOpenDossier}
            />
          ))}
        </p>
      ))}
    </div>
  );
}

function SourceDossier({
  projectId,
  sourceTitle,
  onClose,
}: {
  projectId: string;
  sourceTitle: string;
  onClose: () => void;
}) {
  const evidence = useEvidence(projectId, { page_size: 200 });
  const source = evidence.data?.data.find((item) => item.title === sourceTitle);
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent title={scrub(sourceTitle)} description="Source dossier">
        {evidence.isPending && (
          <p role="status" className="animate-pulse text-[12.5px] text-grey">
            Loading the dossier…
          </p>
        )}
        {source !== undefined && (
          <dl className="space-y-3 text-[12.5px]">
            <div className="flex flex-wrap gap-1.5">
              <Chip tone="blue">{source.status.replaceAll("_", " ")}</Chip>
              {source.appraisal_tier !== null && source.appraisal_tier !== undefined && (
                <Chip tone="soft">{scrub(source.appraisal_tier)}</Chip>
              )}
              {source.cited && <Chip tone="green">Cited</Chip>}
            </div>
            {(
              [
                ["Year", source.year],
                ["Published in", source.venue],
                ["Origin", source.origin],
                ["Evidence type", source.evidence_type],
              ] as const
            )
              .filter(([, value]) => value !== null && value !== undefined)
              .map(([label, value]) => (
                <div key={label}>
                  <dt className="font-semibold text-grey">{label}</dt>
                  <dd className="mt-0.5 text-ink">{scrub(String(value))}</dd>
                </div>
              ))}
            {source.status_reason !== null && source.status_reason !== undefined && (
              <div>
                <dt className="font-semibold text-grey">Status detail</dt>
                <dd className="mt-0.5 text-ink">{scrub(source.status_reason)}</dd>
              </div>
            )}
            {source.url !== null && source.url !== undefined && (
              <div>
                <dt className="font-semibold text-grey">Link</dt>
                <dd className="mt-0.5 break-all">
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.url}
                  </a>
                </dd>
              </div>
            )}
          </dl>
        )}
        {evidence.data !== undefined && source === undefined && (
          <p className="text-[12.5px] text-grey">
            This source isn't in the evidence list yet.
          </p>
        )}
      </SheetContent>
    </Sheet>
  );
}

/** The evidence base: annotated prose, citation ladder, shared dossier.
 *  The dossier is URL-addressable (?source=…) — deep-linkable, refresh-safe. */
export function ArtefactView() {
  const { projectId = "" } = useParams();
  const artefact = useArtefact(projectId);
  const coverage = useCoverage(projectId);
  const [searchParams, setSearchParams] = useSearchParams();
  const dossierSource = searchParams.get("source");

  const openDossier = (title: string) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("source", title);
      return next;
    });
  };
  const closeDossier = () => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("source");
      return next;
    });
  };

  if (artefact.isPending) {
    return (
      <main aria-busy="true" aria-label="Loading the evidence base" className="mx-auto max-w-3xl px-6 py-10">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="mb-4 h-24 animate-pulse border border-line bg-paper-2" />
        ))}
      </main>
    );
  }

  if (artefact.isError || artefact.data === undefined) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Card role="status" className="p-8 text-center">
          <h1 className="font-display text-lg font-bold text-navy">
            No evidence base yet
          </h1>
          <p className="mt-1.5 text-[13px] text-grey">
            The evidence base appears here once an analysis reaches synthesis.
          </p>
        </Card>
      </main>
    );
  }

  const data = artefact.data;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-8">
        <h1 className="font-display text-[28px] font-extrabold leading-tight tracking-[-0.5px] text-navy">
          {scrub(data.title)}
        </h1>
        <p className="mt-2 text-[13.5px] text-grey">{scrub(data.question)}</p>
        {coverage.data !== undefined && (
          <p className="mt-3 border-l-2 border-l-blue bg-blue-tint-2 px-3 py-2 text-[12.5px] leading-relaxed text-navy">
            {scrub(coverage.data.sentence)}
          </p>
        )}
      </header>

      {(data.sections ?? []).map((section, index) => (
        <section key={index} className="mb-9">
          <h2 className="mb-3 font-display text-lg font-bold text-navy">
            {scrub(section.title)}
          </h2>
          <div className="space-y-4">
            {(section.blocks ?? []).map((block) => (
              <AnnotatedProse
                key={block.block_id}
                projectId={projectId}
                block={block}
                onOpenDossier={openDossier}
              />
            ))}
          </div>
        </section>
      ))}

      {(data.references ?? []).length > 0 && (
        <section aria-label="References" className="mt-12 border-t border-line pt-6">
          <h2 className="mb-3 font-display text-base font-bold text-navy">References</h2>
          <ol className="space-y-1.5 text-[12.5px] text-ink">
            {(data.references ?? []).map((reference) => (
              <li key={reference.n} className="flex gap-2">
                <span className="font-bold text-blue">[{reference.n}]</span>
                <span>
                  <button
                    type="button"
                    className="cursor-pointer text-left hover:underline"
                    onClick={() => openDossier(reference.title)}
                  >
                    {scrub(reference.title)}
                  </button>
                  {reference.year !== null && reference.year !== undefined && (
                    <span className="text-grey"> ({reference.year})</span>
                  )}
                  {reference.venue !== null && reference.venue !== undefined && (
                    <span className="text-grey"> · {scrub(reference.venue)}</span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {dossierSource !== null && (
        <SourceDossier
          projectId={projectId}
          sourceTitle={dossierSource}
          onClose={closeDossier}
        />
      )}
    </main>
  );
}

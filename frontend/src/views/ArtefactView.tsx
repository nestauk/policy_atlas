import { useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router";

import type { components } from "../api/gen/types";
import { useApiClient, useArtefact, useCoverage, useEvidence, useFindings, useProject, useSourceDossier } from "../api/queries";
import { useQuery } from "@tanstack/react-query";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { hasTerminalPartialLiveArtefact, useRunStream } from "../store";
import type { LiveSection, RunStreamState } from "../store";
import { Card } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { Sheet, SheetContent } from "../ui/radix/Sheet";
import { Tooltip } from "../ui/radix/Tooltip";
import { SourceDossierBody } from "./SourcesView";

type CitationOut = components["schemas"]["CitationOut"];
type GapOut = components["schemas"]["GapOut"];

// Structural view of the artefact's blocks/claims: the generated schema
// renders `span` as `number[]` in the inlined response type, so the view
// accepts the loose shape and guards the two-element invariant itself.
interface ClaimLike {
  claim_id: string;
  claim_type: components["schemas"]["ClaimOut"]["claim_type"];
  text: string;
  span?: number[] | null;
  citations?: CitationOut[];
  gap?: GapOut | null;
  weakly_grounded?: boolean | null;
}
interface BlockLike {
  block_id: string;
  prose: string;
  claims?: ClaimLike[];
}
interface SectionLike {
  title: string;
  role?: "key_findings" | "standard" | "conclusions";
  focus?: string | null;
  blocks?: BlockLike[];
}

/* --- typed annotation vocabulary (strand 5): claim breadth beyond
   citation/gap — reasoning · pattern/theme · source-check, styled per type
   with inline chips. Unknown types render as plain prose (honest absence). */

/** Demo-validated span styling (EvidenceBase.tsx SPAN_STYLE): typed dotted/
 *  dashed underlines with a hover tint — the annotation layer lives IN the
 *  text and the whole span is the affordance. */
const SPAN_STYLE: Partial<Record<ClaimLike["claim_type"], string>> = {
  citation: "border-b border-dotted border-blue hover:bg-blue-tint-2",
  gap: "border-b border-dotted border-yellow hover:bg-yellow-tint",
  reasoning: "border-b border-dashed border-line-2 hover:bg-ground",
  pattern: "border-b border-dotted border-violet hover:bg-blue-tint-2",
  theme: "border-b border-dotted border-violet hover:bg-blue-tint-2",
  unspanned_assertion: "border-b border-dotted border-orange hover:bg-yellow-tint",
};

/** The grounding-tier vocabulary (demo ui.tsx TIER_LABEL/TIER_TEXT — locked;
 *  unknown tier → the raw value never renders, the chip omits). */
const TIER_LABEL: Record<string, string> = {
  tier_1: "Tier 1 · direct quote",
  tier_2: "Tier 2 · grounded",
  tier_3: "Tier 3 · supported",
  tier_4: "Tier 4 · reasoning",
  unsupported_mis_cited: "Unsupported — flagged",
};

const TIER_TEXT: Record<string, string> = {
  tier_1: "Direct quote, verified against the source",
  tier_2: "Grounded in a specific passage",
  tier_3: "Supported across passages",
  tier_4: "Reasoning from the evidence, not a quote",
  unsupported_mis_cited: "Failed verification — flagged, never hidden",
};

const TYPE_LABEL: Partial<Record<ClaimLike["claim_type"], string>> = {
  gap: "gap",
  reasoning: "reasoning",
  pattern: "pattern",
  theme: "theme",
  unspanned_assertion: "source check",
};

const TYPE_HINT: Partial<Record<ClaimLike["claim_type"], string>> = {
  gap: "This is a recorded evidence gap: the analysis looked and found the base thin here. Gaps are part of the answer, never glossed over.",
  reasoning: "Reasoning from the evidence — not a quoted source.",
  pattern: "A computed pattern across the evidence.",
  theme: "The clustering's reading of the corpus.",
  unspanned_assertion: "A source-check flag from the grounding review.",
};

/**
 * Present sections key-findings-first with conclusions last (strand 5). The
 * server's block order within a section is preserved untouched.
 */
export function orderSections<T extends SectionLike>(sections: T[]): T[] {
  const rank = (section: T) =>
    section.role === "key_findings" ? 0 : section.role === "conclusions" ? 2 : 1;
  return [...sections].sort((a, b) => rank(a) - rank(b));
}

type HighlightParts =
  | { kind: "highlight"; before: string; match: string; after: string }
  | { kind: "degrade"; quote: string; text: string };

/**
 * Locate `quote` inside `text` for highlighting: exact match first, then a
 * whitespace-normalised remap, then the honest degrade (quote shown above
 * the unhighlighted text) — never a broken panel (strand 5).
 */
export function highlightParts(text: string, quote: string): HighlightParts {
  let start = text.indexOf(quote);
  let end = start + quote.length;
  if (start < 0 && quote.trim().length > 0) {
    const squash = (value: string) => value.replace(/\s+/g, " ");
    const index = squash(text).indexOf(squash(quote));
    if (index >= 0) {
      let raw = 0;
      let squashed = 0;
      while (squashed < index && raw < text.length) {
        raw += 1;
        squashed = squash(text.slice(0, raw)).length;
      }
      start = raw;
      end = Math.min(start + quote.length + 20, text.length);
    }
  }
  if (start < 0) return { kind: "degrade", quote, text };
  return {
    kind: "highlight",
    before: text.slice(0, start),
    match: text.slice(start, end),
    after: text.slice(end),
  };
}

function HighlightedContext({ text, quote }: { text: string; quote: string }) {
  const parts = highlightParts(text, quote);
  if (parts.kind === "degrade") {
    return (
      <>
        <span className="mb-1 block italic text-grey">“{scrub(parts.quote)}”</span>
        {scrub(parts.text)}
      </>
    );
  }
  return (
    <>
      {scrub(parts.before)}
      <mark className="bg-yellow-tint font-medium text-navy">{scrub(parts.match)}</mark>
      {scrub(parts.after)}
    </>
  );
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

/** One citation's provenance block in the claim panel (demo CitationContext):
 *  the quote highlighted inside its surrounding source passage. */
function CitationContext({
  projectId,
  citation,
  onOpenDossier,
}: {
  projectId: string;
  citation: CitationOut;
  onOpenDossier: (title: string) => void;
}) {
  const context = useChunkContext(projectId, citation.citation_id);
  const meta = [context.data?.year, context.data?.venue].filter(
    (value): value is string | number => value !== null && value !== undefined && value !== "",
  );
  const tier = citation.grounding_tier ?? null;
  return (
    <div className="border border-line p-4">
      <p className="text-[13px] font-bold leading-snug text-blue">
        [{citation.n}]{" "}
        <button
          type="button"
          className="cursor-pointer text-left hover:underline"
          onClick={() => onOpenDossier(citation.source_title)}
        >
          {scrub(citation.source_title)}
        </button>
      </p>
      {meta.length > 0 && (
        <p className="mt-0.5 text-[11.5px] text-grey">{meta.map((m) => scrub(String(m))).join(" · ")}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {tier !== null && TIER_LABEL[tier] !== undefined && (
          <Tooltip content={<span className="text-xs">{TIER_TEXT[tier]}</span>}>
            <span>
              <Chip tone="soft">{TIER_LABEL[tier]}</Chip>
            </span>
          </Tooltip>
        )}
        {citation.appraisal_label !== null && citation.appraisal_label !== undefined && (
          <Chip tone="blue">{scrub(citation.appraisal_label)}</Chip>
        )}
      </div>
      <div className="mt-3 space-y-2 text-[12.5px] leading-relaxed">
        {context.isPending && (
          <p role="status" className="animate-pulse text-[11.5px] text-grey">
            Loading surrounding context…
          </p>
        )}
        {context.data !== undefined && (
          <>
            {typeof context.data.previous === "string" && context.data.previous !== "" && (
              <p className="text-grey">{scrub(context.data.previous)}</p>
            )}
            <p className="text-navy">
              <HighlightedContext text={context.data.context} quote={citation.quote} />
            </p>
            {typeof context.data.next === "string" && context.data.next !== "" && (
              <p className="text-grey">{scrub(context.data.next)}</p>
            )}
          </>
        )}
        {context.isError && <p className="italic text-grey">“{scrub(citation.quote)}”</p>}
      </div>
    </div>
  );
}

/** The provenance panel a claim span opens (demo ClaimPanel): the claim, its
 *  type explainer, and every citation's highlighted source passage. */
function ClaimPanel({
  projectId,
  claim,
  onClose,
  onOpenDossier,
}: {
  projectId: string;
  claim: ClaimLike | null;
  onClose: () => void;
  onOpenDossier: (title: string) => void;
}) {
  if (claim === null) return null;
  const hint = TYPE_HINT[claim.claim_type];
  const gap = claim.gap ?? null;
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent title="Where this comes from" description="Claim provenance">
        <div className="space-y-5">
          <p className="border-l-2 border-l-blue pl-3 text-[13.5px] font-medium leading-snug text-navy">
            {scrub(claim.text)}
          </p>
          {claim.claim_type === "gap" && (
            <div className="border-l-[3px] border-yellow bg-yellow-tint p-3 text-[13px] leading-relaxed text-navy">
              <p>
                This is a recorded evidence gap: the analysis looked and found the base thin
                here. Gaps are part of the answer, never glossed over.
              </p>
              {gap !== null && (
                <p className="mt-1.5 text-[11.5px] text-grey">
                  {[
                    typeof gap.grade === "string" ? `Graded ${scrub(gap.grade)}` : null,
                    typeof gap.caveat?.search_space === "string"
                      ? scrub(gap.caveat.search_space)
                      : null,
                    typeof gap.caveat?.adequacy_verdict === "string"
                      ? scrub(gap.caveat.adequacy_verdict)
                      : null,
                  ]
                    .filter((part): part is string => part !== null)
                    .join(" · ")}
                </p>
              )}
            </div>
          )}
          {claim.claim_type === "unspanned_assertion" && (
            <p className="border-l-[3px] border-orange bg-yellow-tint p-3 text-[13px] text-navy">
              {TYPE_HINT.unspanned_assertion}
            </p>
          )}
          {claim.claim_type !== "gap" &&
            claim.claim_type !== "unspanned_assertion" &&
            claim.claim_type !== "citation" &&
            hint !== undefined && <p className="text-[12.5px] text-grey">{hint}</p>}
          {claim.weakly_grounded === true && (
            <p className="border-l-[3px] border-orange bg-yellow-tint p-3 text-[13px] text-navy">
              The grounding review could not fully verify this claim against its source — read
              it with that in mind.
            </p>
          )}
          {(claim.citations ?? []).map((citation) => (
            <CitationContext
              key={citation.citation_id}
              projectId={projectId}
              citation={citation}
              onOpenDossier={onOpenDossier}
            />
          ))}
          <p className="border-t border-line pt-3 text-[11px] text-grey">
            Every claim links to the exact passage it came from.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** A claim span in the prose (demo ClaimSpan): the whole span is clickable,
 *  hover previews the first citation, click opens the provenance panel.
 *  Citation numbers ride as one inline chip; typed claims carry their label. */
function ClaimSpan({
  claim,
  text,
  onOpen,
}: {
  claim: ClaimLike;
  text: string;
  onOpen: (claim: ClaimLike) => void;
}) {
  const first = (claim.citations ?? [])[0];
  const tier = first?.grounding_tier ?? null;
  const tip =
    first !== undefined ? (
      <div className="max-w-[260px] space-y-1.5 text-[12px] leading-snug">
        <p className="font-semibold text-navy">{scrub(first.source_title)}</p>
        {first.quote !== "" && (
          <p className="italic text-grey">
            “{scrub(first.quote.slice(0, 180))}
            {first.quote.length > 180 ? "…" : ""}”
          </p>
        )}
        {tier !== null && TIER_LABEL[tier] !== undefined && (
          <p className="text-grey">{TIER_LABEL[tier]}</p>
        )}
        <p className="text-[11px] text-grey">Click to view in context</p>
      </div>
    ) : (
      <span className="text-xs">{TYPE_HINT[claim.claim_type] ?? "Claim"}</span>
    );
  const typeLabel = claim.weakly_grounded === true ? "source check" : TYPE_LABEL[claim.claim_type];
  const citationNumbers = [...new Set((claim.citations ?? []).map((citation) => citation.n))];
  return (
    <span>
      <Tooltip content={tip}>
        <button
          type="button"
          onClick={() => onOpen(claim)}
          className={`citation-marker cursor-pointer text-left align-baseline text-inherit transition-colors focus-visible:outline-2 focus-visible:outline-blue ${SPAN_STYLE[claim.claim_type] ?? ""}`}
        >
          {scrub(text)}
        </button>
      </Tooltip>
      {claim.claim_type === "citation" && citationNumbers.length > 0 && (
        <button
          type="button"
          aria-label={`Citations ${citationNumbers.join(", ")}`}
          onClick={() => onOpen(claim)}
          className="citation-marker mx-1 cursor-pointer border border-blue bg-blue-tint px-1.5 align-[2px] text-[10.5px] font-bold text-blue hover:bg-blue-tint-2"
        >
          [{citationNumbers.join(",")}]
        </button>
      )}
      {claim.claim_type !== "citation" && typeLabel !== undefined && (
        <button
          type="button"
          onClick={() => onOpen(claim)}
          className={`mx-1 cursor-pointer border px-1.5 align-[2px] text-[10px] font-bold ${
            claim.claim_type === "gap"
              ? "border-yellow bg-yellow-tint text-navy"
              : "border-line bg-ground text-grey"
          }`}
        >
          {typeLabel}
        </button>
      )}
    </span>
  );
}

/**
 * Render a block's prose with its annotation layer IN the text: span-anchored
 * claims wrap their exact prose span (overlapping/oversize spans are skipped
 * honestly — flag, don't mis-render); citation claims carry [n] markers;
 * typed claims get their style + chip and open the explainer.
 */
function AnnotatedProse({
  block,
  onOpenClaim,
}: {
  block: BlockLike;
  onOpenClaim: (claim: ClaimLike) => void;
}) {
  const segments = useMemo(() => {
    const prose = block.prose;
    const spanned = (block.claims ?? [])
      .filter(
        (claim): claim is ClaimLike & { span: [number, number] } =>
          claim.span !== null &&
          claim.span !== undefined &&
          claim.span[0] >= 0 &&
          claim.span.length === 2 &&
          claim.span[1] <= prose.length &&
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
    <div className="text-[14.5px] leading-[1.7] text-ink">
      <p className="whitespace-pre-line">
        {segments.map((segment, index) => {
          if (segment.kind === "plain") {
            return <span key={index}>{scrub(segment.text)}</span>;
          }
          return (
            <ClaimSpan key={index} claim={segment.claim} text={segment.text} onOpen={onOpenClaim} />
          );
        })}
      </p>
      {unspanned.map((claim) => (
        <p key={claim.claim_id} className="mt-2 text-[12.5px] text-grey">
          <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} />
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
  const dossier = useSourceDossier(projectId, source?.source_id ?? null);
  const findings = useFindings(projectId, source ? { page_size: 200, source_id: source.source_id } : undefined);
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
        {dossier.isPending && <p role="status" className="animate-pulse text-[12.5px] text-grey">Loading the dossier…</p>}
        {dossier.isError && <p role="alert" className="text-[12.5px] text-navy">This source dossier couldn't be loaded.</p>}
        {dossier.data && <SourceDossierBody source={dossier.data} findings={findings.data?.data} findingsPending={findings.isPending} />}
        {evidence.data !== undefined && source === undefined && (
          <p className="text-[12.5px] text-grey">This source isn't in the evidence list yet.</p>
        )}
      </SheetContent>
    </Sheet>
  );
}

/**
 * The artefact-in-progress (strand 13): all planned section headings with
 * focus placeholders, "Writing this section now…" on the active one, prose
 * filling in place as each completes — whole-section grain. If the run ends
 * badly with sections already streamed, they stay visible under an explicit
 * terminal banner: drafted sections, not the evidence base.
 */
export function LiveArtefactBody({ stream }: { stream: RunStreamState }) {
  const sections = Object.values(stream.liveSections).sort((a, b) => a.index - b.index);
  const terminalPartial = hasTerminalPartialLiveArtefact(stream);
  const visible = sections.filter(
    (section: LiveSection) => !(section.state === "filled" && (section.prose ?? "") === ""),
  );
  return (
    <main className="artefact-page anim-rise mx-auto my-8 max-w-[780px] bg-paper px-10 py-9 shadow-sm ring-1 ring-line">
      {terminalPartial ? (
        <div
          role="alert"
          className="border-l-[3px] border-l-red bg-red-tint px-3.5 py-2.5 text-[12.5px] leading-relaxed text-navy"
        >
          <p className="font-bold">This run ended before the write-up completed.</p>
          <p className="mt-0.5">
            The sections below are drafted text from the interrupted run — not the checked
            evidence base. Citations were never attached. Start a fresh run to produce the full
            artefact.
          </p>
        </div>
      ) : (
        <p role="status" className="flex items-center gap-2 text-[12.5px] text-grey">
          <span aria-hidden="true" className="anim-breathe inline-block h-2 w-2 bg-blue" />
          Being written now — sections appear as they are drafted
        </p>
      )}
      {visible.map((section) => (
        <section key={section.index} className="mt-9">
          <h2 className="font-display text-lg font-bold text-navy">{scrub(section.title)}</h2>
          {section.state === "filled" && (section.prose ?? "") !== "" ? (
            <p className="anim-rise mt-2 whitespace-pre-line text-[14px] leading-[1.75] text-ink">
              {scrub(section.prose ?? "")}
            </p>
          ) : section.state === "writing" && !terminalPartial ? (
            <p role="status" className="anim-breathe mt-2 text-[13px] text-grey">
              Writing this section now…
            </p>
          ) : (
            <p className="mt-2 text-[13px] italic text-grey">
              {section.focus !== "" ? scrub(section.focus) : "Waiting to be written."}
            </p>
          )}
        </section>
      ))}
      {!terminalPartial && (
        <p className="mt-10 border-t border-line pt-4 text-[12px] text-grey">
          Citations and source provenance are attached when the write-up completes and is
          checked.
        </p>
      )}
    </main>
  );
}

/** The evidence base: A4 page frame, coverage snapshot, key-findings-first
 *  ordering, typed annotated prose, citation ladder, shared dossier
 *  (?source=… — deep-linkable, refresh-safe), and the live streaming state
 *  while synthesis writes. */
export function ArtefactView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const artefact = useArtefact(projectId);
  const coverage = useCoverage(projectId);
  const stream = useRunStream(projectId);
  const [searchParams, setSearchParams] = useSearchParams();
  const dossierSource = searchParams.get("source");
  const [detailClaim, setDetailClaim] = useState<ClaimLike | null>(null);
  useDocumentTitle(project.data?.name, "Evidence base");

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

  if (artefact.isError) {
    const code = errorCode(artefact.error);
    if (code === "unauthenticated") return <ReauthRedirect />;
    // `not_found` is the server's honest shape for "no artefact yet" (the
    // read model returns 404 rather than an Optional-with-null body) —
    // that is the expected empty state, not a failure to surface.
    if (code !== "not_found") {
      return (
        <main className="mx-auto max-w-3xl px-6 py-10">
          <Card role="alert" className="p-8 text-center text-[13px] text-navy">
            The evidence base couldn't be loaded.{" "}
            <button
              type="button"
              className="cursor-pointer font-bold text-blue hover:underline"
              onClick={() => void artefact.refetch()}
            >
              Retry
            </button>
          </Card>
        </main>
      );
    }
  }

  if (artefact.isError || artefact.data === undefined || artefact.data === null) {
    // No committed artefact: show the in-progress skeleton when sections are
    // streaming (or streamed before a bad ending) — otherwise the empty state.
    if (Object.keys(stream.liveSections).length > 0) {
      return <LiveArtefactBody stream={stream} />;
    }
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Card role="status" className="p-8 text-center">
          <h1 className="font-display text-lg font-bold text-navy">No evidence base yet</h1>
          <p className="mt-1.5 text-[13px] text-grey">
            The evidence base appears here once an analysis reaches synthesis.
          </p>
        </Card>
      </main>
    );
  }

  const data = artefact.data;
  // A fresh run re-writing the artefact supersedes the committed page while
  // it streams (the reducer clears sections when a different run starts) —
  // and if that run dies mid-write, the terminal-partial view stays up in
  // place of the stale committed page: the user's latest run ended badly and
  // hiding that behind the old artefact would be dishonest (live-check
  // adjudication, 2026-07-29). A new run or a fresh mount clears it.
  if (
    (stream.run?.status === "running" || hasTerminalPartialLiveArtefact(stream)) &&
    Object.keys(stream.liveSections).length > 0
  ) {
    return <LiveArtefactBody stream={stream} />;
  }

  const snapshot = data.coverage_snapshot;
  const studyTypes = Object.entries(snapshot?.study_types ?? {}).sort(([, a], [, b]) => b - a);
  const shownTypes = studyTypes.slice(0, 3);
  const sections = orderSections((data.sections ?? []) as SectionLike[]);

  const snapshotCells: Array<[string, string]> = [];
  if (typeof snapshot?.source_count === "number" && typeof snapshot?.included === "number") {
    // Transcription trap 3: `source_count` is the cited/reference count —
    // never "found".
    snapshotCells.push(["Sources", `${snapshot.source_count} cited · ${snapshot.included} included`]);
  }
  if (shownTypes.length > 0) {
    snapshotCells.push([
      "Study types",
      shownTypes.map(([key, count]) => `${count} ${key.toLowerCase()}`).join(" · ") +
        (studyTypes.length > 3 ? ` · +${studyTypes.length - 3} more` : ""),
    ]);
  }
  if (snapshot?.year_range !== null && snapshot?.year_range !== undefined) {
    snapshotCells.push(["Years", `${snapshot.year_range[0]}–${snapshot.year_range[1]}`]);
  }
  if (typeof snapshot?.screened_out === "number") {
    snapshotCells.push(["Screened out", `${snapshot.screened_out} — all listed with reasons`]);
  }

  return (
    <main className="artefact-page anim-rise mx-auto my-8 max-w-[780px] bg-paper px-10 py-9 shadow-sm ring-1 ring-line">
      <header className="mb-8">
        <p className="text-[11px] font-extrabold uppercase tracking-[0.06em] text-grey">
          Evidence base
        </p>
        <h1 className="mt-1 font-display text-[26px] font-extrabold leading-tight tracking-[-0.5px] text-navy">
          {scrub(data.title)}
        </h1>
        <p className="mt-2 text-[13.5px] text-grey">{scrub(data.question)}</p>
        {snapshotCells.length > 0 && (
          <div className="mt-5 grid grid-cols-2 border border-line sm:grid-cols-4">
            {snapshotCells.map(([label, value]) => (
              <div key={label} className="border-r border-line p-3 last:border-r-0">
                <p className="text-[10.5px] font-bold uppercase tracking-wider text-grey">{label}</p>
                <p className="mt-1 text-[12.5px] font-medium leading-snug text-navy">{value}</p>
              </div>
            ))}
          </div>
        )}
        {coverage.data !== undefined && coverage.data !== null && (
          <p className="mt-3 border-l-2 border-l-blue bg-blue-tint-2 px-3 py-2 text-[12.5px] leading-relaxed text-navy">
            {scrub(coverage.data.sentence)}
          </p>
        )}
      </header>

      {sections.map((section, index) => (
        <section
          key={index}
          className={section.role === "conclusions" ? "mb-9 border-t border-line pt-6" : "mb-9"}
        >
          <h2 className="mb-3 font-display text-lg font-bold text-navy">{scrub(section.title)}</h2>
          <div className="space-y-4">
            {(section.blocks ?? []).map((block) => (
              <AnnotatedProse key={block.block_id} block={block} onOpenClaim={setDetailClaim} />
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

      <ClaimPanel
        projectId={projectId}
        claim={detailClaim}
        onClose={() => setDetailClaim(null)}
        onOpenDossier={(title) => {
          setDetailClaim(null);
          openDossier(title);
        }}
      />

      {dossierSource !== null && (
        <SourceDossier projectId={projectId} sourceTitle={dossierSource} onClose={closeDossier} />
      )}
    </main>
  );
}

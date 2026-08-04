import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import type { components } from "../api/gen/types";
import { useApiClient, useArtefact, useEvidence, useFindings, useProject, useSourceDossier } from "../api/queries";
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
import {
  ContentsSidebar,
  GatheredSection,
  type OutlineSection,
  SectionDisclosure,
  sectionAnchor,
} from "./ArtefactOutline";
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
  theme?: {
    source?: string | null;
    base?: string | null;
    items?: Array<{
      name?: string | null;
      description?: string | null;
      size?: number | null;
      facet?: string | null;
      sources?: Array<{ source_id?: string | null; title?: string | null }> | null;
    }> | null;
  } | null;
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
  // Deliberately quiet (owner, 2026-07-29): the underline is a hint, not a
  // highlight — muted tones at rest, the tint only on hover.
  // reasoning + unspanned_assertion carry no user-facing detail (owner,
  // 2026-07-29): they render as plain prose — see UNMARKED_TYPES.
  citation: "border-b border-dotted border-blue/30 hover:border-blue/60 hover:bg-blue-tint-2",
  gap: "border-b border-dotted border-yellow/60 hover:border-yellow hover:bg-yellow-tint",
  pattern: "border-b border-dotted border-violet/50 hover:border-violet hover:bg-blue-tint-2",
  theme: "border-b border-dotted border-violet/50 hover:border-violet hover:bg-blue-tint-2",
};

/** Claim types whose marking is dev-facing only: the judge's source-check
 *  flags and the writer's connective reasoning have no detail to reveal, so
 *  their prose renders unmarked (owner, 2026-07-29). */
const UNMARKED_TYPES: ReadonlySet<ClaimLike["claim_type"]> = new Set([
  "reasoning",
  "unspanned_assertion",
]);

/** Humanised gap grades (the wire vocabulary is GapPayloadWire.grade). */
const GAP_GRADE_TEXT: Record<string, string> = {
  corpus_absence: "Searched and not found — a recorded search establishes the material isn't there.",
  acknowledged_sparsity: "The evidence base is thin here — backed by the coverage counts.",
  inferred: "Inferred by the analysis from what it read — not established by a recorded search.",
};

/** Fallback for an appraisal chip whose citation carries no classified
 *  document type (the type is the rubric's scoring input — see the dynamic
 *  tooltip in CitationCard). */
const APPRAISAL_FALLBACK_HINT =
  "The cited source's appraised evidence strength — five bands from Weak to Very strong, scored from its classified document type.";

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
  pattern: "pattern",
  theme: "theme",
};

const TYPE_HINT: Partial<Record<ClaimLike["claim_type"], string>> = {
  gap: "This is a recorded evidence gap: the analysis looked and found the base thin here. Gaps are part of the answer, never glossed over.",
  pattern: "A computed pattern across the evidence.",
  theme: "The clustering's reading of the corpus.",
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
      // A run of N whitespace chars squashes to length 1, so the loop can
      // stop inside the run — advance to the match's first real character.
      if (!squash(quote).startsWith(" ")) {
        while (raw < text.length && /\s/.test(text.charAt(raw))) raw += 1;
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
      <p className="text-meta font-bold leading-snug text-blue">
        [{citation.n}]{" "}
        <button
          type="button"
          className="cursor-pointer text-left hover:underline"
          onClick={() => onOpenDossier(citation.source_id ?? citation.source_title)}
        >
          {scrub(citation.source_title)}
        </button>
      </p>
      {meta.length > 0 && (
        <p className="mt-0.5 text-caption text-grey">{meta.map((m) => scrub(String(m))).join(" · ")}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {tier !== null && TIER_LABEL[tier] !== undefined && (
          <Tooltip
            content={
              <div className="max-w-[280px] space-y-1 text-caption">
                <p>{TIER_TEXT[tier]}</p>
                {typeof citation.grounding_rationale === "string" &&
                  citation.grounding_rationale !== "" && (
                    <p className="text-grey">
                      Judge: {scrub(citation.grounding_rationale)}
                    </p>
                  )}
              </div>
            }
          >
            <span>
              <Chip tone="soft">{TIER_LABEL[tier]}</Chip>
            </span>
          </Tooltip>
        )}
        {citation.appraisal_label !== null && citation.appraisal_label !== undefined && (
          <Tooltip
            content={
              <span className="text-caption">
                {typeof citation.evidence_type === "string"
                  ? `${scrub(citation.appraisal_label)} evidence strength — appraised from the document type: ${scrub(citation.evidence_type)}.`
                  : APPRAISAL_FALLBACK_HINT}
              </span>
            }
          >
            <span>
              <Chip tone="blue">{scrub(citation.appraisal_label)}</Chip>
            </span>
          </Tooltip>
        )}
      </div>
      <div className="mt-3 space-y-2 text-caption leading-relaxed">
        {context.isPending && (
          <p role="status" className="animate-pulse text-caption text-grey">
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
          <p className="border-l-2 border-l-blue pl-3 text-meta font-medium leading-snug text-navy">
            {scrub(claim.text)}
          </p>
          {claim.claim_type === "gap" && (
            <div className="border-l-[3px] border-yellow bg-yellow-tint p-3 text-meta leading-relaxed text-navy">
              <p>
                This is a recorded evidence gap: the analysis looked and found the base thin
                here. Gaps are part of the answer, never glossed over.
              </p>
              {gap !== null && (
                <div className="mt-1.5 space-y-0.5 text-caption text-grey">
                  {typeof gap.grade === "string" && GAP_GRADE_TEXT[gap.grade] !== undefined && (
                    <p>{GAP_GRADE_TEXT[gap.grade]}</p>
                  )}
                  {(typeof gap.caveat?.search_space === "string" ||
                    typeof gap.caveat?.adequacy_verdict === "string") && (
                    <p>
                      {[
                        typeof gap.caveat?.search_space === "string"
                          ? `Searched: ${scrub(gap.caveat.search_space)}`
                          : null,
                        typeof gap.caveat?.adequacy_verdict === "string"
                          ? `coverage judged ${scrub(gap.caveat.adequacy_verdict)}`
                          : null,
                      ]
                        .filter((part): part is string => part !== null)
                        .join(" · ")}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
          {claim.claim_type !== "gap" &&
            claim.claim_type !== "citation" &&
            hint !== undefined && <p className="text-caption text-grey">{hint}</p>}
          {(claim.theme?.items?.length ?? 0) > 0 && (
            <div className="border-l-[3px] border-violet bg-blue-tint-2 p-3">
              {(claim.theme?.items ?? []).map((item, index) => (
                <div key={index} className={index > 0 ? "mt-2.5" : undefined}>
                  <p className="text-meta font-semibold text-navy">{scrub(item.name ?? "")}</p>
                  {typeof item.description === "string" && item.description !== "" && (
                    <p className="mt-0.5 text-caption leading-relaxed text-navy">
                      {scrub(item.description)}
                    </p>
                  )}
                  {(item.sources?.length ?? 0) > 0 ? (
                    <details className="mt-0.5 text-caption text-grey">
                      <summary className="cursor-pointer hover:text-navy">
                        Identified across {item.sources?.length} source
                        {(item.sources?.length ?? 0) === 1 ? "" : "s"} — show them
                      </summary>
                      <ul className="mt-1 list-disc space-y-0.5 pl-4">
                        {(item.sources ?? []).map((source) =>
                          typeof source.title === "string" && source.title !== "" ? (
                            <li key={source.source_id ?? source.title}>
                              <button
                                type="button"
                                className="cursor-pointer text-left text-navy hover:text-blue hover:underline"
                                onClick={() => onOpenDossier(source.source_id ?? source.title ?? "")}
                              >
                                {scrub(source.title)}
                              </button>
                            </li>
                          ) : null,
                        )}
                      </ul>
                    </details>
                  ) : typeof item.size === "number" ? (
                    <p className="mt-0.5 text-caption text-grey">
                      Identified across {item.size} sources
                    </p>
                  ) : null}
                  {typeof item.facet === "string" && item.facet !== "" && item.name ? (
                    <p className="mt-0.5 text-caption">
                      <Link
                        className="font-semibold text-blue hover:underline"
                        to={`/projects/${projectId}/findings?facet=${encodeURIComponent(item.facet)}&group=${encodeURIComponent(item.name)}`}
                        onClick={onClose}
                      >
                        See the findings in this theme
                      </Link>
                    </p>
                  ) : null}
                </div>
              ))}
              {typeof claim.theme?.base === "string" && claim.theme.base !== "" && (
                <p className="mt-2 border-t border-line pt-2 text-caption text-grey">
                  Basis: {scrub(claim.theme.base)}
                </p>
              )}
            </div>
          )}
          {claim.weakly_grounded === true && (
            <p className="border-l-[3px] border-orange bg-yellow-tint p-3 text-meta text-navy">
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
          <p className="border-t border-line pt-3 text-caption text-grey">
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
  // Dev-facing markings (source-check flags, connective reasoning) carry no
  // user-facing detail: their prose renders unmarked (owner, 2026-07-29).
  if (UNMARKED_TYPES.has(claim.claim_type)) return <span>{scrub(text)}</span>;
  const first = (claim.citations ?? [])[0];
  const tier = first?.grounding_tier ?? null;
  const tip =
    first !== undefined ? (
      <div className="max-w-[260px] space-y-1.5 text-caption leading-snug">
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
        <p className="text-caption text-grey">Click to view in context</p>
      </div>
    ) : (claim.claim_type === "theme" || claim.claim_type === "pattern") &&
      (claim.theme?.items?.length ?? 0) > 0 ? (
      <div className="max-w-[260px] space-y-1 text-caption leading-snug">
        {(claim.theme?.items ?? []).slice(0, 3).map((item, index) => (
          <div key={index}>
            <p className="font-semibold text-navy">Theme: {scrub(item.name ?? "")}</p>
            {typeof item.description === "string" && item.description !== "" && (
              <p className="text-grey">{scrub(item.description)}</p>
            )}
            {typeof item.size === "number" && (
              <p className="text-caption text-grey">{item.size} sources</p>
            )}
          </div>
        ))}
        <p className="text-caption text-grey">Click for detail</p>
      </div>
    ) : claim.claim_type === "gap" ? (
      <div className="max-w-[260px] space-y-1 text-caption leading-snug">
        <p className="font-semibold text-navy">Evidence gap</p>
        <p className="text-grey">
          {(typeof claim.gap?.grade === "string" ? GAP_GRADE_TEXT[claim.gap.grade] : undefined) ??
            TYPE_HINT.gap}
        </p>
        <p className="text-caption text-grey">Click for the coverage detail</p>
      </div>
    ) : (
      <span className="text-caption">{TYPE_HINT[claim.claim_type] ?? "Claim"}</span>
    );
  const typeLabel = TYPE_LABEL[claim.claim_type];
  const citationNumbers = [...new Set((claim.citations ?? []).map((citation) => citation.n))];
  return (
    <span>
      {/* A real <button> is an ATOMIC inline-block: a sentence-length span
          could never wrap mid-line and shattered the paragraph flow. The
          demo's span[role=button] wraps like ordinary prose (keyboard: Enter
          and Space both activate). */}
      <Tooltip content={tip}>
        <span
          role="button"
          tabIndex={0}
          onClick={() => onOpen(claim)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              onOpen(claim);
            }
          }}
          className={`citation-marker cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-blue ${SPAN_STYLE[claim.claim_type] ?? ""}`}
        >
          {scrub(text)}
        </span>
      </Tooltip>
      {claim.claim_type === "citation" && citationNumbers.length > 0 && (
        <button
          type="button"
          aria-label={`Citations ${citationNumbers.join(", ")}`}
          onClick={() => onOpen(claim)}
          className="citation-marker mx-1 cursor-pointer border border-blue/25 bg-blue-tint-2 px-1.5 align-[2px] text-caption font-semibold text-blue/80 hover:border-blue/60 hover:text-blue"
        >
          [{citationNumbers.join(",")}]
        </button>
      )}
      {claim.claim_type !== "citation" && typeLabel !== undefined && (
        <button
          type="button"
          onClick={() => onOpen(claim)}
          className={`mx-1 cursor-pointer border px-1.5 align-[2px] text-caption font-semibold ${
            claim.claim_type === "gap"
              ? "border-yellow/60 bg-yellow-tint/60 text-navy/80 hover:border-yellow"
              : "border-line bg-ground text-grey hover:border-line-2"
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
export function AnnotatedProse({
  block,
  onOpenClaim,
}: {
  block: BlockLike;
  onOpenClaim: (claim: ClaimLike) => void;
}) {
  const segments = useMemo(() => {
    // Span offsets are Python code-POINT indices (the annotator slices `str`);
    // JS string indexing counts UTF-16 code UNITS, so any astral character
    // (emoji, some CJK) before a span would shift it. Slice by code points.
    const prose = Array.from(block.prose);
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
        parts.push({ kind: "plain", text: prose.slice(cursor, claim.span[0]).join("") });
      }
      parts.push({
        kind: "claim",
        text: prose.slice(claim.span[0], claim.span[1]).join(""),
        claim,
      });
      cursor = claim.span[1];
    }
    if (cursor < prose.length) parts.push({ kind: "plain", text: prose.slice(cursor).join("") });
    return parts;
  }, [block]);

  const unspanned = (block.claims ?? []).filter(
    (claim) => claim.span === null || claim.span === undefined,
  );

  // Key-findings bullets (028 fork B): prose whose non-empty lines all start
  // "- " renders as a list. Segments regroup by line; a claim span crossing a
  // bullet boundary degrades honestly to the trailing anchored list below —
  // its popover survives, it is never mis-rendered across two bullets.
  const lines = block.prose.split("\n").filter((line) => line.trim() !== "");
  const isBulleted = lines.length > 0 && lines.every((line) => line.trimStart().startsWith("- "));
  if (isBulleted) {
    const bullets: Array<Array<(typeof segments)[number]>> = [];
    const crossing: ClaimLike[] = [];
    let current: Array<(typeof segments)[number]> = [];
    for (const segment of segments) {
      const pieces = segment.text.split("\n");
      pieces.forEach((piece, pieceIndex) => {
        if (pieceIndex > 0) {
          if (current.length > 0) bullets.push(current);
          current = [];
        }
        if (piece === "") return;
        if (segment.kind === "claim" && pieces.filter((p) => p.trim() !== "").length > 1) {
          // The span crosses a bullet boundary — degrade the whole claim.
          if (!crossing.includes(segment.claim)) crossing.push(segment.claim);
          current.push({ kind: "plain", text: piece });
          return;
        }
        current.push(
          segment.kind === "claim" ? { kind: "claim", text: piece, claim: segment.claim } : { kind: "plain", text: piece },
        );
      });
    }
    if (current.length > 0) bullets.push(current);
    return (
      <div className="max-w-prose-measure text-body text-ink">
        <ul className="list-none space-y-1.5">
          {bullets.map((bullet, bulletIndex) => (
            <li key={bulletIndex} className="flex gap-2">
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 bg-blue" />
              <span>
                {bullet.map((segment, index) =>
                  segment.kind === "plain" ? (
                    <span key={index}>{scrub(segment.text.replace(/^\s*- /, ""))}</span>
                  ) : (
                    <ClaimSpan
                      key={index}
                      claim={segment.claim}
                      text={segment.text.replace(/^\s*- /, "")}
                      onOpen={onOpenClaim}
                    />
                  ),
                )}
              </span>
            </li>
          ))}
        </ul>
        {crossing.map((claim) => (
          <p key={claim.claim_id} className="mt-2 text-caption text-grey">
            <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} />
          </p>
        ))}
        {unspanned.map((claim) => (
          <p key={claim.claim_id} className="mt-2 text-caption text-grey">
            <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} />
          </p>
        ))}
      </div>
    );
  }

  return (
    <div className="max-w-prose-measure text-body text-ink">
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
        <p key={claim.claim_id} className="mt-2 text-caption text-grey">
          <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} />
        </p>
      ))}
    </div>
  );
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function SourceDossier({
  projectId,
  sourceRef,
  onClose,
}: {
  projectId: string;
  /** A source id (citations carry one) or a display title (references,
   *  theme members — the legacy title-keyed path). */
  sourceRef: string;
  onClose: () => void;
}) {
  const byId = UUID_RE.test(sourceRef);
  const evidence = useEvidence(projectId, { page_size: 200 });
  const source = byId
    ? evidence.data?.data.find((item) => item.source_id === sourceRef)
    : evidence.data?.data.find((item) => item.title === sourceRef);
  const sourceId = byId ? sourceRef : (source?.source_id ?? null);
  const dossier = useSourceDossier(projectId, sourceId);
  const findings = useFindings(
    projectId,
    sourceId !== null ? { page_size: 200, source_id: sourceId } : undefined,
  );
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent
        title={scrub(byId ? (dossier.data?.title ?? source?.title ?? "Source") : sourceRef)}
        description="Source dossier"
      >
        {evidence.isPending && (
          <p role="status" className="animate-pulse text-caption text-grey">
            Loading the dossier…
          </p>
        )}
        {dossier.isPending && <p role="status" className="animate-pulse text-caption text-grey">Loading the dossier…</p>}
        {dossier.isError && <p role="alert" className="text-caption text-navy">This source dossier couldn't be loaded.</p>}
        {dossier.data && <SourceDossierBody source={dossier.data} findings={findings.data?.data} findingsPending={findings.isPending} />}
        {!byId && evidence.data !== undefined && source === undefined && (
          <p className="text-caption text-grey">This source isn't in the evidence list yet.</p>
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
          className="border-l-[3px] border-l-red bg-red-tint px-3.5 py-2.5 text-caption leading-relaxed text-navy"
        >
          <p className="font-bold">This run ended before the write-up completed.</p>
          <p className="mt-0.5">
            The sections below are drafted text from the interrupted run — not the checked
            evidence base. Citations were never attached. Start a fresh run to produce the full
            artefact.
          </p>
        </div>
      ) : (
        <p role="status" className="flex items-center gap-2 text-caption text-grey">
          <span aria-hidden="true" className="anim-breathe inline-block h-2 w-2 bg-blue" />
          Being written now — sections appear as they are drafted
        </p>
      )}
      {visible.map((section) => (
        <section key={section.index} className="mt-9">
          <h2 className="font-display text-heading font-bold text-navy">{scrub(section.title)}</h2>
          {section.state === "filled" && (section.prose ?? "") !== "" ? (
            <p className="anim-rise mt-2 max-w-prose-measure whitespace-pre-line text-body text-ink">
              {scrub(section.prose ?? "")}
            </p>
          ) : section.state === "writing" && !terminalPartial ? (
            <p role="status" className="anim-breathe mt-2 text-meta text-grey">
              Writing this section now…
            </p>
          ) : (
            <p className="mt-2 text-meta italic text-grey">
              {section.focus !== "" ? scrub(section.focus) : "Waiting to be written."}
            </p>
          )}
        </section>
      ))}
      {!terminalPartial && (
        <p className="mt-10 border-t border-line pt-4 text-caption text-grey">
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
          <Card role="alert" className="p-8 text-center text-meta text-navy">
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
          <h1 className="font-display text-title font-bold text-navy">No evidence base yet</h1>
          <p className="mt-1.5 text-meta text-grey">
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

  const outlineEntries = [
    ...sections.map((section, index) => ({
      id: sectionAnchor(section.title, index),
      title: section.title,
    })),
    ...((data.references ?? []).length > 0 ? [{ id: "references", title: "References" }] : []),
    { id: "gathered", title: "How the evidence was gathered" },
  ];

  return (
    <div className="mx-auto flex max-w-[1060px] justify-center gap-6 px-4">
      <ContentsSidebar entries={outlineEntries} />
      <main className="artefact-page anim-rise my-8 min-w-0 max-w-[780px] flex-1 bg-paper px-10 py-9 shadow-sm ring-1 ring-line">
      <header className="mb-8">
        <p className="text-caption font-extrabold uppercase tracking-[0.06em] text-grey">
          Evidence base
        </p>
        <h1 className="mt-1 font-display text-title font-extrabold leading-tight tracking-[-0.5px] text-navy">
          {scrub(data.title)}
        </h1>
        <p className="mt-2 text-meta text-grey">{scrub(data.question)}</p>
        {data.summary != null && data.summary !== "" && data.summary_status === "verified" && (
          <p className="mt-3 max-w-prose-measure border-l-2 border-l-blue bg-blue-tint/30 px-3 py-2 text-body text-ink">
            {scrub(data.summary)}
          </p>
        )}
        {snapshotCells.length > 0 && (
          <div className="mt-5 grid grid-cols-2 border border-line sm:grid-cols-4">
            {snapshotCells.map(([label, value]) => (
              <div key={label} className="border-r border-line p-3 last:border-r-0">
                <p className="text-caption font-bold uppercase tracking-wider text-grey">{label}</p>
                <p className="mt-1 text-caption font-medium leading-snug text-navy">{scrub(value)}</p>
              </div>
            ))}
          </div>
        )}
        {/* Coverage banner removed (owner, 2026-07-29): the adequacy verdict
            surfaces where it matters — inside each gap claim's detail. */}
      </header>

      {sections.map((section, index) => (
        <SectionDisclosure
          key={index}
          id={sectionAnchor(section.title, index)}
          section={section as OutlineSection}
          // Key findings is never collapsible (always in full); conclusions
          // collapsible, default open; ordinary sections default collapsed.
          collapsible={section.role !== "key_findings"}
          defaultOpen={section.role !== "standard"}
        >
          {(section.blocks ?? []).map((block) => (
            <AnnotatedProse key={block.block_id} block={block} onOpenClaim={setDetailClaim} />
          ))}
        </SectionDisclosure>
      ))}

      {(data.references ?? []).length > 0 && (
        <ReferencesSection
          references={data.references ?? []}
          onOpenReference={openDossier}
        />
      )}

      <GatheredSection projectId={projectId} id="gathered" />

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
        <SourceDossier projectId={projectId} sourceRef={dossierSource} onClose={closeDossier} />
      )}
      </main>
    </div>
  );
}

/** References as a collapsible entry with an always-visible summary line —
 *  it is the ArtefactOut.references collection, not a synthesis section
 *  (028 strand 10, binding record). */
function ReferencesSection({
  references,
  onOpenReference,
}: {
  references: Array<{ n: number; title: string; year?: number | null; venue?: string | null }>;
  onOpenReference: (title: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section aria-label="References" id="references" className="mt-12 scroll-mt-20 border-t border-line pt-6">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full cursor-pointer items-baseline gap-2 text-left"
      >
        <h2 className="flex-1 font-display text-heading font-bold text-navy">References</h2>
        <span aria-hidden="true" className="text-meta text-grey">
          {open ? "−" : "+"}
        </span>
      </button>
      {!open && (
        <p className="mt-1.5 text-meta text-grey">
          {references.length === 1 ? "1 numbered source" : `${references.length} numbered sources`} cited
          in this report
        </p>
      )}
      {open && (
        <ol className="mt-3 space-y-1.5 text-caption text-ink">
          {references.map((reference) => (
            <li key={reference.n} className="flex gap-2">
              <span className="font-bold text-blue">[{reference.n}]</span>
              <span>
                <button
                  type="button"
                  className="cursor-pointer text-left hover:underline"
                  onClick={() => onOpenReference(reference.title)}
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
      )}
    </section>
  );
}

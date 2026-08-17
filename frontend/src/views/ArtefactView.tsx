import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import type { components } from "../api/gen/types";
import { useApiClient, useArtefact, useConversations, useEvidence, useFindings, useLandscape, useProject, useSourceDossier } from "../api/queries";
import { useQuery } from "@tanstack/react-query";
import { mostRelevantSources, sectionNavLabel } from "./artefactPresentation";
import type { TopSource } from "./artefactPresentation";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { hasTerminalPartialLiveArtefact, useRunStream } from "../store";
import type { LiveSection, RunStreamState } from "../store";
import { Card } from "../ui/brand/Card";
import { Chip, type ChipProps } from "../ui/brand/Chip";
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
import { addOpenChatTab, useActiveConversation, useConversationMutations } from "./workspace/chat/conversationState";

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
const CITATION_TINT = "border-b border-dotted border-blue/30 hover:border-blue/60 hover:bg-blue-tint-2";

const SPAN_STYLE: Partial<Record<ClaimLike["claim_type"], string>> = {
  // Deliberately quiet (owner, 2026-07-29): the underline is a hint, not a
  // highlight — muted tones at rest, the tint only on hover.
  // reasoning + unspanned_assertion carry no user-facing detail (owner,
  // 2026-07-29): they render as plain prose — see UNMARKED_TYPES.
  citation: CITATION_TINT,
  gap: "border-b border-dotted border-yellow/60 hover:border-yellow hover:bg-yellow-tint",
  pattern: "border-b border-dotted border-violet/50 hover:border-violet hover:bg-blue-tint-2",
  theme: "border-b border-dotted border-violet/50 hover:border-violet hover:bg-blue-tint-2",
};

/** The claim-span affordance's full class string for the report's "citation"
 *  type (marker hook + hover chrome + the tint above) — chat's claim spans
 *  render as this one type (design point 4), so this is exported rather than
 *  re-typed on the chat side. */
export const CITATION_SPAN_CLASS = `citation-marker cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-blue ${CITATION_TINT}`;

/** The report's [n] citation-number marker's boxed-chip class (marker hook +
 *  border/bg chrome, `disabled:` variants for a muted look) — exported so
 *  chat's literal `[n]` markers (both the inline prose marker and the
 *  References row marker) share this one copy instead of the superscript-link
 *  treatment drifting apart from the report (029/030 parity fix). */
export const CITATION_MARKER_CLASS =
  "citation-marker mx-1 cursor-pointer border border-blue/25 bg-blue-tint-2 px-1.5 align-[2px] text-caption font-semibold text-blue/80 hover:border-blue/60 hover:text-blue disabled:cursor-default disabled:border-line disabled:bg-ground disabled:text-grey disabled:hover:border-line disabled:hover:text-grey";

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
 *  unknown tier → the raw value never renders, the chip omits). Exported so
 *  every surface that renders a grounding verdict (chat included) shares
 *  this one copy instead of re-typing it. */
export const TIER_LABEL: Record<string, string> = {
  tier_1: "Tier 1 · direct quote",
  tier_2: "Tier 2 · grounded",
  tier_3: "Tier 3 · supported",
  tier_4: "Tier 4 · reasoning",
  unsupported_mis_cited: "Unsupported — flagged",
};

export const TIER_TEXT: Record<string, string> = {
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

export function HighlightedContext({ text, quote }: { text: string; quote: string }) {
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

/** A chip whose hover reveals its rationale — the one Tooltip-wraps-a-Chip
 *  shape every grounding/verdict/appraisal indicator in the app uses (the
 *  reader's tier + appraisal chips, chat's verdict chip). Exported so no
 *  surface re-types the wrapping. */
export function ChipWithTooltip({
  tone,
  label,
  content,
}: {
  tone: ChipProps["tone"];
  label: ReactNode;
  content: ReactNode;
}) {
  return (
    <Tooltip content={content}>
      <span>
        <Chip tone={tone}>{label}</Chip>
      </span>
    </Tooltip>
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

/** One citation's provenance block (demo CitationContext/ClaimPanel):
 *  source link, its grounding/appraisal chips (a caller-supplied slot — the
 *  reader's tier+appraisal pair, chat's single verdict chip), and the quote
 *  highlighted inside its surrounding source passage — or, on a lookup
 *  failure, the caller's honest fallback line instead of a broken panel.
 *  Presentational: callers own the chunk-context query and the chips. */
export function CitationProvenanceBlock({
  n,
  sourceTitle,
  sourceRef,
  onOpenDossier,
  chips = null,
  context,
  quote,
  fallbackNote,
}: {
  n: number | null;
  sourceTitle: string;
  /** A source id/title to open the dossier with, or `null` when the
   *  citation carries nothing dossier-linkable (renders plain text). */
  sourceRef: string | null;
  onOpenDossier: (sourceRef: string) => void;
  chips?: ReactNode;
  context: { isPending: boolean; isError: boolean; data: components["schemas"]["ChunkContextOut"] | undefined };
  quote: string;
  /** Shown under the quote on a lookup failure, alongside it — never in
   *  place of the honest quote fallback (chat's non-verbatim-quote case). */
  fallbackNote?: string;
}) {
  const meta = [context.data?.year, context.data?.venue].filter(
    (value): value is string | number => value !== null && value !== undefined && value !== "",
  );
  return (
    <div className="border border-line p-4">
      <p className="text-body font-bold leading-snug text-blue">
        [{n ?? "—"}]{" "}
        {sourceRef !== null ? (
          <button
            type="button"
            className="cursor-pointer text-left hover:underline"
            onClick={() => onOpenDossier(sourceRef)}
          >
            {scrub(sourceTitle)}
          </button>
        ) : (
          <span>{scrub(sourceTitle)}</span>
        )}
      </p>
      {meta.length > 0 && (
        <p className="mt-0.5 text-body text-grey">{meta.map((m) => scrub(String(m))).join(" · ")}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">{chips}</div>
      <div className="mt-3 space-y-2 text-body leading-relaxed">
        {context.isPending && (
          <p role="status" className="animate-pulse text-body text-grey">
            Loading surrounding context…
          </p>
        )}
        {context.data !== undefined && (
          <>
            {typeof context.data.previous === "string" && context.data.previous !== "" && (
              <p className="text-grey">{scrub(context.data.previous)}</p>
            )}
            <p className="text-navy">
              <HighlightedContext text={context.data.context} quote={quote} />
            </p>
            {typeof context.data.next === "string" && context.data.next !== "" && (
              <p className="text-grey">{scrub(context.data.next)}</p>
            )}
          </>
        )}
        {context.isError && (
          <>
            <p className="italic text-grey">“{scrub(quote)}”</p>
            {fallbackNote !== undefined && <p className="text-grey">{fallbackNote}</p>}
          </>
        )}
      </div>
    </div>
  );
}

/** The appraisal chip (blue `ChipWithTooltip`) + its evidence-type-aware
 *  tooltip wording — shared by the reader's `CitationContext` and chat's
 *  citation-sheet block (030 parity fold) so the wording can never drift.
 *  Renders unconditionally; callers gate on `appraisal_label` presence
 *  themselves (honest absence — no chip when the citation carries none). */
export function AppraisalChip({ label, evidenceType }: { label: string; evidenceType?: string | null }) {
  return (
    <ChipWithTooltip
      tone="blue"
      label={scrub(label)}
      content={
        <span className="text-meta">
          {typeof evidenceType === "string"
            ? `${scrub(label)} evidence strength — appraised from the document type: ${scrub(evidenceType)}.`
            : APPRAISAL_FALLBACK_HINT}
        </span>
      }
    />
  );
}

/** One citation's provenance block in the claim panel (demo CitationContext):
 *  the reader's tier + appraisal chips over the shared block. */
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
  const tier = citation.grounding_tier ?? null;
  return (
    <CitationProvenanceBlock
      n={citation.n}
      sourceTitle={citation.source_title}
      sourceRef={citation.source_id ?? citation.source_title}
      onOpenDossier={onOpenDossier}
      context={context}
      quote={citation.quote}
      chips={
        <>
          {tier !== null && TIER_LABEL[tier] !== undefined && (
            <ChipWithTooltip
              tone="soft"
              label={TIER_LABEL[tier]}
              content={
                <div className="max-w-[280px] space-y-1 text-meta">
                  <p>{TIER_TEXT[tier]}</p>
                  {typeof citation.grounding_rationale === "string" &&
                    citation.grounding_rationale !== "" && (
                      <p className="text-grey">Judge: {scrub(citation.grounding_rationale)}</p>
                    )}
                </div>
              }
            />
          )}
          {citation.appraisal_label !== null && citation.appraisal_label !== undefined && (
            <AppraisalChip label={citation.appraisal_label} evidenceType={citation.evidence_type} />
          )}
        </>
      }
    />
  );
}

/** The provenance sheet a claim (report) or a claim/citation (chat) opens:
 *  the "Where this comes from" shell, the claim text as a blockquote (one
 *  per string — chat stacks several when multiple claims cite one citation),
 *  a caller-supplied extras slot (the reader's gap/type-hint/theme/weak-
 *  grounding blocks), then the citation blocks as children. */
export function ProvenanceSheet({
  description = "Claim provenance",
  claimTexts,
  extras,
  onClose,
  children,
}: {
  description?: string;
  claimTexts: string[];
  extras?: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent title="Where this comes from" description={description}>
        <div className="space-y-5">
          {claimTexts
            .filter((text) => text !== "")
            .map((text, index) => (
              <p
                key={index}
                className="border-l-2 border-l-blue pl-3 text-body font-medium leading-snug text-navy"
              >
                {scrub(text)}
              </p>
            ))}
          {extras}
          {children}
          <p className="border-t border-line pt-3 text-body text-grey">
            Every claim links to the exact passage it came from.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** The provenance panel a claim span opens (demo ClaimPanel): the claim, its
 *  type explainer, and every citation's highlighted source passage — over
 *  the shared ProvenanceSheet shell. */
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
  const extras = (
    <>
      {claim.claim_type === "gap" && (
        <div className="border-l-[3px] border-yellow bg-yellow-tint p-3 text-body leading-relaxed text-navy">
          <p>
            This is a recorded evidence gap: the analysis looked and found the base thin here.
            Gaps are part of the answer, never glossed over.
          </p>
          {gap !== null && (
            <div className="mt-1.5 space-y-0.5 text-body text-grey">
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
        hint !== undefined && <p className="text-body text-grey">{hint}</p>}
      {(claim.theme?.items?.length ?? 0) > 0 && (
        <div className="border-l-[3px] border-violet bg-blue-tint-2 p-3">
          {(claim.theme?.items ?? []).map((item, index) => (
            <div key={index} className={index > 0 ? "mt-2.5" : undefined}>
              <p className="text-body font-semibold text-navy">{scrub(item.name ?? "")}</p>
              {typeof item.description === "string" && item.description !== "" && (
                <p className="mt-0.5 text-body leading-relaxed text-navy">
                  {scrub(item.description)}
                </p>
              )}
              {(item.sources?.length ?? 0) > 0 ? (
                <details className="mt-0.5 text-body text-grey">
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
                <p className="mt-0.5 text-body text-grey">
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
            <p className="mt-2 border-t border-line pt-2 text-body text-grey">
              Basis: {scrub(claim.theme.base)}
            </p>
          )}
        </div>
      )}
      {claim.weakly_grounded === true && (
        <p className="border-l-[3px] border-orange bg-yellow-tint p-3 text-body text-navy">
          The grounding review could not fully verify this claim against its source — read it
          with that in mind.
        </p>
      )}
    </>
  );
  return (
    <ProvenanceSheet
      description="Claim provenance"
      claimTexts={[claim.text]}
      extras={extras}
      onClose={onClose}
    >
      {(claim.citations ?? []).map((citation) => (
        <CitationContext
          key={citation.citation_id}
          projectId={projectId}
          citation={citation}
          onOpenDossier={onOpenDossier}
        />
      ))}
    </ProvenanceSheet>
  );
}

/** A citation's hover-preview body (report ClaimSpan `tip`): source title
 *  (semibold navy), then its quote excerpt (italic grey, clamped at 180
 *  chars with an ellipsis) — with a caller-supplied tier/verdict node
 *  beneath. Exported so chat's tooltips (the claim-span hover and the bare
 *  `[n]` marker hover) mirror this exact shape instead of showing only their
 *  own verdict line (029/030 parity fix). */
export function CitationTooltipBody({
  sourceTitle,
  quote,
  statusLine,
}: {
  sourceTitle: string;
  quote: string;
  statusLine?: string | null;
}) {
  // statusLine is a plain string by design: the hover's content policy is
  // title · quote · ONE short status (tier label or unchecked wording) ·
  // the click hint — identical on every surface. Rationale/explainer text
  // lives in the provenance sheet's chip tooltip, never on the hover. A JSX
  // slot here is what let the chat hover drift twice (owner, 2026-08-12).
  return (
    <div className="max-w-[260px] space-y-1.5 text-meta leading-snug">
      <p className="font-semibold text-navy">{scrub(sourceTitle)}</p>
      {quote !== "" && (
        <p className="italic text-grey">
          “{scrub(quote.slice(0, 180))}
          {quote.length > 180 ? "…" : ""}”
        </p>
      )}
      {statusLine != null && statusLine !== "" && <p className="text-grey">{statusLine}</p>}
      <p className="text-meta text-grey">Click to view in context</p>
    </div>
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
      <CitationTooltipBody
        sourceTitle={first.source_title}
        quote={first.quote}
        statusLine={tier !== null ? TIER_LABEL[tier] : null}
      />
    ) : (claim.claim_type === "theme" || claim.claim_type === "pattern") &&
      (claim.theme?.items?.length ?? 0) > 0 ? (
      <div className="max-w-[260px] space-y-1 text-meta leading-snug">
        {(claim.theme?.items ?? []).slice(0, 3).map((item, index) => (
          <div key={index}>
            <p className="font-semibold text-navy">Theme: {scrub(item.name ?? "")}</p>
            {typeof item.description === "string" && item.description !== "" && (
              <p className="text-grey">{scrub(item.description)}</p>
            )}
            {typeof item.size === "number" && (
              <p className="text-meta text-grey">{item.size} sources</p>
            )}
          </div>
        ))}
        <p className="text-meta text-grey">Click for detail</p>
      </div>
    ) : claim.claim_type === "gap" ? (
      <div className="max-w-[260px] space-y-1 text-meta leading-snug">
        <p className="font-semibold text-navy">Evidence gap</p>
        <p className="text-grey">
          {(typeof claim.gap?.grade === "string" ? GAP_GRADE_TEXT[claim.gap.grade] : undefined) ??
            TYPE_HINT.gap}
        </p>
        <p className="text-meta text-grey">Click for the coverage detail</p>
      </div>
    ) : (
      <span className="text-meta">{TYPE_HINT[claim.claim_type] ?? "Claim"}</span>
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
          className={
            claim.claim_type === "citation"
              ? CITATION_SPAN_CLASS
              : `citation-marker cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-blue ${SPAN_STYLE[claim.claim_type] ?? ""}`
          }
        >
          {scrub(text)}
        </span>
      </Tooltip>
      {claim.claim_type === "citation" && citationNumbers.length > 0 && (
        <button
          type="button"
          aria-label={`Citations ${citationNumbers.join(", ")}`}
          onClick={() => onOpen(claim)}
          className={CITATION_MARKER_CLASS}
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

export type SpanSegment<C> = { kind: "plain"; text: string } | { kind: "claim"; text: string; claim: C };

/**
 * Split `prose` into plain/claim segments by each claim's `[start, end)`
 * span: overlapping spans keep the first (skip, don't mis-render) and
 * oversize/negative/empty spans are dropped. Shared by the report's
 * `AnnotatedProse` and chat's mirrored span rendering — the one place this
 * code-point slicing (see note below) is allowed to exist.
 */
export function spanSegments<C extends { span?: number[] | null }>(
  prose: string,
  claims: C[],
): SpanSegment<C>[] {
  // Span offsets are Python code-POINT indices (the annotator slices `str`);
  // JS string indexing counts UTF-16 code UNITS, so any astral character
  // (emoji, some CJK) before a span would shift it. Slice by code points.
  const chars = Array.from(prose);
  const spanned = claims
    .filter(
      (claim): claim is C & { span: [number, number] } =>
        claim.span !== null &&
        claim.span !== undefined &&
        claim.span[0] >= 0 &&
        claim.span.length === 2 &&
        claim.span[1] <= chars.length &&
        claim.span[0] < claim.span[1],
    )
    .sort((a, b) => a.span[0] - b.span[0]);
  const parts: SpanSegment<C>[] = [];
  let cursor = 0;
  for (const claim of spanned) {
    if (claim.span[0] < cursor) continue; // overlapping span — keep the first
    if (claim.span[0] > cursor) {
      parts.push({ kind: "plain", text: chars.slice(cursor, claim.span[0]).join("") });
    }
    parts.push({ kind: "claim", text: chars.slice(claim.span[0], claim.span[1]).join(""), claim });
    cursor = claim.span[1];
  }
  if (cursor < chars.length) parts.push({ kind: "plain", text: chars.slice(cursor).join("") });
  return parts;
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
  const segments = useMemo(() => spanSegments(block.prose, block.claims ?? []), [block]);

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
          <p key={claim.claim_id} className="mt-2 text-body text-grey">
            <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} />
          </p>
        ))}
        {unspanned.map((claim) => (
          <p key={claim.claim_id} className="mt-2 text-body text-grey">
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
        <p key={claim.claim_id} className="mt-2 text-body text-grey">
          <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} />
        </p>
      ))}
    </div>
  );
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function SourceDossier({
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
          <p role="status" className="animate-pulse text-body text-grey">
            Loading the dossier…
          </p>
        )}
        {dossier.isPending && <p role="status" className="animate-pulse text-body text-grey">Loading the dossier…</p>}
        {dossier.isError && <p role="alert" className="text-body text-navy">This source dossier couldn't be loaded.</p>}
        {dossier.data && <SourceDossierBody source={dossier.data} findings={findings.data?.data} findingsPending={findings.isPending} />}
        {!byId && evidence.data !== undefined && source === undefined && (
          <p className="text-body text-grey">This source isn't in the evidence list yet.</p>
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
          className="border-l-[3px] border-l-red bg-red-tint px-3.5 py-2.5 text-body leading-relaxed text-navy"
        >
          <p className="font-bold">This run ended before the write-up completed.</p>
          <p className="mt-0.5">
            The sections below are drafted text from the interrupted run — not the checked
            evidence base. Citations were never attached. Start a fresh run to produce the full
            artefact.
          </p>
        </div>
      ) : (
        <p role="status" className="flex items-center gap-2 text-body text-grey">
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
            <p role="status" className="anim-breathe mt-2 text-body text-grey">
              Writing this section now…
            </p>
          ) : (
            <p className="mt-2 text-body italic text-grey">
              {section.focus !== "" ? scrub(section.focus) : "Waiting to be written."}
            </p>
          )}
        </section>
      ))}
      {!terminalPartial && (
        <p className="mt-10 border-t border-line pt-4 text-body text-grey">
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
/**
 * The report's opening statement.
 *
 * Only a verified summary is shown as the answer: an unverified one has not
 * passed the faithfulness check, and presenting it as the answer would be the
 * report vouching for something it has not checked. `pending` and `failed`
 * each say what is true instead, and the report still opens correctly at Key
 * findings beneath.
 */
function AnswerCallout({
  summary,
  status,
}: {
  summary: string | null;
  status: "pending" | "verified" | "failed" | null;
}) {
  if (status === "verified" && summary != null && summary !== "") {
    return (
      <p className="mt-4 max-w-prose-measure border-l-2 border-l-blue bg-blue-tint/30 px-4 py-3 text-lead text-ink">
        {scrub(summary)}
      </p>
    );
  }
  if (status === "pending") {
    return (
      <p role="status" className="mt-4 max-w-prose-measure text-body text-grey">
        The summary is still being checked. The findings below are complete.
      </p>
    );
  }
  if (status === "failed") {
    return (
      <p role="status" className="mt-4 max-w-prose-measure text-body text-grey">
        A summary couldn't be verified for this report, so none is shown. The
        findings below are complete.
      </p>
    );
  }
  return null;
}

/**
 * The handful of sources the report leans on most.
 *
 * Every line is a fact the data already asserts — how often it is cited, its
 * appraisal tier, its evidence type, which sections use it. It never says why
 * a study matters: that is a judgement nobody made, and asserting it would be
 * the report inventing authority for itself.
 */
function MostRelevantSources({
  sources,
  onOpenDossier,
}: {
  sources: TopSource[];
  onOpenDossier: (title: string) => void;
}) {
  if (sources.length === 0) return null;
  return (
    <section className="mt-8 border-t border-line pt-6">
      <h2 className="text-caption font-extrabold uppercase tracking-[0.06em] text-grey">
        Most cited sources
      </h2>
      <ul role="list" className="mt-3 space-y-3">
        {sources.map((source) => (
          <li key={source.sourceId} className="border border-line p-3">
            <button
              type="button"
              onClick={() => onOpenDossier(source.title)}
              className="cursor-pointer text-left text-body font-semibold text-navy hover:underline"
            >
              {scrub(source.title)}
            </button>
            <p className="mt-1 text-body text-grey">
              Cited by {source.citationCount === 1 ? "1 claim" : `${source.citationCount} claims`}
              {source.appraisalLabel != null && ` · ${scrub(source.appraisalLabel)}`}
              {source.evidenceType != null && ` · ${scrub(source.evidenceType)}`}
            </p>
            <p className="mt-1 text-body text-grey">
              In {source.citedInSections.map((title) => scrub(title)).join(", ")}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ArtefactView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const artefact = useArtefact(projectId);
  const chats = useConversations(projectId, { kind: "chat", status: "active" });
  const { create } = useConversationMutations(projectId);
  // Cited-scoped distributions for the facts strip: study types and years
  // count what the report CITES, not the whole included corpus (owner,
  // 2026-08-05); the durable coverage_snapshot keeps the corpus-wide counts.
  const citedLandscape = useLandscape(projectId, "cited");
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
  const { setActiveConversation } = useActiveConversation();
  const askAboutAnalysis = async () => {
    // The open artefact is the chat's entry context (a chip and provenance
    // fact, never a scope fence); reuse a blank chat already carrying it.
    const artefactId = artefact.data?.artefact_id ?? null;
    const blank = chats.data?.data.find(
      (chat) => chat.title === "New chat" && chat.entry_artefact_id === artefactId,
    );
    const conversation = blank ?? await create(artefactId);
    // Open the side panel HERE (rev 3.4): questions arise while reading, so
    // the chat lands beside the artefact instead of navigating away.
    addOpenChatTab(projectId, conversation.id);
    setActiveConversation(conversation.id);
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
          <Card role="alert" className="p-8 text-center text-body text-navy">
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
          <p className="mt-1.5 text-body text-grey">
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
  // Study types and years count the CITED set (the live cited-scope
  // landscape), not the whole included corpus.
  const citedTypes = Object.entries(citedLandscape.data?.evidence_types ?? {}).sort(
    ([, a], [, b]) => b - a,
  );
  const shownTypes = citedTypes.slice(0, 3);
  const citedYears = Object.keys(citedLandscape.data?.years ?? {})
    .map(Number)
    .filter(Number.isInteger);
  const sections = orderSections((data.sections ?? []) as SectionLike[]);

  // Sources and Screened out link into the sources view, filtered to match
  // (028 F.5): `cited` and `status` are SourcesView's existing URL params —
  // there is no `status=cited` value, so the cited count routes through the
  // boolean `cited=true` param instead.
  const snapshotCells: Array<[string, string, string | null]> = [];
  if (typeof snapshot?.source_count === "number" && typeof snapshot?.included === "number") {
    // Transcription trap 3: `source_count` is the cited/reference count —
    // never "found".
    snapshotCells.push([
      "Sources",
      `${snapshot.source_count} cited out of ${snapshot.included} included`,
      `/projects/${projectId}/sources/all?cited=true`,
    ]);
  }
  if (shownTypes.length > 0) {
    snapshotCells.push([
      "Study types",
      shownTypes.map(([key, count]) => `${count} ${key.toLowerCase()}`).join(" · ") +
        (citedTypes.length > 3 ? ` · +${citedTypes.length - 3} more` : ""),
      null,
    ]);
  }
  if (citedYears.length > 0) {
    snapshotCells.push([
      "Years",
      `${Math.min(...citedYears)}–${Math.max(...citedYears)}`,
      null,
    ]);
  }
  if (typeof snapshot?.screened_out === "number") {
    snapshotCells.push([
      "Screened out",
      `${snapshot.screened_out}`,
      `/projects/${projectId}/sources/all?status=screened_out`,
    ]);
  }
  // The report states when it was made. The run's end is the honest answer —
  // the artefact read model carries no timestamp of its own. There is
  // deliberately no author line: the backend has no author for an artefact,
  // and inventing one would have the report assert something nobody wrote.
  const lastUpdated = project.data?.latest_run?.ended_at;
  if (lastUpdated != null) {
    snapshotCells.push(["Last updated", new Date(lastUpdated).toLocaleDateString(), null]);
  }

  const topSources = mostRelevantSources(sections);

  const outlineEntries = [
    ...sections.map((section, index) => ({
      id: sectionAnchor(section.title, index),
      // The contents list is for scanning, so it uses the short nav label
      // when synthesis produced one and a shortened title otherwise.
      title: sectionNavLabel(section, 28),
    })),
    ...((data.references ?? []).length > 0 ? [{ id: "references", title: "References" }] : []),
    { id: "gathered", title: "How the evidence was gathered" },
  ];

  return (
    <div className="mx-auto flex max-w-[1180px] justify-center gap-6 px-4">
      <ContentsSidebar entries={outlineEntries} />
      <main className="artefact-page anim-rise my-8 min-w-0 max-w-[780px] flex-1 bg-paper px-10 py-9 shadow-sm ring-1 ring-line">
      <header className="mb-8">
        <p className="text-caption font-extrabold uppercase tracking-[0.06em] text-grey">
          Evidence base
        </p>
        <h1 className="mt-1 font-display text-display font-extrabold leading-tight tracking-[-0.5px] text-navy">
          {scrub(data.title)}
        </h1>
        <button type="button" onClick={() => void askAboutAnalysis()} className="mt-3 text-caption font-bold text-blue hover:underline">Ask about this analysis</button>
        {/* No question subtitle — the title already carries it (owner, 2026-08-05). */}
        <AnswerCallout summary={data.summary ?? null} status={data.summary_status ?? null} />
        {snapshotCells.length > 0 && (
          <div className="mt-5 grid grid-cols-2 border border-line sm:grid-cols-4">
            {snapshotCells.map(([label, value, href]) => {
              const content = (
                <>
                  <p className="text-caption font-bold uppercase tracking-[0.06em] text-grey">{label}</p>
                  <p className="mt-1 text-body font-medium leading-snug text-navy">{scrub(value)}</p>
                </>
              );
              return href !== null ? (
                <Link
                  key={label}
                  to={href}
                  className="border-r border-line p-3 last:border-r-0 hover:underline"
                >
                  {content}
                </Link>
              ) : (
                <div key={label} className="border-r border-line p-3 last:border-r-0">
                  {content}
                </div>
              );
            })}
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
          // Key findings is never collapsible (always in full); every other
          // section — conclusions included — starts collapsed on its summary
          // (owner, 2026-08-05).
          collapsible={section.role !== "key_findings"}
          defaultOpen={false}
        >
          {(section.blocks ?? []).map((block) => (
            <AnnotatedProse key={block.block_id} block={block} onOpenClaim={setDetailClaim} />
          ))}
        </SectionDisclosure>
      ))}

      <MostRelevantSources sources={topSources} onOpenDossier={openDossier} />

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
        <span aria-hidden="true" className="shrink-0 text-meta font-bold text-blue">
          {open ? "Collapse −" : "Expand +"}
        </span>
      </button>
      {!open && (
        <p className="mt-1.5 text-body text-grey">
          {references.length === 1 ? "1 numbered source" : `${references.length} numbered sources`} cited
          in this report
        </p>
      )}
      {open && (
        <ol className="mt-3 space-y-1.5 text-body text-ink">
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

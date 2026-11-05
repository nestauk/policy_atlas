import { createContext, Fragment, memo, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { CSSProperties, ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import type { components } from "../api/gen/types";
import { useApiClient, useArtefact, useConversations, useEvidence, useFindings, useLandscape, useLonglist, useRuns, useTask, useSourceDossier } from "../api/queries";
import { useQuery } from "@tanstack/react-query";
import {
  cardEvidenceMeta,
  CASE_STUDIES_INTRO,
  drawingOnLine,
  EXECUTIVE_SUMMARY_ANCHOR,
  fullReportIntro,
  FULL_REPORT_ANCHOR,
  mergeMostRelevantNotes,
  mostRelevantSources,
  MOST_RELEVANT_SOURCES_INTRO,
  REPORT_BODY_CLASS,
  REPORT_PART_HEADING_CLASS,
  REPORT_SECTION_HEADING_CLASS,
  sectionNavLabel,
  splitLeadColon,
} from "./artefactPresentation";
import type { TopSource } from "./artefactPresentation";
import type { SidebarEntry } from "./ArtefactOutline";
import { ArtefactDownload } from "./ArtefactDownload";
import { errorCode } from "../lib/errors";
import { useNow } from "../lib/freshness";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { COPY } from "../lib/vocabulary";
import { RESULT_VIEWS, resultView } from "./lifecycle";
import { hasLonglist, isBaselineArtefact, statusRun } from "./scopingActivity";
import { useChatsEnabled } from "./taskResult";
import { LonglistBuilding, LonglistView } from "./longlist/LonglistView";
import { isLonglistBuilding, LONGLIST_WALK_STAGES } from "./longlist/longlistPresentation";
import { usePlanPanel } from "./planPanel";
import { ShortlistView } from "./longlist/ShortlistView";
import { Tabs, TabsList, TabsTrigger } from "../ui/radix/Tabs";
import { hasTerminalPartialLiveArtefact, useRunStream } from "../store";
import type { LiveCitation, LiveClaim, LiveSection, LiveSourceNote, RunStreamState } from "../store";
import { LiveMark } from "../ui/brand/Card";
import { Chip, type ChipProps } from "../ui/brand/Chip";
import { ReauthRedirect } from "../ui/feedback";
import { Sheet, SheetContent } from "../ui/radix/Sheet";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";
import { REPORT_TITLE_CLASS, ReportKindRow, ReportPage, SnapshotCells, type SnapshotCell } from "./reportPage";
import { usePublicView } from "./publicView";
import {
  FullReportExpandAllButton,
  FullReportExpandProvider,
  GatheredSection,
  MobileDisclosureToggle,
  type OutlineSection,
  SectionDisclosure,
  SECTION_EXPAND_LINK_CLASS,
  sectionAnchor,
  useExpandAll,
  useOpenWhenNavigated,
  useScrollWhenNavigated,
  useExpandForPrint,
} from "./ArtefactOutline";
import { Tooltip } from "../ui/radix/Tooltip";
import { AuthorsLine, InstitutionsLine, SourceDossierBody, useDossierRecords } from "./SourcesView";
import { referenceAuthorsLine } from "./artefactPresentation";
import { useActiveConversation } from "./workspace/chat/conversationState";
import "./artefact.css";
import { scrollPane, useEasedHeight, useFollowTail, useHoldHeightWhileShorter, useRevealedText } from "./streamPacing";
import { RetryCard } from "../ui/feedback/RetryCard";
import { LINK_CLASS, QUIET_CONTROL_CLASS } from "../ui/brand/inlineActions";
import { cn } from "../ui/brand/cn";

type CitationOut = components["schemas"]["CitationOut"];
type GapOut = components["schemas"]["GapOut"];
type LatestRun = components["schemas"]["LatestRun"];

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
  /** True for a claim the live page built from a checked section's
   *  citations (task 058, round 8): the sheet opens on what the run knows
   *  (the span, the tier, each citation's id, quote and title) and leaves out
   *  what only the committed report has. */
  live?: boolean;
}
interface BlockLike {
  block_id: string;
  prose: string;
  claims?: ClaimLike[];
}
interface CaseStudyCardLike {
  card_id?: string;
  title: string;
  prose: string;
  claims?: ClaimLike[];
  result_claim_id?: string | null;
  strength?: string | null;
  design?: string | null;
  since_year?: number | null;
}
interface SectionLike {
  title: string;
  nav_label?: string | null;
  role?: "key_findings" | "case_studies" | "standard" | "conclusions" | "intro";
  focus?: string | null;
  blocks?: BlockLike[];
  cards?: CaseStudyCardLike[];
}

/** The run's source notes so far, in the order written (round 8). */
function liveSourceNotes(stream: RunStreamState): LiveSourceNote[] {
  return stream.liveSourceNotes ?? [];
}

/* --- typed annotation vocabulary (strand 5): claim breadth beyond
   citation/gap — reasoning · pattern/theme · source-check, styled per type
   with inline chips. Unknown types render as plain prose (honest absence). */

/** Claim-span hover tint. The annotation layer lives in the text and the
 *  whole span is the affordance; rest state is unmarked so the report body
 *  stays uncluttered (no dotted underlines). */
const CITATION_TINT = "hover:bg-blue-tint-2";

const SPAN_STYLE: Partial<Record<ClaimLike["claim_type"], string>> = {
  // reasoning + unspanned_assertion carry no user-facing detail (owner,
  // 2026-07-29): they render as plain prose — see UNMARKED_TYPES.
  citation: CITATION_TINT,
  gap: "hover:bg-yellow-tint",
  pattern: "hover:bg-blue-tint-2",
  theme: "hover:bg-blue-tint-2",
};

/** The claim-span affordance's full class string for the report's "citation"
 *  type (marker hook + hover chrome + the tint above) — chat's claim spans
 *  render as this one type (design point 4), so this is exported rather than
 *  re-typed on the chat side. */
export const CITATION_SPAN_CLASS = `citation-marker cursor-pointer transition-colors ${CITATION_TINT}`;

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
  "The cited source's appraised evidence strength — five bands from Weak to Very strong, scored from its classified document type; Unrated when the type is not scored.";

/** The grounding-tier vocabulary (demo ui.tsx TIER_LABEL/TIER_TEXT — locked;
 *  unknown tier → the raw value never renders, the chip omits). Exported so
 *  every surface that renders a grounding verdict (chat included) shares
 *  this one copy instead of re-typing it. */
export const TIER_LABEL: Record<string, string> = {
  tier_1: "Tier 1 · direct quote",
  tier_2: "Tier 2 · grounded",
  tier_3: "Tier 3 · supported",
  tier_4: "Tier 4 · reasoning",
  unsupported_mis_cited: "Unsupported",
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
  const rank = (section: T) => {
    if (section.role === "key_findings") return 0;
    if (section.role === "case_studies") return 1;
    if (section.role === "conclusions") return 3;
    return 2; // standard
  };
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
      <mark className="bg-yellow-tint text-navy">{scrub(parts.match)}</mark>
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
function useChunkContext(taskId: string, citationId: string | null) {
  const client = useApiClient();
  return useQuery({
    enabled: citationId !== null,
    queryKey: ["tasks", taskId, "chunk-context", citationId],
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/tasks/{task_id}/citations/{citation_key}/context",
        { params: { path: { task_id: taskId, citation_key: citationId ?? "" } } },
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
      <AuthorsLine authorships={context.data?.authorships} className="mt-0.5 text-body text-grey" />
      {meta.length > 0 && (
        <p className="mt-0.5 text-body text-grey">{meta.map((m) => scrub(String(m))).join(" · ")}</p>
      )}
      <InstitutionsLine authorships={context.data?.authorships} className="mt-0.5 text-caption text-grey" />
      <div className="mt-2 flex flex-wrap gap-1.5">{chips}</div>
      <div className="mt-3 space-y-2 text-body">
        {context.isPending && (
          <p role="status" className="anim-breathe text-body text-grey">
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
            ? label === "Unrated"
              ? `Unrated — the document type (${scrub(evidenceType)}) is not scored; the source can be cited but counts below the evidence bar.`
              : `${scrub(label)} evidence strength — appraised from the document type: ${scrub(evidenceType)}.`
            : APPRAISAL_FALLBACK_HINT}
        </span>
      }
    />
  );
}

/** One citation's provenance block in the claim panel (demo CitationContext):
 *  the reader's tier + appraisal chips over the shared block. */
function CitationContext({
  taskId,
  citation,
  onOpenDossier,
  live = false,
}: {
  taskId: string;
  citation: CitationOut;
  onOpenDossier: (title: string) => void;
  /** The report is still being written: the title is not a link yet. */
  live?: boolean;
}) {
  const context = useChunkContext(taskId, citation.citation_id);
  const tier = citation.grounding_tier ?? null;
  return (
    <CitationProvenanceBlock
      n={citation.n}
      sourceTitle={citation.source_title}
      sourceRef={live ? null : (citation.source_id ?? citation.source_title)}
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
                className="border-l-2 border-l-blue pl-3 text-body leading-snug text-navy"
              >
                {scrub(text)}
              </p>
            ))}
          {extras}
          {children}
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** The provenance panel a claim span opens (demo ClaimPanel): the claim, its
 *  type explainer, and every citation's highlighted source passage — over
 *  the shared ProvenanceSheet shell. */
function ClaimPanel({
  taskId,
  claim,
  onClose,
  onOpenDossier,
}: {
  taskId: string;
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
        <div className="border-l-[3px] border-yellow bg-yellow-tint p-3 text-body text-navy">
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
                <p className="mt-0.5 text-body text-navy">
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
                    className={LINK_CLASS}
                    to={`/tasks/${taskId}/sources/findings?facet=${encodeURIComponent(item.facet)}&group=${encodeURIComponent(item.name)}`}
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
          taskId={taskId}
          citation={citation}
          onOpenDossier={onOpenDossier}
          live={claim.live === true}
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
  showCitationMarker = true,
  live = false,
}: {
  claim: ClaimLike;
  text: string;
  onOpen: (claim: ClaimLike) => void;
  /** When false, the [n] marker button is suppressed — used for the lead
   *  half of a colon-crossing citation so the marker shows only once. */
  showCitationMarker?: boolean;
  /** True on the report while it is written. A checked claim whose
   *  citations carry their ids is a control as on the committed report
   *  (task 058, round 8); one without them (an older stream) shows its
   *  number in the report's look and is not a control. */
  live?: boolean;
}) {
  const swap = useContext(ReportSwapContext);
  // Dev-facing markings (source-check flags, connective reasoning) carry no
  // user-facing detail: their prose renders unmarked (owner, 2026-07-29).
  if (UNMARKED_TYPES.has(claim.claim_type)) return <span>{scrub(text)}</span>;
  const citationNumbers = [...new Set((claim.citations ?? []).map((citation) => citation.n))];
  const inert =
    live && ((claim.citations ?? []).length === 0 || (claim.citations ?? []).some((citation) => !citation.citation_id));
  if (inert) {
    const titles = [...new Set((claim.citations ?? []).map((citation) => scrub(citation.source_title)))];
    return (
      <span>
        <span>{scrub(text)}</span>
        {claim.claim_type === "citation" && citationNumbers.length > 0 && showCitationMarker && (
          <span
            role="img"
            aria-label={`${citationNumbers.length === 1 ? "Citation" : "Citations"} ${citationNumbers.join(", ")}, ${titles.join("; ")}; details when the report is ready`}
            title={titles.join("; ")}
            className={CITATION_MARKER_LIVE_CLASS}
          >
            [{citationNumbers.join(",")}]
          </span>
        )}
      </span>
    );
  }
  // A marker whose number changed at the swap fades its new number in; the
  // text around it does not move (owner, round 7).
  const before = swap.liveNumbers.get(markerKey(claim.span, text));
  const renumbered = swap.arriving && before !== undefined && before !== citationNumbers.join(",");
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
              : `citation-marker cursor-pointer transition-colors ${SPAN_STYLE[claim.claim_type] ?? ""}`
          }
        >
          {scrub(text)}
        </span>
      </Tooltip>
      {claim.claim_type === "citation" && citationNumbers.length > 0 && showCitationMarker && (
        <button
          type="button"
          aria-label={`Citations ${citationNumbers.join(", ")}`}
          onClick={() => onOpen(claim)}
          className={renumbered ? `${CITATION_MARKER_CLASS} anim-swap-in` : CITATION_MARKER_CLASS}
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

type SpanSegment<C> = { kind: "plain"; text: string } | { kind: "claim"; text: string; claim: C };

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

type BulletSegment = SpanSegment<ClaimLike>;

function stripBulletPrefix(text: string, isFirst: boolean): string {
  return isFirst ? text.replace(/^\s*- /, "") : text;
}

function sliceSegment(segment: BulletSegment, start: number, end: number): BulletSegment {
  const text = segment.text.slice(start, end);
  return segment.kind === "plain" ? { kind: "plain", text } : { kind: "claim", text, claim: segment.claim };
}

/**
 * Bold everything before the first `: ` on a key-findings bullet (034 S3).
 *
 * The split is display-only. A claim span that crosses the colon is sliced
 * into two affordances of the same claim rather than mis-joined. No colon
 * leaves the line unbolded.
 */
function renderLeadColonBullet(
  segments: BulletSegment[],
  onOpenClaim: (claim: ClaimLike) => void,
  live = false,
): ReactNode {
  const cleaned: BulletSegment[] = segments.map((segment, index) => {
    const text = stripBulletPrefix(segment.text, index === 0);
    return segment.kind === "plain"
      ? { kind: "plain", text }
      : { kind: "claim", text, claim: segment.claim };
  });
  const full = cleaned.map((segment) => segment.text).join("");
  const split = splitLeadColon(full);

  const renderSegs = (
    parts: BulletSegment[],
    keyPrefix: string,
    suppressMarkerIds?: Set<string>,
  ) =>
    parts.map((segment, index) =>
      segment.kind === "plain" ? (
        <span key={`${keyPrefix}${index}`}>{scrub(segment.text)}</span>
      ) : (
        <ClaimSpan
          key={`${keyPrefix}${index}`}
          claim={segment.claim}
          text={segment.text}
          onOpen={onOpenClaim}
          live={live}
          showCitationMarker={
            suppressMarkerIds !== undefined
              ? !suppressMarkerIds.has(segment.claim.claim_id)
              : true
          }
        />
      ),
    );

  if (split === null) return renderSegs(cleaned, "u");

  const splitAt = full.indexOf(": ");
  const colonEnd = splitAt + 2;
  const leadPieces: BulletSegment[] = [];
  const restPieces: BulletSegment[] = [];
  let offset = 0;
  for (const segment of cleaned) {
    const start = offset;
    const end = offset + segment.text.length;
    offset = end;
    if (end <= splitAt) {
      leadPieces.push(segment);
      continue;
    }
    if (start >= colonEnd) {
      restPieces.push(segment);
      continue;
    }
    if (start < splitAt) {
      leadPieces.push(sliceSegment(segment, 0, splitAt - start));
    }
    if (end > colonEnd) {
      restPieces.push(sliceSegment(segment, colonEnd - start, segment.text.length));
    }
  }
  // Claims whose span crosses the colon appear in both halves: show [n] only
  // in the rest half so the marker is never duplicated (034 S3 fix).
  const restClaimIds = new Set(
    restPieces
      .filter((s): s is Extract<BulletSegment, { kind: "claim" }> => s.kind === "claim")
      .map((s) => s.claim.claim_id),
  );
  return (
    <>
      <strong>
        {renderSegs(leadPieces, "l", restClaimIds)}
        :
      </strong>
      {restPieces.length > 0 ? <> {renderSegs(restPieces, "r")}</> : null}
    </>
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
  live = false,
}: {
  block: BlockLike;
  onOpenClaim: (claim: ClaimLike) => void;
  /** True on the report while it is written (markers are not controls yet). */
  live?: boolean;
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
      <div className={`max-w-prose-measure ${REPORT_BODY_CLASS}`}>
        <ul className="list-none space-y-1.5">
          {bullets.map((bullet, bulletIndex) => {
            const isGap = bullet.some(
              (segment) => segment.kind === "claim" && segment.claim.claim_type === "gap",
            );
            return (
              <li key={bulletIndex} className="flex gap-2">
                <span
                  aria-hidden="true"
                  className={`mt-2 h-1.5 w-1.5 shrink-0 ${isGap ? "bg-yellow" : "bg-blue"}`}
                />
                <span>{renderLeadColonBullet(bullet, onOpenClaim, live)}</span>
              </li>
            );
          })}
        </ul>
        {crossing.map((claim) => (
          <p key={claim.claim_id} className="mt-2 text-lead text-grey max-md:text-body">
            <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} live={live} />
          </p>
        ))}
        {unspanned.map((claim) => (
          <p key={claim.claim_id} className="mt-2 text-lead text-grey max-md:text-body">
            <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} live={live} />
          </p>
        ))}
      </div>
    );
  }

  return (
    <div className={`max-w-prose-measure ${REPORT_BODY_CLASS}`}>
      <p className="whitespace-pre-line">
        {segments.map((segment, index) => {
          if (segment.kind === "plain") {
            return <span key={index}>{scrub(segment.text)}</span>;
          }
          return (
            <ClaimSpan key={index} claim={segment.claim} text={segment.text} onOpen={onOpenClaim} live={live} />
          );
        })}
      </p>
      {unspanned.map((claim) => (
        <p key={claim.claim_id} className="mt-2 text-lead text-grey max-md:text-body">
          <ClaimSpan claim={claim} text={claim.text} onOpen={onOpenClaim} live={live} />
        </p>
      ))}
    </div>
  );
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function SourceDossier({
  taskId,
  sourceRef,
  optionId = null,
  onClose,
}: {
  taskId: string;
  /** A source id (citations carry one) or a display title (references,
   *  theme members — the legacy title-keyed path). */
  sourceRef: string;
  /** The option whose card opened the dossier (the `option` search
   *  parameter): on an options-scoping task the slot then reads "In this
   *  option" (task 046, amendment 3, R67). */
  optionId?: string | null;
  onClose: () => void;
}) {
  const byId = UUID_RE.test(sourceRef);
  const evidence = useEvidence(taskId, { page_size: 200 });
  const source = byId
    ? evidence.data?.data.find((item) => item.source_id === sourceRef)
    : evidence.data?.data.find((item) => item.title === sourceRef);
  const sourceId = byId ? sourceRef : (source?.source_id ?? null);
  const dossier = useSourceDossier(taskId, sourceId);
  const findings = useFindings(
    taskId,
    sourceId !== null ? { page_size: 200, source_id: sourceId } : undefined,
  );
  const records = useDossierRecords(taskId, sourceId, optionId);
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent
        title={scrub(byId ? (dossier.data?.title ?? source?.title ?? "Source") : sourceRef)}
      >
        {/* isLoading, not isPending: while the title→id lookup has not
         *  resolved, the dossier query is disabled and pending forever —
         *  isPending would render a stuck (and duplicate) loading line. */}
        {((!byId && evidence.isPending) || dossier.isLoading) && (
          <p role="status" className="anim-breathe text-body text-grey">
            Loading the dossier…
          </p>
        )}
        {dossier.isError && <p role="alert" className="text-body text-navy">This source dossier couldn't be loaded.</p>}
        {dossier.data && (
          <SourceDossierBody
            records={records}
            source={dossier.data}
            findings={findings.data?.data}
            findingsPending={findings.isPending}
          />
        )}
        {!byId && evidence.data !== undefined && source === undefined && (
          <p className="text-body text-grey">This source isn't in the evidence list yet.</p>
        )}
      </SheetContent>
    </Sheet>
  );
}

/**
 * Whether Results should show the in-progress artefact instead of the
 * committed page.
 *
 * SSE replay of a finished succeeded/degraded run briefly looks like a live
 * write (status "running", sections filling). That must not replace the
 * persisted page. A still-running run, a new run id, and a terminal-partial
 * failed write still take the live view.
 *
 * Args:
 *   stream: Live SSE state for the task's current run.
 *   latestRun: The task's persisted latest-run read model, if loaded.
 *
 * Returns:
 *   True when `LiveArtefactBody` should render.
 */
export function showLiveArtefact(
  stream: RunStreamState,
  latestRun: LatestRun | null | undefined,
): boolean {
  if (Object.keys(stream.liveSections).length === 0) return false;
  const replayingFinished =
    latestRun?.ended_at != null &&
    latestRun.ended_at !== "" &&
    stream.run?.id === latestRun.capability_run_id &&
    (latestRun.status === "succeeded" || latestRun.status === "degraded");
  if (replayingFinished) return false;
  return (
    stream.run?.status === "running" ||
    // A run parked on a check-in keeps the live body (task 058, N11).
    stream.run?.status === "paused" ||
    hasTerminalPartialLiveArtefact(stream)
  );
}

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(onChange: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener?.("change", onChange);
  return () => query.removeEventListener?.("change", onChange);
}

function reducedMotionNow(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(REDUCED_MOTION_QUERY).matches
    : false;
}

/** True when the reader asked the system for reduced motion. */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribeReducedMotion, reducedMotionNow, () => false);
}

/** The latest non-null value seen, kept after the value goes null, so a
 *  line can collapse with its last words instead of blanking first. */
function useLatched<T>(value: T | null): T | null {
  const [latched, setLatched] = useState<T | null>(value);
  if (value !== null && value !== latched) setLatched(value);
  return value ?? latched;
}

/** The server's key-findings slot: generated last, presented first, always
 *  index 0 with this title (`runtime/progress.py` `emit_skeleton`). The
 *  skeleton carries no role, so the slot is recognised by both. */
const KEY_FINDINGS_SLOT_TITLE = "Key findings";

export function isKeyFindingsSlot(section: Pick<LiveSection, "index" | "title">): boolean {
  return section.index === 0 && section.title === KEY_FINDINGS_SLOT_TITLE;
}

/** Placeholder line widths (percent of the measure), two or three lines a
 *  section, varied by index so the page does not read as a template. */
const PLACEHOLDER_WIDTHS: readonly (readonly number[])[] = [
  [100, 93, 58],
  [97, 71],
  [100, 88, 42],
  [94, 100, 66],
  [100, 79],
  [100, 96, 37],
  [91, 64],
];

function PlaceholderLines({
  index,
  still,
  className = "",
  leaving = false,
}: {
  index: number;
  still: boolean;
  className?: string;
  /** Fading out over the first words (round 9). */
  leaving?: boolean;
}) {
  const widths = PLACEHOLDER_WIDTHS[index % PLACEHOLDER_WIDTHS.length];
  return (
    <div
      aria-hidden="true"
      data-testid={leaving ? "placeholder-lines-leaving" : "placeholder-lines"}
      className={`flex max-w-prose-measure flex-col gap-4 py-2 max-md:gap-3.5 ${still ? "" : "anim-breathe"} ${className}`}
    >
      {widths.map((width, line) => (
        <span key={line} className="block h-2.5 bg-line" style={{ width: `${width}%` }} />
      ))}
    </div>
  );
}

/** One stretch of drafted text: where it starts in the draft (code points),
 *  whether it is under repair (`reviseAt` is the repaired span's place in
 *  document order), whether it is a repaired span's new words settling in,
 *  and the writer's citations that end where it ends (`marks`, only when
 *  there are any; `markAt` is the first one's place in document order). */
export type DraftRun = {
  text: string;
  start: number;
  revising: boolean;
  reviseAt?: number;
  settling?: boolean;
  marks?: LiveClaim[];
  markAt?: number;
};

/** A code-point range of a draft. */
type DraftSpan = { start: number; end: number };

/** How a draft is laid out: paragraphs apart by blank lines, or the key
 *  findings' list, one item per line. */
type DraftLayout = "prose" | "list";

/** Blank lines part paragraphs; any line break parts list items. */
const PARAGRAPH_BREAK = /\n[ \t]*\n\s*/g;
const LINE_BREAK = /\n\s*/g;

/** The list item's own marker at the start of a drafted line. */
const ITEM_MARKER = /^\s*-(?:\s|$)/;

/** Each repaired span's blur and its settle start this long after the one
 *  before it, in document order (task 058, owner round 8). */
export const REVISE_STAGGER_MS = 120;

/** How long a repaired span's new words take to resolve out of the blur. */
const SETTLE_IN_MS = 400;

/** How long the draft layer takes to fade off the checked prose. */
const SETTLE_MS = 400;

/**
 * Split drafted text into blocks (paragraphs, or list items), mark the spans
 * under repair and the repaired words settling in, and end a run wherever one
 * of the writer's citations ends, so its provisional marker can follow the
 * cited words. Spans are code-point offsets into the draft, as the server
 * counts them; every run keeps its own offset, so the live block can fade in
 * exactly the words each frame revealed.
 *
 * Args:
 *   draft: The drafted text.
 *   revising: The spans under repair.
 *   claims: The writer's citations.
 *   layout: Paragraphs, or the key findings' list (each line an item, its
 *     "- " dropped).
 *   settling: Spans of repaired words resolving out of the blur.
 *
 * Returns:
 *   The blocks, each a list of runs; empty blocks are dropped.
 */
export function draftBlocks(
  draft: string,
  revising: readonly DraftSpan[] = [],
  claims: readonly LiveClaim[] = [],
  layout: DraftLayout = "prose",
  settling: readonly DraftSpan[] = [],
): DraftRun[][] {
  const chars = Array.from(draft);
  const reviseAt = new Array<number>(chars.length).fill(-1);
  [...revising]
    .sort((a, b) => a.start - b.start)
    .forEach(({ start, end }, at) => {
      for (let i = Math.max(0, start); i < Math.min(end, chars.length); i += 1) {
        if (reviseAt[i] === -1) reviseAt[i] = at;
      }
    });
  const settleAt = new Array<number>(chars.length).fill(-1);
  settling.forEach(({ start, end }, at) => {
    for (let i = Math.max(0, start); i < Math.min(end, chars.length); i += 1) settleAt[i] = at;
  });
  // Citations by the code point they end after; one past the draft is dropped.
  const endingAt = new Map<number, LiveClaim[]>();
  for (const claim of claims) {
    if (claim.end <= 0 || claim.end > chars.length || claim.start >= claim.end) continue;
    endingAt.set(claim.end - 1, [...(endingAt.get(claim.end - 1) ?? []), claim]);
  }
  const runs: DraftRun[] = [];
  const kinds: string[] = [];
  let open = false;
  chars.forEach((char, at) => {
    const kind = `${reviseAt[at]}|${settleAt[at]}`;
    const last = runs.at(-1);
    if (open && last !== undefined && kinds.at(-1) === kind) {
      last.text += char;
    } else {
      const run: DraftRun = { text: char, start: at, revising: reviseAt[at] !== -1 };
      if (reviseAt[at] !== -1) run.reviseAt = reviseAt[at];
      if (settleAt[at] !== -1) run.settling = true;
      runs.push(run);
      kinds.push(kind);
    }
    open = true;
    const ending = endingAt.get(at);
    if (ending !== undefined) {
      (runs.at(-1) as DraftRun).marks = ending;
      open = false;
    }
  });

  const separator = layout === "list" ? LINE_BREAK : PARAGRAPH_BREAK;
  const blocks: DraftRun[][] = [[]];
  const piece = (run: DraftRun, from: number, to: number, last: boolean): DraftRun | null => {
    const text = run.text.slice(from, to);
    const out: DraftRun = { ...run, text, start: run.start + Array.from(run.text.slice(0, from)).length };
    delete out.marks;
    if (last && run.marks !== undefined) out.marks = run.marks;
    return text === "" && out.marks === undefined ? null : out;
  };
  for (const run of runs) {
    let from = 0;
    for (const match of run.text.matchAll(separator)) {
      const out = piece(run, from, match.index, false);
      if (out !== null) blocks[blocks.length - 1].push(out);
      blocks.push([]);
      from = match.index + match[0].length;
    }
    const out = piece(run, from, run.text.length, true);
    if (out !== null) blocks[blocks.length - 1].push(out);
  }
  if (layout === "list") {
    for (const block of blocks) {
      const first = block[0];
      const marker = first === undefined ? null : ITEM_MARKER.exec(first.text);
      if (first === undefined || marker === null) continue;
      first.text = first.text.slice(marker[0].length);
      first.start += Array.from(marker[0]).length;
      if (first.text === "" && first.marks === undefined) block.shift();
    }
  }
  let markAt = 0;
  const kept = blocks.filter((block) => block.some((run) => run.text.trim() !== "" || run.marks !== undefined));
  for (const block of kept) {
    for (const run of block) {
      if (run.marks === undefined) continue;
      run.markAt = markAt;
      markAt += run.marks.length;
    }
  }
  return kept;
}

/** Drafted prose split into paragraphs (`draftBlocks` in the prose layout). */
export function draftParagraphs(
  draft: string,
  revising: readonly DraftSpan[] = [],
  claims: readonly LiveClaim[] = [],
): DraftRun[][] {
  return draftBlocks(draft, revising, claims, "prose");
}

/** The citation marker while the claim is still being checked (task 058,
 *  owner round 7): the final marker's chip in its muted look (Line border,
 *  Ground fill, grey text), a dot in place of the number. Not a control. */
export const CITATION_MARKER_PENDING_CLASS =
  "citation-marker pending-mark mx-1 border border-line bg-ground px-1.5 align-[2px] text-caption font-semibold text-grey";

/** The checked marker while the report is still live and its citations do
 *  not carry their ids (an older stream): the final marker's look, without
 *  the control's cursor and hover. */
export const CITATION_MARKER_LIVE_CLASS =
  "citation-marker mx-1 border border-blue/25 bg-blue-tint-2 px-1.5 align-[2px] text-caption font-semibold text-blue/80";

/** The writer's own citation while the section is written: the marker's chip,
 *  muted, after the cited words. Its titles are the hover text. `at` is its
 *  place in the section, which sets its turn while the claims are checked
 *  (task 058, owner round 8: the chips breathe in sequence). */
function PendingMarker({ claim, at }: { claim: LiveClaim; at: number }) {
  const titles = claim.sources.map((source) => scrub(source.title)).join("; ");
  return (
    <span
      role="img"
      aria-label={`Cited, being checked: ${titles}`}
      title={titles}
      data-testid="provisional-mark"
      className={CITATION_MARKER_PENDING_CLASS}
      style={{ "--mark-at": at } as CSSProperties}
    >
      [·]
    </span>
  );
}

/** One run's words: plain, or, in the live block, one span per reveal batch
 *  that fades in over 150 ms, opacity only (task 058, owner round 7). Pieces
 *  are keyed by where they start, so a batch fades once. */
function RunWords({ run, cuts }: { run: DraftRun; cuts?: readonly number[] }) {
  if (cuts === undefined || cuts.length === 0) return <>{scrub(run.text)}</>;
  const chars = Array.from(run.text);
  const end = run.start + chars.length;
  const bounds = [run.start, ...cuts.filter((cut) => cut > run.start && cut < end), end];
  return (
    <>
      {bounds.slice(0, -1).map((from, at) => {
        const text = scrub(chars.slice(from - run.start, bounds[at + 1] - run.start).join(""));
        return cuts.some((cut) => cut <= from) ? (
          <span key={from} className="anim-word-in">
            {text}
          </span>
        ) : (
          <Fragment key={from}>{text}</Fragment>
        );
      })}
    </>
  );
}

/** One run: under repair it blurs in place, its turn staggered by its place
 *  in the section (`heldRevising`: already blurred, on the settling layer);
 *  a repaired span's new words resolve out of the blur; the pending markers
 *  follow the words they cite. */
function DraftRunView({ run, cuts, heldRevising }: { run: DraftRun; cuts?: readonly number[]; heldRevising: boolean }) {
  const words = <RunWords run={run} cuts={cuts} />;
  const delay = heldRevising || (run.reviseAt ?? 0) === 0 ? undefined : { animationDelay: `${(run.reviseAt ?? 0) * REVISE_STAGGER_MS}ms` };
  return (
    <span>
      {run.revising ? (
        <span data-revising="true" className={heldRevising ? "draft-revised-held" : "draft-revising"} style={delay}>
          {words}
        </span>
      ) : run.settling === true ? (
        <span data-settling="true" className="draft-settle-in">
          {words}
        </span>
      ) : (
        words
      )}
      {run.marks?.map((claim, markAt) => (
        <PendingMarker key={markAt} claim={claim} at={(run.markAt ?? 0) + markAt} />
      ))}
    </span>
  );
}

/** The runs of one block, the list item's lead (before its first ": ")
 *  in bold as the report sets it. */
function DraftBlockView({
  runs,
  list,
  heldRevising,
  cuts,
}: {
  runs: DraftRun[];
  list: boolean;
  heldRevising: boolean;
  cuts?: readonly number[];
}) {
  const render = (part: DraftRun[], prefix: string) =>
    part.map((run, at) => <DraftRunView key={`${prefix}${at}`} run={run} cuts={cuts} heldRevising={heldRevising} />);
  const lead = list ? splitRunsAtLead(runs) : null;
  if (lead === null) return <>{render(runs, "u")}</>;
  return (
    <>
      <strong>
        {render(lead.lead, "l")}
        :
      </strong>
      {lead.rest.length > 0 ? <> {render(lead.rest, "r")}</> : null}
    </>
  );
}

/** A block's runs cut at its first ": ", the two characters dropped, as the
 *  committed list item bolds its lead (`splitLeadColon`); null with none. */
function splitRunsAtLead(runs: DraftRun[]): { lead: DraftRun[]; rest: DraftRun[] } | null {
  const full = runs.map((run) => run.text).join("");
  const colon = full.indexOf(": ");
  if (colon <= 0) return null;
  const lead: DraftRun[] = [];
  const rest: DraftRun[] = [];
  let offset = 0;
  for (const run of runs) {
    const from = offset;
    const to = offset + run.text.length;
    offset = to;
    if (from < colon) {
      const text = run.text.slice(0, Math.min(run.text.length, colon - from));
      const out: DraftRun = { ...run, text };
      if (to > colon) delete out.marks;
      lead.push(out);
    }
    if (to > colon + 2) {
      const cut = Math.max(0, colon + 2 - from);
      rest.push({ ...run, text: run.text.slice(cut), start: run.start + Array.from(run.text.slice(0, cut)).length });
    }
  }
  return { lead, rest };
}

/** Whether two drafted blocks render the same: their runs, the spans under
 *  repair and settling, and the citations that end in them. */
export function sameParagraph(
  previous: { runs: DraftRun[]; list?: boolean; heldRevising?: boolean },
  next: { runs: DraftRun[]; list?: boolean; heldRevising?: boolean },
): boolean {
  if (previous.list !== next.list || previous.heldRevising !== next.heldRevising) return false;
  const a = previous.runs;
  const b = next.runs;
  if (a.length !== b.length) return false;
  return a.every((run, at) => {
    const other = b[at];
    if (
      run.text !== other.text ||
      run.start !== other.start ||
      run.revising !== other.revising ||
      run.reviseAt !== other.reviseAt ||
      run.settling !== other.settling ||
      run.markAt !== other.markAt
    ) {
      return false;
    }
    const marks = run.marks ?? [];
    const otherMarks = other.marks ?? [];
    return (
      marks.length === otherMarks.length &&
      marks.every(
        (mark, markAt) =>
          mark.start === otherMarks[markAt].start &&
          mark.end === otherMarks[markAt].end &&
          mark.sources.map((source) => source.title).join("\u0000") ===
            otherMarks[markAt].sources.map((source) => source.title).join("\u0000"),
      )
    );
  });
}

/** A block the writer has moved past: frozen, so only the live tail
 *  re-renders as text is revealed (task 058, owner round 7). */
export const SettledParagraph = memo(DraftBlockView, sameParagraph);

/** Drafted text: plain text, no Markdown, laid out as the committed prose is
 *  (one paragraph element, blank lines between paragraphs; or the key
 *  findings' list), so the settle and the swap move nothing. Every block but
 *  the last is frozen; the last is the live tail. No `text-wrap: pretty` or
 *  `balance` here: the live lines must not re-break as words arrive. While
 *  the claims are checked (`checking`), the muted markers breathe in
 *  sequence (task 058, owner round 8). */
function DraftProse({
  draft,
  revising,
  claims,
  batches,
  layout = "prose",
  settling,
  heldRevising = false,
  checking = false,
  ariaHidden = false,
  className = "",
}: {
  draft: string;
  revising?: readonly DraftSpan[];
  claims?: readonly LiveClaim[];
  /** Where each recent reveal began (the live draft only): the live block
   *  fades those words in. */
  batches?: readonly number[];
  layout?: DraftLayout;
  settling?: readonly DraftSpan[];
  /** True on the settling layer: the spans under repair are already blurred. */
  heldRevising?: boolean;
  checking?: boolean;
  ariaHidden?: boolean;
  className?: string;
}) {
  const blocks = draftBlocks(draft, revising, claims, layout, settling);
  const list = layout === "list";
  const tailStart = blocks.at(-1)?.[0]?.start ?? 0;
  const cuts = (batches ?? []).filter((cut) => cut > tailStart);
  const render = (runs: DraftRun[], at: number) =>
    at < blocks.length - 1 || cuts.length === 0 ? (
      <SettledParagraph runs={runs} list={list} heldRevising={heldRevising} />
    ) : (
      <DraftBlockView runs={runs} list={list} heldRevising={heldRevising} cuts={cuts} />
    );
  const rootClass = `max-w-prose-measure ${REPORT_BODY_CLASS} ${checking ? "draft-checking" : ""} ${className}`;
  if (list) {
    return (
      <div data-testid="draft-prose" aria-hidden={ariaHidden || undefined} className={rootClass}>
        <ul className="list-none space-y-1.5">
          {blocks.map((runs, at) => (
            <li key={at} className="flex gap-2">
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 bg-blue" />
              <span>{render(runs, at)}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <div data-testid="draft-prose" aria-hidden={ariaHidden || undefined} className={rootClass}>
      <p className="whitespace-pre-line">
        {blocks.map((runs, at) => (
          <Fragment key={at}>
            {at > 0 && "\n\n"}
            {render(runs, at)}
          </Fragment>
        ))}
      </p>
    </div>
  );
}

/** The draft as it streams: paced in the browser (`useRevealedText`), its
 *  height held while a revision shortens it. */
function LiveDraft({
  draft,
  revising,
  claims,
  complete,
  layout = "prose",
  checking = false,
}: {
  draft: string;
  revising?: readonly DraftSpan[];
  claims?: readonly LiveClaim[];
  complete: boolean;
  layout?: DraftLayout;
  checking?: boolean;
}) {
  const revealed = useRevealedText(draft, complete);
  const [box, held] = useHoldHeightWhileShorter(revealed.text.length);
  return (
    <div ref={box} style={held}>
      <DraftProse
        draft={revealed.text}
        revising={revising}
        claims={claims}
        batches={revealed.batches}
        layout={layout}
        checking={checking}
      />
    </div>
  );
}

/** A section's drafted text against its checked prose, piece by piece: the
 *  stretches the two share and, for each span that was repaired, its old and
 *  new words (`at`, its place in document order). `from` is the piece's
 *  offset in the draft, in code points. */
export type SettlePiece =
  | { kind: "same"; text: string; from: number }
  | { kind: "repaired"; old: string; text: string; from: number; at: number };

/** Every place `needle` occurs in `hay` from `from`, ending by `limit`. */
function occurrences(hay: readonly string[], needle: readonly string[], from: number, limit: number): number[] {
  const found: number[] = [];
  for (let at = from; at + needle.length <= limit; at += 1) {
    if (needle.every((char, i) => hay[at + i] === char)) found.push(at);
  }
  return found;
}

/**
 * Line the draft's repaired spans up with the checked prose (task 058, owner
 * round 8: repairs of several claims settle one by one).
 *
 * The text between the spans is the same in both; each span's new words are
 * whatever the prose has between those shared stretches. A shared stretch
 * can occur more than once (two failed sentences one space apart share just
 * " "), so each is placed where the old span's last character comes just
 * before it (a sentence's full stop), nearest to where the new text's length
 * puts it. Spans that touch are joined. Null when the two do not line up, or
 * nothing was repaired: the page then settles the whole draft at once.
 */
export function settlePlan(draft: string, prose: string, revising: readonly DraftSpan[]): SettlePiece[] | null {
  const old = Array.from(draft.trimEnd());
  const next = Array.from(prose.trimEnd());
  const spans: DraftSpan[] = [];
  for (const span of [...revising].sort((a, b) => a.start - b.start)) {
    const start = Math.max(0, Math.min(span.start, old.length));
    const end = Math.max(0, Math.min(span.end, old.length));
    if (start >= end) continue;
    const last = spans.at(-1);
    if (last !== undefined && start <= last.end) last.end = Math.max(last.end, end);
    else spans.push({ start, end });
  }
  if (spans.length === 0) return null;
  const shared = [old.slice(0, spans[0].start), ...spans.map((span, at) => old.slice(span.end, spans[at + 1]?.start ?? old.length))];
  const same = (part: readonly string[], at: number) => part.every((char, i) => next[at + i] === char);
  const head = shared[0];
  const tail = shared[shared.length - 1];
  const tailAt = next.length - tail.length;
  if (!same(head, 0) || tailAt < head.length || !same(tail, tailAt)) return null;
  // How much longer the repaired stretch is than the drafted one.
  const oldMiddle = spans[spans.length - 1].end - spans[0].start;
  const ratio = (tailAt - head.length) / Math.max(1, oldMiddle);
  const pieces: SettlePiece[] = [];
  if (head.length > 0) pieces.push({ kind: "same", text: head.join(""), from: 0 });
  let cursor = head.length;
  for (let at = 0; at < spans.length; at += 1) {
    const between = shared[at + 1];
    const oldWords = old.slice(spans[at].start, spans[at].end);
    let found = tailAt;
    if (at + 1 < shared.length - 1) {
      const places = occurrences(next, between, cursor, tailAt);
      const lastChar = oldWords[oldWords.length - 1];
      const ending = places.filter((place) => place > cursor && next[place - 1] === lastChar);
      const candidates = ending.length > 0 ? ending : places;
      if (candidates.length === 0) return null;
      const expected = cursor + oldWords.length * ratio;
      found = candidates.reduce((best, place) => (Math.abs(place - expected) < Math.abs(best - expected) ? place : best));
    }
    if (found < cursor) return null;
    pieces.push({
      kind: "repaired",
      old: oldWords.join(""),
      text: next.slice(cursor, found).join(""),
      from: spans[at].start,
      at,
    });
    if (between.length > 0) pieces.push({ kind: "same", text: between.join(""), from: spans[at].end });
    cursor = found + between.length;
  }
  return pieces;
}

/**
 * The settling layer's text once `settled` repaired spans have taken their
 * new words: the spans still to settle stay blurred, the settled ones
 * resolve, and the writer's citations follow the words they cite (one that
 * ends inside a settled span follows its new words).
 */
export function settleStep(
  pieces: readonly SettlePiece[],
  settled: number,
  claims: readonly LiveClaim[] = [],
): { text: string; revising: DraftSpan[]; settling: DraftSpan[]; claims: LiveClaim[] } {
  let text = "";
  let at = 0;
  const revising: DraftSpan[] = [];
  const settling: DraftSpan[] = [];
  const placed: { piece: SettlePiece; to: number; length: number }[] = [];
  for (const piece of pieces) {
    const shown = piece.kind === "repaired" && piece.at < settled ? piece.text : piece.kind === "repaired" ? piece.old : piece.text;
    const length = Array.from(shown).length;
    if (piece.kind === "repaired") (piece.at < settled ? settling : revising).push({ start: at, end: at + length });
    placed.push({ piece, to: at, length });
    text += shown;
    at += length;
  }
  const moved: LiveClaim[] = [];
  for (const claim of claims) {
    const home = placed.find(({ piece }) => {
      const oldLength = Array.from(piece.kind === "repaired" ? piece.old : piece.text).length;
      return claim.end > piece.from && claim.end <= piece.from + oldLength;
    });
    if (home === undefined) continue;
    const settledHere = home.piece.kind === "repaired" && home.piece.at < settled;
    const end = settledHere ? home.to + home.length : home.to + (claim.end - home.piece.from);
    if (end <= 0) continue;
    moved.push({ ...claim, start: Math.max(0, Math.min(claim.start, end - 1)), end });
  }
  return { text, revising, settling, claims: moved };
}

/** The section lines the writer's ticks carry for the two slots that are
 *  not numbered sections (round 8): the key findings and the introduction. */
const SLOT_LINES: Partial<Record<string, string>> = { key_findings: "Key findings", intro: "Introduction" };

/** Whether the writer's tick names this section: its section line ends with
 *  the section's title, or is the slot's own line, or the tick has no
 *  section line at all (an older key-findings tick). */
function tickNamesSection(sectionLine: string | undefined, section: { title: string; role?: string }): boolean {
  return (
    sectionLine === undefined ||
    sectionLine.endsWith(section.title) ||
    (section.role !== undefined && SLOT_LINES[section.role] === sectionLine)
  );
}

/** A live section's role on the page, from the skeleton's own `role`, ranked
 *  as the committed report ranks it: key findings, case studies, then the
 *  body (`body` takes the committed `standard` rank). The conclusions, the
 *  code-injected last body section, keep their committed role so their rule
 *  above them is there before the swap. A stream with no roles (an old
 *  replay) knows only the key findings, by their slot. The introduction
 *  (round 8) is not a section on the page: it is the Full report part's
 *  opening paragraph, and the page takes it out of the section order. */
function liveRole(section: LiveSection): NonNullable<SectionLike["role"]> {
  if (section.role === "key_findings" || section.role === "case_studies" || section.role === "intro") return section.role;
  if (section.role === undefined && isKeyFindingsSlot(section)) return "key_findings";
  return section.title === CONCLUSIONS_SLOT_TITLE ? "conclusions" : "standard";
}

/** The checked citations of a completed section as the committed report's
 *  claims (one claim per cited span, its citations in order), so the live
 *  page renders them with the report's own prose component. */
export function liveClaims(prose: string, citations: readonly LiveCitation[] | undefined): ClaimLike[] {
  const chars = Array.from(prose);
  const bySpan = new Map<string, ClaimLike>();
  for (const citation of citations ?? []) {
    const key = `${citation.start}:${citation.end}`;
    let claim = bySpan.get(key);
    if (claim === undefined) {
      claim = {
        // The committed report's claim id when the frame carries it (round
        // 8), so the sheet can follow the claim across the swap.
        claim_id: citation.claimId ?? `live:${key}`,
        claim_type: "citation",
        text: chars.slice(citation.start, citation.end).join(""),
        span: [citation.start, citation.end],
        citations: [],
        live: true,
      };
      bySpan.set(key, claim);
    }
    claim.citations?.push({
      citation_id: citation.citationId,
      n: citation.n,
      source_title: citation.title,
      grounding_tier: citation.tier,
      source_id: citation.sourceId,
      quote: citation.quote,
    } as unknown as CitationOut);
  }
  return [...bySpan.values()];
}

/** A completed case-studies slot's prose ("**Title**\nText", cards apart by a
 *  blank line) back into its cards, each with its citations re-based onto
 *  its own text, as the committed report holds them. */
export function liveCaseStudyCards(
  prose: string,
  citations: readonly LiveCitation[] | undefined,
): CaseStudyCardLike[] {
  const chars = Array.from(prose);
  const text = chars.join("");
  const cards: CaseStudyCardLike[] = [];
  const header = /\*\*(.+?)\*\*\n/g;
  const heads = [...text.matchAll(header)];
  heads.forEach((match, at) => {
    // Offsets in code points, as the server counts them.
    const headStart = Array.from(text.slice(0, match.index)).length;
    const bodyStart = headStart + Array.from(match[0]).length;
    const next = heads[at + 1];
    const bodyEnd = next === undefined ? chars.length : Array.from(text.slice(0, next.index)).length - 2;
    const body = chars.slice(bodyStart, Math.max(bodyStart, bodyEnd)).join("");
    const own = (citations ?? [])
      .filter((citation) => citation.start >= bodyStart && citation.end <= bodyEnd)
      .map((citation) => ({ ...citation, start: citation.start - bodyStart, end: citation.end - bodyStart }));
    cards.push({ title: match[1], prose: body, claims: liveClaims(body, own) });
  });
  return cards;
}

/** The references the checked sections cite so far, numbered as the
 *  committed report numbers them; titles only. */
export function liveReferences(sections: readonly LiveSection[]): { n: number; title: string }[] {
  const byNumber = new Map<number, string>();
  for (const section of sections) {
    for (const citation of section.citations ?? []) {
      if (!byNumber.has(citation.n)) byNumber.set(citation.n, citation.title);
    }
  }
  return [...byNumber.entries()].sort(([a], [b]) => a - b).map(([n, title]) => ({ n, title }));
}

/** The lines under a live section's heading: the key findings' note, the
 *  sources the writer is drawing on, and the action line with the live mark. */
function LiveSubhead({
  section,
  active,
  activity,
  terminal,
}: {
  section: LiveSection & { role: NonNullable<SectionLike["role"]> };
  active: boolean;
  activity: string | null;
  terminal: boolean;
}) {
  const filled = section.state === "filled" && (section.prose ?? "") !== "";
  // The action line under the heading opens while the section is being
  // written and carries the run's live mark at its start (owner,
  // 2026-11-05: "◆ Looking for: …", "◆ Writing", "◆ Checking claims"). Its
  // words stay beside the mark for the whole write, "Writing" included while
  // the draft streams (lead, 2026-11-05). It collapses with its last words
  // when the section settles.
  const writing = active && !terminal;
  const showWords = writing && activity !== null;
  const actionText = useLatched(showWords ? activity : null);
  // The sources the writer has read, from the first read until the checked
  // section replaces the draft (task 058, owner 2026-11-05). Not links.
  const drawingOn = filled || terminal ? null : drawingOnLine(section.sources);
  return (
    <>
      {/* Until the key findings' own words arrive (owner, round 8). */}
      {section.role === "key_findings" && !filled && (section.draft ?? "") === "" && !terminal && (
        <p className="mt-1.5 text-body text-grey">Written last, after the sections are checked.</p>
      )}
      {drawingOn !== null && (
        <p data-testid="drawing-on" className="mt-1.5 text-meta text-grey">
          {scrub(drawingOn)}
        </p>
      )}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-[var(--ease-out-strong)] ${writing ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
      >
        <p
          data-testid="action-line"
          aria-hidden={showWords ? undefined : true}
          className="min-h-0 overflow-hidden text-body text-grey"
        >
          <span className="flex items-center gap-2 pt-1.5">
            {writing && <LiveMark data-testid="section-mark" />}
            {/* Kept as the line closes. */}
            {actionText !== null && <span className="min-w-0">{scrub(actionText)}</span>}
          </span>
        </p>
      </div>
    </>
  );
}

/** A section's body, live or committed, through one component so the
 *  committed report updates the live section in place (owner, round 7).
 *
 *  Live: placeholder lines, then the draft, then the checked prose through
 *  the report's own prose component with its numbered markers, which open
 *  the provenance sheet once their citations carry their ids (round 8).
 *  When the section completes, a settling layer carries the draft into the
 *  checked prose: each repaired span takes its new words in document order,
 *  120 ms apart, resolving out of the blur, while the section's height eases
 *  to fit (round 8); then the layer, pending markers and all, fades off the
 *  checked prose, so the markers arrive without a flash. Under reduced
 *  motion the checked prose replaces the draft at a cut. Committed: the
 *  report's blocks, with their markers live. */
function SectionBody({
  section,
  blocks,
  onOpenClaim,
  terminal = false,
  reduceMotion = false,
  checking = false,
}: {
  /** The live section, while the report is written. */
  section?: LiveSection;
  /** The committed report's blocks, once it has landed. */
  blocks?: BlockLike[];
  onOpenClaim?: (claim: ClaimLike) => void;
  terminal?: boolean;
  reduceMotion?: boolean;
  /** The writer is checking this section's claims ("Checking claims"). */
  checking?: boolean;
}) {
  const state = section?.state ?? "filled";
  const draft = section?.draft ?? "";
  const prose = section?.prose ?? "";
  const filled = state === "filled" && prose !== "";
  // The key findings' list, when the writer writes one ("- " lines), as the
  // committed report sets it; plain prose otherwise.
  const layoutOf = (text: string): DraftLayout =>
    section?.role === "key_findings" && ITEM_MARKER.test(text) ? "list" : "prose";
  // Kept in state from the render that saw the change, so the settled prose
  // never shows a frame without the draft layer over it.
  const [seen, setSeen] = useState({
    state,
    draft,
    revising: section?.revising,
    claims: section?.claims,
    streamed: draft !== "",
  });
  const [ghost, setGhost] = useState<{
    draft: string;
    revising?: LiveSection["revising"];
    claims?: LiveSection["claims"];
    plan: SettlePiece[] | null;
  } | null>(null);
  // How many repaired spans have taken their new words, and whether the
  // layer has begun to fade off the checked prose.
  const [settled, setSettled] = useState(0);
  const [fading, setFading] = useState(false);
  if (
    section !== undefined &&
    (seen.state !== state || seen.draft !== draft || seen.revising !== section.revising || seen.claims !== section.claims)
  ) {
    if (state === "filled" && seen.state !== "filled" && seen.draft !== "" && !reduceMotion) {
      const plan = settlePlan(seen.draft, prose, seen.revising ?? []);
      setGhost({ draft: seen.draft, revising: seen.revising, claims: seen.claims, plan });
      setSettled(0);
      setFading(plan === null);
    }
    setSeen({
      state,
      draft,
      revising: section.revising,
      claims: section.claims,
      streamed: seen.streamed || draft !== "",
    });
  }
  useEffect(() => {
    if (ghost === null) return undefined;
    const repaired = ghost.plan?.filter((piece) => piece.kind === "repaired").length ?? 0;
    const timers: number[] = [];
    for (let at = 0; at < repaired; at += 1) {
      timers.push(window.setTimeout(() => setSettled(at + 1), at * REVISE_STAGGER_MS));
    }
    const fadeAt = repaired === 0 ? 0 : (repaired - 1) * REVISE_STAGGER_MS + SETTLE_IN_MS;
    if (repaired > 0) timers.push(window.setTimeout(() => setFading(true), fadeAt));
    timers.push(window.setTimeout(() => setGhost(null), fadeAt + SETTLE_MS));
    return () => {
      for (const timer of timers) window.clearTimeout(timer);
    };
  }, [ghost]);
  const citations = section?.citations;
  const liveBlocks = useMemo(
    () => [{ block_id: "live", prose, claims: liveClaims(prose, citations) }],
    [prose, citations],
  );

  if (blocks !== undefined || filled) {
    const step =
      ghost === null
        ? null
        : ghost.plan === null
          ? { text: ghost.draft, revising: ghost.revising ?? [], settling: [], claims: ghost.claims ?? [] }
          : settleStep(ghost.plan, settled, ghost.claims);
    const sequencing = ghost !== null && !fading;
    return (
      <SectionProse
        blocks={blocks ?? liveBlocks}
        live={blocks === undefined}
        onOpenClaim={onOpenClaim}
        className={blocks === undefined && !seen.streamed ? "anim-rise" : ""}
        hideBlocks={sequencing}
        easeHeight={blocks === undefined && !reduceMotion}
      >
        {step !== null && (
          <DraftProse
            draft={step.text}
            revising={step.revising}
            settling={step.settling}
            claims={step.claims}
            layout={layoutOf(ghost?.draft ?? "")}
            heldRevising
            ariaHidden
            className={sequencing ? "" : "anim-settle-out pointer-events-none absolute inset-0 bg-paper"}
          />
        )}
      </SectionProse>
    );
  }
  if (terminal && draft === "") {
    return (
      <p className="text-body italic text-grey">
        {section?.focus ? scrub(section.focus) : "Waiting to be written."}
      </p>
    );
  }
  return (
    <DraftAfterPlaceholder index={section?.index ?? 0} reduceMotion={reduceMotion}>
      {draft !== "" ? (
        <LiveDraft
          draft={draft}
          revising={section?.revising}
          claims={section?.claims}
          complete={terminal}
          layout={layoutOf(draft)}
          checking={checking}
        />
      ) : null}
    </DraftAfterPlaceholder>
  );
}

/**
 * A section's placeholder lines, then its streamed draft in the same box
 * (task 058, round 9; the animation sweep's entry 8): when the first words
 * arrive the box keeps the placeholder's height until the text is taller,
 * so the page below never shrinks and regrows, and the lines fade out over
 * the first words in 150 ms. Under reduced motion the height still holds
 * (it is layout, not motion) and the lines go at once.
 */
function DraftAfterPlaceholder({
  index,
  reduceMotion,
  children,
}: {
  index: number;
  reduceMotion: boolean;
  /** The live draft, or null before the first words. */
  children: ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const placeholderHeight = useRef(0);
  const hasDraft = children !== null;
  const [shown, setShown] = useState(hasDraft);
  const [fading, setFading] = useState(false);
  if (shown !== hasDraft) {
    setShown(hasDraft);
    setFading(hasDraft && !reduceMotion);
  }
  useEffect(() => {
    if (!fading) return undefined;
    const id = window.setTimeout(() => setFading(false), 160);
    return () => window.clearTimeout(id);
  }, [fading]);
  useLayoutEffect(() => {
    const outer = box.current;
    const inner = content.current;
    if (outer === null || inner === null) return undefined;
    if (!hasDraft) {
      placeholderHeight.current = inner.offsetHeight;
      outer.style.minHeight = "";
      return undefined;
    }
    const hold = placeholderHeight.current;
    if (hold <= 0 || inner.offsetHeight >= hold || typeof ResizeObserver === "undefined") return undefined;
    outer.style.minHeight = `${hold}px`;
    const observer = new ResizeObserver(() => {
      if (inner.offsetHeight < hold) return;
      outer.style.minHeight = "";
      observer.disconnect();
    });
    observer.observe(inner);
    return () => observer.disconnect();
  }, [hasDraft]);
  return (
    <div ref={box} className="relative">
      <div ref={content}>{children ?? <PlaceholderLines index={index} still={reduceMotion} />}</div>
      {fading && (
        <PlaceholderLines index={index} still leaving className="anim-fade-out pointer-events-none absolute inset-x-0 top-0 bg-paper" />
      )}
    </div>
  );
}

/** The code-injected last section's title (`synthesise.py`). */
const CONCLUSIONS_SLOT_TITLE = "Conclusions";

/** A section's prose as the report sets it, block after block; the live
 *  page's settling layer rides in the same box. Blocks are keyed by
 *  position, so the committed report's blocks update the live ones in place.
 *  While the settling layer carries the repairs (`hideBlocks`) it sits in
 *  the flow and the checked prose waits under it, unseen; the box eases to
 *  each new height over 300 ms (`easeHeight`, the live page only). */
function SectionProse({
  blocks,
  live = false,
  onOpenClaim = () => undefined,
  className = "",
  hideBlocks = false,
  easeHeight = false,
  children,
}: {
  blocks: BlockLike[];
  live?: boolean;
  onOpenClaim?: (claim: ClaimLike) => void;
  className?: string;
  hideBlocks?: boolean;
  easeHeight?: boolean;
  children?: ReactNode;
}) {
  const [box, content] = useEasedHeight(easeHeight);
  return (
    <div ref={box} className={className}>
      <div ref={content} className="relative">
        <div className={hideBlocks ? "pointer-events-none absolute inset-x-0 top-0 space-y-4 opacity-0" : "space-y-4"}>
          {blocks.map((block, at) => (
            <AnnotatedProse key={at} block={block} onOpenClaim={onOpenClaim} live={live} />
          ))}
        </div>
        {children}
      </div>
    </div>
  );
}

/** Whether the page is arriving from the live view: controls that come with
 *  the committed report fade in once (300 ms, the strong ease-out) instead of
 *  appearing at a cut, and a marker whose number changed fades its new
 *  number in. Off on an ordinary load and under reduced motion. */
type ReportSwap = {
  arriving: boolean;
  /** The live markers' numbers by span and words, from the last live page. */
  liveNumbers: ReadonlyMap<string, string>;
};
const ReportSwapContext = createContext<ReportSwap>({ arriving: false, liveNumbers: new Map() });

/** The class for an element that arrives with the committed report. */
function useArrivingClass(): string {
  return useContext(ReportSwapContext).arriving ? "anim-swap-in" : "";
}

/** A claim's identity across the swap: its span and its words. */
function markerKey(span: number[] | null | undefined, text: string): string {
  return `${span?.[0] ?? ""}:${span?.[1] ?? ""}:${text}`;
}

/** The page's anchored blocks: sections, the part headings, references. */
const PLACE_SELECTOR = "main.artefact-page section[id], main.artefact-page #full-report, main.artefact-page #executive-summary";

/** The first anchored block still showing at the top of the scrolling pane,
 *  and how far its top sits from the pane's top. */
function readingPlace(): { id: string; top: number } | null {
  const main = document.querySelector<HTMLElement>("main.artefact-page");
  if (main === null) return null;
  const paneTop = scrollPane(main).getBoundingClientRect().top;
  for (const block of document.querySelectorAll<HTMLElement>(PLACE_SELECTOR)) {
    const rect = block.getBoundingClientRect();
    if (rect.bottom > paneTop) return { id: block.id, top: rect.top - paneTop };
  }
  return null;
}

/**
 * Keep the reader's place when the committed report takes the live page
 * (owner, round 7: the scroll position stays). While live, the block at the
 * top of the pane and its offset are noted on every render and scroll; when
 * the committed report lands, before paint, the pane is moved by however far
 * that block moved, so what grew above the reader (the facts strip, the
 * most relevant sources) does not push the text down.
 */
function useKeepReadingPlace(live: boolean, swapped: boolean): void {
  const place = useRef<{ id: string; top: number } | null>(null);
  useLayoutEffect(() => {
    if (live) place.current = readingPlace();
  });
  useEffect(() => {
    const main = document.querySelector<HTMLElement>("main.artefact-page");
    if (!live || main === null) return undefined;
    const pane = scrollPane(main);
    const target: HTMLElement | Window = pane === document.scrollingElement ? window : pane;
    const note = () => {
      place.current = readingPlace();
    };
    target.addEventListener("scroll", note, { passive: true });
    return () => target.removeEventListener("scroll", note);
  }, [live]);
  useLayoutEffect(() => {
    const before = place.current;
    if (!swapped || before === null) return;
    place.current = null;
    const block = document.getElementById(before.id);
    const main = document.querySelector<HTMLElement>("main.artefact-page");
    if (block === null || main === null) return;
    const pane = scrollPane(main);
    const moved = block.getBoundingClientRect().top - pane.getBoundingClientRect().top - before.top;
    if (Math.abs(moved) >= 1) pane.scrollTop += moved;
  }, [swapped]);
}

/** Each checked live marker's numbers, by its span and words, so a marker
 *  the committed report renumbers can fade its new number in. */
function liveMarkerNumbers(stream: RunStreamState): ReadonlyMap<string, string> {
  const numbers = new Map<string, string>();
  for (const section of Object.values(stream.liveSections)) {
    for (const claim of liveClaims(section.prose ?? "", section.citations)) {
      const ns = [...new Set((claim.citations ?? []).map((citation) => citation.n))].join(",");
      numbers.set(markerKey(claim.span, claim.text), ns);
    }
  }
  return numbers;
}

type RoledLiveSection = LiveSection & { role: NonNullable<SectionLike["role"]> };

/** The live sections in the committed report's order, with their roles, and
 *  the introduction apart (round 8: it opens the Full report part, it is not
 *  a section, so it takes no place in the order). */
function orderedLiveSections(stream: RunStreamState): { sections: RoledLiveSection[]; intro: RoledLiveSection | undefined } {
  const all = Object.values(stream.liveSections)
    .filter((section) => !(section.state === "filled" && (section.prose ?? "") === ""))
    .sort((a, b) => a.index - b.index)
    .map((section) => ({ ...section, role: liveRole(section) }));
  return {
    sections: orderSections(all.filter((section) => section.role !== "intro")),
    intro: all.find((section) => section.role === "intro"),
  };
}

/** The source notes as the committed report's most relevant sources, before
 *  it knows their counts and chips. */
function liveTopSources(notes: readonly LiveSourceNote[]): TopSource[] {
  return notes.map((note) => ({
    sourceId: note.sourceId,
    title: note.title,
    note: note.note,
    citationCount: 0,
    appraisalLabel: null,
    evidenceType: null,
    citedInSections: [],
  }));
}

/** What the reader's open claim and its sheet need from the page. */
type LiveClaimSheet = {
  /** Opens the provenance sheet on a checked claim. */
  onOpenClaim: (claim: ClaimLike) => void;
  /** The sheet itself, keyed "claim-panel" as the committed report keys
   *  it, so an open sheet stays open across the swap. */
  panel: ReactNode;
};

/**
 * The report while it is being written (task 058, N8; annex scene 6; owner
 * round 7: the live page looks like the final page).
 *
 * The same page as the committed report: the kind row, the question as the
 * title, "See the plan", the part headings, the sections in the report's
 * order through the report's own section and prose components, the
 * case-study cards in the report's card layout as they close, the most
 * relevant sources as each note is written, the Full report's opening
 * paragraph as it is written, and a references list that grows as sections
 * are checked. Every proposed section shows placeholder lines until its
 * prose arrives; the section being written carries the live mark and the
 * writer's action line under its heading, then its draft as plain text (the
 * key findings as their list) with a muted marker after each cited sentence,
 * the markers breathing in turn while the claims are checked. On completion
 * the draft settles into the checked prose with its numbered markers, whose
 * hover and sheet work once their citations carry their ids (round 8). What
 * only the committed report has (links into provenance, the download, the
 * facts strip, the method, the chips) is absent, with no placeholder.
 *
 * Returns the page's contents entries and its children, for the
 * committed report to render through the same `ReportPage` element, so
 * React updates the page in place at the swap.
 */
function useLiveReport(
  stream: RunStreamState,
  question: string | null | undefined,
  onSeePlan: (() => void) | undefined,
  sheet?: LiveClaimSheet,
): { entries: SidebarEntry[]; children: ReactNode } {
  const reduceMotion = usePrefersReducedMotion();
  const { sections, intro } = orderedLiveSections(stream);
  const terminalPartial = hasTerminalPartialLiveArtefact(stream);
  const finished = stream.run?.status === "succeeded" || stream.run?.status === "degraded";
  const terminal = terminalPartial || finished;
  const writer = stream.liveness["synthesise"];
  const active = terminal
    ? undefined
    : (sections.find((section) => section.state === "writing") ?? (intro?.state === "writing" ? intro : undefined));
  const activity =
    active !== undefined && writer !== undefined && tickNamesSection(writer.section, active)
      ? writer.activity
      : null;
  // The judge checks a section in one call: the page cannot know which claim
  // it is on, so the chips breathe in turn and nothing else moves (round 8).
  const checking = activity === CHECKING_CLAIMS;
  // A run with no key findings slot is a baseline: one linear profile, no
  // summary and full-report parts (as the committed baseline renders).
  const report = sections.some((section) => section.role === "key_findings");
  const anchored = sections.map((section, at) => ({ section, id: sectionAnchor(section.title, at) }));
  const firstBody = anchored.findIndex(
    ({ section }) => section.role !== "key_findings" && section.role !== "case_studies",
  );
  const front = firstBody === -1 ? anchored : anchored.slice(0, firstBody);
  const body = firstBody === -1 ? [] : anchored.slice(firstBody);
  const references = liveReferences(sections);
  const notes = report ? liveSourceNotes(stream) : [];
  const onOpenClaim = sheet?.onOpenClaim;

  const entries: SidebarEntry[] = [
    ...(report ? [{ kind: "part" as const, id: EXECUTIVE_SUMMARY_ANCHOR, title: "Executive summary" }] : []),
    ...front.map(({ section, id }) => ({ id, title: sectionNavLabel({ title: section.title }, 28) })),
    ...(notes.length > 0 ? [{ id: "sources", title: "Most relevant sources" }] : []),
    ...(report && body.length > 0 ? [{ kind: "part" as const, id: FULL_REPORT_ANCHOR, title: "Full report" }] : []),
    ...body.map(({ section, id }) => ({ id, title: sectionNavLabel({ title: section.title }, 28) })),
    ...(references.length > 0 ? [{ id: "references", title: "References" }] : []),
  ];

  const renderSection = ({ section, id }: (typeof anchored)[number]) => {
    const isActive = section === active;
    const subhead = (
      <LiveSubhead section={section} active={isActive} activity={isActive ? activity : null} terminal={terminal} />
    );
    if (section.role === "case_studies") {
      const cards =
        section.state === "filled" ? liveCaseStudyCards(section.prose ?? "", section.citations) : (section.cards ?? []);
      return (
        <CaseStudiesSection
          key={`section:${id}`}
          section={{ title: section.title, role: "case_studies", cards }}
          id={id}
          live
          onOpenClaim={onOpenClaim}
          busy={isActive}
          subhead={subhead}
          pending={
            cards.length === 0 ? (
              terminal ? null : (
                <PlaceholderLines index={section.index} still={reduceMotion} className="mt-3" />
              )
            ) : null
          }
        />
      );
    }
    return (
      <SectionDisclosure
        key={`section:${id}`}
        id={id}
        section={{ title: section.title, role: section.role === "intro" ? "standard" : section.role }}
        collapsible={false}
        defaultOpen
        busy={isActive}
        subhead={subhead}
      >
        <SectionBody
          section={section}
          terminal={terminal}
          reduceMotion={reduceMotion}
          onOpenClaim={onOpenClaim}
          checking={isActive && checking}
        />
      </SectionDisclosure>
    );
  };

  // The Full report's opening paragraph where the committed report sets it,
  // paced as the sections are; no heading or "Drawing on" line of its own
  // (round 8). Nothing shows before it is begun.
  const introProse = intro?.state === "filled" ? (intro.prose ?? "").trim() : "";
  const introDraft = intro?.draft ?? "";
  const introBegun = intro !== undefined && !terminal && (intro.state === "writing" || introDraft !== "");

  const children = [
    <div key="notice">
      {terminalPartial && (
        <div
          role="alert"
          className="mb-8 border-l-[3px] border-l-red bg-red-tint px-3.5 py-2.5 text-body text-navy"
        >
          <p className="font-bold">This run ended before the write-up completed.</p>
          <p className="mt-0.5">
            The sections below are drafted text from the interrupted run — not the checked
            report. Citations were never attached. Start a fresh run to produce the full
            artefact.
          </p>
        </div>
      )}
    </div>,
    <header key="header" id="answer" className="mb-8">
      <ReportKindRow kind={report ? "Report" : "Baseline"} />
      {question != null && question !== "" && <h1 className={REPORT_TITLE_CLASS}>{scrub(question)}</h1>}
      {onSeePlan !== undefined && <SeePlanLink onClick={onSeePlan} />}
      <p role="status" aria-live="polite" className="sr-only">
        {active !== undefined ? `${scrub(active.title)} is being written` : ""}
      </p>
    </header>,
    report ? (
      <h2 key="executive-summary" id={EXECUTIVE_SUMMARY_ANCHOR} className={`mb-6 ${REPORT_PART_HEADING_CLASS}`}>
        Executive summary
      </h2>
    ) : null,
    ...front.map(renderSection),
    <div key="most-relevant">{notes.length > 0 && <MostRelevantSources live sources={liveTopSources(notes)} />}</div>,
    <FullReportExpandProvider key="full-report">
      {report && body.length > 0 && (
        <div id={FULL_REPORT_ANCHOR} className="mb-6 mt-10 border-t border-line pt-4">
          <div key="head" className="flex items-baseline gap-2">
            <h2 className={`flex-1 ${REPORT_PART_HEADING_CLASS}`}>Full report</h2>
          </div>
          {intro !== undefined && introProse === "" && (
            <LiveSubhead
              key="subhead"
              section={intro}
              active={intro === active}
              activity={intro === active ? activity : null}
              terminal={terminal}
            />
          )}
          {introProse !== "" ? (
            <p key="intro" className={`mt-1.5 max-w-prose-measure ${REPORT_BODY_CLASS}`}>
              {scrub(introProse)}
            </p>
          ) : introBegun ? (
            <div key="intro-draft" data-testid="intro-draft" className="mt-1.5">
              {introDraft !== "" ? (
                <LiveDraft draft={introDraft} complete={terminal} />
              ) : (
                <PlaceholderLines index={intro.index} still={reduceMotion} />
              )}
            </div>
          ) : null}
        </div>
      )}
      {body.map(renderSection)}
      {references.length > 0 && <ReferencesSection references={references} defaultOpen />}
    </FullReportExpandProvider>,
    sheet?.panel ?? null,
    <TailFollower key="tail" active={active !== undefined} />,
  ];
  return { entries, children };
}

/** The writer's activity line while the judge checks a section's claims
 *  (`stage_vocabulary.py`, `synthesise.checking`). */
const CHECKING_CLAIMS = "Checking claims";

/** Keeps a reader who is at the end of the page at the end while text
 *  streams; never moves anyone else (`useFollowTail`). */
function TailFollower({ active }: { active: boolean }) {
  const anchor = useRef<HTMLSpanElement>(null);
  useFollowTail(anchor, active);
  return <span ref={anchor} aria-hidden="true" className="block h-0" />;
}

/**
 * The report while it is being written, on its own (the Result tab renders
 * the same page through `ArtefactReport`, so the swap to the committed
 * report happens in place).
 *
 * Args:
 *   stream: The live run stream.
 *   question: The task's question, the page title.
 *   onSeePlan: Opens the plan document.
 *   taskId: The task, for the provenance sheet's source passages.
 */
export function LiveArtefactBody({
  stream,
  question,
  onSeePlan,
  taskId = "",
}: {
  stream: RunStreamState;
  question?: string | null;
  onSeePlan?: () => void;
  taskId?: string;
}) {
  const [claim, setClaim] = useState<ClaimLike | null>(null);
  const live = useLiveReport(stream, question, onSeePlan, {
    onOpenClaim: setClaim,
    panel: <ClaimPanel key="claim-panel" taskId={taskId} claim={claim} onClose={() => setClaim(null)} onOpenDossier={() => undefined} />,
  });
  return <ReportPage entries={live.entries}>{live.children}</ReportPage>;
}

/**
 * The Result tab before writing (task 058, N11; annex scene 5): the report
 * to be, titled with the question, and one sentence. The run trace in the
 * Task Agent says where the run is.
 */
export function ReportToBe({
  question,
  ended = false,
  onSeePlan,
}: {
  question: string | null | undefined;
  /** The run ended before any section was proposed (failed, aborted, interrupted). */
  ended?: boolean;
  /** Opens the plan document (owner, polish round 2: a small link on the Result tab). */
  onSeePlan?: () => void;
}) {
  return (
    <ReportPage>
      {question != null && question !== "" && <h1 className={REPORT_TITLE_CLASS}>{scrub(question)}</h1>}
      <p className="mt-4 text-body text-grey">
        {ended ? "This run ended before writing began." : "The report's sections are set out when writing begins."}
      </p>
      {onSeePlan !== undefined && <SeePlanLink onClick={onSeePlan} />}
    </ReportPage>
  );
}

/** The Result tab's small link to the plan document. */
function SeePlanLink({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={cn(QUIET_CONTROL_CLASS, "mt-2 text-meta")}>
      See the plan
    </button>
  );
}

/** "3 November", with the year only when it is not this year. */
export function reportDateLabel(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
  });
}

/** Whole minutes since `iso`, never below one. */
export function minutesSince(iso: string, nowMs: number): number {
  return Math.max(0, Math.floor((nowMs - new Date(iso).getTime()) / 60_000));
}

/**
 * The one plain line above an existing report while a new run is under way
 * (task 058, N11; annex scene 8). No button: the sidebar rail and the Agent
 * tab are the routes to the run, whose trace carries the stage.
 */
export function RerunNotice({
  taskId,
  artefactId,
  runStartedAt,
}: {
  taskId: string;
  artefactId: string;
  runStartedAt: string;
}) {
  const runs = useRuns(taskId, { page_size: 50, parentless: true });
  const nowMs = useNow(true, 30_000);
  const madeBy = (runs.data?.data ?? []).find((run) => run.artefact_id === artefactId);
  if (madeBy?.ended_at == null) return null;
  return (
    <p data-testid="rerun-notice" className="mb-6 border-b border-line pb-4 text-body text-grey">
      This report is from {reportDateLabel(madeBy.ended_at)}. A new run started{" "}
      {minutesSince(runStartedAt, nowMs) < 1 ? "just now" : `${minutesSince(runStartedAt, nowMs)} min ago`}.
    </p>
  );
}

/**
 * The handful of sources the report leans on most.
 *
 * Every line is a fact the data already asserts — how often it is cited, its
 * appraisal tier, its evidence type, which sections use it. It never says why
 * a study matters: that is a judgement nobody made, and asserting it would be
 * the report inventing authority for itself.
 */

function CaseStudyCardProse({
  card,
  onOpenClaim,
  live = false,
}: {
  card: CaseStudyCardLike;
  onOpenClaim: (claim: ClaimLike) => void;
  live?: boolean;
}) {
  const claims = card.claims ?? [];
  // One paragraph element either way, so a card that gains its markers at
  // the swap updates in place.
  const segments: SpanSegment<ClaimLike>[] =
    claims.length === 0 ? [{ kind: "plain", text: card.prose }] : spanSegments(card.prose, claims);

  return (
    <p className={`mt-1 max-w-prose-measure whitespace-pre-line ${REPORT_BODY_CLASS}`}>
      {segments.map((segment, index) => {
        if (segment.kind === "plain") return <span key={index}>{scrub(segment.text)}</span>;
        const isResult = card.result_claim_id != null && segment.claim.claim_id === card.result_claim_id;
        const span = <ClaimSpan claim={segment.claim} text={segment.text} onOpen={onOpenClaim} live={live} />;
        return <span key={index}>{isResult ? <strong>{span}</strong> : span}</span>;
      })}
    </p>
  );
}

/**
 * The case studies: heading, the one-line intro and a card per example.
 *
 * The report while it is written renders the same section (task 058, owner
 * round 7): its cards arrive one by one as each closes in the writer's
 * reply, in the report's card layout, with no evidence chips until the
 * committed report brings them.
 */
function CaseStudiesSection({
  section,
  id,
  onOpenClaim = () => undefined,
  live = false,
  busy = false,
  subhead,
  pending,
}: {
  section: SectionLike;
  id: string;
  onOpenClaim?: (claim: ClaimLike) => void;
  live?: boolean;
  busy?: boolean;
  /** The live page's lines under the heading. */
  subhead?: ReactNode;
  /** What stands in for the cards before the first one closes (live only). */
  pending?: ReactNode;
}) {
  useScrollWhenNavigated(id);
  const arriving = useArrivingClass();
  const cards = section.cards ?? [];
  if (cards.length === 0 && !live) return null;
  return (
    <section id={id} aria-busy={busy ? true : undefined} className="mb-9">
      <h2 className={REPORT_SECTION_HEADING_CLASS}>{scrub(section.title)}</h2>
      {subhead}
      <p className={`mt-1.5 max-w-prose-measure ${REPORT_BODY_CLASS}`}>{CASE_STUDIES_INTRO}</p>
      {cards.length === 0 ? (
        pending
      ) : (
        <ul role="list" className="mt-3 grid gap-3">
          {cards.map((card, at) => {
            const { strength, design, sinceYear } = cardEvidenceMeta(card);
            return (
              <li key={`${at}:${card.title}`} className={`border border-line p-4 ${live ? "anim-rise" : ""}`}>
                <p className={`${REPORT_BODY_CLASS} font-bold`}>{scrub(card.title)}</p>
                <CaseStudyCardProse card={card} onOpenClaim={onOpenClaim} live={live} />
                {/* Empty while live; the chips fade in with the committed report. */}
                <div className={`mt-2 flex flex-wrap gap-1.5 ${arriving}`}>
                  {strength != null && (
                    <AppraisalChip label={strength} evidenceType={design} />
                  )}
                  {design != null && <Chip tone="soft">{scrub(design)}</Chip>}
                  {sinceYear != null && <Chip tone="soft">Since {sinceYear}</Chip>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/**
 * The most relevant sources. While the report is written (task 058, owner
 * round 8) the block appears with the first source note, in the final
 * layout, each note rising in as it lands: titles not yet links, no authors
 * or chips. The committed report takes the block over in place; what it adds
 * (the authors, the chips) arrives with `arrivingClass`.
 */
function MostRelevantSources({
  sources,
  onOpenDossier,
  live = false,
  arrivingClass = "",
}: {
  sources: TopSource[];
  /* Opens by source id: the citation-time title snapshot can drift from the
   * evidence row's title in deployed data, so a title-keyed lookup misses. */
  onOpenDossier?: (sourceId: string) => void;
  live?: boolean;
  arrivingClass?: string;
}) {
  useScrollWhenNavigated("sources");
  if (sources.length === 0) return null;
  return (
    <section id="sources" className="mb-9">
      <h2 className={REPORT_SECTION_HEADING_CLASS}>Most relevant sources</h2>
      <p className={`mt-1.5 max-w-prose-measure ${REPORT_BODY_CLASS}`}>{MOST_RELEVANT_SOURCES_INTRO}</p>
      <ul role="list" className="mt-3 grid gap-3">
        {sources.map((source) => (
          <li key={source.sourceId} className={`border border-line p-4 ${live ? "anim-rise" : ""}`}>
            {live || onOpenDossier === undefined ? (
              <p className={`${REPORT_BODY_CLASS} font-bold`}>{scrub(source.title)}</p>
            ) : (
              <button
                type="button"
                onClick={() => onOpenDossier(source.sourceId)}
                className={`cursor-pointer text-left ${REPORT_BODY_CLASS} font-bold hover:underline`}
              >
                {scrub(source.title)}
              </button>
            )}
            {source.authors != null && source.authors.length > 0 && (
              <p className={`mt-0.5 ${REPORT_BODY_CLASS} ${arrivingClass}`}>
                {source.authors.map((a) => scrub(a)).join(", ")}
              </p>
            )}
            {source.note != null && source.note !== "" && (
              <p className={`mt-1 max-w-prose-measure ${REPORT_BODY_CLASS}`}>{scrub(source.note)}</p>
            )}
            {!live && (
              <div className={`mt-2 flex flex-wrap gap-1.5 ${arrivingClass}`}>
                {source.appraisalLabel != null && (
                  <AppraisalChip label={source.appraisalLabel} evidenceType={source.evidenceType} />
                )}
                {source.evidenceType != null && <Chip tone="soft">{scrub(source.evidenceType)}</Chip>}
                <Chip tone="soft">
                  {source.citationCount === 1 ? "Cited by 1 claim" : `Cited by ${source.citationCount} claims`}
                </Chip>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * The Result tab. An Evidence search's report, or a scoping task's baseline,
 * renders as it always has; once a scoping task has a longlist the Result
 * gains the view switch — **Baseline · Longlist · Report** — and opens on
 * the longlist (task 045, deliverable 9; ruling 50). The chosen view rides
 * `?view=` so a link or a refresh keeps it. The public view never switches:
 * a link grants no read of options.
 */
export function ArtefactView() {
  const { taskId = "" } = useParams();
  const isPublicView = usePublicView();
  const task = useTask(taskId);
  const stream = useRunStream(taskId);
  // While a longlist walk runs the Result is the longlist being built
  // (task 058, N24), before and after the longlist read first answers.
  const building = !isPublicView && isLonglistBuilding(task.data, stream.stages);
  if (isPublicView || (!hasLonglist(task.data) && !building)) return <ArtefactReport />;
  return <ScopingResult taskId={taskId} building={building} />;
}

/** A scoping task's Result once its longlist exists or is being built: the
 *  switch, then the chosen view. */
function ScopingResult({ taskId, building }: { taskId: string; building: boolean }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const longlist = useLonglist(taskId);
  const view = resultView(searchParams.get("view"));
  const select = (next: string) => {
    setSearchParams((current) => {
      const params = new URLSearchParams(current);
      // The longlist is the default; the baseline and the shortlist need spelling out.
      if (next === "baseline" || next === "shortlist") params.set("view", next);
      else params.delete("view");
      return params;
    });
  };
  return (
    <>
      <Tabs value={view} onValueChange={select} className="mx-auto w-full max-w-5xl px-6 pt-6 max-md:px-4">
        <TabsList aria-label="Result view">
          {RESULT_VIEWS.map((option) => (
            <TabsTrigger
              key={option.key}
              value={option.key}
              disabled={option.note !== undefined}
              title={option.note}
              className="disabled:cursor-default disabled:text-grey/70"
            >
              {option.label}
              {option.note !== undefined && (
                <span className="ml-1.5 font-normal">· {option.note}</span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {view === "baseline" ? (
        <ArtefactReport />
      ) : building && (view === "longlist" || longlist.data == null) ? (
        <LonglistBuilding taskId={taskId} />
      ) : longlist.data != null ? (
        view === "shortlist" ? (
          <ShortlistView taskId={taskId} longlist={longlist.data} />
        ) : (
          <LonglistView taskId={taskId} longlist={longlist.data} />
        )
      ) : longlist.isPending ? (
        <main aria-busy="true" aria-label="Loading the longlist" className={`${LIFECYCLE_PAGE_CLASS} py-8`}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="mb-4 h-16 anim-breathe border border-line bg-paper-2" />
          ))}
        </main>
      ) : (
        // The task says a longlist exists but the read found none (a stale
        // read model, or a failed fetch): the baseline is still there.
        <ArtefactReport />
      )}
    </>
  );
}

/** The committed report's claim with this id, in a block or a card. */
function committedClaim(sections: readonly SectionLike[] | undefined, claimId: string): ClaimLike | null {
  for (const section of sections ?? []) {
    for (const holder of [...(section.blocks ?? []), ...(section.cards ?? [])]) {
      const found = (holder.claims ?? []).find((claim) => claim.claim_id === claimId);
      if (found !== undefined) return found;
    }
  }
  return null;
}

/** The evidence base: A4 page frame, coverage snapshot, key-findings-first
 *  ordering, typed annotated prose, citation ladder, shared dossier
 *  (?source=… — deep-linkable, refresh-safe), and the live streaming state
 *  while synthesis writes. */
function ArtefactReport() {
  const { taskId = "" } = useParams();
  const isPublicView = usePublicView();
  const planPanel = usePlanPanel();
  const task = useTask(taskId);
  const artefact = useArtefact(taskId);
  // The public view (task 037) must issue only public-surface requests:
  // conversations stay unfetched and the chat affordance below is hidden.
  const chats = useConversations(
    taskId,
    { kind: "chat", status: "active" },
    { enabled: !isPublicView },
  );
  // Cited-scoped distributions for the facts strip: study types and years
  // count what the report CITES, not the whole included corpus (owner,
  // 2026-08-05); the durable coverage_snapshot keeps the corpus-wide counts.
  const citedLandscape = useLandscape(taskId, "cited");
  const stream = useRunStream(taskId);
  const [searchParams, setSearchParams] = useSearchParams();
  const dossierSource = searchParams.get("source");
  const dossierOption = searchParams.get("option");
  const [detailClaim, setDetailClaim] = useState<ClaimLike | null>(null);
  // Task 044 (deliverable 9): an options-scoping task's Result is the
  // baseline, not a report. It is headed "Baseline" and nothing else; the
  // walk's state lives on the plan document (owner ruling 2026-09-18 — the
  // band under the title came off).
  const baseline = isBaselineArtefact(artefact.data);
  useDocumentTitle(task.data?.name, baseline ? "Baseline" : "Report");
  const latestRun = statusRun(task.data);
  const question = task.data?.question ?? stream.task.question ?? task.data?.name ?? null;
  const showLive = showLiveArtefact(stream, latestRun);
  // A run watched while it wrote keeps its page when it finishes until the
  // committed report for that run has loaded; then the report takes its
  // place, with no click (owner, 2026-11-05; N8's "Read the full report"
  // button is withdrawn). A run that had already finished when the page
  // loaded opens the report at once.
  const [watchedRunId, setWatchedRunId] = useState<string | null>(null);
  const liveRunId = stream.run?.id ?? null;
  if (
    showLive &&
    task.data !== undefined &&
    stream.run?.status === "running" &&
    liveRunId !== null &&
    watchedRunId !== liveRunId
  ) {
    setWatchedRunId(liveRunId);
  }
  const finishedHere =
    liveRunId !== null &&
    liveRunId === watchedRunId &&
    (stream.run?.status === "succeeded" || stream.run?.status === "degraded") &&
    Object.keys(stream.liveSections).length > 0;
  // The read models have caught up with the finished run: the task names
  // its end and the report read is not still in flight.
  const committedLanded =
    latestRun?.capability_run_id === liveRunId &&
    latestRun?.ended_at != null &&
    !task.isFetching &&
    !artefact.isFetching;
  const readyHere = finishedHere && !committedLanded;
  const reduceMotion = usePrefersReducedMotion();
  const openDossier = (title: string) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("source", title);
      next.delete("option");
      return next;
    });
  };
  // A claim opened on the live page follows itself into the committed
  // report by its claim id once that report has taken the page (never into
  // an older report held under a re-run), so the sheet gains what only the
  // committed report has (task 058, round 8).
  const shownClaim =
    detailClaim?.live === true && !(showLive || readyHere) && artefact.data != null
      ? (committedClaim(artefact.data.sections as SectionLike[] | undefined, detailClaim.claim_id) ?? detailClaim)
      : detailClaim;
  const claimPanel = (
    <ClaimPanel
      key="claim-panel"
      taskId={taskId}
      claim={shownClaim}
      onClose={() => setDetailClaim(null)}
      onOpenDossier={(title) => {
        setDetailClaim(null);
        openDossier(title);
      }}
    />
  );
  const live = useLiveReport(stream, question, isPublicView ? undefined : planPanel.openPlan, {
    onOpenClaim: setDetailClaim,
    panel: claimPanel,
  });
  // The swap (owner, round 7): the live page and the committed report are
  // the same element tree (the swap context, then `ReportPage`, then keyed
  // slots), so React updates the page in place; the scroll position stays.
  // What arrives with the committed report fades in once over 300 ms; under
  // reduced motion it is a cut.
  const renderingLive = showLive || readyHere;
  // `hadIntro` and `hadNotes`: the live page already showed the Full
  // report's opening paragraph and the most relevant sources, so they stay
  // put at the swap and only what the committed report adds to them fades
  // in (round 8).
  const [swap, setSwap] = useState<{ live: boolean; swapped: boolean; hadIntro: boolean; hadNotes: boolean } & ReportSwap>({
    live: false,
    swapped: false,
    arriving: false,
    liveNumbers: new Map(),
    hadIntro: false,
    hadNotes: false,
  });
  if (renderingLive && !swap.live) {
    setSwap({ live: true, swapped: false, arriving: false, liveNumbers: new Map(), hadIntro: false, hadNotes: false });
  } else if (!renderingLive && swap.live && artefact.data != null) {
    setSwap({
      live: false,
      swapped: true,
      arriving: !reduceMotion,
      liveNumbers: liveMarkerNumbers(stream),
      hadIntro: Object.values(stream.liveSections).some(
        (section) => section.role === "intro" && section.state === "filled" && (section.prose ?? "").trim() !== "",
      ),
      hadNotes: liveSourceNotes(stream).length > 0,
    });
  }
  const swapValue = useMemo<ReportSwap>(
    () => ({ arriving: swap.arriving, liveNumbers: swap.liveNumbers }),
    [swap.arriving, swap.liveNumbers],
  );
  const arriving = swap.arriving ? "anim-swap-in" : "";
  useKeepReadingPlace(renderingLive, swap.swapped);
  const liveBody = (
    <ReportSwapContext.Provider value={swapValue}>
      <ReportPage entries={live.entries}>{live.children}</ReportPage>
    </ReportSwapContext.Provider>
  );
  // A new run over an existing report: not the replay of the run that made it.
  const rerunLive =
    !isPublicView &&
    task.data !== undefined &&
    stream.run !== null &&
    (stream.run.status === "running" || stream.run.status === "paused") &&
    // A longlist walk does not rewrite the report, so no re-run line over the baseline.
    !stream.stages.some((entry) => LONGLIST_WALK_STAGES.has(entry.stage)) &&
    !(latestRun?.capability_run_id === stream.run.id && latestRun.ended_at != null);
  const rerunStartedAt =
    latestRun?.capability_run_id === stream.run?.id ? latestRun?.started_at : stream.run?.startedAt;

  const closeDossier = () => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("source");
      next.delete("option");
      return next;
    });
  };
  const { setActiveConversation, openDraftChat } = useActiveConversation();
  // Chats need a result to ask about (038 V8) — the same gate as New chat.
  const chatsEnabled = useChatsEnabled(taskId);
  const askAboutAnalysis = () => {
    // The open artefact is the chat's entry context (a chip and provenance
    // fact, never a scope fence); reuse a blank chat already carrying it,
    // else open a DRAFT beside the artefact (rev 3.4) — the row is created
    // on the first message, never before (038 V8).
    const artefactId = artefact.data?.artefact_id ?? null;
    const blank = chats.data?.data.find(
      (chat) => chat.title === "New chat" && chat.entry_artefact_id === artefactId,
    );
    if (blank !== undefined) return setActiveConversation(blank.id);
    openDraftChat(artefactId);
  };

  if (artefact.isPending) {
    return (
      <main aria-busy="true" aria-label="Loading the report" className={`${LIFECYCLE_PAGE_CLASS} py-8`}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="mb-4 h-24 anim-breathe border border-line bg-paper-2" />
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
        <main className={`${LIFECYCLE_PAGE_CLASS} py-8`}>
          <RetryCard copy="The report couldn't be loaded." onRetry={() => void artefact.refetch()} />
        </main>
      );
    }
  }

  if (artefact.isError || artefact.data === undefined || artefact.data === null) {
    // No committed artefact: show the in-progress skeleton when sections are
    // streaming (or streamed before a bad ending) — otherwise the empty state.
    if (showLive || readyHere) return liveBody;
    const endedEarly =
      stream.run?.status === "failed" ||
      stream.run?.status === "aborted" ||
      stream.run?.status === "interrupted";
    return <ReportToBe question={question} ended={endedEarly} onSeePlan={isPublicView ? undefined : planPanel.openPlan} />;
  }

  const data = artefact.data;
  // A fresh run re-writing the artefact supersedes the committed page while
  // it streams (the reducer clears sections when a different run starts) —
  // and if that run dies mid-write, the terminal-partial view stays up in
  // place of the stale committed page: the user's latest run ended badly and
  // hiding that behind the old artefact would be dishonest (live-check
  // adjudication, 2026-07-29). A new run or a fresh mount clears it. Replay
  // of a finished succeeded run must not flash through this view.
  if (showLive || readyHere) return liveBody;

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
  // frontSections = key_findings + case_studies (executive summary part);
  // bodySections = standard + conclusions (full report part).
  const firstBodyIndex = sections.findIndex(
    (section) => section.role !== "key_findings" && section.role !== "case_studies",
  );
  const frontSections =
    firstBodyIndex === -1 ? sections.map((section, index) => ({ section, index })) : sections.slice(0, firstBodyIndex).map((section, index) => ({ section, index }));
  const bodySections =
    firstBodyIndex === -1
      ? []
      : sections.slice(firstBodyIndex).map((section, index) => ({
          section,
          index: firstBodyIndex + index,
        }));

  // Sources links into the sources view, filtered to the cited set
  // (028 F.5): there is no `status=cited` value, so the cited count routes
  // through the boolean `cited=true` param.
  const snapshotCells: SnapshotCell[] = [];
  if (typeof snapshot?.source_count === "number" && typeof snapshot?.included === "number") {
    // Transcription trap 3: `source_count` is the cited/reference count —
    // never "found".
    snapshotCells.push([
      "Sources",
      `${snapshot.source_count} cited out of ${snapshot.included} included`,
      `/tasks/${taskId}/sources/all?cited=true`,
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
      "Published",
      `${Math.min(...citedYears)}–${Math.max(...citedYears)}`,
      null,
    ]);
  }
  // The report states when it was made. The run's end is the honest answer —
  // the artefact read model carries no timestamp of its own. There is
  // deliberately no author line: the backend has no author for an artefact,
  // and inventing one would have the report assert something nobody wrote.
  const lastUpdated = task.data?.latest_run?.ended_at;
  if (lastUpdated != null) {
    snapshotCells.push(["Last updated", new Date(lastUpdated).toLocaleDateString(), null]);
  }

  const topSources = mergeMostRelevantNotes(
    mostRelevantSources(sections),
    (data.most_relevant_notes ?? []) as Array<{ source_id: string; note: string }>,
  );

  const roadmapText = fullReportIntro(bodySections.length, data.full_report_intro);

  // A baseline is one linear profile, not a summary over a full report: the
  // two part headings would frame an empty half (it mints no key findings and
  // no case studies), so the outline lists its sections flat.
  const outlineHead: SidebarEntry[] = baseline
    ? sections.map((section, index) => ({
        id: sectionAnchor(section.title, index),
        title: sectionNavLabel(section, 28),
      }))
    : [
        { kind: "part", id: EXECUTIVE_SUMMARY_ANCHOR, title: "Executive summary" },
        ...frontSections.map(({ section, index }) => ({
          id: sectionAnchor(section.title, index),
          title: sectionNavLabel(section, 28),
        })),
        ...(topSources.length > 0
          ? [{ id: "sources", title: "Most relevant sources" }]
          : []),
        ...(bodySections.length > 0
          ? [{ kind: "part" as const, id: FULL_REPORT_ANCHOR, title: "Full report" }]
          : []),
        ...bodySections.map(({ section, index }) => ({
          id: sectionAnchor(section.title, index),
          title: sectionNavLabel(section, 28),
        })),
      ];
  const outlineEntries: SidebarEntry[] = [
    ...outlineHead,
    ...((data.references ?? []).length > 0 ? [{ id: "references", title: "References" }] : []),
    { id: "gathered", title: "Method" },
  ];

  const sectionBlocks = (section: SectionLike) => (
    <SectionBody blocks={section.blocks ?? []} onOpenClaim={setDetailClaim} />
  );
  const renderSection = ({ section, index }: { section: SectionLike; index: number }) => {
    const id = sectionAnchor(section.title, index);
    return section.role === "case_studies" ? (
      <CaseStudiesSection key={`section:${id}`} section={section} id={id} onOpenClaim={setDetailClaim} />
    ) : (
      <SectionDisclosure
        key={`section:${id}`}
        id={id}
        section={section as OutlineSection}
        collapsible={section.role !== "key_findings"}
        defaultOpen={false}
        arrivingClass={arriving}
      >
        {sectionBlocks(section)}
      </SectionDisclosure>
    );
  };

  return (
    <ReportSwapContext.Provider value={swapValue}>
      <ReportPage entries={outlineEntries}>
        {[
          <div key="notice">
            {rerunLive && rerunStartedAt !== undefined && (
              <RerunNotice taskId={taskId} artefactId={data.artefact_id} runStartedAt={rerunStartedAt} />
            )}
          </div>,
          <header key="header" id="answer" className="mb-8">
            <ReportKindRow kind={baseline ? "Baseline" : "Report"}>
              {/* The kind-of-artefact slot. The roll-up's depth label
                  ("scoping pass") stays on the wire for the later per-row
                  surfaces; the Result's heading says what the reader is
                  looking at (owner ruling 2026-09-18). */}
              <span className={arriving}>
                <ArtefactDownload artefact={data} />
              </span>
            </ReportKindRow>
            <h1 className={REPORT_TITLE_CLASS}>{scrub(data.title)}</h1>
            {!isPublicView && <SeePlanLink onClick={planPanel.openPlan} />}
            <div className={arriving}>
              <SnapshotCells cells={snapshotCells} />
            </div>
            {!isPublicView && (
              <button
                type="button"
                onClick={askAboutAnalysis}
                disabled={!chatsEnabled}
                title={chatsEnabled ? undefined : COPY.newChatUnavailable}
                className={cn(LINK_CLASS, "print-hide mt-3 text-meta", arriving)}
              >
                Ask about this analysis
              </button>
            )}
            {/* Coverage banner removed (owner, 2026-07-29): the adequacy verdict
                surfaces where it matters — inside each gap claim's detail. */}
          </header>,

          /* Executive summary part — In brief hidden (034 owner steer: overlaps
             key findings). A baseline has no summary half to head (see the
             outline above). */
          baseline ? null : (
            <h2 key="executive-summary" id={EXECUTIVE_SUMMARY_ANCHOR} className={`mb-6 ${REPORT_PART_HEADING_CLASS}`}>
              Executive summary
            </h2>
          ),

          ...frontSections.map(renderSection),

          /* A baseline writes no most-relevant-source notes and cites few
             sources per section, so the report's "cited most often" block
             would rank two or three documents as if that were a finding.
             Report only (task 044). */
          <div key="most-relevant" className={swap.hadNotes ? "" : arriving}>
            {baseline ? null : (
              <MostRelevantSources
                sources={topSources}
                onOpenDossier={openDossier}
                arrivingClass={swap.hadNotes ? arriving : ""}
              />
            )}
          </div>,

          /* Full report part */
          <FullReportExpandProvider key="full-report">
            {bodySections.length > 0 &&
              (baseline ? (
                // The baseline's sections ARE the document — no "Full report"
                // part to open, just the one control that opens them all.
                <div className={`mb-6 flex justify-end ${arriving}`}>
                  <FullReportExpandAllButton />
                </div>
              ) : (
                <div id={FULL_REPORT_ANCHOR} className="mb-6 mt-10 border-t border-line pt-4">
                  <div key="head" className="flex items-baseline gap-2">
                    <h2 className={`flex-1 ${REPORT_PART_HEADING_CLASS}`}>Full report</h2>
                    <span className={arriving}>
                      <FullReportExpandAllButton />
                    </span>
                  </div>
                  {roadmapText !== null && (
                    <p
                      key="intro"
                      className={`mt-1.5 max-w-prose-measure ${REPORT_BODY_CLASS} ${swap.hadIntro ? "" : arriving}`}
                    >
                      {scrub(roadmapText)}
                    </p>
                  )}
                </div>
              ))}

            {bodySections.map(renderSection)}

            {(data.references ?? []).length > 0 && (
              <ReferencesSection references={data.references ?? []} onOpenReference={openDossier} />
            )}

            <div className={arriving}>
              <GatheredSection taskId={taskId} id="gathered" />
            </div>
          </FullReportExpandProvider>,

          claimPanel,

          dossierSource !== null ? (
            <SourceDossier
              key="dossier"
              taskId={taskId}
              sourceRef={dossierSource}
              optionId={dossierOption}
              onClose={closeDossier}
            />
          ) : null,
        ]}
      </ReportPage>
    </ReportSwapContext.Provider>
  );
}

/** References as a collapsible entry with an always-visible summary line —
 *  it is the ArtefactOut.references collection, not a synthesis section
 *  (028 strand 10, binding record). While the report is written the same
 *  list grows as sections are checked, open, titles only and no links
 *  (task 058, owner round 7); the committed report adds the links and the
 *  authors in place. */
export function ReferencesSection({
  references,
  onOpenReference,
  defaultOpen = false,
}: {
  references: Array<{
    n: number;
    title: string;
    year?: number | null;
    venue?: string | null;
    authorships?: components["schemas"]["AuthorshipOut"][];
  }>;
  /** Absent while the report is live: the titles are not links yet. */
  onOpenReference?: (title: string) => void;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const arriving = useArrivingClass();
  useOpenWhenNavigated("references", setOpen);
  useExpandForPrint(setOpen);
  useExpandAll(setOpen);
  return (
    <section aria-label="References" id="references" className="mt-12 border-t border-line pt-6">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full cursor-pointer items-baseline gap-2 text-left"
      >
        <h2 className={`flex-1 ${REPORT_SECTION_HEADING_CLASS}`}>References</h2>
        <span aria-hidden="true" className={`${SECTION_EXPAND_LINK_CLASS} max-md:hidden`}>
          {open ? "Collapse −" : "Expand +"}
        </span>
      </button>
      {!open && (
        <p className="mt-1.5 text-lead text-grey max-md:text-body">
          {references.length === 1 ? "1 numbered source" : `${references.length} numbered sources`} cited
          in this report
        </p>
      )}
      {!open && <MobileDisclosureToggle expanded={false} onToggle={() => setOpen(true)} />}
      {open && (
        <ol className="mt-3 space-y-1.5 text-lead text-ink max-md:text-body">
          {references.map((reference) => {
            const authors = referenceAuthorsLine(reference.authorships);
            return (
              <li key={reference.n} className="flex gap-2">
                <span className="font-bold text-blue">[{reference.n}]</span>
                <span>
                  {onOpenReference === undefined ? (
                    <span>{scrub(reference.title)}</span>
                  ) : (
                    <button
                      type="button"
                      className="cursor-pointer text-left hover:underline"
                      onClick={() => onOpenReference(reference.title)}
                    >
                      {scrub(reference.title)}
                    </button>
                  )}
                  <span className={arriving}>
                    {authors !== null && <span className="text-grey"> — {scrub(authors)}</span>}
                    {reference.year !== null && reference.year !== undefined && (
                      <span className="text-grey"> ({reference.year})</span>
                    )}
                    {reference.venue !== null && reference.venue !== undefined && (
                      <span className="text-grey"> · {scrub(reference.venue)}</span>
                    )}
                  </span>
                </span>
              </li>
            );
          })}
        </ol>
      )}
      {open && <MobileDisclosureToggle expanded onToggle={() => setOpen(false)} />}
    </section>
  );
}

import { Children, createContext, Fragment, memo, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { CSSProperties, ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import type { components } from "../api/gen/types";
import { useApiClient, useArtefact, useConversations, useEvidence, useFindings, useLandscape, useLonglist, usePlan, useRuns, useTask, useSourceDossier } from "../api/queries";
import { useQuery } from "@tanstack/react-query";
import {
  cardEvidenceMeta,
  cardEvidenceSourceId,
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
import { referenceAuthorsShort, referenceParts, SOURCE_TITLE_LINK_CLASS } from "../ui/brand/reference";
import { ReferenceUrl } from "../ui/brand/ReferenceUrl";
import type { SidebarEntry } from "./ArtefactOutline";
import { ArtefactDownload } from "./ArtefactDownload";
import { formatDate } from "../lib/dates";
import { errorCode } from "../lib/errors";
import { useNow } from "../lib/freshness";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { COPY } from "../lib/vocabulary";
import { RESULT_VIEWS, resultView } from "./lifecycle";
import { hasLonglist, isBaselineArtefact, isToc, statusRun } from "./scopingActivity";
import { useChatsEnabled } from "./taskResult";
import { LonglistBuilding, LonglistView } from "./longlist/LonglistView";
import { isLonglistBuilding, LONGLIST_WALK_STAGES } from "./longlist/longlistPresentation";
import { usePlanPanel } from "./planPanel";
import { TocResult } from "./toc/TocResult";
import { ShortlistView } from "./longlist/ShortlistView";
import { Tabs, TabsList, TabsTrigger } from "../ui/radix/Tabs";
import { hasTerminalPartialLiveArtefact, useRunStream } from "../store";
import type { LiveCheckedClaim, LiveCitation, LiveClaim, LiveSection, LiveSourceNote, RunStreamState } from "../store";
import { LiveMark } from "../ui/brand/Card";
import { FoldMarkIcon } from "../ui/brand/FoldMarkIcon";
import { ArrowLeftIcon } from "../ui/brand/icons";
import { Chip, type ChipProps } from "../ui/brand/Chip";
import { BULLET_ITEM_CLASS, BULLET_MARK_CLASS } from "../ui/brand/BulletList";
import { useOpenAtTop } from "../lib/openAtTop";
import {
  citationJudgement,
  evidenceTypeLabel,
  strengthHint,
  TIER_LABEL,
  UNCHECKED,
  type CitationJudgement,
} from "../ui/brand/evidence";
import { StrengthMark } from "../ui/brand/EvidenceMarks";
import { ReauthRedirect } from "../ui/feedback";
import { Sheet, SheetContent } from "../ui/radix/Sheet";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";
import {
  REPORT_ACTIONS_CLASS,
  REPORT_DATELINE_CLASS,
  REPORT_TITLE_CLASS,
  ReportFacts,
  ReportKindRow,
  ReportPage,
  type ReportFact,
} from "./reportPage";
import { usePublicView } from "./publicView";
import {
  DisclosureHeading,
  FullReportExpandAllButton,
  FullReportExpandProvider,
  GATHERED_SECTION_TITLE,
  GatheredSection,
  gatheredSectionShows,
  MobileDisclosureToggle,
  type OutlineSection,
  ReportExpandScope,
  SectionDisclosure,
  seedReportExpanded,
  type SectionHeadingLevel,
  sectionAnchor,
  useExpandAll,
  useOpenWhenNavigated,
  useRememberedOpen,
  useScrollWhenNavigated,
} from "./ArtefactOutline";
import { DisclosureWord, useExpandForPrint } from "../ui/brand/Disclosure";
import { Tooltip } from "../ui/radix/Tooltip";
import { DOSSIER_LOADING_LINE, SourceDossierBody, useDossierRecords } from "./SourcesView";
import { useActiveConversation } from "./workspace/chat/conversationState";
import "./artefact.css";
import { scrollPane, useEasedHeight, useFollowTail, useHoldHeightWhileShorter, useRevealedText } from "./streamPacing";
import { RetryCard } from "../ui/feedback/RetryCard";
import { LINK_CLASS, QUIET_CONTROL_CLASS } from "../ui/brand/inlineActions";
import { cn } from "../ui/brand/cn";
import { GROWING_RULE_CLASS } from "../ui/brand/Nav";
import { formatCount } from "../lib/format";

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
  /** The judge's verdict on the claim (`ClaimOut`, round 13: the verdict is
   *  the claim's, no longer copied onto each citation). */
  grounding_tier?: string | null;
  grounding_rationale?: string | null;
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
  "citation-marker citation-number ml-1 cursor-pointer border border-blue/25 bg-blue-tint-2 px-1.5 align-[2px] text-caption font-semibold text-blue/80 hover:border-blue/60 hover:text-blue disabled:cursor-default disabled:border-line disabled:bg-ground disabled:text-grey disabled:hover:border-line disabled:hover:text-grey";

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
  | { kind: "degrade"; quote: string };

/** Where `quote` sits in `text`: exact first, then whitespace-normalised;
 *  `null` when it is not there. */
function locateQuote(text: string, quote: string): { start: number; end: number } | null {
  if (quote.trim().length === 0) return null;
  const exact = text.indexOf(quote);
  if (exact >= 0) return { start: exact, end: exact + quote.length };
  const squash = (value: string) => value.replace(/\s+/g, " ");
  const index = squash(text).indexOf(squash(quote));
  if (index < 0) return null;
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
  return { start: raw, end: Math.min(raw + quote.length + 20, text.length) };
}

/**
 * Locate `quote` inside `text` for highlighting: exact match first, then a
 * whitespace-normalised remap, then the same without the quote's trailing
 * `.`, `,`, `;` or `:` (the writer often ends a quote with a stop the passage
 * does not have there), then the honest degrade (the quote alone, the passage
 * not repeated; round 12) — never a broken panel (strand 5).
 */
export function highlightParts(text: string, quote: string): HighlightParts {
  const found = locateQuote(text, quote) ?? locateQuote(text, quote.trimEnd().replace(/[.,;:]+$/, ""));
  if (found === null) return { kind: "degrade", quote };
  return {
    kind: "highlight",
    before: text.slice(0, found.start),
    match: text.slice(found.start, found.end),
    after: text.slice(found.end),
  };
}

/** The passage with the quoted words in the highlight. */
function HighlightedPassage({ parts }: { parts: Extract<HighlightParts, { kind: "highlight" }> }) {
  return (
    <>
      {scrub(parts.before)}
      <mark className="bg-yellow-tint text-navy">{scrub(parts.match)}</mark>
      {scrub(parts.after)}
    </>
  );
}

/** The Findings table's passage: the highlight, or on no match the quote
 *  above the unhighlighted passage. */
export function HighlightedContext({ text, quote }: { text: string; quote: string }) {
  const parts = highlightParts(text, quote);
  if (parts.kind === "degrade") {
    return (
      <>
        <span className="mb-1 block italic text-grey">“{scrub(parts.quote)}”</span>
        {scrub(text)}
      </>
    );
  }
  return <HighlightedPassage parts={parts} />;
}

/** A chip whose hover reveals its rationale — the one Tooltip-wraps-a-Chip
 *  shape every grounding/verdict/appraisal indicator in the app uses (the
 *  report's classification and strength chips, chat's verdict chip).
 *  Exported so no surface re-types the wrapping. The help cursor marks a
 *  value with a reason behind it, as the Sources table does (round 12). */
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
    <Tooltip content={content} className="text-meta">
      {/* A flex wrapper, not a line box: the chip sits on its row's line
          whatever its first item is (the strength's empty tone square set
          the chip's baseline and dropped it 1 px; round 12). */}
      <span className="inline-flex cursor-help">
        <Chip tone={tone}>{label}</Chip>
      </span>
    </Tooltip>
  );
}

/** What a passage read needs: the saved citation's id for a committed
 *  report, or the cited chunk and the quote while the report is still being
 *  written (the live frame's `chunk_id`, 2026-11-09). */
type PassageRef = { citation_id: string | null; quote: string; chunk_id?: string | null };

/** Fetch one citation's clamped chunk context on demand (the click rung).
 *  A committed report's citation is read by its id. While the report is
 *  still being written (`live`) its citation rows are not committed yet,
 *  so the read goes by the cited chunk and the quote, the way chat's does
 *  (owner, 2026-11-09: the root of "the passage doesn't load during the
 *  write"); the chunks were committed long before. A 4xx is not retried; it
 *  means the same thing on every attempt. */
function useChunkContext(taskId: string, citation: PassageRef, live = false) {
  const client = useApiClient();
  const chunkId = live ? (citation.chunk_id ?? null) : null;
  const byChunk = chunkId !== null && citation.quote !== "";
  return useQuery({
    enabled: byChunk || (!live && citation.citation_id !== null),
    queryKey: byChunk
      ? ["tasks", taskId, "chat-chunk-context", chunkId, citation.quote]
      : ["tasks", taskId, "chunk-context", citation.citation_id],
    queryFn: async () => {
      const { data, error, response } = byChunk
        ? await client.GET("/api/v1/tasks/{task_id}/chunks/{chunk_id}/context", {
            params: { path: { task_id: taskId, chunk_id: chunkId }, query: { quote: citation.quote } },
          })
        : await client.GET("/api/v1/tasks/{task_id}/citations/{citation_key}/context", {
            params: { path: { task_id: taskId, citation_key: citation.citation_id ?? "" } },
          });
      if (data === undefined) throw Object.assign(new Error("Failed to load the passage"), { status: response.status, body: error });
      return data;
    },
    retry: (failureCount, error) => {
      const status = (error as { status?: number }).status;
      if (status !== undefined && status < 500) return false;
      return failureCount < 3;
    },
  });
}

/** Under a quote of a live report whose frame carries no chunk (recorded
 *  before the field existed): no passage read can run until the commit. */
const LIVE_PASSAGE_NOTE = "The surrounding passage is read once the report is complete.";

/** The judge's callout tint (owner, round 13): a checked tier on Blue
 *  Wash 2 ("blue means checked"), an unsupported one on Red Tint, an
 *  unchecked one on Ground. */
function judgementTint(judgement: CitationJudgement): string {
  if (judgement.label === UNCHECKED) return "bg-ground";
  if (judgement.label === TIER_LABEL.unsupported_mis_cited) return "bg-red-tint";
  return "bg-blue-tint-2";
}

/** A part's label on the sheet, the dossier's label style (Meta Grey).
 *  "Judge" carries the Policy Atlas blue diamond before it, the mark of the
 *  product's own AI work (owner, round 13). */
function ProvenanceLabel({ children, ai = false }: { children: string; ai?: boolean }) {
  return (
    <p data-provenance-label="" className="mb-1 flex items-center gap-1.5 text-meta text-grey">
      {ai && <FoldMarkIcon size={10} data-testid="ai-mark" />}
      {children}
    </p>
  );
}

/** The judge's verdict: "Judge" led by the blue diamond (the product's AI
 *  judgement), over its tinted callout, the tier's label in Navy Semibold
 *  and the judge's words at Body Grey (owner, round 13). */
function JudgeBlock({ judgement }: { judgement: CitationJudgement }) {
  return (
    <div data-judge-block="">
      <ProvenanceLabel ai>Judge</ProvenanceLabel>
      <div className={cn("px-3 py-2", judgementTint(judgement))}>
        <p className="text-body font-semibold text-navy">{judgement.label}</p>
        <p className="mt-0.5 text-body text-grey">{scrub(judgement.words)}</p>
      </div>
    </div>
  );
}

/** The evidence type on the sheet's marks line, its hover the classifier's
 *  reasoning read from the cited source's dossier, as the badges and the
 *  Sources table do (owner, round 13): the dotted word, the help cursor,
 *  the Meta tooltip. Without a task and a source to ask, the type alone. */
function ClassificationHint({ taskId, sourceId, type }: { taskId: string; sourceId: string | null; type: string }) {
  const label = scrub(evidenceTypeLabel(type));
  if (taskId === "" || sourceId === null) return <span>{label}</span>;
  return (
    <Tooltip content={<ClassificationReason taskId={taskId} sourceId={sourceId} />} className="text-meta">
      <span className="cursor-help">
        <span className="reason-word">{label}</span>
      </span>
    </Tooltip>
  );
}

/** A theme item's sources in the citation sheet: "Identified across N
 *  sources", then the shared Show / Hide word and chevron; open, the titles,
 *  each opening its dossier. */
function ThemeItemSources({
  sources,
  onOpenDossier,
}: {
  sources: readonly { source_id?: string | null; title?: string | null }[];
  onOpenDossier: (sourceRef: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="mt-1 text-meta text-grey"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="group flex cursor-pointer list-none flex-wrap items-center gap-x-2 hover:text-navy [&::-webkit-details-marker]:hidden">
        <span>
          Identified across {formatCount(sources.length)} source{sources.length === 1 ? "" : "s"}
        </span>
        <DisclosureWord open={open} />
      </summary>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-body">
        {sources.map((source) =>
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
  );
}

/** One quote in a source's box: "Quote" over the passage at Body, the quoted
 *  words in the highlight, the surrounding sentences Grey; when the quote is
 *  not found in the passage, the quote alone at Body Navy (the passage is not
 *  repeated); on a lookup failure the quote alone with the caller's honest
 *  note. */
export function CitationQuote({
  context,
  quote,
  fallbackNote,
  note,
  label = "Quote",
}: {
  context: {
    isPending: boolean;
    /** Pending and fetching (a query result); a disabled read is not loading. */
    isLoading?: boolean;
    isError: boolean;
    data: components["schemas"]["ChunkContextOut"] | undefined;
  };
  quote: string;
  fallbackNote?: string;
  /** Shown under the quote whatever the read did (the live report's note). */
  note?: string;
  /** "Quote", or "Quote 1", "Quote 2", … when a source gives several. */
  label?: string;
}) {
  const parts = context.data !== undefined ? highlightParts(context.data.context, quote) : null;
  // The quote is known before the passage is read: it shows at once, and the
  // passage takes its place when it lands (owner, 2026-11-09: a citation
  // opened during the write showed only "Loading…").
  const loading = context.isLoading ?? (context.isPending && !context.isError);
  return (
    <div>
      <ProvenanceLabel>{label}</ProvenanceLabel>
      <div className="space-y-2 text-body">
        {context.data !== undefined && parts?.kind === "highlight" ? (
          <>
            {typeof context.data.previous === "string" && context.data.previous !== "" && (
              <p className="text-grey">{scrub(context.data.previous)}</p>
            )}
            <p className="text-navy">
              <HighlightedPassage parts={parts} />
            </p>
            {typeof context.data.next === "string" && context.data.next !== "" && (
              <p className="text-grey">{scrub(context.data.next)}</p>
            )}
          </>
        ) : (
          <p className="text-navy">“{scrub(quote)}”</p>
        )}
        {loading && (
          <p role="status" className="anim-breathe-soft text-grey">
            Loading surrounding context…
          </p>
        )}
        {context.isError && fallbackNote !== undefined && <p className="text-grey">{fallbackNote}</p>}
        {note !== undefined && <p className="text-grey">{note}</p>}
      </div>
    </div>
  );
}

/** A source's marks line (owner, round 14): the evidence type (dotted,
 *  its classifier's reasoning on hover), then the strength with its tone
 *  square (its appraisal on hover), then any plain facts ("Since 2019",
 *  "Cited by 3 claims"), at Meta Grey, joined by middots. One line for the
 *  citation sheet, the case studies and the most relevant sources. Nothing
 *  when there is nothing to say. */
function EvidenceMarksLine({
  taskId,
  sourceId,
  evidenceType,
  strength,
  facts = [],
  className,
}: {
  taskId: string;
  sourceId: string | null;
  evidenceType: string | null;
  strength: string | null;
  facts?: readonly string[];
  className?: string;
}) {
  const parts: ReactNode[] = [];
  if (evidenceType !== null) parts.push(<ClassificationHint key="type" taskId={taskId} sourceId={sourceId} type={evidenceType} />);
  if (strength !== null) parts.push(<StrengthHint key="strength" label={strength} evidenceType={evidenceType} />);
  for (const fact of facts) parts.push(<span key={fact}>{fact}</span>);
  if (parts.length === 0) return null;
  return (
    <p data-marks-line="" className={cn("flex flex-wrap items-center gap-x-1.5 text-meta text-grey", className)}>
      {parts.map((part, at) => (
        <Fragment key={at}>
          {at > 0 && <span aria-hidden="true">·</span>}
          {part}
        </Fragment>
      ))}
    </p>
  );
}

/** One source's provenance block (owner, round 13): its own box (a Line
 *  hairline, no coloured rule: that is the Claim's). The report's sheet
 *  groups a claim's citations by source, one box each, and shows the
 *  claim's one verdict under the Claim; chat passes one citation and its own
 *  `judgement`, set first in the box. Then the source, unlabelled, with
 *  12 px of room above and below, title first: "[2] Title" at Body Semibold
 *  Navy, the title the way into the dossier, then "Sampleton A, Mockford C ·
 *  2022 · BMJ Open" in Grey, then the evidence type (its reasoning on hover)
 *  and strength at Meta; then each quote under its own "Quote" label,
 *  highlighted inside its passage (`CitationQuote`). One type scale (round
 *  12). Presentational: callers own the chunk-context queries. */
export function CitationProvenanceBlock({
  n,
  sourceTitle,
  sourceRef,
  onOpenDossier,
  context,
  quote,
  fallbackNote,
  hideNumber = false,
  evidenceType = null,
  strength = null,
  judgement = null,
  taskId = "",
  sourceId = null,
  quotes,
}: {
  /** Reference number; `hideNumber` drops the "[n]" for callers with no numbering. */
  n: number | null;
  hideNumber?: boolean;
  sourceTitle: string;
  /** A source id/title to open the dossier with, or `null` when the
   *  citation carries nothing dossier-linkable (renders plain text). */
  sourceRef: string | null;
  onOpenDossier: (sourceRef: string) => void;
  context: { isPending: boolean; isError: boolean; data: components["schemas"]["ChunkContextOut"] | undefined };
  quote: string;
  /** Shown under the quote on a lookup failure, alongside it — never in
   *  place of the honest quote fallback (chat's non-verbatim-quote case). */
  fallbackNote?: string;
  /** The cited source's classified evidence type, when it has one. */
  evidenceType?: string | null;
  /** The cited source's appraised strength, when it has one. */
  strength?: string | null;
  /** A per-citation verdict (chat). The report's sheet shows its claim's
   *  one verdict under the Claim instead (`ProvenanceSheet`'s `judgement`). */
  judgement?: CitationJudgement | null;
  /** The task and the cited source, for the evidence type's reasoning on
   *  hover; without them the type is plain. */
  taskId?: string;
  sourceId?: string | null;
  /** Several quotes from this one source, each a `CitationQuote` (the
   *  report groups a claim's citations by source, owner round 13); without
   *  it the block shows the one `quote` in `context`. */
  quotes?: ReactNode;
}) {
  // Title first (owner, round 13): the title on its own line, then the
  // authors, year and venue in Grey; the References keep their author-year
  // form.
  const byline = [
    referenceAuthorsShort(context.data?.authorships),
    context.data?.year,
    context.data?.venue,
  ].filter((part): part is string | number => part != null && part !== "");
  const title = scrub(sourceTitle);
  return (
    <div data-citation-block="" className="border border-line p-4">
      {judgement !== null && <JudgeBlock judgement={judgement} />}
      {/* The source, unlabelled, with its own room: the title, then its
          byline, then the evidence marks. */}
      <div className={judgement !== null ? "my-3" : "mb-3"}>
        {/* The number in its own column, so a long title wraps beside it. */}
        <p className="flex items-baseline gap-1.5 text-body font-semibold text-navy [overflow-wrap:anywhere]">
          {!hideNumber && <span className="shrink-0 font-normal tabular-nums text-grey">[{n ?? "—"}]</span>}
          {sourceRef !== null ? (
            <button
              type="button"
              className={cn("cursor-pointer text-left", SOURCE_TITLE_LINK_CLASS)}
              onClick={() => onOpenDossier(sourceRef)}
            >
              {title}
            </button>
          ) : (
            <span>{title}</span>
          )}
        </p>
        {byline.length > 0 && (
          <p className="mt-0.5 text-body text-grey">{byline.map((part) => scrub(String(part))).join(" · ")}</p>
        )}
        <EvidenceMarksLine
          taskId={taskId}
          sourceId={sourceId}
          evidenceType={evidenceType}
          strength={strength}
          className="mt-1"
        />
      </div>
      {/* Each quote under its own "Quote" label (owner, round 13). */}
      <div className="space-y-3">
        {quotes ?? <CitationQuote context={context} quote={quote} fallbackNote={fallbackNote} />}
      </div>
    </div>
  );
}

/** The strength as the Sources table sets it: the tone square, then the
 *  word with the dotted underline and help cursor of a value with a reason
 *  behind it; the reason on hover. */
function StrengthHint({ label, evidenceType }: { label: string; evidenceType?: string | null }) {
  return (
    <Tooltip content={<p>{scrub(strengthHint(label, evidenceType))}</p>} className="text-meta">
      <span className="inline-flex cursor-help items-center gap-1.5">
        <StrengthMark
          tier={label}
          wordClassName="reason-word"
        />
      </span>
    </Tooltip>
  );
}

/** The reasoning behind a source's evidence type, read on first hover. */
function ClassificationReason({ taskId, sourceId }: { taskId: string; sourceId: string }) {
  const dossier = useSourceDossier(taskId, sourceId);
  if (dossier.isPending) {
    // The words are on their way: a breathing line where they will sit.
    return <span aria-hidden="true" className="block h-3 w-48 max-w-full bg-line anim-breathe-soft" />;
  }
  const reason = dossier.data?.classification_reason;
  if (typeof reason === "string" && reason.trim() !== "") return <p>{scrub(reason)}</p>;
  return <p>{dossier.isError ? "The reasoning could not be loaded." : "No reasoning was recorded for this type."}</p>;
}

/** One quote of a source group: its passage read on demand (by chunk and
 *  quote while the report is still being written). */
function ReportQuote({ taskId, citation, label, live = false }: { taskId: string; citation: CitationOut & PassageRef; label: string; live?: boolean }) {
  const context = useChunkContext(taskId, citation, live);
  const unreadable = live && (citation.chunk_id ?? null) === null;
  return <CitationQuote context={context} quote={citation.quote} label={label} note={unreadable ? LIVE_PASSAGE_NOTE : undefined} />;
}

/** One source's box in the claim panel (owner, round 13): a claim's
 *  citations grouped by source, the source line once, then each of its
 *  quotes under its own "Quote" label. The byline comes from the first
 *  quote's passage read (the chunk context carries the authors, year and
 *  venue). */
function SourceGroupBlock({
  taskId,
  citations,
  onOpenDossier,
  live = false,
}: {
  taskId: string;
  citations: CitationOut[];
  onOpenDossier: (title: string) => void;
  /** The report is still being written: the title is not a link yet. */
  live?: boolean;
}) {
  const first = citations[0];
  const context = useChunkContext(taskId, first, live);
  return (
    <CitationProvenanceBlock
      n={first.n}
      sourceTitle={first.source_title}
      sourceRef={live ? null : (first.source_id ?? first.source_title)}
      onOpenDossier={onOpenDossier}
      context={context}
      quote={first.quote}
      evidenceType={nonEmpty(first.evidence_type)}
      strength={nonEmpty(first.appraisal_label)}
      taskId={taskId}
      sourceId={nonEmpty(first.source_id)}
      quotes={citations.map((citation, at) => (
        <ReportQuote
          key={citation.citation_id}
          taskId={taskId}
          citation={citation}
          live={live}
          // Several quotes from one source are numbered in order (owner, round 13).
          label={citations.length > 1 ? `Quote ${at + 1}` : "Quote"}
        />
      ))}
    />
  );
}

/** A claim's citations grouped by source (`source_id`, else the title), in
 *  the order each source is first cited. */
export function citationsBySource<C extends { source_id?: string | null; source_title: string }>(
  citations: readonly C[],
): C[][] {
  const groups = new Map<string, C[]>();
  for (const citation of citations) {
    const key = citation.source_id ?? `title:${citation.source_title}`;
    const group = groups.get(key);
    if (group === undefined) groups.set(key, [citation]);
    else group.push(citation);
  }
  return [...groups.values()];
}

/** The claim's verdict (round 13: the tier and rationale are the claim's,
 *  `ClaimOut.grounding_tier` and `grounding_rationale`). A claim with no
 *  citations has nothing judged against a source. */
function claimJudgement(claim: ClaimLike): CitationJudgement | null {
  if ((claim.citations ?? []).length === 0) return null;
  return citationJudgement(claim.grounding_tier, claim.grounding_rationale);
}

function nonEmpty(value: string | null | undefined): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

/** The citation sheet's title, the report's and chat's (owner, round 13;
 *  it read "Where this comes from"). */
export const PROVENANCE_SHEET_TITLE = "Evidence for this claim";

/** The provenance sheet a claim (report) or a claim/citation (chat) opens
 *  (owner, round 13): the "Evidence for this claim" shell, then the claim's
 *  block (its words behind the 2 px blue rule; one line per string — chat
 *  stacks several when multiple claims cite one citation), a caller-supplied
 *  extras slot (the reader's gap/type-hint/theme/weak-grounding lines), the
 *  claim's one Judge block (lead, round 13), then one bounded block per
 *  citation, 16 px apart. The Sheet keeps its close
 *  button and focus rules. */
export function ProvenanceSheet({
  description = "Claim provenance",
  claimTexts,
  extras,
  judgement = null,
  onClose,
  children,
}: {
  description?: string;
  claimTexts: string[];
  extras?: ReactNode;
  /** The claim's one verdict, shown once under the Claim (lead, round 13:
   *  the read model copies the claim's verdict onto every citation). */
  judgement?: CitationJudgement | null;
  onClose: () => void;
  /** One element per source box (the label over them counts sources). */
  children: ReactNode;
}) {
  const citationCount = Children.toArray(children).length;
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      {/* "Claim provenance" repeats the title on screen: it stays the
          dialog's accessible description only (round 10, C3). */}
      <SheetContent title={PROVENANCE_SHEET_TITLE} description={description} descriptionHidden>
        {/* The claim's block, then one bounded block per citation, 16 px
            apart (owner, round 13). */}
        <div className="space-y-4">
          {claimTexts.some((text) => text !== "") && (
            <div>
              <ProvenanceLabel>Claim</ProvenanceLabel>
              <div className="space-y-2 border-l-2 border-l-blue pl-3">
                {claimTexts
                  .filter((text) => text !== "")
                  .map((text, index) => (
                    <p key={index} className="text-body text-navy">
                      {scrub(text)}
                    </p>
                  ))}
              </div>
            </div>
          )}
          {extras}
          {judgement !== null && <JudgeBlock judgement={judgement} />}
          {citationCount > 0 && (
            // One label over the boxes, counting sources: "Source", "Sources · 2".
            <div className="space-y-4">
              <ProvenanceLabel>{citationCount === 1 ? "Source" : `Sources · ${citationCount}`}</ProvenanceLabel>
              {children}
            </div>
          )}
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
        <div className="text-body text-navy">
          <p>
            This is a recorded evidence gap: the analysis looked and found the base thin here.
            Gaps are part of the answer, never glossed over.
          </p>
          {gap !== null && (
            <div className="mt-1 space-y-0.5 text-meta text-grey">
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
        <div>
          {(claim.theme?.items ?? []).map((item, index) => (
            <div key={index} className={index > 0 ? "mt-3" : undefined}>
              <p className="text-body text-navy">{scrub(item.name ?? "")}</p>
              {typeof item.description === "string" && item.description !== "" && (
                <p className="mt-0.5 text-body text-grey">
                  {scrub(item.description)}
                </p>
              )}
              {(item.sources?.length ?? 0) > 0 ? (
                <ThemeItemSources sources={item.sources ?? []} onOpenDossier={onOpenDossier} />
              ) : typeof item.size === "number" ? (
                <p className="mt-1 text-meta text-grey">
                  Identified across {item.size} sources
                </p>
              ) : null}
              {typeof item.facet === "string" && item.facet !== "" && item.name ? (
                <p className="mt-1 text-meta">
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
            <p className="mt-3 text-meta text-grey">
              Basis: {scrub(claim.theme.base)}
            </p>
          )}
        </div>
      )}
      {claim.weakly_grounded === true && (
        <p className="text-body text-navy">
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
      judgement={claimJudgement(claim)}
      onClose={onClose}
    >
      {citationsBySource(claim.citations ?? []).map((group) => (
        <SourceGroupBlock
          key={group[0].citation_id}
          taskId={taskId}
          citations={group}
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

/** A claim's citation numbers, each once, in ascending order ("[7,12]"). */
function sortedNumbers(citations: readonly { n: number }[] | undefined): number[] {
  return [...new Set((citations ?? []).map((citation) => citation.n))].sort((a, b) => a - b);
}

/** "7 and 12", "3, 7 and 12". */
function numberList(numbers: readonly number[]): string {
  return numbers.length < 2 ? numbers.join("") : `${numbers.slice(0, -1).join(", ")} and ${numbers.at(-1)}`;
}

/**
 * The marker's accessible name (round 10, C1): what it opens. One source
 * names it, "Source 2: School meals and child weight outcomes"; several are
 * counted, "Sources 7 and 12".
 */
export function markerName(citations: readonly { n: number; source_title: string }[]): string {
  const numbers = sortedNumbers(citations);
  if (numbers.length === 1) {
    const title = citations.find((citation) => citation.n === numbers[0])?.source_title ?? "";
    return title === "" ? `Source ${numbers[0]}` : `Source ${numbers[0]}: ${scrub(title)}`;
  }
  return `Sources ${numberList(numbers)}`;
}

/** A claim span in the prose (demo ClaimSpan): the whole span is clickable
 *  and hover previews the first citation; the marker is the one control
 *  (round 10, finding 4), with the same preview on hover and on keyboard
 *  focus, and opens the provenance panel. Citation numbers ride as one
 *  inline chip; typed claims carry their label. */
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
  const citationNumbers = sortedNumbers(claim.citations);
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
  const tier = claim.grounding_tier ?? null;
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
      {/* The words are a pointer target only: hover tints them and shows the
          preview, a click opens the panel. The marker after them is the one
          control a keyboard and a screen reader meet (round 10, finding 4),
          so a claim is one tab stop and the sentence is not read as a
          button. A real <button> around the words would be an atomic inline
          block that could never wrap mid-line. */}
      <Tooltip content={tip}>
        <span
          onClick={() => onOpen(claim)}
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
        <Tooltip content={tip}>
          <button
            type="button"
            aria-label={markerName(claim.citations ?? [])}
            onClick={() => onOpen(claim)}
            className={renumbered ? `${CITATION_MARKER_CLASS} anim-swap-in` : CITATION_MARKER_CLASS}
          >
            [{citationNumbers.join(",")}]
          </button>
        </Tooltip>
      )}
      {claim.claim_type !== "citation" && typeLabel !== undefined && (
        <Tooltip content={tip}>
          <button
            type="button"
            onClick={() => onOpen(claim)}
            className={`citation-number ml-1 cursor-pointer border px-1.5 align-[2px] text-caption font-semibold ${
              claim.claim_type === "gap"
                ? "border-yellow/60 bg-yellow-tint/60 text-navy/80 hover:border-yellow"
                : "border-line bg-ground text-grey hover:border-line-2"
            }`}
          >
            {typeLabel}
          </button>
        </Tooltip>
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

/* The key findings' bullets are the shared report bullet (`BulletList`'s
 * `BULLET_ITEM_CLASS` and `BULLET_MARK_CLASS`, ui/brand): one source for the
 * square on the x-height; a gap's square is Yellow. */

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
        {/* The bullet is an Electric Blue square (owner, round 11, reversing
            round 10's Navy) centred on the text's x-height
            (`BULLET_MARK_CLASS`); the items stand apart (round 10,
            finding 8). `data-bullet` prints it as a border, since print
            drops backgrounds. */}
        <ul className="list-none space-y-3">
          {bullets.map((bullet, bulletIndex) => {
            const isGap = bullet.some(
              (segment) => segment.kind === "claim" && segment.claim.claim_type === "gap",
            );
            return (
              <li key={bulletIndex} className={BULLET_ITEM_CLASS}>
                <span
                  aria-hidden="true"
                  data-bullet={isGap ? "gap" : ""}
                  className={`${BULLET_MARK_CLASS} ${isGap ? "bg-yellow" : "bg-blue"}`}
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
  onBack,
}: {
  taskId: string;
  /** A source id (citations carry one) or a display title (references,
   *  theme members — the legacy title-keyed path). */
  sourceRef: string;
  /** Opened from a claim's sheet: "Back to the claim" returns to it (owner,
   *  round 13). Absent from every other route in. */
  onBack?: () => void;
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
        headerAction={
          onBack !== undefined ? (
            // "Back" with the icons module's left arrow; its
            // name and tooltip say where it goes (owner, round 13).
            <Tooltip content={<p>Back to the claim</p>} className="text-meta">
              <button
                type="button"
                onClick={onBack}
                aria-label="Back to the claim"
                className={cn(QUIET_CONTROL_CLASS, "inline-flex items-center gap-1 text-meta")}
              >
                <ArrowLeftIcon size={14} />
                Back
              </button>
            </Tooltip>
          ) : undefined
        }
      >
        {/* isLoading, not isPending: while the title→id lookup has not
         *  resolved, the dossier query is disabled and pending forever —
         *  isPending would render a stuck (and duplicate) loading line. */}
        {((!byId && evidence.isPending) || dossier.isLoading) && (
          <p role="status" className="anim-breathe-soft text-body text-grey">
            {DOSSIER_LOADING_LINE}
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

export function PlaceholderLines({
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
  "citation-marker citation-number pending-mark ml-1 border border-line bg-ground px-1.5 align-[2px] text-caption font-semibold text-grey";

/** The checked marker while the report is still live and its citations do
 *  not carry their ids (an older stream): the final marker's look, without
 *  the control's cursor and hover. */
export const CITATION_MARKER_LIVE_CLASS =
  "citation-marker citation-number ml-1 border border-blue/25 bg-blue-tint-2 px-1.5 align-[2px] text-caption font-semibold text-blue/80";

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
        <ul className="list-none space-y-3">
          {blocks.map((runs, at) => (
            <li key={at} className={BULLET_ITEM_CLASS}>
              <span aria-hidden="true" data-bullet="" className={`${BULLET_MARK_CLASS} bg-blue`} />
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
export function LiveDraft({
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
export function liveClaims(
  prose: string,
  citations: readonly LiveCitation[] | undefined,
  checked: readonly LiveCheckedClaim[] | undefined = undefined,
): ClaimLike[] {
  const chars = Array.from(prose);
  const bySpan = new Map<string, ClaimLike>();
  // The checker's verdict is the claim's (round 13), matched by the claim's
  // id when both carry it, else by its span.
  const byId = new Map((checked ?? []).filter((claim) => claim.claimId !== null).map((claim) => [claim.claimId, claim]));
  const bySpanVerdict = new Map((checked ?? []).map((claim) => [`${claim.start}:${claim.end}`, claim]));
  for (const citation of citations ?? []) {
    const key = `${citation.start}:${citation.end}`;
    let claim = bySpan.get(key);
    if (claim === undefined) {
      const verdict = (citation.claimId !== null ? byId.get(citation.claimId) : undefined) ?? bySpanVerdict.get(key);
      claim = {
        grounding_tier: verdict?.tier ?? null,
        grounding_rationale: verdict?.rationale ?? null,
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
      source_id: citation.sourceId,
      quote: citation.quote,
      // The passage read while the report is still being written (2026-11-09).
      chunk_id: citation.chunkId ?? null,
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
  checked: readonly LiveCheckedClaim[] | undefined = undefined,
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
    const ownChecked = (checked ?? [])
      .filter((claim) => claim.start >= bodyStart && claim.end <= bodyEnd)
      .map((claim) => ({ ...claim, start: claim.start - bodyStart, end: claim.end - bodyStart }));
    cards.push({ title: match[1], prose: body, claims: liveClaims(body, own, ownChecked) });
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
export function LiveSubhead({
  section,
  active,
  activity,
  terminal,
  still,
}: {
  section: LiveSection & { role: NonNullable<SectionLike["role"]> };
  active: boolean;
  activity: string | null;
  terminal: boolean;
  /** The stream is not connected: the live mark holds still (lead ruling). */
  still: boolean;
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
            {writing && <LiveMark data-testid="section-mark" still={still} />}
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
  const checkedClaims = section?.checkedClaims;
  const liveBlocks = useMemo(
    () => [{ block_id: "live", prose, claims: liveClaims(prose, citations, checkedClaims) }],
    [prose, citations, checkedClaims],
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
      const ns = sortedNumbers(claim.citations).join(",");
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
  // The section's live mark holds still while the stream is down (lead ruling).
  const markStill = stream.connectionStatus !== "connected";

  // Sections inside a part are h3; a baseline has no parts (round 10).
  const level: SectionHeadingLevel = report ? 3 : 2;
  const entries: SidebarEntry[] = [
    ...(report ? [{ kind: "part" as const, id: EXECUTIVE_SUMMARY_ANCHOR, title: "Executive summary" }] : []),
    ...front.map(({ section, id }) => ({ id, title: sectionNavLabel({ title: section.title }, Infinity) })),
    ...(notes.length > 0 ? [{ id: "sources", title: "Most relevant sources" }] : []),
    ...(report && body.length > 0 ? [{ kind: "part" as const, id: FULL_REPORT_ANCHOR, title: "Full report" }] : []),
    ...body.map(({ section, id }) => ({ id, title: sectionNavLabel({ title: section.title }, Infinity) })),
    ...(references.length > 0 ? [{ id: "references", title: "References" }] : []),
  ];

  const renderSection = ({ section, id }: (typeof anchored)[number]) => {
    const isActive = section === active;
    const subhead = (
      <LiveSubhead
        section={section}
        active={isActive}
        activity={isActive ? activity : null}
        terminal={terminal}
        still={markStill}
      />
    );
    if (section.role === "case_studies") {
      const cards =
        section.state === "filled"
          ? liveCaseStudyCards(section.prose ?? "", section.citations, section.checkedClaims)
          : (section.cards ?? []);
      return (
        <CaseStudiesSection
          key={`section:${id}`}
          section={{ title: section.title, role: "case_studies", cards }}
          id={id}
          level={level}
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
        level={level}
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
      {/* The committed report's action line, holding only what the live
          page has, so the swap fills it in place (round 10, finding 9). */}
      {onSeePlan !== undefined && (
        <div className={REPORT_ACTIONS_CLASS}>
          <SeePlanLink onClick={onSeePlan} />
        </div>
      )}
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
    // The executive summary's last part, as on the committed page (owner,
    // round 11).
    <div key="most-relevant">{notes.length > 0 && <MostRelevantSources live sources={liveTopSources(notes)} level={level} />}</div>,
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
              still={markStill}
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
      {onSeePlan !== undefined && <SeePlanLink onClick={onSeePlan} className="mt-2" />}
    </ReportPage>
  );
}

/** The Result tab's small link to the plan document. Not printed. */
function SeePlanLink({ onClick, className }: { onClick: () => void; className?: string }) {
  return (
    <button type="button" onClick={onClick} className={cn(QUIET_CONTROL_CLASS, "print-hide text-meta", className)}>
      See the plan
    </button>
  );
}

/** A link to a source's dossier on this page (`?source=`), keeping the
 *  page's other parameters: a real address, so it opens in a new tab or
 *  copies, while a plain click opens the sheet in place (round 10). */
function sourceHref(sourceRef: string): string {
  const params = new URLSearchParams(typeof window === "undefined" ? "" : window.location.search);
  params.set("source", sourceRef);
  params.delete("option");
  return `?${params.toString()}`;
}

/** Whether a click should open the link in place: a plain primary click,
 *  not one asking for a new tab or window. */
function plainClick(event: React.MouseEvent): boolean {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

/* A source title that opens its dossier (the references, the most relevant
 * sources, the provenance sheet) takes the shared `SOURCE_TITLE_LINK_CLASS`
 * (ui/brand/reference): Navy, underlined in Line 2, Navy on hover. */

function SourceTitleLink({
  sourceRef,
  onOpen,
  className,
  children,
}: {
  sourceRef: string;
  onOpen: (sourceRef: string) => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <a
      href={sourceHref(sourceRef)}
      onClick={(event) => {
        if (!plainClick(event)) return;
        event.preventDefault();
        onOpen(sourceRef);
      }}
      className={cn(SOURCE_TITLE_LINK_CLASS, className)}
    >
      {children}
    </a>
  );
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
      This report is from {formatDate(madeBy.ended_at, "long")}. A new run started{" "}
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
/** The case studies' and the most relevant sources' cards: each entry a
 *  ruled card (a Line hairline, 16 px inside), 12 px apart (owner, round 11:
 *  back in boxes, as before round 10). */
const REPORT_CARD_LIST_CLASS = "mt-3 grid gap-3";
const REPORT_CARD_CLASS = "border border-line p-4";

function CaseStudiesSection({
  section,
  id,
  taskId = "",
  onOpenClaim = () => undefined,
  live = false,
  busy = false,
  subhead,
  pending,
  level = 3,
}: {
  section: SectionLike;
  id: string;
  /** The task, for the classification chip's reasoning (committed only). */
  taskId?: string;
  onOpenClaim?: (claim: ClaimLike) => void;
  live?: boolean;
  busy?: boolean;
  /** The live page's lines under the heading. */
  subhead?: ReactNode;
  /** What stands in for the cards before the first one closes (live only). */
  pending?: ReactNode;
  level?: SectionHeadingLevel;
}) {
  useScrollWhenNavigated(id);
  const arriving = useArrivingClass();
  const cards = section.cards ?? [];
  if (cards.length === 0 && !live) return null;
  const Heading = level === 3 ? "h3" : "h2";
  const CardHeading = level === 3 ? "h4" : "h3";
  return (
    <section id={id} aria-busy={busy ? true : undefined} className="mb-9">
      <Heading className={REPORT_SECTION_HEADING_CLASS}>{scrub(section.title)}</Heading>
      {subhead}
      <p className={`mt-1.5 max-w-prose-measure ${REPORT_BODY_CLASS}`}>{CASE_STUDIES_INTRO}</p>
      {cards.length === 0 ? (
        pending
      ) : (
        // Each case study in its own ruled card (owner, round 11, reversing
        // round 10's ruled entries).
        <ul role="list" className={REPORT_CARD_LIST_CLASS}>
          {cards.map((card, at) => {
            const { strength, design, sinceYear } = cardEvidenceMeta(card);
            return (
              <li key={`${at}:${card.title}`} className={`${REPORT_CARD_CLASS} ${live ? "anim-rise" : ""}`}>
                <CardHeading className="text-lead font-bold text-navy max-md:text-body">{scrub(card.title)}</CardHeading>
                {/* The marks line under the title (owner, round 14): type,
                    strength, then "Since 2019"; it arrives with the
                    committed report. */}
                {!live && (
                  <EvidenceMarksLine
                    taskId={taskId}
                    sourceId={cardEvidenceSourceId(card, design)}
                    evidenceType={design}
                    strength={strength}
                    facts={sinceYear != null ? [`Since ${sinceYear}`] : []}
                    className={cn("mt-1", arriving)}
                  />
                )}
                <CaseStudyCardProse card={card} onOpenClaim={onOpenClaim} live={live} />
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
  taskId = "",
  onOpenDossier,
  live = false,
  arrivingClass = "",
  level = 3,
}: {
  sources: TopSource[];
  /** The task, for the classification chip's reasoning (committed only). */
  taskId?: string;
  /* Opens by source id: the citation-time title snapshot can drift from the
   * evidence row's title in deployed data, so a title-keyed lookup misses. */
  onOpenDossier?: (sourceId: string) => void;
  live?: boolean;
  arrivingClass?: string;
  level?: SectionHeadingLevel;
}) {
  useScrollWhenNavigated("sources");
  if (sources.length === 0) return null;
  const Heading = level === 3 ? "h3" : "h2";
  return (
    <section id="sources" className="mb-9">
      <Heading className={REPORT_SECTION_HEADING_CLASS}>Most relevant sources</Heading>
      <p className={`mt-1.5 max-w-prose-measure ${REPORT_BODY_CLASS}`}>{MOST_RELEVANT_SOURCES_INTRO}</p>
      {/* In the case studies' ruled card (owner, round 11). */}
      <ul role="list" className={REPORT_CARD_LIST_CLASS}>
        {sources.map((source) => (
          <li key={source.sourceId} className={`${REPORT_CARD_CLASS} ${live ? "anim-rise" : ""}`}>
            <p className={`${REPORT_BODY_CLASS} font-bold`}>
              {live || onOpenDossier === undefined ? (
                scrub(source.title)
              ) : (
                <SourceTitleLink sourceRef={source.sourceId} onOpen={onOpenDossier}>
                  {scrub(source.title)}
                </SourceTitleLink>
              )}
            </p>
            {source.authors != null && source.authors.length > 0 && (
              <p className={`mt-0.5 ${REPORT_BODY_CLASS} ${arrivingClass}`}>
                {source.authors.map((a) => scrub(a)).join(", ")}
              </p>
            )}
            {/* The marks line under the title and authors (owner, round
                14): type, strength, then "Cited by 3 claims". */}
            {!live && (
              <EvidenceMarksLine
                taskId={taskId}
                sourceId={source.sourceId}
                evidenceType={source.evidenceType}
                strength={source.appraisalLabel}
                facts={[source.citationCount === 1 ? "Cited by 1 claim" : `Cited by ${formatCount(source.citationCount)} claims`]}
                className={cn("mt-1", arrivingClass)}
              />
            )}
            {source.note != null && source.note !== "" && (
              <p className={`mt-1 max-w-prose-measure ${REPORT_BODY_CLASS}`}>{scrub(source.note)}</p>
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
 * `?view=` so a link or a refresh keeps it. The public view switches too
 * once the task has a longlist (owner, round 12: a shared scoping task shows
 * its longlist and shortlist), never onto a longlist being built; its views
 * are read-only there.
 */
export function ArtefactView() {
  const { taskId = "" } = useParams();
  const isPublicView = usePublicView();
  const task = useTask(taskId);
  const stream = useRunStream(taskId);
  // While a longlist walk runs the Result is the longlist being built
  // (task 058, N24), before and after the longlist read first answers.
  const building = !isPublicView && isLonglistBuilding(task.data, stream.stages);
  // A theory of change is public like the Result tab (C17): the graph and its
  // evidence are on the public read leg.
  if (isToc(task.data)) return <TocResult taskId={taskId} />;
  // The report's expand state is the task's, kept while the reader moves
  // between its tabs (owner, round 12).
  return (
    <ReportExpandScope taskId={taskId}>
      {!hasLonglist(task.data) && !building ? (
        <ArtefactReport />
      ) : (
        <ScopingResult taskId={taskId} building={building} />
      )}
    </ReportExpandScope>
  );
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
        {/* The tab language of the whole app (round 10, finding 3): the
            growing rule, one line on a phone (scrolling sideways if it must),
            and a view still to come locked as a lifecycle stage is, with no
            note beside it (C3). */}
        <TabsList aria-label="Result view" className="overflow-x-auto whitespace-nowrap [scrollbar-width:none]">
          {RESULT_VIEWS.map((option) => (
            <TabsTrigger
              key={option.key}
              value={option.key}
              disabled={option.note !== undefined}
              className={cn(
                "mb-0 shrink-0 border-b-[3px] pb-2 data-[state=active]:border-transparent",
                GROWING_RULE_CLASS,
                "data-[state=active]:after:scale-x-100 data-[state=active]:hover:after:scale-x-100 data-[state=active]:focus-visible:after:scale-x-100",
                "disabled:cursor-not-allowed disabled:text-line-2 disabled:hover:text-line-2 disabled:after:hidden",
              )}
            >
              {option.label}
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
  // Cited-scoped distributions for the facts line: the years count what the
  // report CITES, not the whole included corpus (owner, 2026-08-05); the
  // durable coverage_snapshot keeps the corpus-wide counts. The same read
  // says whether the method section renders.
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
  // The title is the refined research question from the plan (owner, round
  // 14), live and committed; the task's question when the plan has none. The
  // plan read is not on the public surface, so a public link reads the
  // task's question.
  const plan = usePlan(isPublicView ? "" : taskId);
  const question =
    nonEmpty(plan.data?.plan?.question) ?? task.data?.question ?? stream.task.question ?? task.data?.name ?? null;
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
  // A claim named in the address (`?claim=`) is the sheet a source was
  // opened from: the dossier's "Back to the claim" and the browser's Back
  // return to it (owner, round 13).
  const claimParam = searchParams.get("claim");
  const committedSections = artefact.data?.sections as SectionLike[] | undefined;
  const claimFromAddress =
    dossierSource === null && claimParam !== null ? committedClaim(committedSections, claimParam) : null;
  const shownClaim =
    detailClaim?.live === true && !(showLive || readyHere) && artefact.data != null
      ? (committedClaim(committedSections, detailClaim.claim_id) ?? detailClaim)
      : (detailClaim ?? claimFromAddress);
  const openDossierFromClaim = (sourceRef: string, claimId: string) => {
    setDetailClaim(null);
    // The entry the reader leaves names the claim, so Back returns to its
    // sheet; then the source opens on a new entry that keeps the claim.
    const here = new URLSearchParams(window.location.search);
    here.set("claim", claimId);
    history.replaceState(history.state, "", `${window.location.pathname}?${here.toString()}${window.location.hash}`);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("claim", claimId);
      next.set("source", sourceRef);
      next.delete("option");
      return next;
    });
  };
  const closeClaim = () => {
    setDetailClaim(null);
    if (claimParam !== null) {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.delete("claim");
          return next;
        },
        { replace: true },
      );
    }
  };
  const claimPanel = (
    <ClaimPanel
      key="claim-panel"
      taskId={taskId}
      claim={shownClaim}
      onClose={closeClaim}
      onOpenDossier={(sourceRef) =>
        shownClaim !== null && shownClaim.live !== true
          ? openDossierFromClaim(sourceRef, shownClaim.claim_id)
          : (setDetailClaim(null), openDossier(sourceRef))
      }
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
    // The reader is watching the report being written: the committed report
    // opens with every section open (owner, round 12). Seeded before the
    // sections render, in this same pass.
    seedReportExpanded(taskId);
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
  // The baseline opens at its top with focus on its title (round 13, as the
  // Longlist and Shortlist do), so switching to it never keeps the
  // longlist's scroll offset. Not the report, and not a baseline the reader
  // watched being written: there the reading place is kept.
  const baselineTitle = useRef<HTMLHeadingElement>(null);
  useOpenAtTop(baselineTitle, "baseline");
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
      next.delete("claim");
      return next;
    });
  };
  // Back to the claim's sheet, in place of the source (owner, round 13).
  const backToClaim = () => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete("source");
        next.delete("option");
        return next;
      },
      { replace: true },
    );
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
  // The years count the CITED set (the live cited-scope landscape), not the
  // whole included corpus.
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

  // The facts line (round 10, finding 2 and C4): Sources and Published;
  // the study types are the method section's, not repeated here, and the
  // date has its own line under the title (owner, round 11). The sources
  // count opens this page's References (owner, round 11, replacing the
  // Sources tab's cited filter of 028 F.5), when the report has any.
  const facts: ReportFact[] = [];
  if (typeof snapshot?.source_count === "number" && typeof snapshot?.included === "number") {
    // Transcription trap 3: `source_count` is the cited/reference count —
    // never "found".
    facts.push([
      "Sources",
      `${formatCount(snapshot.source_count)} cited out of ${formatCount(snapshot.included)} included`,
      (data.references ?? []).length > 0 ? "#references" : null,
    ]);
  }
  if (citedYears.length > 0) {
    const from = Math.min(...citedYears);
    const to = Math.max(...citedYears);
    facts.push(["Published", from === to ? String(from) : `${from}–${to}`, null]);
  }
  // The report states when it was made. The run's end is the honest answer —
  // the artefact read model carries no timestamp of its own. There is
  // deliberately no author line: the backend has no author for an artefact,
  // and inventing one would have the report assert something nobody wrote.
  const lastUpdated = task.data?.latest_run?.ended_at;

  const topSources = mergeMostRelevantNotes(
    mostRelevantSources(sections),
    (data.most_relevant_notes ?? []) as Array<{ source_id: string; note: string }>,
  );

  const roadmapText = fullReportIntro(bodySections.length, data.full_report_intro);

  // A baseline is one linear profile, not a summary over a full report: the
  // two part headings would frame an empty half (it mints no key findings and
  // no case studies), so the outline lists its sections flat.
  // Titles in full: the sidebar wraps them (round 10, finding 6); a
  // server `nav_label` still wins.
  const outlineHead: SidebarEntry[] = baseline
    ? sections.map((section, index) => ({
        id: sectionAnchor(section.title, index),
        title: sectionNavLabel(section, Infinity),
      }))
    : [
        { kind: "part", id: EXECUTIVE_SUMMARY_ANCHOR, title: "Executive summary" },
        ...frontSections.map(({ section, index }) => ({
          id: sectionAnchor(section.title, index),
          title: sectionNavLabel(section, Infinity),
        })),
        // The last part of the executive summary (owner, round 11, reversing
        // round 10's D2).
        ...(topSources.length > 0 ? [{ id: "sources", title: "Most relevant sources" }] : []),
        ...(bodySections.length > 0
          ? [{ kind: "part" as const, id: FULL_REPORT_ANCHOR, title: "Full report" }]
          : []),
        ...bodySections.map(({ section, index }) => ({
          id: sectionAnchor(section.title, index),
          title: sectionNavLabel(section, Infinity),
        })),
      ];
  const outlineEntries: SidebarEntry[] = [
    ...outlineHead,
    ...((data.references ?? []).length > 0 ? [{ id: "references", title: "References" }] : []),
    // Listed only when the section will render (round 10, finding 6), under
    // its heading's own words (C2).
    ...(gatheredSectionShows(citedLandscape) ? [{ id: "gathered", title: GATHERED_SECTION_TITLE }] : []),
  ];
  // Sections inside a part are h3; a baseline has no parts (round 10).
  const level: SectionHeadingLevel = baseline ? 2 : 3;

  const sectionBlocks = (section: SectionLike) => (
    <SectionBody blocks={section.blocks ?? []} onOpenClaim={setDetailClaim} />
  );
  const renderSection = ({ section, index }: { section: SectionLike; index: number }) => {
    const id = sectionAnchor(section.title, index);
    return section.role === "case_studies" ? (
      <CaseStudiesSection
        key={`section:${id}`}
        section={section}
        id={id}
        taskId={taskId}
        onOpenClaim={setDetailClaim}
        level={level}
      />
    ) : (
      <SectionDisclosure
        key={`section:${id}`}
        id={id}
        section={section as OutlineSection}
        collapsible={section.role !== "key_findings"}
        defaultOpen={false}
        arrivingClass={arriving}
        level={level}
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
                <ArtefactDownload artefact={data} question={baseline ? null : question} />
              </span>
            </ReportKindRow>
            {/* A report's title is its question, live and committed, so the
                heading never changes at the swap; the generated title names
                the download (round 10, D1). A baseline keeps its own title
                ("Do nothing: …"), which says what the profile is. */}
            <h1
              ref={baseline && !swap.swapped ? baselineTitle : undefined}
              tabIndex={baseline ? -1 : undefined}
              className={cn(REPORT_TITLE_CLASS, baseline && "outline-none")}
            >
              {scrub(baseline ? data.title : (question ?? data.title))}
            </h1>
            {/* The date on its own line under the title (owner, round 11). */}
            {lastUpdated != null && (
              <p className={cn(REPORT_DATELINE_CLASS, arriving)}>
                Last updated <time dateTime={lastUpdated}>{formatDate(lastUpdated, "long")}</time>
              </p>
            )}
            {/* One action line under the title, then the facts (round 10,
                finding 9). */}
            {!isPublicView && (
              <div className={REPORT_ACTIONS_CLASS}>
                <SeePlanLink onClick={planPanel.openPlan} />
                <button
                  type="button"
                  onClick={askAboutAnalysis}
                  disabled={!chatsEnabled}
                  title={chatsEnabled ? undefined : COPY.newChatUnavailable}
                  className={cn(LINK_CLASS, "text-meta", arriving)}
                >
                  Ask about this analysis
                </button>
              </div>
            )}
            <div className={arriving}>
              <ReportFacts facts={facts} />
            </div>
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

          /* The executive summary's last part, above the Full report (owner,
             round 11, reversing round 10's D2). A baseline writes no
             most-relevant-source notes and cites few sources per section,
             so the report's "cited most often" block would rank two or
             three documents as if that were a finding. Report only (task
             044). */
          <div key="most-relevant" className={swap.hadNotes ? "" : arriving}>
            {baseline ? null : (
              <MostRelevantSources
                sources={topSources}
                taskId={taskId}
                onOpenDossier={openDossier}
                arrivingClass={swap.hadNotes ? arriving : ""}
                level={level}
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
              onBack={claimParam !== null ? backToClaim : undefined}
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
 *  details in place.
 *
 *  Each reference is one entry in a citation form (round 10, C5): "Sampleton
 *  A, Mockford C (2022). Title. Venue. doi.org/…", the number in a Grey
 *  column, the title a link to its dossier, the address a Grey link without
 *  its scheme on screen and in full in print, so the list carries a source
 *  out of the workspace. A reference with no authors starts at its title. */
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
    url?: string | null;
    authorships?: components["schemas"]["AuthorshipOut"][];
  }>;
  /** Absent while the report is live: the titles are not links yet. */
  onOpenReference?: (title: string) => void;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useRememberedOpen("references", defaultOpen);
  const arriving = useArrivingClass();
  useOpenWhenNavigated("references", setOpen);
  useExpandForPrint(setOpen);
  useExpandAll(setOpen);
  return (
    <section aria-label="References" id="references" className="mt-12 border-t border-line pt-6">
      <DisclosureHeading level={2} open={open} onToggle={() => setOpen((value) => !value)}>
        References
      </DisclosureHeading>
      {!open && (
        <p className="mt-1.5 text-lead text-grey max-md:text-body">
          {references.length === 1 ? "1 numbered source" : `${references.length} numbered sources`} cited
          in this report
        </p>
      )}
      {!open && <MobileDisclosureToggle expanded={false} onToggle={() => setOpen(true)} />}
      {open && (
        <ol className="mt-3 space-y-2 text-body text-ink">
          {references.map((reference) => (
            <li key={reference.n} className="flex gap-3">
              {/* The number opens the source's sheet, in Electric Blue
                  (owner, round 14); while the report is written it is
                  the number alone. */}
              {onOpenReference !== undefined ? (
                <button
                  type="button"
                  onClick={() => onOpenReference(reference.title)}
                  aria-label={`Source ${reference.n}: ${scrub(reference.title)}`}
                  className="w-9 shrink-0 cursor-pointer self-start text-right font-semibold tabular-nums text-blue hover:underline"
                >
                  [{reference.n}]
                </button>
              ) : (
                <span className="w-9 shrink-0 text-right font-semibold tabular-nums text-grey">[{reference.n}]</span>
              )}
              <ReferenceEntry reference={reference} onOpen={onOpenReference} arrivingClass={arriving} />
            </li>
          ))}
        </ol>
      )}
      {open && <MobileDisclosureToggle expanded onToggle={() => setOpen(false)} />}
    </section>
  );
}

/** One reference in the list's citation form. While the report is live it
 *  is the title alone, not a link; the committed report adds the authors
 *  and year before it and the venue and address after it, fading in. */
function ReferenceEntry({
  reference,
  onOpen,
  arrivingClass,
}: {
  reference: {
    title: string;
    year?: number | null;
    venue?: string | null;
    url?: string | null;
    authorships?: components["schemas"]["AuthorshipOut"][];
  };
  onOpen?: (title: string) => void;
  arrivingClass: string;
}) {
  const committed = onOpen !== undefined;
  // The parts the Markdown download writes too (`referenceParts`); while the
  // report is live the entry is its title alone.
  const parts = referenceParts(reference);
  const lead = committed && parts.lead !== null ? scrub(parts.lead) : null;
  const afterTitle = parts.afterTitle;
  const venue = committed ? parts.venue : null;
  const url = committed ? parts.url : null;
  const title = scrub(reference.title);
  return (
    <span className="min-w-0 [overflow-wrap:anywhere]">
      {lead !== null && <span className={arrivingClass}>{lead}</span>}
      {committed ? (
        <SourceTitleLink sourceRef={reference.title} onOpen={onOpen}>
          {title}
        </SourceTitleLink>
      ) : (
        <span>{title}</span>
      )}
      {committed && (
        <span className={arrivingClass}>
          {afterTitle}
          {venue !== null && <span className="text-grey"> {scrub(venue)}</span>}
          {url !== null && (
            <>
              {" "}
              <ReferenceUrl url={url} printFull />
            </>
          )}
        </span>
      )}
    </span>
  );
}

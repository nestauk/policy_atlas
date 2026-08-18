import { Fragment, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/queries";
import { conflictSentences, isConflictCode } from "../../../lib/errors";
import { scrub } from "../../../lib/scrub";
import type { ChatConversationRow } from "../../../store";
import { Button } from "../../../ui/brand/Button";
import { Chip } from "../../../ui/brand/Chip";
import { Tooltip } from "../../../ui/radix/Tooltip";
import {
  AppraisalChip,
  CITATION_MARKER_CLASS,
  CITATION_SPAN_CLASS,
  ChipWithTooltip,
  CitationProvenanceBlock,
  CitationTooltipBody,
  ProvenanceSheet,
  SourceDossier,
  spanSegments,
  TIER_LABEL,
  TIER_TEXT,
} from "../../ArtefactView";

interface ChatCitation {
  id?: string;
  chunk_id?: string;
  citation_id?: string;
  n?: number;
  quote?: string;
  source_title?: string;
  source_id?: string;
  title?: string;
  state?: string;
  // 030 fold: named exactly as the artefact read model's `CitationOut` — the
  // persist-time fields another 029 strand writes onto `answer_payload`'s
  // citation dicts. `quote_snapped` needs no UI treatment yet (just
  // tolerated); the appraisal pair feeds the sheet's citation-block chip
  // (parity with `ArtefactView.CitationContext` — see `AppraisalChip`).
  appraisal_label?: string;
  evidence_type?: string;
  quote_snapped?: boolean;
}

// The wire shape is `answer_payload.claims[]`: loose (typed as
// `{[key: string]: unknown}[]` in ChatTurnOut) but the fields chat_floor.py /
// chat_enrichment.py actually write are stable — text, span (character
// offsets into `answer`, same Python code-POINT convention the report's
// ClaimOut.span uses — see ArtefactView.spanSegments), citation_ns (a claim
// references citations by NUMBER, matching CitationOut.n), verdict/rationale
// once the judge has run, and a `derived` flag for sentence-grain claims the
// floor synthesised for an otherwise-uncovered marker occurrence (029 strand
// — these carry citation-worthy text too and are matched the same way).
interface ChatClaim {
  claim_id?: string;
  text?: string;
  span?: [number, number] | null;
  citation_ns?: number[];
  citation_ids?: string[];
  citations?: string[];
  verdict?: string;
  grounding_tier?: string;
  rationale?: string;
  weakly_grounded?: boolean;
  derived?: boolean;
}

/** Either sheet-opening path (030 fold): a citation click (inline marker,
 *  References row) is citation-keyed — the claim(s) citing it, stacked, over
 *  that one citation; a claim-span click is claim-keyed — that one claim,
 *  over every citation it carries. */
type ActiveProvenance =
  | { kind: "citation"; turn: ChatConversationRow; citation: ChatCitation }
  | { kind: "claim"; turn: ChatConversationRow; claim: ChatClaim };

/** Plain-prose chat thread with citations and durable honesty states.
 *
 * Args:
 *   props: Project-scoped transcript rows and planning hand-off callback.
 *
 * Returns:
 *   User bubbles, assistant prose, and citation affordances.
 */
export function ChatMessages({ projectId, rows, onOpenPlanning, onRetry }: { projectId: string; rows: ChatConversationRow[]; onOpenPlanning: () => void; onRetry: (clientTurnId: string) => void }) {
  const [active, setActive] = useState<ActiveProvenance | null>(null);
  const [dossierRef, setDossierRef] = useState<string | null>(null);
  const datedRows = useMemo(() => rows.map((row, index) => ({ row, showDate: index === 0 || dayOf(createdAt(row)) !== dayOf(createdAt(rows[index - 1])) })), [rows]);
  return <div className="space-y-5">{datedRows.map(({ row, showDate }) => <div key={keyOf(row)} className="space-y-3">{showDate && <DateDivider value={createdAt(row)} />}<UserBubble text={userMessageOf(row)} />{activityOf(row).length > 0 && <p className="mr-8 text-body text-grey">{activitySummary(activityOf(row))}</p>}<AssistantMessage turn={row} onCitation={(citation) => setActive({ kind: "citation", turn: row, citation })} onClaim={(claim) => setActive({ kind: "claim", turn: row, claim })} onOpenDossier={setDossierRef} onOpenPlanning={onOpenPlanning} onRetry={onRetry} /></div>)}{active !== null && <ChatProvenanceSheet projectId={projectId} active={active} onClose={() => setActive(null)} onOpenDossier={setDossierRef} />}{dossierRef !== null && <SourceDossier projectId={projectId} sourceRef={dossierRef} onClose={() => setDossierRef(null)} />}</div>;
}

function AssistantMessage({ turn, onCitation, onClaim, onOpenDossier, onOpenPlanning, onRetry }: { turn: ChatConversationRow; onCitation: (citation: ChatCitation) => void; onClaim: (claim: ChatClaim) => void; onOpenDossier: (sourceRef: string) => void; onOpenPlanning: () => void; onRetry: (clientTurnId: string) => void }) {
  const answer = "id" in turn ? turn.answer ?? "" : turn.answer;
  const citations = citationsOf(turn);
  const claims = claimsOf(turn);
  const cancelled = turn.status === "cancelled";
  const failed = turn.status === "failed";
  const warning = "id" in turn && turn.warning_not_evidence_checked;
  const handoff = "id" in turn && turn.handoff === "evidence_not_held";
  const copy = async () => { await navigator.clipboard?.writeText(copyText(answer, citations, turn)); };
  // A failed turn still renders honestly (contract rubric: pending/failed
  // rows stay visibly honest) — any partial prose received before the
  // failure, a short plain-language reason, and a way to try again. Never
  // silence into the blank the caller sees when there's simply no answer.
  if (failed) {
    const code = errorCodeOf(turn);
    const message = isConflictCode(code) ? conflictSentences[code] : "This answer failed.";
    return <div className="mr-8 space-y-2">
      {answer && <p className="max-w-[52ch] whitespace-pre-wrap text-body leading-relaxed text-ink"><AnnotatedChatProse text={answer} citations={citations} claims={claims} turn={turn} disabled onCitation={onCitation} onClaim={onClaim} /></p>}
      <p role="alert" className="text-body text-red">{message}</p>
      <Button size="sm" variant="secondary" onClick={() => onRetry(clientTurnIdOf(turn))}>Retry</Button>
    </div>;
  }
  if (!answer && !("id" in turn && turn.status === "pending")) return null;
  return <div className="mr-8 space-y-2"><p className="max-w-[52ch] whitespace-pre-wrap text-body leading-relaxed text-ink"><AnnotatedChatProse text={answer} citations={citations} claims={claims} turn={turn} disabled={cancelled} onCitation={onCitation} onClaim={onClaim} /></p>{"id" in turn && turn.status === "pending" && <p role="status" className="animate-pulse text-body text-grey">Checking the evidence…</p>}{cancelled && <Chip tone="yellow">Stopped before evidence check</Chip>}{warning && <Chip tone="yellow">Not evidence-checked</Chip>}{handoff && <div className="border-l-2 border-yellow bg-yellow-tint/50 p-3 text-body text-navy">The evidence base does not hold this.<Button size="sm" variant="secondary" className="ml-2" onClick={onOpenPlanning}>Open planning</Button></div>}{citations.length > 0 && <References citations={citations} turn={turn} onCitation={onCitation} onOpenDossier={onOpenDossier} />}{answer && <button type="button" aria-label="Copy answer" title="Copy answer" onClick={() => void copy()} className="text-grey hover:text-blue"><svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="5" y="5" width="9" height="10" rx="1" /><path d="M11 5V3a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h2" /></svg></button>}</div>;
}

/** The prose's annotation layer (029 Fix C + 030 fold): span-anchored claims
 *  wrap their exact prose span in the report's own citation-marker treatment
 *  (`ArtefactView.CITATION_SPAN_CLASS` — chat claims are never typed beyond
 *  "citation" for display, per the fold's design), with the report-shaped
 *  title/quote/verdict preview Tooltip on hover (`citationTooltipBody`) and a
 *  click/Enter/Space opening the claim-oriented provenance sheet for THAT
 *  claim's citations. The literal `[n]` marker text keeps rendering as its
 *  own small boxed-chip button (`ArtefactView.CITATION_MARKER_CLASS`) — same
 *  class, same Tooltip preview — wherever it falls (inside or outside a
 *  claim's span), and keeps opening the citation-oriented sheet (a marker's
 *  click stops propagation so a marker nested inside a clickable claim span
 *  never also fires the span's own click). Overlapping/unspanned claims fall
 *  back to marker-only behaviour for those regions — `spanSegments` never
 *  invents a merge. A cancelled turn carries no annotation at all: markers
 *  stay inert (disabled, no tooltip), matching today. */
function AnnotatedChatProse({ text, citations, claims, turn, disabled, onCitation, onClaim }: { text: string; citations: ChatCitation[]; claims: ChatClaim[]; turn: ChatConversationRow; disabled: boolean; onCitation: (citation: ChatCitation) => void; onClaim: (claim: ChatClaim) => void }) {
  // Delta-review Fix 2: an uncited claim (no citation_ns/citation_ids/
  // citations at all — valid uncited reasoning) carries no provenance to
  // show, so it must not wear the provenance affordance either. Filtering it
  // out of spanSegments' input renders it as ordinary plain-segment prose —
  // the same honest-absence treatment the report reader gives its own
  // UNMARKED_TYPES reasoning claims.
  const segments = useMemo(() => {
    const citedClaims = disabled ? [] : claims.filter(claimHasCitations);
    return spanSegments(text, citedClaims);
  }, [text, claims, disabled]);
  return <>{segments.map((segment, index) => {
    const { nodes: marked, hasMarker } = markedTextParts(segment.text, citations, turn, disabled, onCitation);
    if (segment.kind === "plain") return <Fragment key={index}>{marked}</Fragment>;
    const claimCitations = citationsForClaim(citations, segment.claim);
    const tip = claimCitations.length > 0 ? citationTooltipBody(turn, claimCitations[0]) : null;
    const span = (
      <span
        role="button"
        tabIndex={0}
        onClick={() => onClaim(segment.claim)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onClaim(segment.claim);
          }
        }}
        className={CITATION_SPAN_CLASS}
      >
        {marked}
      </span>
    );
    // Delta-review Fix 1: when the segment's own rendered parts include a
    // resolved `[n]` marker, that marker carries its own hover preview
    // already — wrapping the enclosing claim span in a second Tooltip stacks
    // two Radix roots open on the same pointer-move batch (empirically two
    // panels, byte-identical in the single-citation case). Only claim spans
    // with NO marker inside them still show the span-level preview.
    return !hasMarker && tip !== null ? <Tooltip key={index} content={tip}>{span}</Tooltip> : <Fragment key={index}>{span}</Fragment>;
  })}</>;
}

/** A claim carries provenance worth marking iff it names at least one
 *  citation, by any of the wire's shapes (029 Fix C / 030 fold: the live
 *  shape is `citation_ns`; `citation_ids`/`citations` are the older/
 *  alternate id shapes `claimsCiting`/`citationsForClaim` also tolerate). */
function claimHasCitations(claim: ChatClaim): boolean {
  return (
    (Array.isArray(claim.citation_ns) && claim.citation_ns.length > 0) ||
    (Array.isArray(claim.citation_ids) && claim.citation_ids.length > 0) ||
    (Array.isArray(claim.citations) && claim.citations.length > 0)
  );
}

/** Split one prose segment on literal `[n]` markers into the small marker
 *  button — the report's boxed-chip class (030 parity fold; a muted
 *  `disabled:` variant for a cancelled turn) — + title/quote/verdict preview
 *  Tooltip (029 Fix C, 030 parity fold) — unchanged whether the segment is
 *  plain text or the inside of a claim span. Also reports whether it rendered
 *  at least one resolved marker (delta-review Fix 1: the caller uses that to
 *  decide whether the enclosing claim span still needs its own Tooltip). */
function markedTextParts(text: string, citations: ChatCitation[], turn: ChatConversationRow, disabled: boolean, onCitation: (citation: ChatCitation) => void): { nodes: React.ReactNode[]; hasMarker: boolean } {
  const parts = text.split(/(\[\d+\])/g);
  let hasMarker = false;
  const nodes = parts.map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    const citation = match === null ? null : resolveCitation(citations, Number(match[1]));
    if (citation === null) return <span key={index}>{scrub(part)}</span>;
    hasMarker = true;
    const marker = (
      <button
        type="button"
        disabled={disabled}
        onClick={(event) => { event.stopPropagation(); onCitation(citation); }}
        // Delta-review Fix 3: the click handler's stopPropagation only covers
        // the pointer path — a keyboard Enter/Space on a focused nested
        // marker fires a `keydown` that still bubbles to the enclosing claim
        // span's own `role=button` handler, opening the CLAIM sheet instead
        // of this marker's citation sheet. Stop it here too; the button's own
        // native Enter/Space activation still fires `onClick` above.
        onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") event.stopPropagation(); }}
        className={CITATION_MARKER_CLASS}
      >
        {part}
      </button>
    );
    return disabled ? <span key={index}>{marker}</span> : <Tooltip key={index} content={citationTooltipBody(turn, citation)}>{marker}</Tooltip>;
  });
  return { nodes, hasMarker };
}

/** Delta-review Fix 4: resolve a literal `[n]` marker's citation the same way
 *  every other lookup on this page keys citations — by `citation.n` — rather
 *  than the array's position. Falls back to the positional read only when no
 *  citation carries a matching `n` (an older/looser payload shape), so a
 *  reordered or gapped `citations` array (e.g. one dropped as
 *  invalid/malformed upstream) still resolves the right source instead of a
 *  neighbour's. */
function resolveCitation(citations: ChatCitation[], n: number): ChatCitation | null {
  const byNumber = citations.find((citation) => citation.n === n);
  if (byNumber !== undefined) return byNumber;
  const positional = citations[n - 1];
  return positional !== undefined ? positional : null;
}

// 029 Fix D: collapsed by default — no dedicated Collapsible/Accordion
// component exists under ui/ yet, so a native <details> gives keyboard
// support (Enter/Space on the summary) for free, styled to the footer's
// existing caption typography.
function References({ citations, turn, onCitation, onOpenDossier }: { citations: ChatCitation[]; turn: ChatConversationRow; onCitation: (citation: ChatCitation) => void; onOpenDossier: (sourceRef: string) => void }) {
  return <footer className="border-t border-line pt-2"><details><summary className="cursor-pointer text-caption font-bold uppercase tracking-[0.06em] text-grey">References ({citations.length})</summary><div className="mt-2 space-y-2">{citations.map((citation, index) => {
    const sourceRef = citation.source_id ?? citation.source_title ?? null;
    const titleText = scrub(citation.source_title ?? citation.title ?? citationId(citation) ?? "Citation");
    return <div key={citationId(citation) || index} className="text-caption text-ink"><button type="button" onClick={() => onCitation(citation)} className={CITATION_MARKER_CLASS}>[{citation.n ?? index + 1}]</button>{" "}
      {sourceRef !== null
        ? <button type="button" onClick={() => onOpenDossier(sourceRef)} className="cursor-pointer text-left font-semibold hover:underline">{titleText}</button>
        : <span>{titleText}</span>}
      {citation.quote && <span className="text-grey"> — “{scrub(citation.quote)}”</span>}
      <span className="ml-2"><VerdictChip turn={turn} citation={citation} /></span>
    </div>;
  })}</div></details></footer>;
}

/** The judge verdict chip + rationale tooltip (029 Fix B), over the shared
 *  `ChipWithTooltip` (030 fold) — chat's own tone/label vocabulary (the
 *  verdict tier only; the citation's appraisal pair, when present, renders
 *  as its own separate `AppraisalChip` — sheet only, see `ChatCitationBlock`).
 *  Shared by the References row and the citation sheet so there is exactly
 *  one copy. */
function VerdictChip({ turn, citation }: { turn: ChatConversationRow; citation: ChatCitation }) {
  const { tier } = verdictInfoFor(turn, citation);
  const checkFailed = enrichmentStatusOf(turn) === "failed";
  const uncheckedLabel = checkFailed ? "Unchecked · check unavailable" : "Unchecked · awaiting evidence check";
  return <ChipWithTooltip tone={tier === "unsupported_mis_cited" ? "red" : tier === null ? "soft" : "blue"} label={tier === null ? uncheckedLabel : TIER_LABEL[tier]} content={verdictTooltipContent(turn, citation)} />;
}

/** The rationale/hint body shared by `VerdictChip` and the inline marker's
 *  hover (Fix C) — a Tooltip's `content`, never a chip of its own. */
function verdictTooltipContent(turn: ChatConversationRow, citation: ChatCitation) {
  const { tier, rationale } = verdictInfoFor(turn, citation);
  const checkFailed = enrichmentStatusOf(turn) === "failed";
  const uncheckedHint = checkFailed ? "The evidence check could not run for this answer" : "Awaiting evidence check";
  return <div className="max-w-[280px] space-y-1 text-caption"><p>{tier === null ? uncheckedHint : TIER_TEXT[tier]}</p>{rationale !== null && <p className="text-grey">Judge: {scrub(rationale)}</p>}</div>;
}

/** The claim-span hover and the bare `[n]` marker hover's shared preview
 *  (030 parity fold, mirroring ArtefactView's `ClaimSpan` tip exactly):
 *  the citation's source title · its quote excerpt (180-char clamp) · then
 *  chat's own verdict line (`verdictTooltipContent` — enriched tier + judge
 *  rationale, or the Unchecked/check-unavailable wording) — over the
 *  report's shared `CitationTooltipBody` shell so the two surfaces can never
 *  drift apart. */
function citationTooltipBody(turn: ChatConversationRow, citation: ChatCitation) {
  // Hover content policy is the shared component's (tier label only, no
  // rationale) — the judge rationale shows in the sheet's VerdictChip
  // tooltip, exactly where the report shows its own.
  const { tier } = verdictInfoFor(turn, citation);
  const checkFailed = enrichmentStatusOf(turn) === "failed";
  const statusLine =
    tier !== null
      ? TIER_LABEL[tier]
      : checkFailed
        ? "Unchecked · check unavailable"
        : "Unchecked · awaiting evidence check";
  return (
    <CitationTooltipBody
      sourceTitle={citation.source_title ?? citation.title ?? citationId(citation) ?? "Citation"}
      quote={citation.quote ?? ""}
      statusLine={statusLine}
    />
  );
}

function enrichmentStatusOf(turn: ChatConversationRow): string | null {
  if (!("id" in turn)) return null;
  const enrichment = (turn as Record<string, unknown>).enrichment;
  if (enrichment !== null && typeof enrichment === "object") {
    const status = (enrichment as Record<string, unknown>).status;
    return typeof status === "string" ? status : null;
  }
  return null;
}

/** One citation's chunk-keyed context, on demand (029 Fix A). A 404 here is
 *  the designed honest-absence outcome — the model's quote is non-verbatim
 *  and the exact passage search came up empty (see 029
 *  verification.md § Known unverified items) — never a transient failure to
 *  retry into a multi-second "Loading…" storm. `staleTime` means re-opening
 *  the same citation's sheet doesn't refetch it. */
function useChatChunkContext(projectId: string, citation: ChatCitation | null) {
  const client = useApiClient();
  const chunkId = citation?.chunk_id ?? citation?.id ?? citation?.citation_id ?? "";
  const quote = citation?.quote ?? "";
  return useQuery({
    queryKey: ["projects", projectId, "chat-chunk-context", chunkId, quote],
    enabled: citation !== null && chunkId !== "" && quote !== "",
    retry: false,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/projects/{project_id}/chunks/{chunk_id}/context", { params: { path: { project_id: projectId, chunk_id: chunkId }, query: { quote } } });
      if (data === undefined) throw error;
      return data;
    },
  });
}

/** The click rung (029 Fix B, composed over the report's shared shell for
 *  030): either a citation-keyed open (inline marker, References row — the
 *  claim(s) citing that one citation, stacked, over its one provenance
 *  block) or a claim-keyed open (a claim span — that one claim, over every
 *  citation it carries). Replaces the old sticky `CitationPopover`/bespoke
 *  `CitationSheet`. */
function ChatProvenanceSheet({ projectId, active, onClose, onOpenDossier }: { projectId: string; active: ActiveProvenance; onClose: () => void; onOpenDossier: (sourceRef: string) => void }) {
  const allCitations = citationsOf(active.turn);
  const claimTexts =
    active.kind === "citation"
      ? claimsCiting(active.turn, active.citation).map((claim) => claim.text ?? "")
      : [active.claim.text ?? ""];
  const shownCitations = active.kind === "citation" ? [active.citation] : citationsForClaim(allCitations, active.claim);
  return (
    <ProvenanceSheet
      description={active.kind === "claim" ? "Claim provenance" : "Citation provenance"}
      claimTexts={claimTexts}
      onClose={onClose}
    >
      {shownCitations.map((citation, index) => (
        <ChatCitationBlock key={citationId(citation) || index} projectId={projectId} turn={active.turn} citation={citation} onOpenDossier={onOpenDossier} />
      ))}
    </ProvenanceSheet>
  );
}

/** One citation's provenance block within the sheet above — the shared
 *  `CitationProvenanceBlock`, fed this chunk's on-demand context (Fix A), the
 *  verdict chip (Fix B), and — when the field is present — the appraisal
 *  chip in exact parity with the artefact reader's `CitationContext` (030
 *  fold). Absent `appraisal_label` renders no chip (honest absence); this
 *  is the sheet's citation block only — References rows and hover tooltips
 *  don't gain it. */
function ChatCitationBlock({ projectId, turn, citation, onOpenDossier }: { projectId: string; turn: ChatConversationRow; citation: ChatCitation; onOpenDossier: (sourceRef: string) => void }) {
  const context = useChatChunkContext(projectId, citation);
  const sourceRef = citation.source_id ?? citation.source_title ?? null;
  const titleText = citation.source_title ?? citation.title ?? citationId(citation) ?? "Citation";
  return (
    <CitationProvenanceBlock
      n={citation.n ?? null}
      sourceTitle={titleText}
      sourceRef={sourceRef}
      onOpenDossier={onOpenDossier}
      chips={
        <>
          <VerdictChip turn={turn} citation={citation} />
          {citation.appraisal_label !== null && citation.appraisal_label !== undefined && (
            <AppraisalChip label={citation.appraisal_label} evidenceType={citation.evidence_type} />
          )}
        </>
      }
      context={context}
      quote={citation.quote ?? ""}
      fallbackNote="Exact passage not found in the source — showing the cited quote."
    />
  );
}

function UserBubble({ text }: { text: string }) { return <div className="ml-8 border border-blue-tint bg-blue-tint-2 px-3.5 py-2.5"><p className="max-w-prose-measure whitespace-pre-wrap text-body text-ink">{scrub(text)}</p></div>; }
function DateDivider({ value }: { value: string }) { return <div className="flex items-center gap-2 text-caption text-grey"><span className="h-px flex-1 bg-line" />{new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" })}<span className="h-px flex-1 bg-line" /></div>; }
function createdAt(row: ChatConversationRow) { return "id" in row ? row.created_at : row.createdAt; }
function userMessageOf(row: ChatConversationRow) { return "id" in row ? row.user_message : row.userMessage; }
function keyOf(row: ChatConversationRow) { return "id" in row ? row.id : row.clientTurnId; }
function dayOf(value: string) { return new Date(value).toISOString().slice(0, 10); }
function activityOf(row: ChatConversationRow) { return "id" in row ? [] : row.activityLabels; }
function clientTurnIdOf(row: ChatConversationRow) { return "id" in row ? row.client_turn_id : row.clientTurnId; }
// The durable `ChatTurnOut` carries no error fields at all — a failed row
// read back from a refetch degrades to the generic fallback below.
function errorCodeOf(row: ChatConversationRow) { return "id" in row ? undefined : row.errorCode; }
function activitySummary(labels: string[]) { return labels.length === 1 ? labels[0] : `${labels.at(-1) ?? "Checked the evidence"} — ${labels.length} searches`; }
function citationsOf(turn: ChatConversationRow): ChatCitation[] { return "id" in turn && Array.isArray(turn.citations) ? turn.citations.filter((citation) => citation !== null && typeof citation === "object") as ChatCitation[] : []; }
function citationId(citation: ChatCitation) { return citation.id ?? citation.chunk_id ?? citation.citation_id ?? ""; }
function verdictInfoFor(turn: ChatConversationRow, citation: ChatCitation): { tier: string | null; rationale: string | null } {
  const claim = claimFor(turn, citation);
  const rationale = claim !== null && typeof claim.rationale === "string" && claim.rationale !== "" ? claim.rationale : null;
  // The only live shape is `citation.state === "verdict:<tier>"` — the
  // floor's allowlist can never emit a bare `verdict`/`grounding_tier` key
  // on the citation itself, so reading those here only widened what a
  // loosened payload could display. The claim-level fallback below is a
  // distinct, real schema field and stays.
  const fromState = citation.state?.startsWith("verdict:") ? citation.state.slice("verdict:".length) : null;
  if (fromState !== null && TIER_LABEL[fromState]) return { tier: fromState, rationale };
  const value = claim?.verdict ?? claim?.grounding_tier;
  if (typeof value === "string" && TIER_LABEL[value]) return { tier: value, rationale };
  return { tier: null, rationale };
}

// All claims — derived ones included, same as the floor's own coverage pass
// (chat_floor.derive_claims_for_uncovered_citations) — that cite a given
// citation, by number (the live shape) or by id (an older/alternate shape).
function claimsOf(turn: ChatConversationRow): ChatClaim[] {
  if (!("id" in turn)) return [];
  return Array.isArray(turn.claims) ? (turn.claims.filter((claim) => claim !== null && typeof claim === "object") as ChatClaim[]) : [];
}

function claimsCiting(turn: ChatConversationRow, citation: ChatCitation): ChatClaim[] {
  const cid = citationId(citation);
  return claimsOf(turn).filter((claim) => {
    const ns = Array.isArray(claim.citation_ns) ? claim.citation_ns : [];
    if (typeof citation.n === "number" && ns.includes(citation.n)) return true;
    const ids = Array.isArray(claim.citation_ids) ? claim.citation_ids : Array.isArray(claim.citations) ? claim.citations : [];
    return ids.includes(cid);
  });
}

function claimFor(turn: ChatConversationRow, citation: ChatCitation): ChatClaim | null {
  return claimsCiting(turn, citation)[0] ?? null;
}

// The reverse of `claimsCiting`: every citation a given claim cites, by
// number (the live shape) or by id (an older/alternate shape) — feeds a
// claim span's hover preview (its first citation) and its provenance sheet
// (all of them, as CitationProvenanceBlocks).
function citationsForClaim(citations: ChatCitation[], claim: ChatClaim): ChatCitation[] {
  const ns = new Set(Array.isArray(claim.citation_ns) ? claim.citation_ns : []);
  const ids = new Set([...(claim.citation_ids ?? []), ...(claim.citations ?? [])]);
  return citations.filter((citation) => (typeof citation.n === "number" && ns.has(citation.n)) || ids.has(citationId(citation)));
}

function verdictFor(turn: ChatConversationRow, citation: ChatCitation): string | null { return verdictInfoFor(turn, citation).tier; }
function copyText(answer: string, citations: ChatCitation[], turn: ChatConversationRow) { return [answer, ...citations.map((citation, index) => `[${citation.n ?? index + 1}] ${citation.source_title ?? citation.title ?? citationId(citation)}${citation.quote ? ` — ${citation.quote}` : ""} — ${verdictFor(turn, citation) ? TIER_LABEL[verdictFor(turn, citation)!] : "Unchecked"}`)].filter(Boolean).join("\n"); }

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/queries";
import { conflictSentences, isConflictCode } from "../../../lib/errors";
import { scrub } from "../../../lib/scrub";
import type { ChatConversationRow } from "../../../store";
import { Button } from "../../../ui/brand/Button";
import { Chip } from "../../../ui/brand/Chip";
import { Sheet, SheetContent } from "../../../ui/radix/Sheet";
import { Tooltip } from "../../../ui/radix/Tooltip";
import { HighlightedContext, SourceDossier, TIER_LABEL, TIER_TEXT } from "../../ArtefactView";

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
}

// The wire shape is `answer_payload.claims[]`: loose (typed as
// `{[key: string]: unknown}[]` in ChatTurnOut) but the fields chat_floor.py /
// chat_enrichment.py actually write are stable — text, citation_ns (a claim
// references citations by NUMBER, matching CitationOut.n), verdict/rationale
// once the judge has run, and a `derived` flag for sentence-grain claims the
// floor synthesised for an otherwise-uncovered marker occurrence (029 strand
// — these carry citation-worthy text too and are matched the same way).
interface ChatClaim {
  claim_id?: string;
  text?: string;
  citation_ns?: number[];
  citation_ids?: string[];
  citations?: string[];
  verdict?: string;
  grounding_tier?: string;
  rationale?: string;
  weakly_grounded?: boolean;
  derived?: boolean;
}

/** Plain-prose chat thread with citations and durable honesty states.
 *
 * Args:
 *   props: Project-scoped transcript rows and planning hand-off callback.
 *
 * Returns:
 *   User bubbles, assistant prose, and citation affordances.
 */
export function ChatMessages({ projectId, rows, onOpenPlanning, onRetry }: { projectId: string; rows: ChatConversationRow[]; onOpenPlanning: () => void; onRetry: (clientTurnId: string) => void }) {
  // The sheet needs its turn alongside the clicked citation (claim text and
  // verdict both key off the turn's claims[]) — carry the pair together so
  // every opener (inline marker, References row) stays a one-arg callback.
  const [active, setActive] = useState<{ turn: ChatConversationRow; citation: ChatCitation } | null>(null);
  const [dossierRef, setDossierRef] = useState<string | null>(null);
  const datedRows = useMemo(() => rows.map((row, index) => ({ row, showDate: index === 0 || dayOf(createdAt(row)) !== dayOf(createdAt(rows[index - 1])) })), [rows]);
  return <div className="space-y-5">{datedRows.map(({ row, showDate }) => <div key={keyOf(row)} className="space-y-3">{showDate && <DateDivider value={createdAt(row)} />}<UserBubble text={userMessageOf(row)} />{activityOf(row).length > 0 && <p className="mr-8 text-caption text-grey">{activitySummary(activityOf(row))}</p>}<AssistantMessage turn={row} onCitation={(citation) => setActive({ turn: row, citation })} onOpenDossier={setDossierRef} onOpenPlanning={onOpenPlanning} onRetry={onRetry} /></div>)}{active !== null && <CitationSheet projectId={projectId} turn={active.turn} citation={active.citation} onClose={() => setActive(null)} onOpenDossier={setDossierRef} />}{dossierRef !== null && <SourceDossier projectId={projectId} sourceRef={dossierRef} onClose={() => setDossierRef(null)} />}</div>;
}

function AssistantMessage({ turn, onCitation, onOpenDossier, onOpenPlanning, onRetry }: { turn: ChatConversationRow; onCitation: (citation: ChatCitation) => void; onOpenDossier: (sourceRef: string) => void; onOpenPlanning: () => void; onRetry: (clientTurnId: string) => void }) {
  const answer = "id" in turn ? turn.answer ?? "" : turn.answer;
  const citations = citationsOf(turn);
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
      {answer && <p className="max-w-[52ch] whitespace-pre-wrap text-body leading-relaxed text-ink"><CitationProse text={answer} citations={citations} turn={turn} disabled onCitation={onCitation} /></p>}
      <p role="alert" className="text-caption text-red">{message}</p>
      <Button size="sm" variant="secondary" onClick={() => onRetry(clientTurnIdOf(turn))}>Retry</Button>
    </div>;
  }
  if (!answer && !("id" in turn && turn.status === "pending")) return null;
  return <div className="mr-8 space-y-2"><p className="max-w-[52ch] whitespace-pre-wrap text-body leading-relaxed text-ink"><CitationProse text={answer} citations={citations} turn={turn} disabled={cancelled} onCitation={onCitation} /></p>{"id" in turn && turn.status === "pending" && <p role="status" className="animate-pulse text-caption text-grey">Checking the evidence…</p>}{cancelled && <Chip tone="yellow">Stopped before evidence check</Chip>}{warning && <Chip tone="yellow">Not evidence-checked</Chip>}{handoff && <div className="border-l-2 border-yellow bg-yellow-tint/50 p-3 text-caption text-navy">The evidence base does not hold this.<Button size="sm" variant="secondary" className="ml-2" onClick={onOpenPlanning}>Open planning</Button></div>}{citations.length > 0 && <References citations={citations} turn={turn} onCitation={onCitation} onOpenDossier={onOpenDossier} />}{answer && <button type="button" aria-label="Copy answer" title="Copy answer" onClick={() => void copy()} className="text-grey hover:text-blue"><svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="5" y="5" width="9" height="10" rx="1" /><path d="M11 5V3a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h2" /></svg></button>}</div>;
}

/** The prose's inline `[n]` markers (029 Fix C): same `citation-marker` class
 *  the evidence-base reader's citation numbers carry, and the same Tooltip
 *  component previewing the citing claim's verdict — never the full
 *  provenance panel, that is what a click opens (Fix B). A cancelled turn's
 *  markers stay inert (disabled, no tooltip) — the check never ran, so a
 *  hover must not promise a verdict that doesn't exist. */
function CitationProse({ text, citations, turn, disabled, onCitation }: { text: string; citations: ChatCitation[]; turn: ChatConversationRow; disabled: boolean; onCitation: (citation: ChatCitation) => void }) {
  const parts = text.split(/(\[\d+\])/g);
  return <>{parts.map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    const citation = match === null ? null : citations[Number(match[1]) - 1];
    if (citation === null || citation === undefined) return <span key={index}>{scrub(part)}</span>;
    const marker = <button type="button" disabled={disabled} onClick={() => onCitation(citation)} className="citation-marker align-super text-caption font-bold text-blue hover:underline disabled:text-grey">{part}</button>;
    return disabled ? <span key={index}>{marker}</span> : <Tooltip key={index} content={verdictTooltipContent(turn, citation)}>{marker}</Tooltip>;
  })}</>;
}

// 029 Fix D: collapsed by default — no dedicated Collapsible/Accordion
// component exists under ui/ yet, so a native <details> gives keyboard
// support (Enter/Space on the summary) for free, styled to the footer's
// existing caption typography.
function References({ citations, turn, onCitation, onOpenDossier }: { citations: ChatCitation[]; turn: ChatConversationRow; onCitation: (citation: ChatCitation) => void; onOpenDossier: (sourceRef: string) => void }) {
  return <footer className="border-t border-line pt-2"><details><summary className="cursor-pointer text-caption font-bold uppercase tracking-wider text-grey">References ({citations.length})</summary><div className="mt-2 space-y-2">{citations.map((citation, index) => {
    const sourceRef = citation.source_id ?? citation.source_title ?? null;
    const titleText = scrub(citation.source_title ?? citation.title ?? citationId(citation) ?? "Citation");
    return <div key={citationId(citation) || index} className="text-caption text-ink"><button type="button" onClick={() => onCitation(citation)} className="citation-marker font-bold text-blue hover:underline">[{citation.n ?? index + 1}]</button>{" "}
      {sourceRef !== null
        ? <button type="button" onClick={() => onOpenDossier(sourceRef)} className="cursor-pointer text-left font-semibold hover:underline">{titleText}</button>
        : <span>{titleText}</span>}
      {citation.quote && <span className="text-grey"> — “{scrub(citation.quote)}”</span>}
      <span className="ml-2"><VerdictChip turn={turn} citation={citation} /></span>
    </div>;
  })}</div></details></footer>;
}

/** The judge verdict chip + rationale tooltip (029 Fix B): the exact
 *  Tooltip-wrapping-Chip shape ArtefactView's CitationContext uses for its
 *  grounding-tier chip, kept on chat's own tone/label vocabulary (chat has
 *  no appraisal_label on its citations — only the verdict tier). Shared by
 *  the References row and the citation sheet so there is exactly one copy. */
function VerdictChip({ turn, citation }: { turn: ChatConversationRow; citation: ChatCitation }) {
  const { tier } = verdictInfoFor(turn, citation);
  const checkFailed = enrichmentStatusOf(turn) === "failed";
  const uncheckedLabel = checkFailed ? "Unchecked · check unavailable" : "Unchecked · awaiting evidence check";
  return <Tooltip content={verdictTooltipContent(turn, citation)}><span><Chip tone={tier === "unsupported_mis_cited" ? "red" : tier === null ? "soft" : "blue"}>{tier === null ? uncheckedLabel : TIER_LABEL[tier]}</Chip></span></Tooltip>;
}

/** The rationale/hint body shared by `VerdictChip` and the inline marker's
 *  hover (Fix C) — a Tooltip's `content`, never a chip of its own. */
function verdictTooltipContent(turn: ChatConversationRow, citation: ChatCitation) {
  const { tier, rationale } = verdictInfoFor(turn, citation);
  const checkFailed = enrichmentStatusOf(turn) === "failed";
  const uncheckedHint = checkFailed ? "The evidence check could not run for this answer" : "Awaiting evidence check";
  return <div className="max-w-[280px] space-y-1 text-caption"><p>{tier === null ? uncheckedHint : TIER_TEXT[tier]}</p>{rationale !== null && <p className="text-grey">Judge: {scrub(rationale)}</p>}</div>;
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

/** The click rung (029 Fix B): the evidence-base reader's own Sheet, titled
 *  the same way, structured like ClaimPanel/CitationContext top to bottom —
 *  the citing claim text(s) as blockquotes, the citation's source/meta/
 *  verdict, then the highlighted quote-in-context (Fix A's no-retry +
 *  honest-fallback line). Replaces the old sticky `CitationPopover`. */
function CitationSheet({ projectId, turn, citation, onClose, onOpenDossier }: { projectId: string; turn: ChatConversationRow; citation: ChatCitation; onClose: () => void; onOpenDossier: (sourceRef: string) => void }) {
  const context = useChatChunkContext(projectId, citation);
  const meta = [context.data?.year, context.data?.venue].filter((value): value is string | number => value !== null && value !== undefined && value !== "");
  const sourceRef = citation.source_id ?? citation.source_title ?? null;
  const titleText = scrub(citation.source_title ?? citation.title ?? citationId(citation) ?? "Citation");
  const claims = claimsCiting(turn, citation);
  return (
    <Sheet open onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent title="Where this comes from" description="Citation provenance">
        <div className="space-y-5">
          {claims.map((claim, index) => typeof claim.text === "string" && claim.text !== "" && (
            <p key={claim.claim_id ?? index} className="border-l-2 border-l-blue pl-3 text-meta font-medium leading-snug text-navy">
              {scrub(claim.text)}
            </p>
          ))}
          <div className="border border-line p-4">
            <p className="text-meta font-bold leading-snug text-blue">
              [{citation.n ?? "—"}]{" "}
              {sourceRef !== null ? (
                <button type="button" className="cursor-pointer text-left hover:underline" onClick={() => onOpenDossier(sourceRef)}>{titleText}</button>
              ) : (
                <span>{titleText}</span>
              )}
            </p>
            {meta.length > 0 && <p className="mt-0.5 text-caption text-grey">{meta.map((value) => scrub(String(value))).join(" · ")}</p>}
            <div className="mt-2"><VerdictChip turn={turn} citation={citation} /></div>
            <div className="mt-3 space-y-2 text-caption leading-relaxed">
              {context.isPending && (
                <p role="status" className="animate-pulse text-caption text-grey">Loading surrounding context…</p>
              )}
              {context.data !== undefined && (
                <>
                  {typeof context.data.previous === "string" && context.data.previous !== "" && <p className="text-grey">{scrub(context.data.previous)}</p>}
                  <p className="text-navy"><HighlightedContext text={context.data.context} quote={citation.quote ?? ""} /></p>
                  {typeof context.data.next === "string" && context.data.next !== "" && <p className="text-grey">{scrub(context.data.next)}</p>}
                </>
              )}
              {context.isError && (
                <>
                  {citation.quote && <p className="italic text-grey">“{scrub(citation.quote)}”</p>}
                  <p className="text-grey">Exact passage not found in the source — showing the cited quote.</p>
                </>
              )}
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
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

function verdictFor(turn: ChatConversationRow, citation: ChatCitation): string | null { return verdictInfoFor(turn, citation).tier; }
function copyText(answer: string, citations: ChatCitation[], turn: ChatConversationRow) { return [answer, ...citations.map((citation, index) => `[${citation.n ?? index + 1}] ${citation.source_title ?? citation.title ?? citationId(citation)}${citation.quote ? ` — ${citation.quote}` : ""} — ${verdictFor(turn, citation) ? TIER_LABEL[verdictFor(turn, citation)!] : "Unchecked"}`)].filter(Boolean).join("\n"); }

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/queries";
import { scrub } from "../../../lib/scrub";
import type { ChatConversationRow } from "../../../store";
import { Button } from "../../../ui/brand/Button";
import { Chip } from "../../../ui/brand/Chip";
import { Tooltip } from "../../../ui/radix/Tooltip";
import { HighlightedContext, SourceDossier } from "../../ArtefactView";

const TIER_LABEL: Record<string, string> = {
  tier_1: "Tier 1 · direct quote", tier_2: "Tier 2 · grounded", tier_3: "Tier 3 · supported", tier_4: "Tier 4 · reasoning", unsupported_mis_cited: "Unsupported — flagged",
};
const TIER_TEXT: Record<string, string> = {
  tier_1: "Direct quote, verified against the source", tier_2: "Grounded in a specific passage", tier_3: "Supported across passages", tier_4: "Reasoning from the evidence, not a quote", unsupported_mis_cited: "Failed verification — flagged, never hidden",
};

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
  verdict?: string;
  grounding_tier?: string;
}

/** Plain-prose chat thread with citations and durable honesty states.
 *
 * Args:
 *   props: Project-scoped transcript rows and planning hand-off callback.
 *
 * Returns:
 *   User bubbles, assistant prose, and citation affordances.
 */
export function ChatMessages({ projectId, rows, onOpenPlanning }: { projectId: string; rows: ChatConversationRow[]; onOpenPlanning: () => void }) {
  const [citation, setCitation] = useState<ChatCitation | null>(null);
  const [dossierRef, setDossierRef] = useState<string | null>(null);
  const datedRows = useMemo(() => rows.map((row, index) => ({ row, showDate: index === 0 || dayOf(createdAt(row)) !== dayOf(createdAt(rows[index - 1])) })), [rows]);
  return <div className="space-y-5">{datedRows.map(({ row, showDate }) => <div key={keyOf(row)} className="space-y-3">{showDate && <DateDivider value={createdAt(row)} />}<UserBubble text={userMessageOf(row)} />{activityOf(row).length > 0 && <p className="mr-8 text-caption text-grey">{activitySummary(activityOf(row))}</p>}<AssistantMessage turn={row} onCitation={setCitation} onOpenDossier={setDossierRef} onOpenPlanning={onOpenPlanning} /></div>)}{citation !== null && <CitationPopover projectId={projectId} citation={citation} onClose={() => setCitation(null)} onOpenDossier={setDossierRef} />}{dossierRef !== null && <SourceDossier projectId={projectId} sourceRef={dossierRef} onClose={() => setDossierRef(null)} />}</div>;
}

function AssistantMessage({ turn, onCitation, onOpenDossier, onOpenPlanning }: { turn: ChatConversationRow; onCitation: (citation: ChatCitation) => void; onOpenDossier: (sourceRef: string) => void; onOpenPlanning: () => void }) {
  const answer = "id" in turn ? turn.answer ?? "" : turn.answer;
  const citations = citationsOf(turn);
  const cancelled = "id" in turn && turn.status === "cancelled";
  const warning = "id" in turn && turn.warning_not_evidence_checked;
  const handoff = "id" in turn && turn.handoff === "evidence_not_held";
  const copy = async () => { await navigator.clipboard?.writeText(copyText(answer, citations, turn)); };
  if (!answer && !("id" in turn && turn.status === "pending")) return null;
  return <div className="mr-8 space-y-2"><p className="max-w-[52ch] whitespace-pre-wrap text-body leading-relaxed text-ink"><CitationProse text={answer} citations={citations} disabled={cancelled} onCitation={onCitation} /></p>{"id" in turn && turn.status === "pending" && <p role="status" className="animate-pulse text-caption text-grey">Checking the evidence…</p>}{cancelled && <Chip tone="yellow">Stopped before evidence check</Chip>}{warning && <Chip tone="yellow">Not evidence-checked</Chip>}{handoff && <div className="border-l-2 border-yellow bg-yellow-tint/50 p-3 text-caption text-navy">The evidence base does not hold this.<Button size="sm" variant="secondary" className="ml-2" onClick={onOpenPlanning}>Open planning</Button></div>}{citations.length > 0 && <References citations={citations} turn={turn} onCitation={onCitation} onOpenDossier={onOpenDossier} />}{answer && <button type="button" aria-label="Copy answer" title="Copy answer" onClick={() => void copy()} className="text-grey hover:text-blue"><svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="5" y="5" width="9" height="10" rx="1" /><path d="M11 5V3a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h2" /></svg></button>}</div>;
}

function CitationProse({ text, citations, disabled, onCitation }: { text: string; citations: ChatCitation[]; disabled: boolean; onCitation: (citation: ChatCitation) => void }) {
  const parts = text.split(/(\[\d+\])/g);
  return <>{parts.map((part, index) => { const match = /^\[(\d+)\]$/.exec(part); const citation = match === null ? null : citations[Number(match[1]) - 1]; return citation !== null && citation !== undefined ? <button key={index} type="button" disabled={disabled} onClick={() => onCitation(citation)} className="align-super text-caption font-bold text-blue hover:underline disabled:text-grey">{part}</button> : <span key={index}>{scrub(part)}</span>; })}</>;
}

function References({ citations, turn, onCitation, onOpenDossier }: { citations: ChatCitation[]; turn: ChatConversationRow; onCitation: (citation: ChatCitation) => void; onOpenDossier: (sourceRef: string) => void }) {
  const checkFailed = enrichmentStatusOf(turn) === "failed";
  const uncheckedLabel = checkFailed ? "Unchecked · check unavailable" : "Unchecked · awaiting evidence check";
  const uncheckedHint = checkFailed ? "The evidence check could not run for this answer" : "Awaiting evidence check";
  return <footer className="border-t border-line pt-2"><p className="text-caption font-bold uppercase tracking-wider text-grey">References</p><div className="mt-2 space-y-2">{citations.map((citation, index) => {
    const { tier, rationale } = verdictInfoFor(turn, citation);
    const sourceRef = citation.source_id ?? citation.source_title ?? null;
    const titleText = scrub(citation.source_title ?? citation.title ?? citationId(citation) ?? "Citation");
    return <div key={citationId(citation) || index} className="text-caption text-ink"><button type="button" onClick={() => onCitation(citation)} className="font-bold text-blue hover:underline">[{citation.n ?? index + 1}]</button>{" "}
      {sourceRef !== null
        ? <button type="button" onClick={() => onOpenDossier(sourceRef)} className="cursor-pointer text-left font-semibold hover:underline">{titleText}</button>
        : <span>{titleText}</span>}
      {citation.quote && <span className="text-grey"> — “{scrub(citation.quote)}”</span>}
      <span className="ml-2">
        <Tooltip content={<div className="max-w-[280px] space-y-1 text-caption"><p>{tier === null ? uncheckedHint : TIER_TEXT[tier]}</p>{rationale !== null && <p className="text-grey">Judge: {scrub(rationale)}</p>}</div>}>
          <span><Chip tone={tier === "unsupported_mis_cited" ? "red" : tier === null ? "soft" : "blue"}>{tier === null ? uncheckedLabel : TIER_LABEL[tier]}</Chip></span>
        </Tooltip>
      </span>
    </div>;
  })}</div></footer>;
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

function CitationPopover({ projectId, citation, onClose, onOpenDossier }: { projectId: string; citation: ChatCitation; onClose: () => void; onOpenDossier: (sourceRef: string) => void }) {
  const client = useApiClient();
  const chunkId = citation.chunk_id ?? citation.id ?? citation.citation_id ?? "";
  const sourceRef = citation.source_id ?? citation.source_title ?? null;
  const context = useQuery({ queryKey: ["projects", projectId, "chat-chunk-context", chunkId, citation.quote], enabled: Boolean(chunkId && citation.quote), queryFn: async () => { const { data, error } = await client.GET("/api/v1/projects/{project_id}/chunks/{chunk_id}/context", { params: { path: { project_id: projectId, chunk_id: chunkId }, query: { quote: citation.quote ?? "" } } }); if (data === undefined) throw error; return data; } });
  const meta = [context.data?.year, context.data?.venue].filter((value): value is string | number => value !== null && value !== undefined && value !== "");
  return <div role="dialog" aria-label="Citation context" className="sticky bottom-3 ml-auto max-w-md border border-line bg-paper p-4 shadow-lg">
    <button type="button" aria-label="Close citation context" onClick={onClose} className="float-right text-grey">×</button>
    {(citation.source_title ?? citation.title) != null && (
      <p className="text-caption font-bold text-blue">
        {sourceRef !== null
          ? <button type="button" className="cursor-pointer text-left hover:underline" onClick={() => onOpenDossier(sourceRef)}>{scrub(citation.source_title ?? citation.title ?? "")}</button>
          : scrub(citation.source_title ?? citation.title ?? "")}
      </p>
    )}
    {meta.length > 0 && <p className="mt-0.5 text-caption text-grey">{meta.map((value) => scrub(String(value))).join(" · ")}</p>}
    {context.isPending && <p role="status" className="mt-2 text-caption text-grey">Loading context…</p>}
    {context.data && <div className="mt-2 whitespace-pre-wrap text-caption leading-relaxed text-ink">{context.data.previous && <p className="text-grey">{scrub(context.data.previous)}</p>}<p><HighlightedContext text={context.data.context} quote={citation.quote ?? ""} /></p>{context.data.next && <p className="text-grey">{scrub(context.data.next)}</p>}</div>}
    {context.isError && citation.quote && <p className="mt-2 text-caption italic text-grey">“{scrub(citation.quote)}”</p>}
  </div>;
}

function UserBubble({ text }: { text: string }) { return <div className="ml-8 border border-blue-tint bg-blue-tint-2 px-3.5 py-2.5"><p className="max-w-prose-measure whitespace-pre-wrap text-body text-ink">{scrub(text)}</p></div>; }
function DateDivider({ value }: { value: string }) { return <div className="flex items-center gap-2 text-caption text-grey"><span className="h-px flex-1 bg-line" />{new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" })}<span className="h-px flex-1 bg-line" /></div>; }
function createdAt(row: ChatConversationRow) { return "id" in row ? row.created_at : row.createdAt; }
function userMessageOf(row: ChatConversationRow) { return "id" in row ? row.user_message : row.userMessage; }
function keyOf(row: ChatConversationRow) { return "id" in row ? row.id : row.clientTurnId; }
function dayOf(value: string) { return new Date(value).toISOString().slice(0, 10); }
function activityOf(row: ChatConversationRow) { return "id" in row ? [] : row.activityLabels; }
function activitySummary(labels: string[]) { return labels.length === 1 ? labels[0] : `${labels.at(-1) ?? "Checked the evidence"} — ${labels.length} searches`; }
function citationsOf(turn: ChatConversationRow): ChatCitation[] { return "id" in turn && Array.isArray(turn.citations) ? turn.citations.filter((citation) => citation !== null && typeof citation === "object") as ChatCitation[] : []; }
function citationId(citation: ChatCitation) { return citation.id ?? citation.chunk_id ?? citation.citation_id ?? ""; }
function verdictInfoFor(turn: ChatConversationRow, citation: ChatCitation): { tier: string | null; rationale: string | null } {
  const claim = claimFor(turn, citation);
  const rationale = claim !== null && typeof claim.rationale === "string" && claim.rationale !== "" ? claim.rationale : null;
  const fromState = citation.state?.startsWith("verdict:") ? citation.state.slice("verdict:".length) : null;
  if (fromState !== null && TIER_LABEL[fromState]) return { tier: fromState, rationale };
  if (citation.verdict && TIER_LABEL[citation.verdict]) return { tier: citation.verdict, rationale };
  if (citation.grounding_tier && TIER_LABEL[citation.grounding_tier]) return { tier: citation.grounding_tier, rationale };
  const value = claim?.verdict ?? claim?.grounding_tier;
  if (typeof value === "string" && TIER_LABEL[value]) return { tier: value, rationale };
  return { tier: null, rationale };
}

function claimFor(turn: ChatConversationRow, citation: ChatCitation): Record<string, unknown> | null {
  if (!("id" in turn)) return null;
  for (const claim of turn.claims ?? []) {
    if (claim === null || typeof claim !== "object") continue;
    const candidate = claim as Record<string, unknown>;
    const ns = Array.isArray(candidate.citation_ns) ? candidate.citation_ns : [];
    if (typeof citation.n === "number" && ns.includes(citation.n)) return candidate;
    const ids = Array.isArray(candidate.citation_ids) ? candidate.citation_ids : Array.isArray(candidate.citations) ? candidate.citations : [];
    if (ids.includes(citationId(citation))) return candidate;
  }
  return null;
}

function verdictFor(turn: ChatConversationRow, citation: ChatCitation): string | null { return verdictInfoFor(turn, citation).tier; }
function copyText(answer: string, citations: ChatCitation[], turn: ChatConversationRow) { return [answer, ...citations.map((citation, index) => `[${citation.n ?? index + 1}] ${citation.source_title ?? citation.title ?? citationId(citation)}${citation.quote ? ` — ${citation.quote}` : ""} — ${verdictFor(turn, citation) ? TIER_LABEL[verdictFor(turn, citation)!] : "Unchecked"}`)].filter(Boolean).join("\n"); }

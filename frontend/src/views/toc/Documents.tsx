import { type ReactNode, useState } from "react";

import { useSourceDossier, useTocDocumentContext } from "../../api/queries";
import { formatCount } from "../../lib/format";
import { scrub } from "../../lib/scrub";
import { DisclosureToggle } from "../../ui/brand/DisclosureToggle";
import { evidenceTypeLabel } from "../../ui/brand/evidence";
import { referenceAuthorsShort, SOURCE_TITLE_LINK_CLASS } from "../../ui/brand/reference";
import { SUPPORT_COLOUR, VERDICT_COLOUR, VerdictMark, VerdictSquare } from "../../ui/brand/verdictTones";
import { Tooltip } from "../../ui/radix/Tooltip";
import { CITATION_MARKER_CLASS, CitationProvenanceBlock, ProvenanceSheet, SourceDossier } from "../ArtefactView";
import { evidenceBalance, figureGroups, figureHeadline, SUPPORT_LABEL, VERDICT_LABEL, VERDICT_VAR } from "./tocModel";
import type { SourceType, Support, TocDocument, TocFigure, Verdict } from "./types";

/**
 * The sidebar's two text sizes: body for prose, meta for every listed item.
 * Listed items (documents, figures, case studies) share one look: a semibold
 * title, a source line, and the quote in italics, all in the body ink.
 */
export const ITEM_TITLE = "font-semibold leading-snug text-navy";
export const ITEM_QUOTE = "mt-1 block italic text-ink";

const SOURCE_LABEL: Record<SourceType, string> = { academic: "Academic", policy: "Policy document", web: "Web page" };

/** A verdict as every ToC surface writes it (decision 7): the shared tone
 *  square, then "Leaning supports" in ink; "Not enough evidence" takes the
 *  Line 2 grey square (§ 8). The surface sets the word's weight. */
export function VerdictWords({ verdict, className }: { verdict: Verdict; className?: string }) {
  return <VerdictMark colour={VERDICT_COLOUR[verdict]} word={VERDICT_LABEL[verdict]} className={className} />;
}

/** Block colours: the verdict colours, weak support a lighter green. */
const BLOCK: Record<Exclude<Support, "not_about">, { background: string; opacity?: number }> = {
  refutes: { background: VERDICT_VAR.against },
  mixed: { background: VERDICT_VAR.not_sure_mixed },
  weak: { background: VERDICT_VAR.supported, opacity: 0.55 },
  strong: { background: VERDICT_VAR.supported },
};
/** Pixels of block height per unit of weight (one strong, fully relevant study). */
const PX_PER_WEIGHT = 40;

/**
 * The evidence balance (C36): four columns, Refutes to Strongly supports, each
 * document a block whose height is proportional to its weight. Hovering or
 * focusing a block shows its document as the document list shows it; clicking
 * it opens the document's citation, as the list does.
 */
export function EvidenceBalance({ documents, detail, onOpen }: { documents: TocDocument[]; detail: (doc: TocDocument) => ReactNode; onOpen: (doc: TocDocument) => void }) {
  const columns = evidenceBalance(documents);
  return (
    <div className="mt-2" role="group" aria-label={columns.map((col) => `${SUPPORT_LABEL[col.support]}: ${col.docs.length}`).join(", ")}>
      <div className="grid grid-cols-4 items-end gap-2">
        {columns.map((col) => (
          <div key={col.support} data-testid={`balance-${col.support}`} className="flex min-h-16 flex-col-reverse gap-[3px] border-b-2 border-line-2 pb-[3px]">
            {col.docs.map((doc, index) => (
              <Tooltip key={index} content={detail(doc)} className="max-w-sm text-body text-ink">
                <button
                  type="button"
                  data-testid="balance-block"
                  aria-label={`Open document ${index + 1} in ${SUPPORT_LABEL[col.support]}`}
                  onClick={() => onOpen(doc)}
                  className="block w-full cursor-pointer outline-offset-2 hover:brightness-90"
                  style={{ height: Math.max(4, Math.round(doc.weight * PX_PER_WEIGHT)), ...BLOCK[col.support] }}
                />
              </Tooltip>
            ))}
          </div>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-4 gap-2 text-center text-meta text-grey" aria-hidden="true">
        {columns.map((col) => (
          <span key={col.support}>{SUPPORT_LABEL[col.support]}</span>
        ))}
      </div>
    </div>
  );
}

type ScoredDocument = Pick<TocDocument, "support" | "quality" | "relevance" | "relevance_reason"> &
  Partial<Pick<TocDocument, "scored_by" | "judge_support" | "judge_relevance" | "added_by">>;

/** A document's facts after its support: "quality 3", "relevance 2", the judge's
 *  scores beside the user's, who added it, and why it is relevant. */
function documentFactsAfterSupport(doc: ScoredDocument): string[] {
  // The user's scores count (C42); the judge's stay visible beside them.
  const judge =
    doc.scored_by != null && doc.judge_support != null ? `your scores (judge: ${SUPPORT_LABEL[doc.judge_support].toLowerCase()} · relevance ${doc.judge_relevance})` : null;
  const added = doc.added_by != null ? `added by ${doc.added_by}` : null;
  return [`quality ${doc.quality}`, `relevance ${doc.relevance}`, judge, added, doc.relevance_reason].filter((part): part is string => Boolean(part));
}

/** "Strongly supports · quality 3 · relevance 2 · UK children aged 9 to 11". */
export function documentChips(doc: ScoredDocument): string {
  return [SUPPORT_LABEL[doc.support], ...documentFactsAfterSupport(doc)].join(" · ");
}

/** A document's facts as a marks line (decision 7): the support's tone square
 *  and its word in ink, then the scores, joined by the middot. */
function DocumentFacts({ doc }: { doc: ScoredDocument }) {
  const colour = SUPPORT_COLOUR[doc.support];
  return (
    <p className="mt-0.5">
      {colour !== null && <VerdictSquare colour={colour} className="mr-1.5 mb-[0.15em]" />}
      {scrub([SUPPORT_LABEL[doc.support], ...documentFactsAfterSupport(doc)].join(" · "))}
    </p>
  );
}

/** A source line: the authors in the References' short form (or the source
 *  type when there are none), then the rest. */
export function sourceLine(sourceType: SourceType, authors: readonly string[] | undefined, ...rest: (string | number | null | undefined)[]): string {
  const who = sourceType === "web" ? null : referenceAuthorsShort((authors ?? []).map((name) => ({ name })));
  return [who ?? SOURCE_LABEL[sourceType], ...rest].filter((part) => part != null && part !== "").join(" · ");
}

/** An evidence type in the shared sentence case, or nothing. */
function typeLabel(type: string | null | undefined): string | null {
  return typeof type === "string" && type.trim() !== "" ? evidenceTypeLabel(type) : null;
}

/** One cited document: its number in the panel, the judgement behind it and the passage to show. */
export interface TocCitation {
  n: number;
  /** The judgement row; null on rows written before evidence ids. */
  evidenceId: string | null;
  title: string;
  url: string | null;
  /** The passage to highlight; the judgement's own quote when null. */
  quote: string | null;
  /** The judgement's quote, shown alone when the passage cannot be found. */
  fallbackQuote: string;
  /** The task's document row (`task_source_snapshot_id`): its title opens
   *  the source's dossier, and its marks come from it. Null when unknown. */
  sourceId?: string | null;
}

/** One citation's block in the sheet, as the Evidence search's: the source
 *  (its title the way into its dossier), its evidence type and strength from
 *  the dossier, then its quote inside the passage it came from (task 054,
 *  A15). */
function CitationBlock({
  taskId,
  citation,
  numbered,
  onOpenDossier,
}: {
  taskId: string;
  citation: TocCitation;
  numbered: boolean;
  onOpenDossier: (sourceId: string) => void;
}) {
  const fetched = useTocDocumentContext(taskId, citation.evidenceId, citation.quote);
  const context = citation.evidenceId !== null ? fetched : { isPending: false, isError: true, data: undefined };
  const sourceId = citation.sourceId ?? null;
  const block = (marks: { evidenceType: string | null; strength: string | null }) => (
    <CitationProvenanceBlock
      n={citation.n}
      hideNumber={!numbered}
      sourceTitle={citation.title}
      sourceRef={sourceId}
      onOpenDossier={onOpenDossier}
      context={context}
      quote={citation.quote ?? citation.fallbackQuote}
      evidenceType={marks.evidenceType}
      strength={marks.strength}
      taskId={taskId}
      sourceId={sourceId}
    />
  );
  // Only a citation with a document row reads its dossier for its marks.
  return sourceId === null ? block({ evidenceType: null, strength: null }) : <WithMarks taskId={taskId} sourceId={sourceId} render={block} />;
}

/** A source's evidence type and strength, read from its dossier. */
function WithMarks({
  taskId,
  sourceId,
  render,
}: {
  taskId: string;
  sourceId: string;
  render: (marks: { evidenceType: string | null; strength: string | null }) => ReactNode;
}) {
  const dossier = useSourceDossier(taskId, sourceId);
  return <>{render({ evidenceType: dossier.data?.evidence_type ?? null, strength: dossier.data?.appraisal_tier ?? null })}</>;
}

/** The Evidence search's citation sheet, for ToC citations: "Evidence for
 *  this claim", the claim, then one box per source. A source's title opens
 *  its dossier over the sheet, with "Back to the claim" (task 054, A15). */
export function CitationSheet({ taskId, claim, citations, numbered = true, onClose }: { taskId: string; claim: string | null; citations: TocCitation[]; numbered?: boolean; onClose: () => void }) {
  const [source, setSource] = useState<string | null>(null);
  if (source !== null) {
    return <SourceDossier taskId={taskId} sourceRef={source} onClose={onClose} onBack={() => setSource(null)} />;
  }
  return (
    <ProvenanceSheet claimTexts={claim !== null ? [claim] : []} onClose={onClose}>
      {citations.map((citation) => (
        <CitationBlock
          key={`${citation.n}-${citation.evidenceId ?? citation.title}`}
          taskId={taskId}
          citation={citation}
          numbered={numbered}
          onOpenDossier={setSource}
        />
      ))}
    </ProvenanceSheet>
  );
}

/** "[1,3]" after a sentence, as the Evidence search shows it; opens the citation sidebar. */
export function CitationMarker({ taskId, claim, citations }: { taskId: string; claim: string | null; citations: TocCitation[] }) {
  const [open, setOpen] = useState(false);
  if (citations.length === 0) return null;
  const numbers = citations.map((citation) => citation.n);
  return (
    <>
      <button type="button" aria-label={`Citations ${numbers.join(", ")}`} onClick={() => setOpen(true)} className={CITATION_MARKER_CLASS}>
        [{numbers.join(",")}]
      </button>
      {open && <CitationSheet taskId={taskId} claim={claim} citations={citations} onClose={() => setOpen(false)} />}
    </>
  );
}

/**
 * One document in full: title (a link when it has a URL), source line, its
 * scores and quote; its number when it has one. `url`, `quote` and `chips`
 * override the document's own.
 */
export function DocumentItem({
  doc,
  n,
  url = doc.url,
  quote = doc.quote,
  chips,
  onOpen,
  actions,
  muted = false,
}: {
  doc: TocDocument;
  n?: number;
  url?: string | null;
  quote?: string | null;
  /** In place of the document's own facts line ("Removed by …"). */
  chips?: string;
  onOpen?: () => void;
  /** Editing controls under the document (C42). */
  actions?: ReactNode;
  /** Greyed: removed from the link by the user. */
  muted?: boolean;
}) {
  return (
    <li className={`border-t border-line py-2.5 text-body${muted ? " opacity-60" : ""}`}>
      <p className={ITEM_TITLE}>
        {n !== undefined && <span className="mr-1 font-normal tabular-nums text-grey">[{n}]</span>}
        {onOpen !== undefined ? (
          <button type="button" onClick={onOpen} className={`cursor-pointer text-left ${SOURCE_TITLE_LINK_CLASS}`}>
            {scrub(doc.title)}
          </button>
        ) : url !== null ? (
          <a href={url} target="_blank" rel="noreferrer" className={SOURCE_TITLE_LINK_CLASS}>
            {scrub(doc.title)}
          </a>
        ) : (
          scrub(doc.title)
        )}
      </p>
      <p className="mt-0.5">{scrub(sourceLine(doc.source_type, doc.authors, doc.year, typeLabel(doc.evidence_type)))}</p>
      {chips !== undefined ? <p className="mt-0.5">{scrub(chips)}</p> : <DocumentFacts doc={doc} />}
      {quote !== null && quote !== "" && <q className={ITEM_QUOTE}>{scrub(quote)}</q>}
      {actions}
    </li>
  );
}

/** Groups shown before "Show all N figures". */
const FIGURE_GROUPS_SHOWN = 3;

/** "Smith et al. · Obesity Reviews · 2019 · systematic review". */
function figureSource(figure: TocFigure): string {
  return sourceLine(figure.source_type, figure.source_authors, figure.source_venue, figure.source_year, typeLabel(figure.evidence_type));
}

/**
 * Figures as the panels show them (C37): each figure leads with its plain
 * statement, then its source line with a citation marker and its quote in
 * italics, as every listed item in the panel does. Two or more figures with the same measure and unit get a
 * bold "Evidence suggests A to B" line first: a range, never an average.
 */
export function FigureList({ taskId, figures, citationOf }: { taskId: string; figures: TocFigure[]; citationOf: (figure: TocFigure) => TocCitation | null }) {
  const [all, setAll] = useState(false);
  const groups = figureGroups(figures);
  const shown = all ? groups : groups.slice(0, FIGURE_GROUPS_SHOWN);
  return (
    <div className="mt-1">
      {shown.map((group) => (
        <div key={group.key} data-testid="figure-group" className="border-t border-line py-2.5 text-body">
          {group.figures.length >= 2 && <p className={ITEM_TITLE}>{scrub(figureHeadline(group))}</p>}
          {group.figures.map((figure) => {
            const citation = citationOf(figure);
            return (
              <div key={figure.figure_id} className="mt-1">
                <p className={ITEM_TITLE}>{scrub(figure.statement ?? figureHeadline({ key: figure.figure_id, figures: [figure] }))}</p>
                <p className="mt-0.5">
                  {scrub(figureSource(figure))}
                  {citation !== null && <CitationMarker taskId={taskId} claim={figure.statement} citations={[citation]} />}
                </p>
                <q className={ITEM_QUOTE}>{scrub(figure.quote)}</q>
              </div>
            );
          })}
        </div>
      ))}
      {groups.length > FIGURE_GROUPS_SHOWN && (
        <DisclosureToggle open={all} onToggle={() => setAll((open) => !open)} className="mt-1 text-body">
          {all ? "Hide" : `Show all ${formatCount(figures.length)} figures`}
        </DisclosureToggle>
      )}
    </div>
  );
}

/** A link's documents that support or refute it, heaviest first: the order the panel numbers them in. */
export function citedDocuments(documents: TocDocument[]): TocDocument[] {
  return documents
    .filter((doc) => doc.support !== "not_about" && doc.removed_by == null && (doc.status ?? "counted") === "counted")
    .sort((a, b) => b.weight - a.weight);
}

/** A cited document as a citation, with its number. */
export function documentCitation(doc: TocDocument, n: number, quote: string | null = null): TocCitation {
  return {
    n,
    evidenceId: doc.evidence_id || null,
    title: doc.title,
    url: doc.url,
    quote,
    fallbackQuote: doc.quote ?? "",
    sourceId: doc.task_source_snapshot_id || null,
  };
}

/** The citation list: a link's cited documents, numbered as the markers number them, each with its support, quality and relevance. */
export function LinkDocuments({ cited, onOpen, actions }: { cited: TocDocument[]; onOpen: (doc: TocDocument) => void; actions?: (doc: TocDocument) => ReactNode }) {
  if (cited.length === 0) return <p className="text-body text-grey">None found.</p>;
  return (
    <ul>
      {cited.map((doc, index) => (
        <DocumentItem key={doc.task_source_snapshot_id} doc={doc} n={index + 1} onOpen={() => onOpen(doc)} actions={actions?.(doc)} />
      ))}
    </ul>
  );
}

import { type ReactNode, useState } from "react";

import { useTocDocumentContext } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Tooltip } from "../../ui/radix/Tooltip";
import { CITATION_MARKER_CLASS, CitationProvenanceBlock, ProvenanceSheet } from "../ArtefactView";
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

/** A coloured dot for a verdict. */
export function VerdictDot({ verdict }: { verdict: Verdict }) {
  return <span aria-hidden="true" className="mr-2 inline-block h-[10px] w-[10px] shrink-0 rounded-full" style={{ background: VERDICT_VAR[verdict] }} />;
}

/** "Leaning supports" in the verdict's own colour, bold. */
export function VerdictWords({ verdict }: { verdict: Verdict }) {
  return <span className={`toc-verdict-${verdict} font-bold`}>{VERDICT_LABEL[verdict]}</span>;
}

/** Block colours: the verdict colours, weak support a lighter green. */
const BLOCK: Record<Exclude<Support, "not_about">, { background: string; opacity?: number }> = {
  refutes: { background: VERDICT_VAR.not_confident },
  mixed: { background: VERDICT_VAR.not_sure_mixed },
  weak: { background: VERDICT_VAR.confident, opacity: 0.55 },
  strong: { background: VERDICT_VAR.confident },
};
/** Pixels of block height per unit of weight (one strong, fully relevant study). */
const PX_PER_WEIGHT = 40;

/**
 * The evidence balance (C36): four columns, Refutes to Strongly supports, each
 * document a block whose height is proportional to its weight. Hovering or
 * focusing a block shows its document as the document list shows it; clicking
 * it opens the document's citation, as the list does.
 */
export function EvidenceBalance<T extends Pick<TocDocument, "support" | "weight">>({
  documents,
  detail,
  onOpen,
}: {
  documents: T[];
  detail?: (doc: T) => ReactNode;
  /** Clicking a block opens its document's citation. */
  onOpen?: (doc: T) => void;
}) {
  const columns = evidenceBalance(documents);
  const caption = { refutes: "Refutes", mixed: "Mixed", weak: "Weakly supports", strong: "Strongly supports" };
  return (
    <div className="mt-2" role="group" aria-label={columns.map((col) => `${caption[col.support]}: ${col.docs.length}`).join(", ")}>
      <div className="grid grid-cols-4 items-end gap-2">
        {columns.map((col) => (
          <div key={col.support} data-testid={`balance-${col.support}`} className="flex min-h-16 flex-col-reverse gap-[3px] border-b-2 border-line-2 pb-[3px]">
            {col.docs.map((doc, index) => {
              const style = { height: Math.max(4, Math.round(doc.weight * PX_PER_WEIGHT)), ...BLOCK[col.support] };
              const block =
                onOpen === undefined ? (
                  <div key={index} data-testid="balance-block" tabIndex={detail === undefined ? undefined : 0} className="rounded-[3px] outline-offset-2" style={style} />
                ) : (
                  <button
                    key={index}
                    type="button"
                    data-testid="balance-block"
                    aria-label={`Open document ${index + 1} in ${caption[col.support]}`}
                    onClick={() => onOpen(doc)}
                    className="block w-full cursor-pointer rounded-[3px] outline-offset-2 hover:brightness-90"
                    style={style}
                  />
                );
              return detail === undefined ? (
                block
              ) : (
                <Tooltip key={index} content={detail(doc)} className="max-w-sm text-body text-ink">
                  {block}
                </Tooltip>
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-4 gap-2 text-center text-meta text-grey" aria-hidden="true">
        {columns.map((col) => (
          <span key={col.support}>{caption[col.support]}</span>
        ))}
      </div>
    </div>
  );
}

/** "Strongly supports · quality 3 · relevance 2 · UK children aged 9 to 11". */
export function documentChips(doc: Pick<TocDocument, "support" | "quality" | "relevance" | "relevance_reason"> & Partial<Pick<TocDocument, "scored_by" | "judge_support" | "judge_relevance" | "added_by">>): string {
  // The user's scores count (C42); the judge's stay visible beside them.
  const judge =
    doc.scored_by != null && doc.judge_support != null ? `your scores (judge: ${SUPPORT_LABEL[doc.judge_support].toLowerCase()} · relevance ${doc.judge_relevance})` : null;
  const added = doc.added_by != null ? `added by ${doc.added_by}` : null;
  return [SUPPORT_LABEL[doc.support], `quality ${doc.quality}`, `relevance ${doc.relevance}`, judge, added, doc.relevance_reason].filter(Boolean).join(" · ");
}

/** "Smith et al.", one author's name, or the publishing organisation (Overton's single author); null when unknown. */
export function shortAuthors(authors: readonly string[] | undefined): string | null {
  const names = (authors ?? []).filter((name) => name !== "");
  if (names.length === 0) return null;
  return names.length === 1 ? (names[0] ?? null) : `${names[0]} et al.`;
}

/** A source line: short authors (or the source type when there are none), then the rest. */
export function sourceLine(sourceType: SourceType, authors: readonly string[] | undefined, ...rest: (string | number | null | undefined)[]): string {
  const who = sourceType === "web" ? null : shortAuthors(authors);
  return [who ?? SOURCE_LABEL[sourceType], ...rest].filter((part) => part != null && part !== "").join(" · ");
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
}

/** One citation's block in the sidebar: the source, then its quote inside the passage it came from. */
function CitationBlock({ taskId, citation, numbered }: { taskId: string; citation: TocCitation; numbered: boolean }) {
  const fetched = useTocDocumentContext(taskId, citation.evidenceId, citation.quote);
  const context = citation.evidenceId !== null ? fetched : { isPending: false, isError: true, data: undefined };
  return (
    <>
      <CitationProvenanceBlock
        n={citation.n}
        hideNumber={!numbered}
        sourceTitle={citation.title}
        sourceRef={null}
        onOpenDossier={() => undefined}
        context={context}
        quote={citation.quote ?? citation.fallbackQuote}
      />
      {citation.url !== null && (
        <a href={citation.url} target="_blank" rel="noreferrer" className="block text-body font-bold text-blue hover:underline">
          Open the source
        </a>
      )}
    </>
  );
}

/** The Evidence search's citation sidebar, for ToC citations. */
export function CitationSheet({ taskId, claim, citations, numbered = true, onClose }: { taskId: string; claim: string | null; citations: TocCitation[]; numbered?: boolean; onClose: () => void }) {
  return (
    <ProvenanceSheet description="Source passage" claimTexts={claim !== null ? [claim] : []} onClose={onClose}>
      {citations.map((citation) => (
        <CitationBlock key={`${citation.n}-${citation.evidenceId ?? citation.title}`} taskId={taskId} citation={citation} numbered={numbered} />
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

/** One document in full: title (a link when it has a URL), source line and quote; its number when it has one. */
export function DocumentItem({
  n,
  title,
  url,
  quote,
  chips,
  onOpen,
  authors,
  actions,
  muted = false,
  ...rest
}: {
  n?: number;
  title: string;
  url: string | null;
  quote: string | null;
  chips?: string;
  authors?: string[];
  onOpen?: () => void;
  /** Editing controls under the document (C42). */
  actions?: ReactNode;
  /** Greyed: removed from the link by the user. */
  muted?: boolean;
} & Pick<TocDocument, "source_type" | "year" | "evidence_type">) {
  return (
    <li className={`border-t border-line py-2.5 text-body${muted ? " opacity-60" : ""}`}>
      <p className={ITEM_TITLE}>
        {n !== undefined && <span className="mr-1 text-grey">[{n}]</span>}
        {onOpen !== undefined ? (
          <button type="button" onClick={onOpen} className="cursor-pointer text-left text-blue hover:underline">
            {scrub(title)}
          </button>
        ) : url !== null ? (
          <a href={url} target="_blank" rel="noreferrer" className="text-blue hover:underline">
            {scrub(title)}
          </a>
        ) : (
          scrub(title)
        )}
      </p>
      <p className="mt-0.5">{sourceLine(rest.source_type, authors, rest.year, rest.evidence_type)}</p>
      {chips !== undefined && <p className="mt-0.5">{scrub(chips)}</p>}
      {quote !== null && quote !== "" && <q className={ITEM_QUOTE}>{scrub(quote)}</q>}
      {actions}
    </li>
  );
}

/** Groups shown before "Show all N figures". */
const FIGURE_GROUPS_SHOWN = 3;

/** "Smith et al. · Obesity Reviews · 2019 · systematic review". */
function figureSource(figure: TocFigure): string {
  return sourceLine(figure.source_type, figure.source_authors, figure.source_venue, figure.source_year, figure.evidence_type);
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
      {!all && groups.length > FIGURE_GROUPS_SHOWN && (
        <button type="button" onClick={() => setAll(true)} className="cursor-pointer text-body font-bold text-blue hover:underline">
          Show all {figures.length} figures
        </button>
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
  return { n, evidenceId: doc.evidence_id || null, title: doc.title, url: doc.url, quote, fallbackQuote: doc.quote ?? "" };
}

/** The citation list: a link's documents, numbered as the markers number them, each with its support, quality and relevance. */
export function LinkDocuments({ taskId, documents, actions }: { taskId: string; documents: TocDocument[]; actions?: (doc: TocDocument) => ReactNode }) {
  const [opened, setOpened] = useState<number | null>(null);
  const shown = citedDocuments(documents);
  if (shown.length === 0) return <p className="text-body text-grey">None found.</p>;
  const doc = opened === null ? undefined : shown[opened - 1];
  return (
    <>
      <ul>
        {shown.map((item, index) => (
          <DocumentItem
            key={item.task_source_snapshot_id}
            n={index + 1}
            title={item.title}
            url={item.url}
            quote={item.quote}
            chips={documentChips(item)}
            authors={item.authors}
            onOpen={() => setOpened(index + 1)}
            actions={actions?.(item)}
            source_type={item.source_type}
            year={item.year}
            evidence_type={item.evidence_type}
          />
        ))}
      </ul>
      {doc !== undefined && opened !== null && (
        <CitationSheet taskId={taskId} claim={null} citations={[documentCitation(doc, opened)]} numbered={false} onClose={() => setOpened(null)} />
      )}
    </>
  );
}

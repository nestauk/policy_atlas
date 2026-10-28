import { useState } from "react";

import { useTocDocumentContext } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { CitationProvenanceBlock, ProvenanceSheet } from "../ArtefactView";
import { referenceAuthorsLine } from "../artefactPresentation";
import { evidenceBalance, SUPPORT_LABEL, VERDICT_LABEL, VERDICT_VAR } from "./tocModel";
import type { SourceType, Support, TocDocument, Verdict } from "./types";

const SOURCE_LABEL: Record<SourceType, string> = { academic: "Academic", policy: "Policy document", web: "Web page" };

/** A coloured dot for a verdict. */
export function VerdictDot({ verdict }: { verdict: Verdict }) {
  return <span aria-hidden="true" className="mr-2 inline-block h-[10px] w-[10px] shrink-0 rounded-full" style={{ background: VERDICT_VAR[verdict] }} />;
}

/** "Not sure: mixed" in the verdict's own colour, bold. */
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
 * document a block whose height is proportional to its weight.
 */
export function EvidenceBalance({ documents }: { documents: Pick<TocDocument, "support" | "weight">[] }) {
  const columns = evidenceBalance(documents);
  const caption = { refutes: "Refutes", mixed: "Mixed", weak: "Weakly supports", strong: "Strongly supports" };
  return (
    <div className="mt-2" role="img" aria-label={columns.map((col) => `${caption[col.support]}: ${col.weights.length}`).join(", ")}>
      <div className="grid grid-cols-4 items-end gap-2">
        {columns.map((col) => (
          <div key={col.support} data-testid={`balance-${col.support}`} className="flex min-h-16 flex-col-reverse gap-[3px] border-b-2 border-line-2 pb-[3px]">
            {col.weights.map((weight, index) => (
              <div
                key={index}
                data-testid="balance-block"
                className="rounded-[3px]"
                style={{ height: Math.max(4, Math.round(weight * PX_PER_WEIGHT)), ...BLOCK[col.support] }}
              />
            ))}
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
export function documentChips(doc: Pick<TocDocument, "support" | "quality" | "relevance" | "relevance_reason">): string {
  return [SUPPORT_LABEL[doc.support], `quality ${doc.quality}`, `relevance ${doc.relevance}`, doc.relevance_reason].filter(Boolean).join(" · ");
}

/** Authors as the Evidence search references show them; the source label when there are none (and for web pages). */
function meta(doc: Pick<TocDocument, "source_type" | "year"> & { evidence_type?: string | null; authors?: string[] }): string {
  const authors = doc.source_type === "web" ? null : referenceAuthorsLine((doc.authors ?? []).map((name) => ({ name })));
  return [authors ?? SOURCE_LABEL[doc.source_type], doc.year, doc.evidence_type].filter((part) => part != null && part !== "").join(" · ");
}

/** One document in full: title (a link when it has a URL), source type, year and quote. */
export function DocumentItem({
  title,
  url,
  quote,
  chips,
  onOpen,
  ...rest
}: { title: string; url: string | null; quote: string | null; chips?: string; authors?: string[]; onOpen?: () => void } & Pick<TocDocument, "source_type" | "year" | "evidence_type">) {
  return (
    <li className="border-t border-line py-2.5 text-meta">
      <p className="font-semibold leading-snug text-navy">
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
      <p className="mt-0.5 text-grey">{meta(rest)}</p>
      {chips !== undefined && <p className="mt-0.5 text-grey">{scrub(chips)}</p>}
      {quote !== null && quote !== "" && <q className="mt-1 block text-navy">{scrub(quote)}</q>}
    </li>
  );
}

/** A link's documents that support or refute it, heaviest first, each with its support, quality and relevance. */
export function LinkDocuments({ taskId, documents }: { taskId: string; documents: TocDocument[] }) {
  const [opened, setOpened] = useState<TocDocument | null>(null);
  const shown = documents.filter((doc) => doc.support !== "not_about").sort((a, b) => b.weight - a.weight);
  if (shown.length === 0) return <p className="text-meta text-grey">None found.</p>;
  return (
    <>
      <ul>
        {shown.map((doc) => (
          <DocumentItem
            key={doc.task_source_snapshot_id}
            title={doc.title}
            url={doc.url}
            quote={doc.quote}
            chips={documentChips(doc)}
            authors={doc.authors}
            onOpen={() => setOpened(doc)}
            source_type={doc.source_type}
            year={doc.year}
            evidence_type={doc.evidence_type}
          />
        ))}
      </ul>
      {opened !== null && <DocumentSheet taskId={taskId} doc={opened} onClose={() => setOpened(null)} />}
    </>
  );
}

/** The Evidence search report's citation sidebar, for one ToC document: its quote inside the passage it came from. */
export function DocumentSheet({ taskId, doc, onClose }: { taskId: string; doc: TocDocument; onClose: () => void }) {
  // Rows written before evidence ids existed have none: show the quote alone.
  const hasId = Boolean(doc.evidence_id);
  const fetched = useTocDocumentContext(taskId, hasId ? doc.evidence_id : null);
  const context = hasId ? fetched : { isPending: false, isError: true, data: undefined };
  const quote = doc.quote ?? "";
  return (
    <ProvenanceSheet description="Source passage" claimTexts={[]} onClose={onClose}>
      <CitationProvenanceBlock
        n={null}
        hideNumber
        sourceTitle={doc.title}
        sourceRef={null}
        onOpenDossier={() => undefined}
        context={context}
        quote={quote}
      />
      {doc.url !== null && (
        <a href={doc.url} target="_blank" rel="noreferrer" className="block text-body font-bold text-blue hover:underline">
          Open the source
        </a>
      )}
    </ProvenanceSheet>
  );
}

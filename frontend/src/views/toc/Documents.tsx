import { useState } from "react";

import { useTocDocumentContext } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { CitationProvenanceBlock, ProvenanceSheet } from "../ArtefactView";
import { referenceAuthorsLine } from "../artefactPresentation";
import type { Grade, SourceType, TocDocument } from "./types";
import { gradeSentence } from "./tocModel";

const SOURCE_LABEL: Record<SourceType, string> = { academic: "Academic", policy: "Policy document", web: "Web page" };

/** A coloured dot for a grade; "none" is a dashed ring. */
export function GradeDot({ grade }: { grade: Grade }) {
  return <span aria-hidden="true" className={`toc-dot-${grade} mr-2 inline-block h-[9px] w-[9px] shrink-0 rounded-full`} />;
}

/** "Medium evidence it worked elsewhere." in the grade's own colour. */
export function GradeWords({ grade, question }: { grade: Grade; question: "elsewhere" | "here" | "merged" }) {
  return <span className={`toc-grade-${grade} font-bold`}>{gradeSentence(grade, question)}</span>;
}

type Question = "elsewhere" | "here";

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
  onOpen,
  ...rest
}: { title: string; url: string | null; quote: string | null; authors?: string[]; onOpen?: () => void } & Pick<TocDocument, "source_type" | "year" | "evidence_type">) {
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
      {quote !== null && quote !== "" && <q className="mt-1 block text-navy">{scrub(quote)}</q>}
    </li>
  );
}

/**
 * The documents behind one question, in Supports and Challenges groups.
 *
 * A document that answers both questions is listed in full once, under
 * *worked elsewhere*; under *holds here* it is a one-line reference with its
 * here-quote ("Also counts here").
 */
export function QuestionDocuments({ taskId, documents, question }: { taskId: string; documents: TocDocument[]; question: Question }) {
  const [opened, setOpened] = useState<TocDocument | null>(null);
  const stanceOf = (doc: TocDocument) => doc[question].stance;
  const answersElsewhere = (doc: TocDocument) => doc.elsewhere.stance !== "not_about";
  const groups = [
    { key: "supports", label: "Supports", docs: documents.filter((d) => stanceOf(d) === "supports") },
    { key: "challenges", label: "Challenges", docs: documents.filter((d) => stanceOf(d) === "challenges") },
  ] as const;
  return (
    <div className="mt-2">
      {groups.map((group) => (
        <div key={group.key}>
          <p className="mt-3 text-meta font-bold text-navy">
            {group.label} ({group.docs.length})
          </p>
          {group.docs.length === 0 ? (
            <p className="text-meta text-grey">None found.</p>
          ) : (
            <ul>
              {group.docs.map((doc) =>
                question === "here" && answersElsewhere(doc) ? (
                  <li key={doc.task_source_snapshot_id} className="border-t border-line py-2.5 text-meta">
                    <p className="text-navy">
                      Also counts here:{" "}
                      <button type="button" onClick={() => setOpened(doc)} className="cursor-pointer text-left text-blue hover:underline">
                        {scrub(doc.title)}
                      </button>
                      {doc.year !== null ? ` (${doc.year})` : ""}
                    </p>
                    {doc.here.quote !== null && doc.here.quote !== "" && <q className="mt-1 block text-navy">{scrub(doc.here.quote)}</q>}
                  </li>
                ) : (
                  <DocumentItem
                    key={doc.task_source_snapshot_id}
                    title={doc.title}
                    url={doc.url}
                    quote={doc[question].quote}
                    authors={doc.authors}
                    onOpen={() => setOpened(doc)}
                    source_type={doc.source_type}
                    year={doc.year}
                    evidence_type={doc.evidence_type}
                  />
                ),
              )}
            </ul>
          )}
        </div>
      ))}
      {opened !== null && <DocumentSheet taskId={taskId} doc={opened} question={question} onClose={() => setOpened(null)} />}
    </div>
  );
}

/** The Evidence search report's citation sidebar, for one ToC document: its quote inside the passage it came from. */
export function DocumentSheet({ taskId, doc, question, onClose }: { taskId: string; doc: TocDocument; question: Question; onClose: () => void }) {
  // Rows written before evidence ids existed have none: show the quote alone.
  const hasId = Boolean(doc.evidence_id);
  const fetched = useTocDocumentContext(taskId, hasId ? doc.evidence_id : null, question);
  const context = hasId ? fetched : { isPending: false, isError: true, data: undefined };
  const quote = doc[question].quote ?? "";
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

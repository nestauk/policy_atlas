import { scrub } from "../../lib/scrub";
import { CitationMarker, citedDocuments, DocumentItem, documentCitation, EvidenceBalance, FigureList, ITEM_QUOTE, ITEM_TITLE, LinkDocuments, shortAuthors, VerdictDot, VerdictWords } from "./Documents";
import { LAYER_LABEL, ORIGIN_LABEL } from "./tocModel";
import type { TocBox, TocDocument, TocEvidence, TocGraph, TocLink } from "./types";

export type Selection = { kind: "box" | "link"; id: string };

const HEAD = "mt-5 text-meta font-bold uppercase tracking-[0.06em] text-grey";
/** A part inside a section ("Conditions", "Size of change"). */
const SUB = "mt-3 text-meta font-bold text-navy";

function Origin({ origin, rules }: { origin: TocBox["origin"]; rules?: TocGraph["grade_rules"] }) {
  return (
    <>
      {rules !== undefined && (
        <details className="mt-3 text-meta">
          <summary className="cursor-pointer font-bold text-navy">How the verdict is given</summary>
          <dl className="mt-1 space-y-1 text-grey">
            {rules.map((row) => (
              <div key={row.label}>
                <dt className="inline font-semibold">{row.label}: </dt>
                <dd className="inline">{row.rule}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
      <details className="mt-3 text-meta">
        <summary className="cursor-pointer font-bold text-navy">Where this came from</summary>
        <p className="mt-1 text-grey">{ORIGIN_LABEL[origin]}</p>
      </details>
    </>
  );
}

/** "Definition", "Indicator", "Timing": how we'd know a box's change happened. */
function Criteria({ criteria }: { criteria: TocBox["result_criteria"] }) {
  const rows = [
    ["Definition", criteria.definition],
    ["Indicator", criteria.indicator],
    ["Timing", criteria.timing],
  ].filter((row): row is [string, string] => row[1] != null);
  if (rows.length === 0) return null;
  return (
    <>
      <p className={HEAD}>How we'd know it happened</p>
      <dl className="mt-1 grid grid-cols-[5.5rem_1fr] gap-x-3 gap-y-1 text-body">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-grey">{label}</dt>
            <dd>{scrub(value)}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}

function BoxDetail({ taskId, box, evidence }: { taskId: string; box: TocBox; evidence: TocEvidence | null | undefined }) {
  const found = evidence?.boxes.find((entry) => entry.box_id === box.box_id);
  const studies = found?.case_studies ?? [];
  const figures = found?.figures ?? [];
  // One numbering for the panel: the case studies' documents, then the figures'.
  const order = [...new Set([...studies.map((study) => study.task_source_snapshot_id), ...figures.map((figure) => figure.task_source_snapshot_id)])];
  const numberOf = (tss: string) => order.indexOf(tss) + 1;
  const seenIn = studies
    .filter((study) => box.seen_in_cites.includes(study.task_source_snapshot_id))
    .filter((study, index, all) => all.findIndex((other) => other.task_source_snapshot_id === study.task_source_snapshot_id) === index)
    .map((study) => ({
      n: numberOf(study.task_source_snapshot_id),
      evidenceId: study.evidence_id,
      title: study.title,
      url: study.url,
      quote: study.quote,
      fallbackQuote: study.quote,
    }));
  return (
    <>
      <p className="text-meta text-grey">
        {LAYER_LABEL[box.layer]}
        {box.code !== null && <> <span className="font-semibold">{box.code}</span></>}
      </p>
      <h3 className="mt-0.5 text-body font-bold leading-snug text-navy">{scrub(box.text)}</h3>
      {box.description !== null && <p className="mt-2 text-body">{scrub(box.description)}</p>}
      <Criteria criteria={box.result_criteria} />
      {figures.length > 0 && (
        <>
          <p className={HEAD}>Figures</p>
          <FigureList
            taskId={taskId}
            figures={figures}
            citationOf={(figure) => ({
              n: numberOf(figure.task_source_snapshot_id),
              evidenceId: figure.evidence_id,
              title: figure.source_title,
              url: figure.url,
              quote: figure.quote,
              fallbackQuote: figure.quote,
            })}
          />
        </>
      )}
      {(studies.length > 0 || box.seen_in !== null) && (
        <>
          <p className={HEAD}>Case studies ({studies.length})</p>
          {box.seen_in !== null && (
            <p className="mt-1 text-body">
              {scrub(box.seen_in)}
              <CitationMarker taskId={taskId} claim={box.seen_in} citations={seenIn} />
            </p>
          )}
          <ul>
            {studies.map((study) => (
              <li key={`${study.task_source_snapshot_id}-${study.programme}`} className="border-t border-line py-2.5 text-meta">
                <p className={ITEM_TITLE}>
                  <span className="mr-1 text-grey">[{numberOf(study.task_source_snapshot_id)}]</span>
                  {scrub(study.programme)}
                  {study.place !== null ? `, ${scrub(study.place)}` : ""}
                </p>
                <p className="mt-0.5">{scrub(study.note)}</p>
                <q className={ITEM_QUOTE}>{scrub(study.quote)}</q>
                <ul>
                  <DocumentItem title={study.title} url={study.url} quote={null} authors={study.authors} source_type={study.source_type} year={study.year} evidence_type={null} />
                </ul>
              </li>
            ))}
          </ul>
        </>
      )}
      <Origin origin={box.origin} />
    </>
  );
}

function LinkDetail({ taskId, link, graph, evidence }: { taskId: string; link: TocLink; graph: TocGraph; evidence: TocEvidence | null | undefined }) {
  const linkEvidence = evidence?.links.find((entry) => entry.link_id === link.link_id);
  const documents = linkEvidence?.documents ?? [];
  const figures = linkEvidence?.figures ?? [];
  // The citation list's order numbers every marker in this panel.
  const cited = citedDocuments(documents);
  const numberOf = (tss: string) => cited.findIndex((doc) => doc.task_source_snapshot_id === tss) + 1;
  const sentenceCitations = link.evidence_cites
    .map((tss) => cited.find((doc) => doc.task_source_snapshot_id === tss))
    .filter((doc): doc is TocDocument => doc !== undefined)
    .map((doc) => documentCitation(doc, numberOf(doc.task_source_snapshot_id)))
    .sort((a, b) => a.n - b.n);
  const pending = link.state === "checking" || link.state === "unchecked";
  const codeOf = (boxId: string) => graph.boxes.find((box) => box.box_id === boxId)?.code ?? null;
  const [source, target] = [codeOf(link.source_box_id), codeOf(link.target_box_id)];
  // "Connection #5 · S3 → L1" (C35); rows written before codes have none.
  const codes = link.code !== null && source !== null && target !== null ? `${link.code} · ${source} → ${target}` : null;
  return (
    <>
      <p className="text-meta text-grey">
        {link.critical ? "Critical connection" : "Connection"}
        {codes !== null && <> <span className="font-semibold">{codes}</span></>}
        {link.critical && " · test this first"}
      </p>
      <h3 className="mt-0.5 text-body font-bold leading-snug text-navy">{scrub(link.title ?? link.sentence)}</h3>
      {pending ? (
        <p className="mt-1 text-body text-grey">Checking the evidence…</p>
      ) : (
        <p data-testid="link-verdict" className="mt-1 flex items-center text-body">
          <VerdictDot verdict={link.verdict} />
          <VerdictWords verdict={link.verdict} />
        </p>
      )}

      <p className={HEAD}>How this works</p>
      <p className="mt-1 text-body">
        {(
          [
            ["If", link.if_text],
            ["for", link.for_text],
            ["then", link.then_text],
            ["because", link.because_text],
          ] as const
        ).map(([word, text], index) => (
          <span key={word}>
            {index > 0 && ", "}
            <b>{word}</b> {scrub(text.replace(/[.,;\s]+$/, ""))}
          </span>
        ))}
        .
      </p>
      {link.conditions.length > 0 && (
        <>
          <p className={SUB}>Conditions</p>
          <ul className="mt-1 list-disc pl-5 text-body">
            {link.conditions.map((condition) => (
              <li key={condition}>{scrub(condition)}</li>
            ))}
          </ul>
        </>
      )}

      <p className={HEAD}>Evidence</p>
      {!pending && (
        <>
          {figures.length > 0 && (
            <>
              <p className={SUB}>Size of change</p>
              <FigureList
                taskId={taskId}
                figures={figures}
                citationOf={(figure) => {
                  const doc = cited.find((item) => item.task_source_snapshot_id === figure.task_source_snapshot_id);
                  return doc === undefined ? null : { ...documentCitation(doc, numberOf(figure.task_source_snapshot_id), figure.quote), evidenceId: figure.evidence_id };
                }}
              />
            </>
          )}
          <p className={SUB}>
            Evidence balance: <VerdictWords verdict={link.verdict} />
          </p>
          <EvidenceBalance
            documents={cited}
            label={(doc) => [`[${numberOf(doc.task_source_snapshot_id)}]`, shortAuthors(doc.authors), doc.year, scrub(doc.title)].filter((part) => part != null).join(" ")}
          />
          {link.evidence_sentence !== null && (
            <p className="mt-2 text-body">
              {scrub(link.evidence_sentence)}
              <CitationMarker taskId={taskId} claim={link.evidence_sentence} citations={sentenceCitations} />
            </p>
          )}
        </>
      )}
      <p className={SUB}>Documents ({cited.length})</p>
      <LinkDocuments taskId={taskId} documents={documents} />
      <Origin origin={link.origin} rules={graph.grade_rules} />
    </>
  );
}

/** The right-hand panel: one box or one connection, read-only. */
export function DetailPanel({
  taskId,
  graph,
  evidence,
  selection,
  onClose,
}: {
  taskId: string;
  graph: TocGraph;
  evidence: TocEvidence | null | undefined;
  selection: Selection;
  onClose: () => void;
}) {
  const box = selection.kind === "box" ? graph.boxes.find((b) => b.box_id === selection.id) : undefined;
  const link = selection.kind === "link" ? graph.links.find((l) => l.link_id === selection.id) : undefined;
  if (box === undefined && link === undefined) return null;
  return (
    <aside aria-label="Details" className="max-h-[680px] [:fullscreen>&]:max-h-screen w-[380px] shrink-0 overflow-y-auto border-l border-line bg-paper px-5 py-4 max-lg:w-full max-lg:border-l-0 max-lg:border-t">
      <button type="button" onClick={onClose} aria-label="Close" className="float-right cursor-pointer text-lead leading-none text-grey hover:text-navy">
        ×
      </button>
      {box !== undefined && <BoxDetail taskId={taskId} box={box} evidence={evidence} />}
      {link !== undefined && <LinkDetail taskId={taskId} link={link} graph={graph} evidence={evidence} />}
    </aside>
  );
}

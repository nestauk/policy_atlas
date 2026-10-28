import { scrub } from "../../lib/scrub";
import { DocumentItem, GradeWords, QuestionDocuments } from "./Documents";
import { LAYER_LABEL, ORIGIN_LABEL } from "./tocModel";
import type { TocBox, TocEvidence, TocGraph, TocLink } from "./types";

export type Selection = { kind: "box" | "link"; id: string };

const HEAD = "mt-4 text-meta font-bold text-navy";

function Origin({ origin, rules }: { origin: TocBox["origin"]; rules?: TocGraph["grade_rules"] }) {
  return (
    <>
      {rules !== undefined && (
        <details className="mt-3 text-meta">
          <summary className="cursor-pointer font-bold text-navy">How these grades were given</summary>
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

function BoxDetail({ box, evidence }: { box: TocBox; evidence: TocEvidence | null | undefined }) {
  const criteria = box.result_criteria;
  const found = evidence?.boxes.find((entry) => entry.box_id === box.box_id);
  return (
    <>
      <p className="text-meta text-grey">
        {LAYER_LABEL[box.layer]}
        {box.code !== null && <> <span className="text-caption font-semibold">{box.code}</span></>}
      </p>
      <h3 className="mt-0.5 text-body font-bold leading-snug text-navy">{scrub(box.text)}</h3>
      {(criteria.definition ?? criteria.indicator ?? criteria.timing) != null && (
        <>
          <p className={HEAD}>Result criteria</p>
          <dl className="mt-1 grid grid-cols-[5.5rem_1fr] gap-x-3 gap-y-1 text-meta">
            {criteria.definition != null && (
              <>
                <dt className="text-grey">Definition</dt>
                <dd>{scrub(criteria.definition)}</dd>
              </>
            )}
            {criteria.indicator != null && (
              <>
                <dt className="text-grey">Indicator</dt>
                <dd>{scrub(criteria.indicator)}</dd>
              </>
            )}
            {criteria.timing != null && (
              <>
                <dt className="text-grey">Timing</dt>
                <dd>{scrub(criteria.timing)}</dd>
              </>
            )}
          </dl>
        </>
      )}
      {box.description !== null && <p className="mt-3 text-meta">{scrub(box.description)}</p>}
      {found !== undefined && found.case_studies.length > 0 && (
        <>
          <p className={HEAD}>Case studies ({found.case_studies.length})</p>
          <ul>
            {found.case_studies.map((study) => (
              <li key={`${study.task_source_snapshot_id}-${study.programme}`} className="border-t border-line py-2.5 text-meta">
                <p className="font-semibold text-navy">
                  {scrub(study.programme)}
                  {study.place !== null ? `, ${scrub(study.place)}` : ""}
                </p>
                <p className="mt-0.5">{scrub(study.note)}</p>
                <q className="mt-1 block text-navy">{scrub(study.quote)}</q>
                <ul>
                  <DocumentItem title={study.title} url={study.url} quote={null} source_type={study.source_type} year={study.year} evidence_type={null} />
                </ul>
              </li>
            ))}
          </ul>
        </>
      )}
      {found !== undefined && found.indicators.length > 0 && (
        <>
          <p className={HEAD}>Indicators used</p>
          <p className="text-meta">{found.indicators.map(scrub).join(" · ")}</p>
        </>
      )}
      <Origin origin={box.origin} />
    </>
  );
}

function LinkDetail({ taskId, link, graph, evidence }: { taskId: string; link: TocLink; graph: TocGraph; evidence: TocEvidence | null | undefined }) {
  const documents = evidence?.links.find((entry) => entry.link_id === link.link_id)?.documents ?? [];
  const codeOf = (boxId: string) => graph.boxes.find((box) => box.box_id === boxId)?.code ?? null;
  const [source, target] = [codeOf(link.source_box_id), codeOf(link.target_box_id)];
  // "Connection #5 · S3 → L1" (C35); rows written before codes have none.
  const codes = link.code !== null && source !== null && target !== null ? `${link.code} · ${source} → ${target}` : null;
  return (
    <>
      <p className="text-meta text-grey">
        {link.critical ? "Critical connection" : "Connection"}
        {codes !== null && <> <span className="text-caption font-semibold">{codes}</span></>}
        {link.critical && " · test this first"}
      </p>
      <h3 className="mt-0.5 text-body font-bold leading-snug text-navy">{scrub(link.sentence)}</h3>
      <p className={HEAD}>How this step works</p>
      <dl className="mt-1 grid grid-cols-[4rem_1fr] gap-x-3 gap-y-1 text-meta">
        <dt className="text-grey">If</dt>
        <dd>{scrub(link.if_text)}</dd>
        <dt className="text-grey">For</dt>
        <dd>{scrub(link.for_text)}</dd>
        <dt className="text-grey">Then</dt>
        <dd>{scrub(link.then_text)}</dd>
        <dt className="text-grey">Because</dt>
        <dd>{scrub(link.because_text)}</dd>
      </dl>
      {link.conditions.length > 0 && (
        <>
          <p className={HEAD}>Conditions</p>
          <ul className="mt-1 list-disc pl-5 text-meta">
            {link.conditions.map((condition) => (
              <li key={condition}>{scrub(condition)}</li>
            ))}
          </ul>
        </>
      )}
      {link.merged ? (
        <section className="mt-4 border-t border-line pt-3 text-meta">
          <p>
            <GradeWords grade={link.elsewhere.grade} question="merged" />
            {link.elsewhere_sentence !== null && <> {scrub(link.elsewhere_sentence)}</>}
          </p>
          <QuestionDocuments taskId={taskId} documents={documents} question="elsewhere" />
        </section>
      ) : (
        <>
          <section className="mt-4 border-t border-line pt-3 text-meta" aria-label="Worked elsewhere">
            <p className="font-bold text-navy">Worked elsewhere</p>
            <p className="mt-1">
              <GradeWords grade={link.elsewhere.grade} question="elsewhere" />
              {link.elsewhere_sentence !== null && <> {scrub(link.elsewhere_sentence)}</>}
            </p>
            <QuestionDocuments taskId={taskId} documents={documents} question="elsewhere" />
          </section>
          <section className="mt-4 border-t border-line pt-3 text-meta" aria-label="Holds here">
            <p className="font-bold text-navy">Holds here</p>
            <p className="mt-1">
              <GradeWords grade={link.here.grade} question="here" />
              {link.here_sentence !== null && <> {scrub(link.here_sentence)}</>}
            </p>
            <QuestionDocuments taskId={taskId} documents={documents} question="here" />
          </section>
        </>
      )}
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
    <aside aria-label="Details" className="max-h-[680px] w-[380px] shrink-0 overflow-y-auto border-l border-line bg-paper px-5 py-4 max-lg:w-full max-lg:border-l-0 max-lg:border-t">
      <button type="button" onClick={onClose} aria-label="Close" className="float-right cursor-pointer text-lead leading-none text-grey hover:text-navy">
        ×
      </button>
      {box !== undefined && <BoxDetail box={box} evidence={evidence} />}
      {link !== undefined && <LinkDetail taskId={taskId} link={link} graph={graph} evidence={evidence} />}
    </aside>
  );
}

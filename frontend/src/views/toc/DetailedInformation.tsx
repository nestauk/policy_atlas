import { useState } from "react";

import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { REPORT_BODY_CLASS, REPORT_LABEL_CLASS, REPORT_PART_HEADING_CLASS } from "../artefactPresentation";
import { SectionDisclosure } from "../ArtefactOutline";
import { GradeWords, QuestionDocuments } from "./Documents";
import { groupAssumptions, GRADE_VAR, keptPathways, LAYER_LABEL, pathwayTitles } from "./tocModel";
import type { TocBox, TocDocument, TocEvidence, TocGraph, TocLink, TocPathway } from "./types";

const CRITICAL = "Critical connection · test this first";
const P = `mt-1 max-w-[44em] ${REPORT_BODY_CLASS}`;

/** The small "+" after a sentence: shows or hides that question's documents. */
function WithDocuments({ taskId, documents, question, children }: { taskId: string; documents: TocDocument[]; question: "elsewhere" | "here"; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const count = documents.filter((doc) => doc[question].stance !== "not_about").length;
  return (
    <>
      <p className={P}>
        {children}
        {count > 0 && (
          <button
            type="button"
            aria-expanded={open}
            aria-label={`${open ? "Hide" : "Show"} the ${count} documents`}
            onClick={() => setOpen((value) => !value)}
            className="print-hide ml-1 inline-grid h-[18px] w-[18px] cursor-pointer place-items-center rounded-full border border-line-2 bg-paper text-meta font-bold leading-none text-grey hover:border-navy hover:text-navy"
          >
            +
          </button>
        )}
      </p>
      {open && (
        <div className="ml-4 max-w-[44em]">
          <QuestionDocuments taskId={taskId} documents={documents} question={question} />
        </div>
      )}
    </>
  );
}

function BoxRow({ box }: { box: TocBox }) {
  return (
    <div className="py-3">
      <p className={REPORT_LABEL_CLASS}>
        {LAYER_LABEL[box.layer]}
        {box.code !== null && ` · ${box.code}`}
      </p>
      <p className={`${REPORT_BODY_CLASS} font-bold text-navy`}>{scrub(box.text)}</p>
      {box.description !== null && <p className={P}>{scrub(box.description)}</p>}
    </div>
  );
}

function LinkRow({ taskId, link, documents }: { taskId: string; link: TocLink; documents: TocDocument[] }) {
  const pending = link.state === "checking" || link.state === "unchecked";
  const grade = link.lower_grade;
  return (
    <div
      className="my-1 ml-3 border-l-2 py-2 pl-5"
      style={{ borderLeftColor: pending ? "var(--color-line-2)" : GRADE_VAR[grade], borderLeftStyle: grade === "weak" || grade === "none" ? "dashed" : "solid" }}
    >
      {link.critical && <p className={REPORT_LABEL_CLASS}>{CRITICAL}</p>}
      <p className={P}>{scrub(link.sentence)}</p>
      {link.merged ? (
        <WithDocuments taskId={taskId} documents={documents} question="elsewhere">
          <GradeWords grade={link.elsewhere.grade} question="merged" />
          {link.elsewhere_sentence !== null && <> {scrub(link.elsewhere_sentence)}</>}
        </WithDocuments>
      ) : (
        <>
          <WithDocuments taskId={taskId} documents={documents} question="elsewhere">
            <GradeWords grade={link.elsewhere.grade} question="elsewhere" />
            {link.elsewhere_sentence !== null && <> {scrub(link.elsewhere_sentence)}</>}
          </WithDocuments>
          <WithDocuments taskId={taskId} documents={documents} question="here">
            <GradeWords grade={link.here.grade} question="here" />
            {link.here_sentence !== null && <> {scrub(link.here_sentence)}</>}
          </WithDocuments>
        </>
      )}
    </div>
  );
}

/** One pathway, as boxes and the connections between them, in order. */
function PathwayBody({ taskId, pathway, graph, evidence }: { taskId: string; pathway: TocPathway; graph: TocGraph; evidence: TocEvidence | null | undefined }) {
  const linkById = new Map(graph.links.map((link) => [link.link_id, link]));
  const boxById = new Map(graph.boxes.map((box) => [box.box_id, box]));
  const shown = new Set<string>();
  const rows: React.ReactNode[] = [];
  const addBox = (boxId: string) => {
    const box = boxById.get(boxId);
    if (box === undefined || shown.has(boxId)) return;
    shown.add(boxId);
    rows.push(<BoxRow key={`box-${boxId}`} box={box} />);
  };
  for (const linkId of pathway.link_ids) {
    const link = linkById.get(linkId);
    if (link === undefined) continue;
    addBox(link.source_box_id);
    const documents = evidence?.links.find((entry) => entry.link_id === linkId)?.documents ?? [];
    rows.push(<LinkRow taskId={taskId} key={`link-${linkId}`} link={link} documents={documents} />);
    addBox(link.target_box_id);
  }
  return <>{rows}</>;
}

function Assumptions({ graph }: { graph: TocGraph }) {
  const groups = groupAssumptions(graph);
  const boxText = new Map(graph.boxes.map((box) => [box.box_id, box.text]));
  if (groups.length === 0) return <p className={P}>No assumptions recorded.</p>;
  // Report typography only: a label per type, then body text. One entry per
  // link: the step it belongs to, its conditions, then its evidence once.
  return (
    <>
      {groups.map((group) => {
        const links = [...new Map(group.items.map(({ link }) => [link.link_id, link])).values()];
        return (
          <div key={group.key} className="mt-5">
            <p className={REPORT_LABEL_CLASS}>{group.label}</p>
            {links.map((link) => (
              <div key={link.link_id} className={`mt-2 max-w-[44em] ${REPORT_BODY_CLASS}`}>
                <p>
                  On the step from {scrub(boxText.get(link.source_box_id) ?? "")} to {scrub(boxText.get(link.target_box_id) ?? "")}:
                </p>
                <ul className="mt-1 list-disc pl-6">
                  {link.conditions.map((condition) => (
                    <li key={condition}>{scrub(condition)}</li>
                  ))}
                </ul>
                <p className="mt-1">
                  <GradeWords grade={link.here.grade} question="here" />
                  {link.here.grade !== "none" && link.here_sentence !== null && <> {scrub(link.here_sentence)}</>}
                  {link.critical && <strong className="text-navy"> {CRITICAL}.</strong>}
                </p>
              </div>
            ))}
          </div>
        );
      })}
    </>
  );
}

const section = (title: string, summary?: string) => ({
  title,
  role: "standard" as const,
  summary: summary ?? null,
  summary_status: summary === undefined ? null : ("verified" as const),
});

/**
 * Detailed information: the written form of the canvas, and the PDF report.
 * One section per kept pathway, then Assumptions, the set-aside pathways and
 * the questions for an evaluation. Uses the report's expand/collapse
 * sections, which open on their own when the browser prints.
 */
export function DetailedInformation({ taskId, graph, evidence }: { taskId: string; graph: TocGraph; evidence: TocEvidence | null | undefined }) {
  const titles = pathwayTitles(graph);
  const kept = keptPathways(graph);
  const setAside = graph.pathways.filter((pathway) => pathway.status === "set_aside");
  const questions = graph.summary?.evaluation_questions ?? [];
  return (
    <section aria-label="Detailed information" className="mt-10">
      <div className="flex items-center justify-between gap-4 pb-2">
        <h2 className={REPORT_PART_HEADING_CLASS}>Detailed information</h2>
        <Button variant="secondary" size="sm" className="print-hide border border-navy" onClick={() => window.print()}>
          Download as PDF
        </Button>
      </div>
      {kept.map((pathway, index) => (
        <div key={pathway.pathway_id} className="border-t border-line pt-4">
          <SectionDisclosure id={`toc-pathway-${pathway.pathway_id}`} section={section(titles.get(pathway.pathway_id) ?? pathway.label)} defaultOpen={index === 0} collapsible>
            <PathwayBody taskId={taskId} pathway={pathway} graph={graph} evidence={evidence} />
          </SectionDisclosure>
        </div>
      ))}
      <div className="border-t border-line pt-4">
        <SectionDisclosure
          id="toc-assumptions"
          section={section("Assumptions", "Every condition the theory relies on, grouped by type, with the evidence that it holds here.")}
          defaultOpen={false}
          collapsible
        >
          <Assumptions graph={graph} />
        </SectionDisclosure>
      </div>
      {setAside.length > 0 && (
        <div className="border-t border-line pt-4">
          <SectionDisclosure id="toc-set-aside" section={section("Considered and set aside")} defaultOpen={false} collapsible>
            {setAside.map((pathway) => (
              <div key={pathway.pathway_id} className="py-1">
                <p className={`${REPORT_BODY_CLASS} font-bold text-navy`}>{scrub(pathway.label)}</p>
                {pathway.reason !== null && <p className={P}>{scrub(pathway.reason)}</p>}
              </div>
            ))}
          </SectionDisclosure>
        </div>
      )}
      {questions.length > 0 && (
        <div className="border-t border-line pt-4">
          <SectionDisclosure id="toc-questions" section={section("Questions for an evaluation")} defaultOpen={false} collapsible>
            <ol className={`list-decimal space-y-1 pl-5 ${REPORT_BODY_CLASS}`}>
              {questions.map((question) => (
                <li key={question}>{scrub(question)}</li>
              ))}
            </ol>
          </SectionDisclosure>
        </div>
      )}
    </section>
  );
}

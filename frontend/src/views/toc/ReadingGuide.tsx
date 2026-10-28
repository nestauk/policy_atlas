import { scrub } from "../../lib/scrub";
import { GradeDot } from "./Documents";
import { GRADE_LABEL, GRADES } from "./tocModel";
import type { TocGraph } from "./types";

/** "How to read this": opens above the canvas. */
export function ReadingGuide({ graph }: { graph: Pick<TocGraph, "grade_rules" | "context" | "supporting_activities"> }) {
  return (
    <section aria-label="How to read this" className="mb-3 border border-line bg-paper-2 px-5 py-4 text-meta">
      <h3 className="text-body font-bold text-navy">How to read this</h3>
      <p className="mt-2 max-w-[64em]">
        Read from left to right: Inputs and activities (what the programme does), Outputs (what it delivers), Short-term outcomes (the first changes it
        should cause), Long-term outcomes (the lasting changes) and Impact (the long-term aim). The dashed line separates what the programme directly
        influences from what it contributes to. Steps that could go wrong sit below the line.
      </p>
      <p className="mt-2 max-w-[64em]">
        Boxes are the steps. The connections between them carry the evidence, and their colour shows how strong it is:{" "}
        {GRADES.map((grade, index) => (
          <span key={grade} className="whitespace-nowrap">
            <GradeDot grade={grade} />
            {GRADE_LABEL[grade].toLowerCase()}
            {index < GRADES.length - 1 ? ", " : "."}{" "}
          </span>
        ))}
        A dashed line means weak, and a dotted line means no evidence found.
      </p>
      <p className="mt-2 max-w-[64em]">
        Every connection answers two questions: did it work where it was tried (worked elsewhere), and will it work here, now (holds here)? A connection
        takes the colour of the weaker answer; hover to see both. The navy dot marks the critical connection: test it first.
      </p>
      <ul className="mt-2 max-w-[64em] space-y-1">
        {graph.grade_rules.map((row) => (
          <li key={row.label}>
            <span className="font-semibold">{scrub(row.label)}: </span>
            {scrub(row.rule)}
          </li>
        ))}
      </ul>
      {graph.context.length > 0 && (
        <p className="mt-2 max-w-[64em]">
          <span className="font-semibold">Context. </span>
          {graph.context.map(scrub).join(" ")}
        </p>
      )}
      {graph.supporting_activities.length > 0 && (
        <p className="mt-2 max-w-[64em]">
          <span className="font-semibold">Supporting activities. </span>
          {graph.supporting_activities.map(scrub).join(" · ")}
        </p>
      )}
    </section>
  );
}

import { scrub } from "../../lib/scrub";
import { VERDICT_LABEL, VERDICT_VAR, VERDICTS } from "./tocModel";
import type { TocGraph, Verdict } from "./types";

/** The critical connection's mark: a warning triangle with an exclamation point, drawn centred on (x, y). */
export function CriticalMark({ x = 0, y = 0 }: { x?: number; y?: number }) {
  return (
    <g transform={`translate(${x},${y})`} aria-hidden="true">
      <path d="M0,-9 L9,7 L-9,7 Z" fill="var(--color-paper)" stroke={VERDICT_VAR.not_confident} strokeWidth={2} strokeLinejoin="round" />
      <path d="M0,-3 L0,2" stroke={VERDICT_VAR.not_confident} strokeWidth={2} strokeLinecap="round" />
      <circle cx="0" cy="4.6" r="1.1" fill={VERDICT_VAR.not_confident} />
    </g>
  );
}

/** The critical mark at text size, for the key and the detail panel. */
export function CriticalIcon() {
  return (
    <svg width="20" height="18" viewBox="-10 -10 20 18" aria-hidden="true" className="inline-block shrink-0 align-[-3px]">
      <CriticalMark />
    </svg>
  );
}

/** A short line sample for each verdict, drawn as on the canvas (C36). */
function LineSample({ verdict }: { verdict: Verdict }) {
  const line = (stroke: string, width: number, dash?: string) => (
    <line x1="0" y1="4" x2="34" y2="4" stroke={stroke} strokeWidth={width} strokeDasharray={dash} />
  );
  return (
    <svg width="34" height="8" aria-hidden="true">
      {verdict === "confident" && line(VERDICT_VAR.confident, 3)}
      {verdict === "not_sure_mixed" && (
        <>
          {line(VERDICT_VAR.not_sure_mixed, 5)}
          {line(VERDICT_VAR.confident, 2, "6 6")}
        </>
      )}
      {verdict === "not_sure_insufficient" && line(VERDICT_VAR.not_sure_insufficient, 3, "6 5")}
      {verdict === "not_confident" && line(VERDICT_VAR.not_confident, 3, "2 5")}
    </svg>
  );
}

/** The key under the canvas: one line style per verdict, and the critical connection's mark. */
export function VerdictLegend() {
  return (
    <ul aria-label="Line key" className="mt-2 flex flex-wrap gap-x-[18px] gap-y-1 text-meta text-grey">
      {VERDICTS.map((verdict) => (
        <li key={verdict} className="inline-flex items-center gap-1.5">
          <LineSample verdict={verdict} />
          {VERDICT_LABEL[verdict]}
        </li>
      ))}
      <li className="inline-flex items-center gap-1.5">
        <CriticalIcon />
        Critical connection
      </li>
    </ul>
  );
}

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
        Boxes are the steps. Each connection between them has one evidence verdict, and its line style shows it (see the key under the canvas). The
        verdict weighs every document that supports or refutes the step by its quality and by how well it applies to this population and place. The
        connection marked with a warning triangle is the critical connection: test it first.
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

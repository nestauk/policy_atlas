import { scrub } from "../../lib/scrub";
import { VERDICT_VAR } from "../../ui/brand/verdictTones";
import { VERDICT_LABEL, VERDICTS } from "./tocModel";
import type { TocGraph, Verdict } from "./types";

/** The critical connection's mark: a warning triangle with an exclamation point, drawn centred on (x, y). */
export function CriticalMark({ x = 0, y = 0 }: { x?: number; y?: number }) {
  return (
    <g transform={`translate(${x},${y})`} aria-hidden="true">
      <path d="M0,-9 L9,7 L-9,7 Z" fill="var(--color-paper)" stroke={VERDICT_VAR.against} strokeWidth={2} strokeLinejoin="round" />
      <path d="M0,-3 L0,2" stroke={VERDICT_VAR.against} strokeWidth={2} strokeLinecap="round" />
      <circle cx="0" cy="4.6" r="1.1" fill={VERDICT_VAR.against} />
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

/** Each verdict's dash on the canvas; a solid line has none. */
const DASH: Record<Verdict, string | undefined> = {
  supported: undefined,
  not_sure_mixed: undefined,
  not_sure_insufficient: "6 5",
  against: "2 5",
  leaning_supports: "12 5",
  leaning_against: "12 5",
};

/** A short line sample for each verdict, drawn as on the canvas (C36). */
function LineSample({ verdict }: { verdict: Verdict }) {
  return (
    <svg width="34" height="8" aria-hidden="true">
      <line x1="0" y1="4" x2="34" y2="4" stroke={VERDICT_VAR[verdict]} strokeWidth={3} strokeDasharray={DASH[verdict]} />
    </svg>
  );
}

/** The key under the canvas: one line style per verdict, and the critical connection's mark. */
export function VerdictLegend() {
  return (
    <ul aria-label="Line key" className="mt-2 flex flex-wrap gap-x-4.5 gap-y-1 text-meta text-grey">
      {VERDICTS.map((verdict) => (
        <li key={verdict} className="inline-flex items-center gap-1.5">
          <LineSample verdict={verdict} />
          {VERDICT_LABEL[verdict]}
        </li>
      ))}
      <li className="inline-flex items-center gap-1.5">
        <svg width="34" height="8" aria-hidden="true">
          <line x1="0" y1="4" x2="34" y2="4" stroke="var(--color-line-2)" strokeWidth={3} />
        </svg>
        Needs evidence
      </li>
      <li className="inline-flex items-center gap-1.5">
        <CriticalIcon />
        Critical connection
      </li>
    </ul>
  );
}

/** "How to read this": opens above the canvas. */
export function ReadingGuide({ graph }: { graph: Pick<TocGraph, "grade_rules"> }) {
  return (
    <section aria-label="How to read this" className="mb-3 border border-line bg-paper px-5 py-4 text-body">
      <h3 className="text-body font-bold text-navy">How to read this</h3>
      <p className="mt-2 max-w-[44em]">
        Read from left to right: Inputs and activities (what the programme does), Outputs (what it delivers), Short-term outcomes (the first changes it
        should cause), Long-term outcomes (the lasting changes) and Impact (the long-term aim). The dashed line separates what the programme directly
        influences from what it contributes to. Steps that could go wrong sit below the line.
      </p>
      <p className="mt-2 max-w-[44em]">
        Boxes are the steps. Each connection between them has one evidence verdict, and its line style shows it (see the key under the canvas). The
        verdict weighs every document that supports or refutes the step by its quality and by how well it applies to this population and place. The
        connection marked with a warning triangle is the critical connection: test it first.
      </p>
      <ul className="mt-2 max-w-[44em] space-y-1">
        {graph.grade_rules.map((row) => (
          <li key={row.label}>
            <span className="font-semibold">{scrub(row.label)}: </span>
            {scrub(row.rule)}
          </li>
        ))}
      </ul>
    </section>
  );
}

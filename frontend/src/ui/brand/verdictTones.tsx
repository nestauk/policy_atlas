import type { components } from "../../api/gen/types";
import { TONE_HEX, TONE_VAR, type ToneColour } from "./evidence";
import { ToneSquare } from "./EvidenceMarks";

/*
 * The theory of change's verdict tones (task 054, 058 alignment phase 7;
 * owner 2026-11-09, decision 7: the shared tones everywhere). A connection's
 * verdict, a document's support and the theory's overall verdict take the
 * palette's green, yellow and red tone squares, as an evidence strength does;
 * "Not enough evidence" takes a Line 2 grey square (§ 8), the canvas line's
 * faint grey. The square always sits before the word, in ink.
 */

type Schemas = components["schemas"];

/** A connection's verdict, as the theory's read sends it. */
export type TocVerdict = Schemas["TocLinkOut"]["verdict"];
/** What one document says about a connection. */
export type TocSupport = Schemas["TocDocumentOut"]["support"];
/** The theory's overall verdict: can it work, and what does the evidence say. */
export type TocTheoryVerdict = Pick<Schemas["TocTheoryVerdictOut"], "mechanism" | "evidence">;

/** Each connection verdict's square: supports green, mixed yellow, against
 *  red, not enough evidence grey. The leaning verdicts take their side's tone;
 *  the canvas tells them apart by the line's dash. */
export const VERDICT_COLOUR: Readonly<Record<TocVerdict, ToneColour>> = {
  supported: "green",
  leaning_supports: "green",
  not_sure_mixed: "yellow",
  not_sure_insufficient: "grey",
  leaning_against: "red",
  against: "red",
};

/** Each verdict's colour as its CSS token: the canvas's lines and
 *  arrowheads, the line key and the evidence balance. */
export const VERDICT_VAR: Readonly<Record<TocVerdict, string>> = mapVerdicts(TONE_VAR);

/** Each verdict's colour as hex, for the draw.io export. */
export const VERDICT_HEX: Readonly<Record<TocVerdict, string>> = mapVerdicts(TONE_HEX);

function mapVerdicts(values: Readonly<Record<ToneColour, string>>): Record<TocVerdict, string> {
  return Object.fromEntries(Object.entries(VERDICT_COLOUR).map(([verdict, colour]) => [verdict, values[colour]])) as Record<TocVerdict, string>;
}

/** Each document support's square, as the evidence balance colours it; a
 *  document not about the step has none. */
export const SUPPORT_COLOUR: Readonly<Record<TocSupport, ToneColour | null>> = {
  strong: "green",
  weak: "green",
  mixed: "yellow",
  refutes: "red",
  not_about: null,
};

/**
 * The theory's overall verdict as a square, from what the verdict says (never
 * from its words): an implausible mechanism or evidence against is red, mixed
 * evidence yellow, supporting evidence green, too little evidence grey.
 *
 * Args:
 *   verdict: The verdict's mechanism and evidence.
 *
 * Returns:
 *   The square's colour.
 */
export function theoryVerdictColour(verdict: TocTheoryVerdict): ToneColour {
  if (verdict.mechanism === "implausible" || verdict.evidence === "against") return "red";
  if (verdict.evidence === "mixed") return "yellow";
  if (verdict.evidence === "supports") return "green";
  return "grey";
}

/** A verdict's 6 px square: the shared `ToneSquare`. Decorative; `data-tone`
 *  names its colour. The surface sets the spacing through `className`. */
export function VerdictSquare({ colour, className }: { colour: ToneColour; className?: string }) {
  return <ToneSquare colour={colour} className={className} testId="verdict-mark" />;
}

/**
 * A verdict as the theory's surfaces write it: its square, then its word in
 * ink. Inline, the square raised to the middle of the first line, so a word
 * that wraps in a narrow cell keeps its square beside its first line. The
 * surface sets the word's weight.
 */
export function VerdictMark({ colour, word, className }: { colour: ToneColour | null; word: string; className?: string }) {
  return (
    <span className={className}>
      {colour !== null && <VerdictSquare colour={colour} className="mr-1.5 mb-[0.15em]" />}
      {word}
    </span>
  );
}

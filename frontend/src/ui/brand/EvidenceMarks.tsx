import { scrub } from "../../lib/scrub";
import { cn } from "./cn";
import { readDepthColour, strengthTierColour, toneSquareClass, type ReadDepth, type ToneColour } from "./evidence";

/**
 * The 6 px tone square (round 12): the palette's green, yellow or red,
 * always before the word that says the same thing. Decorative to assistive
 * technology; `data-tone` names its colour. Spacing belongs to the surface
 * (a flex gap, or the Sources table's inline margin through `className`).
 */
export function ToneSquare({
  colour,
  className,
  testId,
}: {
  colour: ToneColour;
  className?: string;
  /** A test hook naming what the square marks ("strength-mark", "status-mark"). */
  testId?: string;
}) {
  return <span aria-hidden="true" data-testid={testId} data-tone={colour} className={cn(toneSquareClass(colour), className)} />;
}

/**
 * A strength as every surface writes it: its tone square, then the word. A
 * tier outside the vocabulary keeps its word and has no square. The
 * surface sets the spacing and the word's affordance (the dotted underline
 * of a value with a reason behind it).
 */
export function StrengthMark({
  tier,
  squareClassName,
  wordClassName,
}: {
  tier: string;
  squareClassName?: string;
  wordClassName?: string;
}) {
  const colour = strengthTierColour(tier);
  return (
    <>
      {colour !== null && <ToneSquare colour={colour} className={squareClassName} testId="strength-mark" />}
      <span className={wordClassName}>{scrub(tier)}</span>
    </>
  );
}

/**
 * A read depth as the dossier and chat write it: its tone square (green
 * full text, yellow abstract, red neither), then the word. The Sources
 * table's cell builds its own link and hover around the same square.
 */
export function DepthMark({
  depth,
  squareClassName,
  wordClassName,
}: {
  depth: ReadDepth;
  squareClassName?: string;
  wordClassName?: string;
}) {
  return (
    <>
      <ToneSquare colour={readDepthColour(depth)} className={squareClassName} testId="status-mark" />
      <span className={wordClassName}>{depth}</span>
    </>
  );
}

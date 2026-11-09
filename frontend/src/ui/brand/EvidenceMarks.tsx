import { scrub } from "../../lib/scrub";
import { cn } from "./cn";
import { readDepthColour, strengthTierColour, strengthTierName, toneSquareClass, type ReadDepth, type ToneColour } from "./evidence";

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
 * A strength as every surface writes it: its tone square, then the word in
 * the vocabulary's case ("moderate" prints "Moderate"). A tier outside the
 * vocabulary keeps its word and has no square. The
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
      <span className={wordClassName}>{scrub(strengthTierName(tier))}</span>
    </>
  );
}

/**
 * A read depth as the Sources table, the dossier and chat write it: its
 * tone square (green full text, yellow abstract, red neither), then the
 * word. With `href` (the document's own address, once the text was
 * collected; round 12, and the dossier too on 2026-11-09) the word is the
 * link to it, opening in a new tab as the report's addresses do. The table
 * builds its own hover around the same square for the other depths.
 */
export function DepthMark({
  depth,
  href,
  squareClassName,
  wordClassName,
}: {
  depth: ReadDepth;
  /** A safe address for the document (`safeHref`), or none. */
  href?: string;
  squareClassName?: string;
  wordClassName?: string;
}) {
  return (
    <>
      <ToneSquare colour={readDepthColour(depth)} className={squareClassName} testId="status-mark" />
      {href !== undefined ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${depth} (opens the document in a new tab)`}
          className={cn("text-link", wordClassName)}
        >
          {depth}
        </a>
      ) : (
        <span className={wordClassName}>{depth}</span>
      )}
    </>
  );
}

import { Fragment, useEffect, useState } from "react";

import { scrub } from "../../lib/scrub";
import { cn } from "../../ui/brand/cn";
import { prefersReducedMotion } from "../../ui/motion/motion";
import { useRevealedText } from "../streamPacing";

/** The old text's fade (`anim-fade-out`). */
const LEAVE_MS = 150;

/** The batch fade's length (`anim-word-in`). */
const WORD_FADE_MS = 150;

/**
 * A name that changes as a generation (owner, round 14): when `text`
 * changes while it is on screen (the backend names a task from its
 * confirmed question, or a chat from its first message), the old text fades
 * out over 150 ms, then the new one is revealed in place the way streamed
 * text is (`useRevealedText`: whole words at the steady pace, each batch
 * fading in), with no width easing. A first render holds still, so a
 * reader's own rename (which remounts it) just commits. Under reduced
 * motion it is a cut. A screen reader hears the new text throughout.
 *
 * The root is a `peer` carrying `data-changing` while it changes, so a
 * control after it (the name's menu chevron) can fade with it.
 *
 * Args:
 *   text: The text now.
 *   wrap: Wraps as text; otherwise it truncates on one line.
 *   className: The text's type.
 *   testIdPrefix: Names the leaving and revealing parts for tests.
 */
export function ChangingText({
  text,
  wrap = false,
  className,
  testIdPrefix = "text",
}: {
  text: string;
  wrap?: boolean;
  className?: string;
  testIdPrefix?: string;
}) {
  const [seen, setSeen] = useState(text);
  const [leaving, setLeaving] = useState<string | null>(null);
  const [revealing, setRevealing] = useState(false);
  // Derived during render, so the old text starts leaving in the commit
  // that brings the new one.
  if (seen !== text) {
    setSeen(text);
    if (!prefersReducedMotion()) {
      setLeaving(seen);
      setRevealing(false);
    }
  }
  // The old text's fade, then the reveal.
  useEffect(() => {
    if (leaving === null) return undefined;
    const id = window.setTimeout(() => {
      setLeaving(null);
      setRevealing(true);
    }, LEAVE_MS);
    return () => window.clearTimeout(id);
  }, [leaving]);
  const textClass = cn("min-w-0", wrap ? "text-pretty" : "truncate", className);
  return (
    <span className={cn("peer min-w-0", wrap ? "" : "flex")} data-changing={leaving !== null || revealing ? "true" : undefined}>
      {leaving !== null ? (
        <>
          <span aria-hidden="true" data-testid={`${testIdPrefix}-leaving`} className={cn(textClass, "anim-fade-out")}>
            {scrub(leaving)}
          </span>
          <span className="sr-only">{scrub(text)}</span>
        </>
      ) : revealing ? (
        <RevealedText text={text} className={textClass} testId={`${testIdPrefix}-revealing`} onDone={() => setRevealing(false)} />
      ) : (
        <span className={textClass}>{scrub(text)}</span>
      )}
    </span>
  );
}

/** The new text at the streamed text's pace: whole words, each batch fading
 *  in (`anim-word-in`), the whole text told to a screen reader at once. */
function RevealedText({ text, className, testId, onDone }: { text: string; className: string; testId: string; onDone: () => void }) {
  // A trailing space ends the last word, so it comes at the same pace
  // rather than after the reveal's idle wait.
  const revealed = useRevealedText(`${text} `, false, 0);
  const chars = Array.from(revealed.text);
  const shown = chars.length;
  const done = revealed.text.trimEnd() === text;
  useEffect(() => {
    if (!done) return undefined;
    // After the last batch's fade.
    const id = window.setTimeout(onDone, WORD_FADE_MS);
    return () => window.clearTimeout(id);
  }, [done, onDone]);
  const cuts = revealed.batches.filter((cut) => cut > 0 && cut < shown);
  const bounds = [0, ...cuts, shown];
  return (
    <span className={className}>
      <span aria-hidden="true" data-testid={testId}>
        {bounds.slice(0, -1).map((from, at) => {
          const piece = scrub(chars.slice(from, bounds[at + 1]).join(""));
          return at === 0 ? <Fragment key={from}>{piece}</Fragment> : <span key={from} className="anim-word-in">{piece}</span>;
        })}
      </span>
      <span className="sr-only">{scrub(text)}</span>
    </span>
  );
}

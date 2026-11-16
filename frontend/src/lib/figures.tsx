import { Fragment } from "react";

/**
 * Text whose digits are set in tabular figures, so a ticking count or timer
 * does not shift as its digits change, while the words and spaces around
 * them keep their normal width (Averta's tabular feature also widens the
 * space, so it cannot go on the whole line).
 *
 * Args:
 *   text: The line to show, already scrubbed.
 */
export function Figures({ text }: { text: string }) {
  const parts = text.split(/(\d[\d,.]*)/);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <span key={index} className="tabular-nums">
            {part}
          </span>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  );
}

import type { SVGProps } from "react";

/** The four action glyphs of the longlist and shortlist rows (task 055):
 *  one stroke weight, 16px box, `currentColor`, so they sit in a ghost
 *  button beside text at Meta size. Drawn here; the app carries no icon
 *  library. */
const BASE: SVGProps<SVGSVGElement> = {
  width: 16,
  height: 16,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
  focusable: false,
};

/** Add to shortlist. */
export function PlusIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...BASE} {...props}>
      <path d="M8 3v10M3 8h10" />
    </svg>
  );
}

/** Remove from shortlist. */
export function MinusIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...BASE} {...props}>
      <path d="M3 8h10" />
    </svg>
  );
}

/** Exclude: a circle with a bar. */
export function BanIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...BASE} {...props}>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M4.2 4.2l7.6 7.6" />
    </svg>
  );
}

/** Include again: an arrow turning back. */
export function UndoIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...BASE} {...props}>
      <path d="M6 4.5L3.5 7l2.5 2.5" />
      <path d="M3.5 7h5.25a3.25 3.25 0 010 6.5H7" />
    </svg>
  );
}

import { useEffect } from "react";
import { flushSync } from "react-dom";

import { cn } from "./cn";
import { ChevronIcon } from "./icons";

/**
 * The one rotating chevron (task 058, consolidation batch B; DESIGN.md §
 * Disclosure): the 12 px glyph pointing right when shut, turning down over
 * 200 ms on the strong ease-out as it opens, at a cut under reduced motion.
 * Grey, turning Navy with its control's hover: the control carries `group`.
 * Every disclosure draws it: `DisclosureWord`, the search queries' line, the
 * option card's documents, History's rows and "Show steps", the trace's
 * "Show steps", the Findings rows, the report's contents, the longlist's
 * "Show all" and the chats' Archived. A surface sets only its seat (a
 * margin, `self-center`) through `className`.
 *
 * Args:
 *   open: Whether the disclosure is open. Omit it when the open state lives
 *     in CSS (a `<details>`), and turn it with a `group-open:` class.
 *   className: The surface's seat.
 */
export function DisclosureChevron({ open = false, className }: { open?: boolean; className?: string }) {
  return (
    <ChevronIcon
      size={12}
      className={cn(
        "shrink-0 text-grey transition-[transform,color] duration-200 ease-[var(--ease-out-strong)] group-hover:text-navy motion-reduce:transition-none",
        open && "rotate-90",
        className,
      )}
    />
  );
}

/**
 * The report's one disclosure vocabulary (round 10, C7): the chevron, then
 * "Show" or "Hide", Grey Semibold Meta over a Line 2 underline that turns
 * Navy on hover, as the trace's "Show steps" and the search queries' "Show".
 * The chevron points right when shut and turns down as it opens (200 ms).
 * Decorative inside a disclosure button (its name is the heading), so
 * `aria-hidden`; it hides in print, where everything prints open.
 */
export function DisclosureWord({
  open,
  className,
  named = false,
}: {
  open: boolean;
  className?: string;
  /** The word names its own button (the phone's twin toggle). */
  named?: boolean;
}) {
  return (
    <span
      aria-hidden={named ? undefined : true}
      className={cn("print-hide inline-flex shrink-0 items-center gap-1 text-meta font-semibold text-grey", className)}
    >
      <DisclosureChevron open={open} />
      <span className="underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 group-hover:text-navy group-hover:decoration-navy">
        {open ? "Hide" : "Show"}
      </span>
    </span>
  );
}

/** Open a collapsed section when the browser is about to print, so the PDF
 *  contains the full report rather than the on-screen collapsed summaries.
 *  `flushSync` is required: without it, `window.print()` can capture the
 *  still-collapsed DOM before React commits the expand. */
export function useExpandForPrint(setOpen: (open: boolean) => void): void {
  useEffect(() => {
    const expand = () => {
      flushSync(() => {
        setOpen(true);
      });
    };
    window.addEventListener("beforeprint", expand);
    return () => window.removeEventListener("beforeprint", expand);
  }, [setOpen]);
}

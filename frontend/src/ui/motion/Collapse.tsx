import { useEffect, useState, type ReactNode } from "react";

import { cn } from "../brand/cn";
import { ARRIVE_MS, prefersReducedMotion } from "./motion";

/** Whether the page can run the collapse: not under reduced motion, and not
 *  in a DOM without Web Animations (the tests' jsdom), where it cuts. */
function cuts(): boolean {
  return (
    typeof document === "undefined" ||
    typeof document.body?.animate !== "function" ||
    prefersReducedMotion()
  );
}

/**
 * A block that opens and closes by easing its height (task 058, round 9):
 * `grid-template-rows` from 0fr to 1fr and its opacity, on the strong
 * ease-out. While it closes it keeps its children, so they fold away rather
 * than vanish, and it unmounts them once closed. It clips only while it
 * moves or is shut, so focus rings and shadows inside it show at rest.
 * Under reduced motion (and where Web Animations are missing) it is a cut.
 *
 * Args:
 *   show: Whether the block is open.
 *   appear: Ease open on the first mount too (an arrival); otherwise a block
 *     that mounts open is simply there.
 *   durationMs: How long the height eases (300 ms; 200 ms for a fold).
 *   children: The content. Pass it whether or not `show`, so a closing block
 *     has something to fold away.
 */
export function Collapse({
  show,
  appear = false,
  durationMs = ARRIVE_MS,
  className,
  children,
}: {
  show: boolean;
  appear?: boolean;
  durationMs?: number;
  className?: string;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(show);
  const [moving, setMoving] = useState(show && appear);
  const [last, setLast] = useState(show);
  if (last !== show) {
    setLast(show);
    setMoving(true);
    if (show) setMounted(true);
  }

  useEffect(() => {
    if (!moving) return undefined;
    const id = window.setTimeout(() => {
      setMoving(false);
      if (!show) setMounted(false);
    }, durationMs);
    return () => window.clearTimeout(id);
  }, [moving, show, durationMs]);

  if (!mounted && !show) return null;
  if (!show && cuts()) return null;
  return (
    <div
      data-collapse={show ? "open" : "closed"}
      aria-hidden={show ? undefined : true}
      inert={!show}
      className={cn(
        "grid transition-[grid-template-rows,opacity] ease-[var(--ease-out-strong)] motion-reduce:transition-none",
        show ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
        appear && "starting:grid-rows-[0fr] starting:opacity-0",
        className,
      )}
      style={{ transitionDuration: `${durationMs}ms` }}
    >
      <div className={cn("min-h-0", (moving || !show) && "overflow-hidden")}>{children}</div>
    </div>
  );
}

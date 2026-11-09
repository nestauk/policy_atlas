import { useLayoutEffect, type ReactNode } from "react";

import { useArrives } from "../../ui/motion/arrivals";
import { prefersReducedMotion } from "../../ui/motion/motion";
import { EASE_HEIGHT_MS, EASING_ATTR, useEasedHeight } from "../streamPacing";

/** The strong ease-out (`--ease-out-strong`). */
const EASE_OUT_STRONG = "cubic-bezier(0.23, 1, 0.32, 1)";

/**
 * A block of the Task Agent thread that grows smoothly (owner, round 14:
 * the action line popping back after an answer, a decision card appearing
 * and the progress card appearing all jumped).
 *
 * Arriving after the thread's first paint, it opens from nothing to its
 * height over 300 ms on the strong ease-out, so the thread around it makes
 * room gradually instead of the block landing under the thread's clip and
 * sliding back. Afterwards it eases to every new height (`useEasedHeight`):
 * a turn on its way that becomes the stored one (the same block, keyed by
 * the turn's id) eases from the action line to the decision card in place.
 * The open runs in a layout effect, before the thread's own box measures,
 * so the thread sees no jump to ease. History holds still; under reduced
 * motion it is a cut.
 *
 * Args:
 *   arrivalId: The block's arrival id (the thread's `ArrivalProvider`).
 *   children: The block.
 */
export function GrowBox({ arrivalId, children }: { arrivalId: string; children: ReactNode }) {
  const reduced = prefersReducedMotion();
  const arrives = useArrives(`grow:${arrivalId}`);
  const [box, content] = useEasedHeight(!reduced);
  // On arrival only: later heights are `useEasedHeight`'s.
  useLayoutEffect(() => {
    if (arrives && !reduced) openFromNothing(box.current, content.current);
  }, [arrives, reduced, box, content]);
  return (
    <div ref={box}>
      <div ref={content}>{children}</div>
    </div>
  );
}

/** Opens a block from nothing to its height, marked as easing so the boxes
 *  around it follow rather than ease it again. */
function openFromNothing(outer: HTMLElement | null, inner: HTMLElement | null): void {
  if (outer === null || inner === null || typeof outer.animate !== "function") return;
  const height = inner.offsetHeight;
  if (height < 1) return;
  outer.style.overflow = "clip";
  outer.setAttribute(EASING_ATTR, "");
  const animation = outer.animate([{ height: "0px" }, { height: `${height}px` }], {
    duration: EASE_HEIGHT_MS,
    easing: EASE_OUT_STRONG,
  });
  animation.onfinish = () => {
    outer.style.overflow = "";
    outer.removeAttribute(EASING_ATTR);
  };
}

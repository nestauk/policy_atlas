import type { ReactNode } from "react";

import { useArrives } from "../../ui/motion/arrivals";
import { prefersReducedMotion } from "../../ui/motion/motion";
import { useEasedHeight } from "../streamPacing";

/**
 * A block of the Task Agent thread that grows smoothly (owner, round 14:
 * the action line popping back after an answer, a decision card appearing
 * and the progress card appearing all jumped).
 *
 * Arriving after the thread's first paint, it opens from nothing to its
 * height over 300 ms on the strong ease-out, so the thread around it makes
 * room gradually instead of jumping. Afterwards it eases every new height
 * (`useEasedHeight`): a turn on its way that becomes the stored one (the
 * same block, keyed by the turn's id) eases from the action line to the
 * decision card in place. It opens before its first paint, so the thread's
 * own box sees no jump to ease. History holds still; under reduced motion
 * it is a cut.
 *
 * Args:
 *   arrivalId: The block's arrival id (the thread's `ArrivalProvider`).
 *   children: The block.
 */
export function GrowBox({ arrivalId, children }: { arrivalId: string; children: ReactNode }) {
  const arrives = useArrives(`grow:${arrivalId}`);
  const [box, content] = useEasedHeight(!prefersReducedMotion(), false, arrives);
  return (
    <div ref={box}>
      <div ref={content}>{children}</div>
    </div>
  );
}

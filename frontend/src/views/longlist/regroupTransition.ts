import { useEffect, useState } from "react";
import { flushSync } from "react-dom";

import { prefersReducedMotion } from "../../ui/motion/motion";

/** The class `longlist.css` keys the regrouping's names on, set on the
 *  document only while a regrouping transition runs. */
const REGROUPING_CLASS = "longlist-regrouping";

type ViewTransitionStart = (update: () => void) => { finished: Promise<void> };

/** The browser's View Transition, when it has one (not jsdom, not every browser). */
function viewTransitionStart(): ViewTransitionStart | null {
  const start = (document as Document & { startViewTransition?: ViewTransitionStart }).startViewTransition;
  return typeof start === "function" ? start.bind(document) : null;
}

/**
 * The value on screen, moving its rows when their order or grouping changes
 * (round 10, finding 2; round 12: a shortlist toggle moves the row to the
 * head of its group or grid cell the same way). Rows already on screen keep
 * their opacity and travel to their new place over 300 ms on the strong
 * ease-out (a View Transition, each row named by its option through
 * `--longlist-row` and the `longlist-row` class), so the list never blanks.
 * A change that keeps the signature (a value landing) shows at once. Without
 * View Transitions, or under reduced motion, the rows cut to their new order.
 *
 * Args:
 *   value: What the view renders now (memoised on the reads).
 *   signature: The rows' order and grouping; a change moves them.
 *
 * Returns:
 *   The value to render.
 */
export function useRegroupTransition<T>(value: T, signature: string): T {
  const [shown, setShown] = useState({ signature, value });
  // A value landing within the same order updates in place.
  if (shown.signature === signature && shown.value !== value) setShown({ signature, value });
  useEffect(() => {
    if (shown.signature === signature) return;
    const commit = () => setShown({ signature, value });
    const start = viewTransitionStart();
    if (start === null || prefersReducedMotion()) {
      commit();
      return;
    }
    const root = document.documentElement;
    root.classList.add(REGROUPING_CLASS);
    const transition = start(() => flushSync(commit));
    void transition.finished.finally(() => root.classList.remove(REGROUPING_CLASS));
  }, [signature, value, shown.signature]);
  return shown.signature === signature ? value : shown.value;
}

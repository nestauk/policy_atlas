import { useCallback, useEffect, useRef } from "react";
import type { UIEvent, WheelEvent } from "react";

/** Reaching the end is not asking for the footer. */
const AT_END_WITHIN = 8;
/** Wheel travel past the end that counts as asking (a deliberate extra nudge). */
const OVERSCROLL_TO_OPEN = 80;
/** Scrolling this far back up hides the footer again. */
const HIDE_BEYOND = 120;

/** The Agent tab's footer reveal (038 V8, owner 2026-09-05): the site footer
 *  under the conversation opens only when the reader keeps scrolling down
 *  while already at the transcript's end — a deliberate nudge, not merely
 *  arriving there — so the composer can rest at the bottom of the screen
 *  without the footer sliding in under it. Any upward scroll hides it.
 *
 * Args:
 *   onChange: Called with `true`/`false` when the footer should open/close.
 *
 * Returns:
 *   `onScroll` and `onWheel` handlers for the scroll region.
 */
export function useFooterReveal(onChange?: (open: boolean) => void) {
  const open = useRef(false);
  const overscroll = useRef(0);
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const set = (next: boolean) => {
    if (next === open.current) return;
    open.current = next;
    onChangeRef.current?.(next);
  };
  const distanceFromEnd = (el: HTMLElement) => el.scrollHeight - el.scrollTop - el.clientHeight;

  const onScroll = useCallback((event: UIEvent<HTMLElement>) => {
    const distance = distanceFromEnd(event.currentTarget);
    if (distance > AT_END_WITHIN) overscroll.current = 0;
    if (distance > HIDE_BEYOND) set(false);
  }, []);

  const onWheel = useCallback((event: WheelEvent<HTMLElement>) => {
    if (event.deltaY < 0) {
      overscroll.current = 0;
      set(false);
      return;
    }
    if (distanceFromEnd(event.currentTarget) > AT_END_WITHIN) return;
    overscroll.current += event.deltaY;
    if (overscroll.current >= OVERSCROLL_TO_OPEN) set(true);
  }, []);

  return { onScroll, onWheel };
}

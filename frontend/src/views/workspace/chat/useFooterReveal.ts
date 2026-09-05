import { useEffect, useRef } from "react";
import type { TouchEvent, UIEvent, WheelEvent } from "react";

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
 *   `onScroll`, `onWheel`, `onTouchStart` and `onTouchMove` handlers for the
 *   scroll region — the wheel/trackpad and the touch forms of the same nudge.
 */
export function useFooterReveal(onChange?: (open: boolean) => void) {
  const open = useRef(false);
  const overscroll = useRef(0);
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  // Everything below reads refs only, so the handlers are stable by
  // construction — no memoisation needed.
  const set = (next: boolean) => {
    if (next === open.current) return;
    open.current = next;
    onChangeRef.current?.(next);
  };
  const distanceFromEnd = (el: HTMLElement) => el.scrollHeight - el.scrollTop - el.clientHeight;

  const onScroll = (event: UIEvent<HTMLElement>) => {
    const distance = distanceFromEnd(event.currentTarget);
    if (distance > AT_END_WITHIN) overscroll.current = 0;
    if (distance > HIDE_BEYOND) set(false);
  };

  // One rule for both input forms: `deltaY` > 0 is the content moving up
  // (the reader asking for more below), < 0 is the reader coming back.
  const nudge = (el: HTMLElement, deltaY: number) => {
    if (deltaY < 0) {
      overscroll.current = 0;
      set(false);
      return;
    }
    if (distanceFromEnd(el) > AT_END_WITHIN) return;
    overscroll.current += deltaY;
    if (overscroll.current >= OVERSCROLL_TO_OPEN) set(true);
  };

  const onWheel = (event: WheelEvent<HTMLElement>) => nudge(event.currentTarget, event.deltaY);

  // Touch: a finger travelling up the screen scrolls the content down, so the
  // nudge is the finger's upward travel once the transcript is at its end.
  const lastTouchY = useRef<number | null>(null);
  const onTouchStart = (event: TouchEvent<HTMLElement>) => {
    lastTouchY.current = event.touches[0]?.clientY ?? null;
  };
  const onTouchMove = (event: TouchEvent<HTMLElement>) => {
    const y = event.touches[0]?.clientY;
    if (y === undefined || lastTouchY.current === null) return;
    const deltaY = lastTouchY.current - y;
    lastTouchY.current = y;
    if (deltaY !== 0) nudge(event.currentTarget, deltaY);
  };

  return { onScroll, onWheel, onTouchStart, onTouchMove };
}

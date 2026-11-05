import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";

/*
 * Streamed prose, paced in the browser (task 058, owner round 7: "feels a bit
 * jittery"; recipe in research/streaming-text-smoothness.md).
 *
 * The store's `draft` stays the arrival target. The page shows a revealed
 * prefix of it that a frame loop grows at a steady rate, faster when the
 * backlog is large, and only ever up to the end of a whole word, so bursts
 * from the network are spread out and no half-word is shown.
 */

/** Characters per millisecond the reveal never drops below. A tuning value,
 *  not sourced: about the measured arrival rate of 2 to 6 words every 80 to
 *  160 ms. */
export const REVEAL_BASE_RATE = 0.15;

/** The backlog shrinks with this time constant (it is revealed at
 *  backlog / window characters per millisecond, so a burst of any size
 *  loses about two thirds of its backlog in one window, then finishes at
 *  the base rate). A tuning value, not sourced: longer is smoother but lags
 *  the arrival more. */
export const REVEAL_CATCH_UP_MS = 800;

/** After this long with no new text the trailing word is shown too, so a
 *  draft that ends without a space (the writer is checking its claims) is
 *  never held back. A tuning value, not sourced. */
export const REVEAL_IDLE_FLUSH_MS = 500;

/** How many recent reveal batches are kept for the fade (older ones have
 *  long finished fading). */
const BATCHES_KEPT = 64;

/** A reader within this many pixels of the end of the scrolling pane is
 *  following the text as it grows. */
export const FOLLOW_WITHIN_PX = 40;

/** The end of the last whole word at or before `limit`: the position just
 *  after the last whitespace character, or 0 when there is none. */
export function wordBoundary(chars: readonly string[], limit: number): number {
  for (let at = Math.min(limit, chars.length); at > 0; at -= 1) {
    if (/\s/.test(chars[at - 1])) return at;
  }
  return 0;
}

/** How many leading code points two strings share. */
function sharedPrefix(a: readonly string[], b: readonly string[]): number {
  const most = Math.min(a.length, b.length);
  let at = 0;
  while (at < most && a[at] === b[at]) at += 1;
  return at;
}

function tabHidden(): boolean {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

/**
 * The part of a streamed draft to show now.
 *
 * A frame loop reveals characters at max(base rate, backlog / catch-up
 * window), snapped back to the end of a whole word, with one state update
 * per frame; it stops when it has caught up and starts again when the draft
 * grows. A draft that is replaced rather than extended (a revision) cuts the
 * revealed part back to what the two share, during render, so no frame shows
 * text that is gone. A hidden tab and a finished section show everything.
 * Text already there when the section mounts shows at once.
 *
 * Args:
 *   draft: The text that has arrived so far.
 *   complete: True when the section or the run has ended: show it all.
 *
 * Returns:
 *   `text`, the revealed prefix of `draft`, and `batches`, the code-point
 *   offsets where each recent frame's reveal began (text already there at
 *   mount is not a batch), for the live paragraph's fade.
 */
export function useRevealedText(draft: string, complete = false): { text: string; batches: readonly number[] } {
  const chars = useMemo(() => Array.from(draft), [draft]);
  const [state, setState] = useState<{ draft: string; chars: string[]; shown: number; batches: readonly number[] }>(
    () => ({ draft, chars, shown: chars.length, batches: [] }),
  );
  let shown = state.shown;
  let batches = state.batches;
  if (state.draft !== draft) {
    // Extended: keep what is shown. Replaced: keep only what the two share.
    shown = draft.startsWith(state.draft)
      ? state.shown
      : Math.min(state.shown, wordBoundary(chars, sharedPrefix(state.chars, chars)));
    batches = state.batches.filter((start) => start < shown);
    setState({ draft, chars, shown, batches });
  }
  if (complete || shown > chars.length) shown = chars.length;

  const shownRef = useRef(shown);
  useLayoutEffect(() => {
    shownRef.current = shown;
  }, [shown]);

  useEffect(() => {
    const showAll = () => {
      shownRef.current = chars.length;
      setState((current) => (current.draft === draft ? { ...current, shown: chars.length } : current));
    };
    if (complete || tabHidden()) {
      if (shownRef.current < chars.length) showAll();
      return undefined;
    }
    let frame = 0;
    let last: number | null = null;
    let budget = 0;
    let flush = false;
    const step = (now: number) => {
      frame = 0;
      const elapsed = last === null ? 16 : Math.max(0, now - last);
      last = now;
      const current = shownRef.current;
      const limit = flush ? chars.length : wordBoundary(chars, chars.length);
      if (current >= limit) return;
      const backlog = limit - current;
      budget = Math.min(backlog, budget + elapsed * Math.max(REVEAL_BASE_RATE, backlog / REVEAL_CATCH_UP_MS));
      const reach = Math.min(limit, current + Math.floor(budget));
      const next = reach >= limit ? limit : wordBoundary(chars, reach);
      if (next > current) {
        budget -= next - current;
        shownRef.current = next;
        const from = current;
        setState((state) =>
          state.draft === draft
            ? { ...state, shown: next, batches: [...state.batches, from].slice(-BATCHES_KEPT) }
            : state,
        );
      }
      if (shownRef.current < limit) frame = requestAnimationFrame(step);
    };
    const kick = () => {
      if (frame === 0) frame = requestAnimationFrame(step);
    };
    kick();
    const idle = window.setTimeout(() => {
      flush = true;
      kick();
    }, REVEAL_IDLE_FLUSH_MS);
    const onVisibility = () => {
      if (tabHidden()) showAll();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      if (frame !== 0) cancelAnimationFrame(frame);
      window.clearTimeout(idle);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [draft, chars, complete]);

  const text = useMemo(() => (shown >= chars.length ? draft : chars.slice(0, shown).join("")), [shown, chars, draft]);
  return useMemo(() => ({ text, batches }), [text, batches]);
}

/**
 * Hold a block's height while a revision shortens its text, until the text
 * grows back past it, so the content below does not jump up and back. It is
 * measured and set before paint, so no frame shows the shorter block.
 *
 * Args:
 *   length: The text's length now.
 *
 * Returns:
 *   The ref for the block (its first child is the text) and its style.
 */
export function useHoldHeightWhileShorter(
  length: number,
): [RefObject<HTMLDivElement | null>, { minHeight: number } | undefined] {
  const ref = useRef<HTMLDivElement>(null);
  const [hold, setHold] = useState<number | null>(null);
  const previous = useRef({ length, height: 0 });
  useLayoutEffect(() => {
    const box = ref.current;
    if (box === null) return;
    const natural = (box.firstElementChild as HTMLElement | null)?.offsetHeight ?? box.offsetHeight;
    if (length < previous.current.length && previous.current.height > 0) {
      setHold(Math.max(hold ?? 0, previous.current.height));
    } else if (hold !== null && natural >= hold) {
      setHold(null);
    }
    previous.current = { length, height: Math.max(natural, hold ?? 0) };
  }, [length, hold]);
  return [ref, hold === null ? undefined : { minHeight: hold }];
}

/** The nearest ancestor that scrolls vertically, else the document. */
export function scrollPane(element: HTMLElement): HTMLElement {
  for (let node = element.parentElement; node !== null; node = node.parentElement) {
    const overflow = getComputedStyle(node).overflowY;
    if (overflow === "auto" || overflow === "scroll") return node;
  }
  return (document.scrollingElement as HTMLElement | null) ?? document.documentElement;
}

/** Whether the pane is scrolled to within `FOLLOW_WITHIN_PX` of its end. */
export function nearEnd(pane: HTMLElement): boolean {
  return pane.scrollHeight - pane.scrollTop - pane.clientHeight <= FOLLOW_WITHIN_PX;
}

/**
 * Follow streamed text down the page only for a reader already at the end.
 *
 * Never moves a reader who is anywhere else: a reader within about 40 px of
 * the end of the scrolling pane is kept at the end as the content grows; the
 * first scroll upwards stops that until they come back to the end. Content
 * growing above a reader is left to the browser's scroll anchoring.
 *
 * Args:
 *   anchorRef: An element inside the growing content (its scrolling pane
 *     and its `main` are found from it).
 *   active: True while text is streaming.
 */
export function useFollowTail(anchorRef: RefObject<HTMLElement | null>, active: boolean): void {
  useEffect(() => {
    const anchor = anchorRef.current;
    if (!active || anchor === null) return undefined;
    const pane = scrollPane(anchor);
    const content = anchor.closest("main") ?? anchor.parentElement ?? anchor;
    const events: HTMLElement | Window = pane === document.scrollingElement ? window : pane;
    let following = nearEnd(pane);
    let lastTop = pane.scrollTop;
    const onScroll = () => {
      const top = pane.scrollTop;
      if (top < lastTop - 1) following = false;
      else if (nearEnd(pane)) following = true;
      lastTop = top;
    };
    const observer = new ResizeObserver(() => {
      if (!following) return;
      pane.scrollTop = pane.scrollHeight;
      lastTop = pane.scrollTop;
    });
    observer.observe(content);
    events.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      observer.disconnect();
      events.removeEventListener("scroll", onScroll);
    };
  }, [anchorRef, active]);
}

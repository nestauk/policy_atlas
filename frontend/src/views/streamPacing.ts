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
 *   initialShown: How much of `draft` to show at mount (code points), for a
 *     block that takes over from another mid-reveal (the Task Agent's reply
 *     as its streamed turn becomes the stored one); default all of it.
 *
 * Returns:
 *   `text`, the revealed prefix of `draft`, and `batches`, the code-point
 *   offsets where each recent frame's reveal began (text already there at
 *   mount is not a batch), for the live paragraph's fade.
 */
export function useRevealedText(
  draft: string,
  complete = false,
  initialShown?: number,
): { text: string; batches: readonly number[] } {
  const chars = useMemo(() => Array.from(draft), [draft]);
  const [state, setState] = useState<{ draft: string; chars: string[]; shown: number; batches: readonly number[] }>(
    () => ({ draft, chars, shown: Math.min(initialShown ?? chars.length, chars.length), batches: [] }),
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

/** Marks an eased box while its height animation runs, so a box around it
 *  follows the in-between heights instead of easing them again. */
export const EASING_ATTR = "data-easing";

/** Eased boxes waiting to measure a change, run together deepest first. */
let pendingMeasures: { depth: number; measure: () => void }[] = [];

/** How many elements enclose `element`: a nested box is deeper than the box
 *  around it. */
function depthOf(element: Element): number {
  let depth = 0;
  for (let node = element.parentElement; node !== null; node = node.parentElement) depth += 1;
  return depth;
}

/**
 * Measure a box's change once every observer has heard it, the deepest box
 * first (round 14: the thread's box, created first, measured a reply's new
 * line before the reply's own box had eased it, and clipped the action line
 * under it). All the observers hear one change in the same delivery; the
 * flush runs after it, so a nested box always absorbs its own change before
 * a box around it measures.
 */
function scheduleMeasure(depth: number, measure: () => void): void {
  if (pendingMeasures.length === 0) {
    queueMicrotask(() => {
      const batch = pendingMeasures.sort((a, b) => b.depth - a.depth);
      pendingMeasures = [];
      for (const item of batch) item.measure();
    });
  }
  pendingMeasures.push({ depth, measure });
}

/** How long a section's height takes to follow its text when repaired
 *  sentences change length (task 058, owner round 8). */
export const EASE_HEIGHT_MS = 300;

/** The strong ease-out (`--ease-out-strong`). */
const EASE_OUT_STRONG = "cubic-bezier(0.23, 1, 0.32, 1)";

/**
 * Ease a box to its content's new height instead of jumping, so a sentence
 * that grows or shrinks moves the text below it smoothly (task 058, owner
 * round 8: repairs of several claims).
 *
 * The content is watched with a MutationObserver, whose callback runs as a
 * microtask after the DOM changes and before the browser lays out and
 * paints; each change of the content's height starts a 300 ms height
 * animation on the box (Web Animations, strong ease-out) from wherever the
 * box is now, so a change during a change carries on from the current
 * height. (A ResizeObserver would start the animation inside its own
 * delivery, resizing the boxes around it that other observers watch, and
 * the browser reports that as a "ResizeObserver loop"; round 9.) The box clips
 * while it animates and is left alone otherwise. Off (`active` false) it does
 * nothing, and the caller turns it off under reduced motion.
 *
 * With `growOnly` a shrink passes straight through (the Task Agent thread,
 * task 058 round 9: a settling card eases its own height, and two height
 * animations would chase each other).
 *
 * Boxes nest (round 12: the thread around a streamed reply). The change is
 * measured after every observer has heard it, the deepest box first
 * (round 14), so an eased box inside this one that hears the same change
 * starts its own ease first and this box eases only what that one does not
 * absorb. A ResizeObserver only
 * reads: it keeps the height to ease from current while the content grows
 * without a DOM change here (the inner box opening); and a grow-only box
 * whose ease ends short of content that grew under it carries on from
 * there.
 *
 * Args:
 *   active: True while the height should ease.
 *   growOnly: Ease growth only; a shrink is a cut.
 *
 * Returns:
 *   The refs for the box and for its content (the box's only child).
 */
export function useEasedHeight(
  active: boolean,
  growOnly = false,
): [RefObject<HTMLDivElement | null>, RefObject<HTMLDivElement | null>] {
  const box = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const outer = box.current;
    const inner = content.current;
    if (!active || outer === null || inner === null || typeof MutationObserver === "undefined") return undefined;
    if (typeof outer.animate !== "function") return undefined;
    let last = inner.offsetHeight;
    let running: Animation | null = null;
    let queued = false;
    const ease = (from: number, next: number) => {
      running?.cancel();
      last = next;
      outer.style.overflow = "clip";
      outer.setAttribute(EASING_ATTR, "");
      const animation = outer.animate([{ height: `${from}px` }, { height: `${next}px` }], {
        duration: EASE_HEIGHT_MS,
        easing: EASE_OUT_STRONG,
      });
      running = animation;
      animation.onfinish = () => {
        if (running !== animation) return;
        running = null;
        // On a grow-only box (the thread), content that grew under the ease
        // with no DOM change here (a nested box opening) carries on from
        // where this one stopped. Only growth, and only there: a box whose
        // content follows its own height would chase itself.
        const now = inner.offsetHeight;
        if (growOnly && now - next >= 1) {
          ease(next, now);
          return;
        }
        last = now;
        outer.style.overflow = "";
        outer.removeAttribute(EASING_ATTR);
      };
    };
    const measure = () => {
      queued = false;
      const next = inner.offsetHeight;
      if (Math.abs(next - last) < 1) return;
      // A box inside this one is easing its own change: the content's height
      // is that box's in-between height, which this box follows rather than
      // chasing with an ease of its own (round 14: the turn's box chased the
      // reply's and clipped the action line under it).
      if (inner.querySelector(`[${EASING_ATTR}]`) !== null) {
        if (running === null) last = next;
        return;
      }
      if (growOnly && next < last) {
        // A shrink passes through: drop any growth still running.
        running?.cancel();
        running = null;
        outer.style.overflow = "";
        outer.removeAttribute(EASING_ATTR);
        last = next;
        return;
      }
      ease(running !== null ? outer.getBoundingClientRect().height : last, next);
    };
    const depth = depthOf(outer);
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      scheduleMeasure(depth, measure);
    });
    observer.observe(inner, { subtree: true, childList: true, characterData: true, attributes: true });
    // Read only: it never resizes a box, so it cannot loop with the
    // observers around it.
    const follower =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => {
            if (running === null && !queued) last = inner.offsetHeight;
          });
    follower?.observe(inner);
    return () => {
      observer.disconnect();
      follower?.disconnect();
      running?.cancel();
      outer.style.overflow = "";
      outer.removeAttribute(EASING_ATTR);
    };
  }, [active, growOnly]);
  return [box, content];
}

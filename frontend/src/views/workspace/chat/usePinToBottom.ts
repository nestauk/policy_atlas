import { useLayoutEffect, useRef, useState } from "react";
import type { RefObject, UIEvent } from "react";

/** A reader this close to the end still counts as "at the end". */
const PINNED_WITHIN = 120;

/** Keep a transcript's scroll region at its end (038 V8, owner 2026-09-05).
 *
 * A freshly opened transcript starts at its end; new content keeps it there
 * while the reader is near the end; a reader who has scrolled up is left
 * alone — and offered a way back (`atEnd` / `jumpToEnd`). The region
 * *growing* (the site footer closing under a reader scrolling up) never pins
 * — only new content and the region shrinking do.
 *
 * Args:
 *   scrollRef: The scroll region.
 *   contentRef: The content inside it (observed for growth).
 *   key: Re-pins from the end when it changes — the conversation's id.
 *
 * Returns:
 *   `onScroll` for the scroll region; `atEnd`, false once the reader has
 *   scrolled up; `jumpToEnd`, which scrolls to the end and re-pins.
 */
export function usePinToBottom(
  scrollRef: RefObject<HTMLElement | null>,
  contentRef: RefObject<HTMLElement | null>,
  key: string,
) {
  const pinned = useRef(true);
  const [atEnd, setAtEnd] = useState(true);
  const sync = (el: HTMLElement) => {
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < PINNED_WITHIN;
  };

  useLayoutEffect(() => {
    const el = scrollRef.current;
    const content = contentRef.current;
    if (el === null || content === null) return;
    pinned.current = true;
    let paneHeight = el.clientHeight;
    const pin = (entries: readonly ResizeObserverEntry[] = []) => {
      const paneGrew = entries.some(
        (entry) => entry.target === el && entry.contentRect.height > paneHeight,
      );
      paneHeight = el.clientHeight;
      if (paneGrew) return;
      if (pinned.current) el.scrollTop = el.scrollHeight;
      sync(el);
    };
    pin();
    const observer = new ResizeObserver(pin);
    observer.observe(content);
    observer.observe(el);
    return () => observer.disconnect();
  }, [scrollRef, contentRef, key]);

  const jumpToEnd = () => {
    const el = scrollRef.current;
    if (el === null) return;
    pinned.current = true;
    setAtEnd(true);
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  };

  return {
    atEnd,
    jumpToEnd,
    onScroll: (event: UIEvent<HTMLElement>) => {
      sync(event.currentTarget);
      setAtEnd(pinned.current);
    },
  };
}

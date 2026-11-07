import { useLayoutEffect, useRef, type RefObject } from "react";

/**
 * Opens a page at its top with focus on its title (round 12, the option
 * card; round 13, owner: the Result tab's Longlist and Shortlist too). The
 * app's scrolling pane keeps the last page's offset across a route change,
 * so a page reached from the foot of another opened at its foot. Once per
 * `key` (the option, the view), so a later render (a dossier over the card,
 * a notice) never moves the reader; a link with a hash keeps its own scroll.
 *
 * Args:
 *   titleRef: The page's title, focusable (`tabIndex={-1}`).
 *   key: What the page shows; a new key opens it at the top again.
 */
export function useOpenAtTop(titleRef: RefObject<HTMLElement | null>, key: string): void {
  const openedFor = useRef<string | null>(null);
  useLayoutEffect(() => {
    const title = titleRef.current;
    if (title === null || openedFor.current === key) return;
    openedFor.current = key;
    if (window.location.hash !== "") return;
    openAtTop(title);
  });
}

/** Scrolls every scrolling ancestor of `title` to its top and focuses it. */
function openAtTop(title: HTMLElement): void {
  for (let node = title.parentElement; node !== null && node !== document.body; node = node.parentElement) {
    const overflowY = getComputedStyle(node).overflowY;
    if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") node.scrollTop = 0;
  }
  if (document.scrollingElement != null) document.scrollingElement.scrollTop = 0;
  title.focus({ preventScroll: true });
}

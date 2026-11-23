import { useEffect, useRef, type RefObject } from "react";
import { useLocation } from "react-router";

/**
 * "Skip to main content": the first tab stop of a shell, shown only while it
 * has focus. It moves focus past the navigation to the routed view's pane.
 *
 * A press focuses the pane and leaves the address alone: the app reads the
 * `#hash` for its own links (a report section, a reference).
 *
 * Args:
 *   pane: The element that holds the routed view. It needs `tabIndex={-1}`.
 */
export function SkipLink({ pane }: { pane: RefObject<HTMLElement | null> }) {
  return (
    <a
      href="#main-content"
      onClick={(event) => {
        event.preventDefault();
        pane.current?.focus();
      }}
      className="sr-only bg-paper px-4 py-2 text-body font-semibold text-navy focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50"
    >
      Skip to main content
    </a>
  );
}

/**
 * After a route change, move focus to the routed view's pane, so a keyboard
 * or screen reader user starts at the new page and not at the link that led
 * there (or at the top of the document, when that link is gone).
 *
 * A view that has put focus somewhere of its own inside the pane (a title, a
 * field with `autoFocus`) keeps it.
 *
 * Args:
 *   pane: The element that holds the routed view. It needs `tabIndex={-1}`.
 */
export function useFocusPaneOnNavigate(pane: RefObject<HTMLElement | null>): void {
  const { pathname } = useLocation();
  const last = useRef(pathname);
  useEffect(() => {
    if (last.current === pathname) return;
    last.current = pathname;
    const element = pane.current;
    if (element === null || element.contains(document.activeElement)) return;
    element.focus({ preventScroll: true });
  }, [pathname, pane]);
}

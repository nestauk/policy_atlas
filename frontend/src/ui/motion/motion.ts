/** The strong ease-out (`--ease-out-strong`), for script-driven motion. */
export const EASE_OUT_STRONG = "cubic-bezier(0.23, 1, 0.32, 1)";

/** How long an arrival or a block making room takes (task 058, round 9). */
export const ARRIVE_MS = 300;

/** Whether the reader asked for reduced motion. False outside a browser. */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/** Whether script-driven motion can run here: Web Animations exist (not in
 *  jsdom) and the reader has not asked for reduced motion. */
export function canAnimate(element: HTMLElement | null): boolean {
  return element !== null && typeof element.animate === "function" && !prefersReducedMotion();
}

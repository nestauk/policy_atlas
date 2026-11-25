/** The strong ease-out (`--ease-out-strong`), for script-driven motion. */
export const EASE_OUT_STRONG = "cubic-bezier(0.23, 1, 0.32, 1)";

/** How long an arrival or a block making room takes. */
export const ARRIVE_MS = 300;

/** How long motion that marks nothing may run before it holds still: the
 *  splash page's fold marks. Movement that starts by itself beside other
 *  content must stop within five seconds or have a pause control (WCAG 2.2.2). */
export const DECORATIVE_MOTION_MS = 5000;

/** Whether the reader asked for reduced motion. False outside a browser. */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/** Whether script-driven motion can run here: Web Animations exist (not in
 *  jsdom) and the reader has not asked for reduced motion. */
export function canAnimate(element: HTMLElement | null): boolean {
  return element !== null && typeof element.animate === "function" && !prefersReducedMotion();
}

/** Whether a surface's exit can run before it unmounts (a sheet, the plan
 *  document): not under reduced motion, nor where Web Animations are
 *  missing, as in the tests' jsdom. */
export function exitRuns(): boolean {
  return typeof document !== "undefined" && canAnimate(document.body);
}

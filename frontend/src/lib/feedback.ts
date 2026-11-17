/**
 * In-app feedback elements (task 059, ADR 0045).
 *
 * Each element is on only where its name is in `VITE_FEEDBACK` at build time.
 * The deploy script sets that from the same list the API reads as
 * `POLICY_ATLAS_FEEDBACK`, so the two sides agree.
 */

/**
 * The element names: citation flag, missing paper, use-intent question, claim
 * flag, report a problem, onboarding profile.
 */
export type FeedbackElement = "cf" | "mp" | "uiq" | "clf" | "rap" | "op";

/**
 * Whether a feedback element is switched on in this build.
 *
 * Args:
 *   element: The element name.
 *
 * Returns:
 *   True when `VITE_FEEDBACK` lists the element.
 */
export function feedbackEnabled(element: FeedbackElement): boolean {
  return (import.meta.env.VITE_FEEDBACK ?? "")
    .split(",")
    .map((name) => name.trim())
    .includes(element);
}

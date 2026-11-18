/**
 * In-app feedback: the feature flags.
 *
 * Each feedback element has its own flag, so that each one can ship alone.
 * `VITE_FEEDBACK` is a comma-separated list of the elements that are on. It is
 * read at build time, as for `VITE_THEORY_OF_CHANGE`. The API has the same list
 * in `POLICY_ATLAS_FEEDBACK` and returns a 404 for an element that is off.
 */

/** The feedback elements. The names are the same as in the API settings. */
export type FeedbackElement =
  | "citation_flag"
  | "missing_paper"
  | "use_intent"
  | "claim_flag"
  | "problem_report"
  | "onboarding";

/**
 * Whether a feedback element is on in this build.
 *
 * Args:
 *   element: The element name.
 *
 * Returns:
 *   True when `VITE_FEEDBACK` names the element.
 */
export function feedbackEnabled(element: FeedbackElement): boolean {
  return (import.meta.env.VITE_FEEDBACK ?? "")
    .split(",")
    .map((name: string) => name.trim())
    .includes(element);
}

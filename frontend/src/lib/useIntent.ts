/**
 * The use-intent question (in-app feedback, element C): the show-once rules.
 *
 * - The question is shown once for each user and report, on the first open.
 * - "Not now" is recorded as `dismissed` and the question never comes back.
 * - An answer collapses to one line, and stays editable through "change".
 *
 * An answer or a dismissal is a record in the API. "Shown, but not answered"
 * is known only to the browser: the time of the first show is kept in
 * `localStorage`, for this user and report. It is also sent as `shown_at`.
 */

/**
 * What the report shows where the question goes:
 * - `ask`: the question.
 * - `answered`: the one-line thanks with the "change" link.
 * - `hidden`: nothing.
 */
export type UseIntentCardState = "ask" | "answered" | "hidden";

/**
 * Decide what to show for the use-intent question.
 *
 * Args:
 *   useIntent: The stored answer of this user for this report (`dismissed`
 *     for "Not now"), or undefined when there is none.
 *   shownBefore: Whether an earlier open of the report showed the question.
 *
 * Returns:
 *   The card state.
 */
export function intentCardState(
  useIntent: string | undefined,
  shownBefore: boolean,
): UseIntentCardState {
  if (useIntent === "dismissed") return "hidden";
  if (useIntent !== undefined) return "answered";
  return shownBefore ? "hidden" : "ask";
}

const shownKey = (userId: string, artefactId: string) =>
  `pa.useIntent.shown.${userId}.${artefactId}`;

/**
 * When the question was first shown to this user for this report.
 *
 * Args:
 *   userId: The signed-in user's token subject.
 *   artefactId: The report.
 *
 * Returns:
 *   The ISO time of the first show, or null when it was never shown (or the
 *   browser has no storage).
 */
export function firstShownAt(userId: string, artefactId: string): string | null {
  try {
    return window.localStorage.getItem(shownKey(userId, artefactId));
  } catch {
    return null;
  }
}

/**
 * Record that the question is shown now, if this is the first time.
 *
 * Args:
 *   userId: The signed-in user's token subject.
 *   artefactId: The report.
 *   now: The current time.
 *
 * Returns:
 *   The ISO time of the first show: the stored one, else `now`.
 */
export function markShown(userId: string, artefactId: string, now: Date): string {
  const stored = firstShownAt(userId, artefactId);
  if (stored !== null) return stored;
  const shownAt = now.toISOString();
  try {
    window.localStorage.setItem(shownKey(userId, artefactId), shownAt);
  } catch {
    // No storage: the question can show again on the next open.
  }
  return shownAt;
}

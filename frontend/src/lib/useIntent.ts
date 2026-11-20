/**
 * The use-intent question (in-app feedback, element C): the time of the first
 * show.
 *
 * An answer or a dismissal is a record in the API. The time when the question
 * was first shown is known only to the browser: it is kept in `localStorage`,
 * for this user and report, and is sent as `shown_at` with the answer.
 */

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

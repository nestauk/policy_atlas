/**
 * Onboarding profile: when the form is shown.
 *
 * The rules (the brief, element F):
 * - The form is shown at first access and is required to proceed.
 * - Exactly one "Skip for now" is allowed.
 * - After a skip, the form is shown again at the next login, with no skip.
 *
 * The API records the time of the first skip (`skipped_once_at`). It does not
 * record logins, so "the same login" is kept in `sessionStorage`: the browser
 * clears it when the tab closes, and the app clears it at sign-out.
 */
import type { components } from "../api/gen/types";

type Profile = components["schemas"]["UserProfileOut"];

/**
 * What the app does about the profile form:
 * - `pass`: show the app.
 * - `ask`: show the form, and offer "Skip for now".
 * - `ask_required`: show the form with no skip.
 */
export type ProfileGate = "pass" | "ask" | "ask_required";

const SKIPPED_KEY = "pa.profile.skipped";

/**
 * Decide if the profile form is due.
 *
 * Args:
 *   profile: The caller's profile, or undefined while it loads or when the
 *     read failed. An unknown profile never blocks the app.
 *   skippedThisSession: Whether the user pressed "Skip for now" in this login.
 *
 * Returns:
 *   The gate state.
 */
export function profileGate(
  profile: Pick<Profile, "completed_at" | "skipped_once_at"> | undefined,
  skippedThisSession: boolean,
): ProfileGate {
  if (profile === undefined || profile.completed_at != null) return "pass";
  if (profile.skipped_once_at == null) return "ask";
  return skippedThisSession ? "pass" : "ask_required";
}

/**
 * Whether this user skipped the form in this login.
 *
 * Args:
 *   userId: The signed-in user's token subject.
 *
 * Returns:
 *   True when `markSkipped` was called for this user in this browser session.
 */
export function skippedThisSession(userId: string): boolean {
  try {
    return window.sessionStorage.getItem(SKIPPED_KEY) === userId;
  } catch {
    return false;
  }
}

/**
 * Remember that this user skipped the form in this login.
 *
 * Args:
 *   userId: The signed-in user's token subject.
 */
export function markSkipped(userId: string): void {
  try {
    window.sessionStorage.setItem(SKIPPED_KEY, userId);
  } catch {
    // Storage is not available: the form shows again on the next page load.
  }
}

/** Forget the skip at sign-out, so the next login shows the form again. */
export function forgetSkipped(): void {
  try {
    window.sessionStorage.removeItem(SKIPPED_KEY);
  } catch {
    // Storage is not available: there is nothing to forget.
  }
}

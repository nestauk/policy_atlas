/**
 * PostHog in the browser: page views, clicks, named events and feature flags.
 *
 * PostHog starts only when the build has `VITE_POSTHOG_PROJECT_TOKEN` and
 * `VITE_POSTHOG_HOST`. Without them (unit tests, mock mode, a local run with
 * no token) each function here does nothing, and feature flags fall back to
 * their environment-variable defaults (see `capabilities.ts`).
 *
 * The guide is `docs/posthog.md`.
 */
import posthog from "posthog-js";

let started = false;

/** Start PostHog. Call once, before the app renders. */
export function initAnalytics(): void {
  const token = import.meta.env.VITE_POSTHOG_PROJECT_TOKEN;
  const host = import.meta.env.VITE_POSTHOG_HOST;
  // Mock mode plays scripted data; its clicks are not real use.
  if (!token || !host || import.meta.env.VITE_MOCK === "1") return;
  posthog.init(token, {
    api_host: host,
    // A dated set of SDK defaults. This one makes each route change in the
    // single-page app send a page view; without it only the first load does.
    defaults: "2025-05-24",
    // The deployed site allows scripts from its own address only
    // (`script-src 'self'` in infra/infra/components/security_headers.py), so
    // PostHog must not fetch its add-on scripts (replay, surveys, toolbar).
    disable_external_dependency_loading: true,
    disable_session_recording: true,
  });
  started = true;
}

/**
 * Tie this browser's events and flags to the signed-in person.
 *
 * Args:
 *   sub: The token `sub` claim, or null when signed out. The API identifies
 *     its own events with the same value (`_identify_posthog_user` in
 *     backend/src/policy_atlas/api/auth.py), so browser and API events land
 *     on one person.
 */
export function identifyUser(sub: string | null): void {
  if (!started) return;
  if (sub) posthog.identify(sub);
  // Only after a real sign-out: a reset on every anonymous page load would
  // make each visit to a public page look like a new visitor.
  else if (posthog._isIdentified()) posthog.reset();
}

/**
 * Send one named event.
 *
 * Args:
 *   event: The event name, in the API's style: `object_verb`, past tense.
 *   properties: Details to filter and break down by in PostHog.
 */
export function track(event: string, properties?: Record<string, unknown>): void {
  if (started) posthog.capture(event, properties);
}

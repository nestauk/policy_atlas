import { useEffect, useState } from "react";

/** How long a live dot keeps breathing after the last update (task 058, N5). */
export const FRESH_WINDOW_MS = 1_500;

/** After this long with no update a running step reads "Still working on
 *  this step" (task 058, N5). */
export const STALL_AFTER_MS = 120_000;

/** A stamp already present when the view mounts is fresh only if its own
 *  time is recent; a stamp that does not parse as a time counts as new. */
function expiredAtMount(stamp: string | null | undefined, windowMs: number): string | null {
  if (stamp == null) return null;
  const at = Date.parse(stamp);
  if (Number.isNaN(at)) return null;
  return Date.now() - at >= windowMs ? stamp : null;
}

/**
 * The wall clock, re-read every `intervalMs` while `ticking` (elapsed times
 * on the running card, the run strip and the task row).
 *
 * Args:
 *   ticking: Whether the clock advances; a finished run freezes it.
 *   intervalMs: How often to re-read the clock.
 *
 * Returns:
 *   Milliseconds since the epoch, as of the last tick.
 */
export function useNow(ticking: boolean, intervalMs = 1_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!ticking) return undefined;
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [ticking, intervalMs]);
  return now;
}

/**
 * Whether something live updated within the last `windowMs`.
 *
 * The stamp is anything that changes when new data arrives: a tick's
 * `occurredAt`, or a polled row's label. Each new stamp starts the window
 * again on the client's own clock, so a skewed server clock cannot keep a
 * dot breathing or stop it early. One rule for every live dot: the running
 * card, the run strip, the Result tab and the task row (task 058, N5).
 *
 * Args:
 *   stamp: The latest update's marker; `null` or `undefined` is never fresh.
 *   windowMs: How long an update stays fresh.
 *
 * Returns:
 *   `true` until `windowMs` has passed since the stamp last changed.
 */
export function useFreshness(stamp: string | null | undefined, windowMs: number = FRESH_WINDOW_MS): boolean {
  const [expired, setExpired] = useState<string | null>(() => expiredAtMount(stamp, windowMs));
  useEffect(() => {
    if (stamp == null || stamp === expired) return undefined;
    const id = window.setTimeout(() => setExpired(stamp), windowMs);
    return () => window.clearTimeout(id);
  }, [stamp, expired, windowMs]);
  return stamp != null && stamp !== expired;
}

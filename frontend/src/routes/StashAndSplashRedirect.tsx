import { Navigate, useLocation } from "react-router";

import { AUTH_RETURN_TO_KEY } from "../auth/OidcAuthProvider";

/**
 * Catch-all for logged-out deep links: stash the attempted URL, then send
 * the visitor to the splash home so Sign in can restore it after Cognito.
 *
 * `location.state.from` (task 037 review fix) wins when present: the
 * public router's wildcard redirect can rewrite the URL to `/result`
 * before this component ever sees it — on stale-but-still-public cached
 * task data that a background refetch then reveals isn't public after
 * all — and stashes its own pre-redirect location under `from` for exactly
 * this case, so the original deep link survives instead of `/result`.
 */
export function StashAndSplashRedirect() {
  const location = useLocation();
  const stashedFrom = (location.state as { from?: string } | null)?.from;
  const returnTo = stashedFrom ?? `${location.pathname}${location.search}${location.hash}`;
  if (returnTo !== "/") {
    sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo);
  }
  return <Navigate to="/" replace />;
}

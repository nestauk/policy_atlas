import { Navigate, useLocation } from "react-router";

import { AUTH_RETURN_TO_KEY } from "../auth/OidcAuthProvider";

/**
 * Catch-all for logged-out deep links: stash the attempted URL, then send
 * the visitor to the splash home so Sign in can restore it after Cognito.
 */
export function StashAndSplashRedirect() {
  const location = useLocation();
  const returnTo = `${location.pathname}${location.search}${location.hash}`;
  if (returnTo !== "/") {
    sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo);
  }
  return <Navigate to="/" replace />;
}

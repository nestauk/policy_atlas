import { Navigate, Outlet, useLocation } from "react-router";

import { useAuth } from "../auth";
import { AUTH_RETURN_TO_KEY } from "../auth/OidcAuthProvider";

/**
 * Guard for authenticated app routes. Unauthenticated visitors are sent to
 * the splash page with the attempted URL stashed for post-login return.
 */
export function RequireAuth() {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === "loading") {
    return (
      <p role="status" className="text-meta text-grey">
        Loading…
      </p>
    );
  }

  if (auth.status !== "authenticated") {
    const returnTo = `${location.pathname}${location.search}${location.hash}`;
    sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo);
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

import { useEffect } from "react";

import { useAuth } from "../../auth";

/** Begin the auth-layer re-auth flow while preserving the current route. */
export function ReauthRedirect() {
  const auth = useAuth();

  useEffect(() => {
    void auth.onUnauthenticated();
  }, [auth]);

  return <p role="status" className="text-sm text-grey">Your session expired. Taking you back to sign in…</p>;
}

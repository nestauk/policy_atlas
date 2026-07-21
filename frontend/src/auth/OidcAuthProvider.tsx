import { useCallback, useMemo } from "react";
import type { ReactNode } from "react";
import {
  AuthProvider as OidcLibProvider,
  useAuth as useOidcLibAuth,
} from "react-oidc-context";

import { AuthContext } from "./AuthContext";
import type { AuthApi, AuthStatus } from "./types";

/**
 * Active when `VITE_OIDC_AUTHORITY` is set. Wraps `react-oidc-context`
 * (authorization code flow + silent refresh) behind the same `AuthApi`
 * shape as the dev-token seam — swapping in AWS Cognito later is a
 * `VITE_OIDC_*` config change, not a code change.
 */
export function OidcAuthProvider({ children }: { children: ReactNode }) {
  const authority = import.meta.env.VITE_OIDC_AUTHORITY;
  const clientId = import.meta.env.VITE_OIDC_CLIENT_ID;
  const redirectUri = import.meta.env.VITE_OIDC_REDIRECT_URI ?? window.location.origin;

  if (!authority || !clientId) {
    throw new Error(
      "OidcAuthProvider requires VITE_OIDC_AUTHORITY and VITE_OIDC_CLIENT_ID to be set",
    );
  }

  return (
    <OidcLibProvider
      authority={authority}
      client_id={clientId}
      redirect_uri={redirectUri}
      onSigninCallback={() => {
        // Strip the `code`/`state` query params the redirect leaves behind.
        window.history.replaceState({}, document.title, window.location.pathname);
      }}
    >
      <OidcAuthAdapter>{children}</OidcAuthAdapter>
    </OidcLibProvider>
  );
}

/** Adapts `react-oidc-context`'s richer surface down to our `AuthApi` shape. */
function OidcAuthAdapter({ children }: { children: ReactNode }) {
  const oidc = useOidcLibAuth();

  const getAccessToken = useCallback(
    async (forceRefresh?: boolean) => {
      if (forceRefresh) {
        try {
          const refreshed = await oidc.signinSilent();
          return refreshed?.access_token ?? null;
        } catch {
          return null;
        }
      }
      return oidc.user?.access_token ?? null;
    },
    [oidc],
  );

  const signIn = useCallback(() => {
    void oidc.signinRedirect();
  }, [oidc]);

  const signOut = useCallback(() => {
    void oidc.signoutRedirect();
  }, [oidc]);

  const status: AuthStatus = oidc.isLoading
    ? "loading"
    : oidc.isAuthenticated
      ? "authenticated"
      : "unauthenticated";

  const value: AuthApi = useMemo(
    () => ({
      getAccessToken,
      signIn,
      signOut,
      user: oidc.user?.profile.sub ? { sub: oidc.user.profile.sub } : null,
      status,
    }),
    [getAccessToken, signIn, signOut, oidc.user, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

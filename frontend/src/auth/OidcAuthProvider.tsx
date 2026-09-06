import { useCallback, useEffect, useMemo, useRef } from "react";
import type { ReactNode } from "react";
import {
  AuthProvider as OidcLibProvider,
  useAuth as useOidcLibAuth,
} from "react-oidc-context";

import { AuthContext } from "./AuthContext";
import type { AuthApi, AuthStatus } from "./types";

/** sessionStorage key for the path to restore after Cognito returns. */
export const AUTH_RETURN_TO_KEY = "policy-atlas.auth-return-to";

/**
 * Active when `VITE_OIDC_AUTHORITY` is set. Wraps `react-oidc-context`
 * (authorization code flow + silent refresh) behind the same `AuthApi`
 * shape as the dev-token seam — swapping in AWS Cognito later is a
 * `VITE_OIDC_*` config change, not a code change.
 *
 * Unauthenticated cold visits render the splash page (children). Explicit
 * `signIn()` / mid-session `onUnauthenticated()` still redirect to Cognito.
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
        const returnTo = sessionStorage.getItem(AUTH_RETURN_TO_KEY);
        sessionStorage.removeItem(AUTH_RETURN_TO_KEY);
        window.history.replaceState({}, document.title, returnTo ?? window.location.pathname);
      }}
    >
      <OidcAuthAdapter clientId={clientId} redirectUri={redirectUri}>
        {children}
      </OidcAuthAdapter>
    </OidcLibProvider>
  );
}

/** Adapts `react-oidc-context`'s richer surface down to our `AuthApi` shape. */
function OidcAuthAdapter({
  children,
  clientId,
  redirectUri,
}: {
  children: ReactNode;
  clientId: string;
  redirectUri: string;
}) {
  const oidc = useOidcLibAuth();

  // `react-oidc-context`'s `oidc` object gets a new identity on every
  // silent renewal, even when nothing user-visible changed. Reading it
  // through a ref inside otherwise-stable callbacks keeps `getAccessToken`
  // etc. (and therefore the `AuthApi` object built below) from changing
  // identity on every renewal — consumers like `useRunStream` key effects
  // on the `AuthApi` reference and would otherwise reconnect needlessly.
  const oidcRef = useRef(oidc);
  useEffect(() => {
    oidcRef.current = oidc;
  });

  const getAccessToken = useCallback(async (forceRefresh?: boolean) => {
    if (forceRefresh) {
      try {
        const refreshed = await oidcRef.current.signinSilent();
        return refreshed?.access_token ?? null;
      } catch {
        return null;
      }
    }
    return oidcRef.current.user?.access_token ?? null;
  }, []);

  const signIn = useCallback(() => {
    void oidcRef.current.signinRedirect();
  }, []);

  const signOut = useCallback(() => {
    // Cognito's /logout is not OIDC RP-Initiated Logout: it requires
    // client_id + logout_uri. oidc-client-ts sends id_token_hint (and
    // optionally post_logout_redirect_uri) and omits client_id, which
    // Cognito surfaces as "Client does not exist".
    void oidcRef.current.signoutRedirect({
      extraQueryParams: {
        client_id: clientId,
        logout_uri: redirectUri,
      },
    });
  }, [clientId, redirectUri]);

  const onUnauthenticated = useCallback(() => {
    const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo);
    void oidcRef.current.signinRedirect();
  }, []);

  // Manual retry after a sign-in error. `code`/`state` are dropped from the
  // stashed return path so the retry can't restore a consumed callback URL
  // and error again (the usual cause: a restored tab or back-navigation to
  // the post-login URL).
  const retrySignIn = useCallback(() => {
    const params = new URLSearchParams(window.location.search);
    params.delete("code");
    params.delete("state");
    const search = params.size > 0 ? `?${params.toString()}` : "";
    const returnTo = `${window.location.pathname}${search}${window.location.hash}`;
    sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo);
    void oidcRef.current.signinRedirect();
  }, []);

  const status: AuthStatus = oidc.isLoading
    ? "loading"
    : oidc.isAuthenticated
      ? "authenticated"
      : "unauthenticated";
  const sub = oidc.user?.profile.sub;

  const value: AuthApi = useMemo(
    () => ({
      getAccessToken,
      signIn,
      signOut,
      onUnauthenticated,
      user: sub ? { sub } : null,
      status,
    }),
    [getAccessToken, signIn, signOut, onUnauthenticated, sub, status],
  );

  // A persistent OIDC error (e.g. a stale sign-in callback) must not mount
  // the shell tokenless — every query 401s with no visible path back to
  // sign-in. Surface the failure with a manual retry instead.
  if (!oidc.isAuthenticated && oidc.error) {
    return (
      <div role="alert" className="text-meta text-grey">
        <p>Sign-in didn&apos;t complete: {oidc.error.message}</p>
        <button
          type="button"
          onClick={retrySignIn}
          className="cursor-pointer text-meta text-grey underline hover:text-navy"
        >
          Sign in again
        </button>
      </div>
    );
  }

  // Initial load / code exchange / outbound redirect — keep queries from
  // firing tokenless. Once idle and unauthenticated, children (splash) mount.
  if (oidc.isLoading || oidc.activeNavigator) {
    return (
      <p role="status" className="text-meta text-grey">
        {oidc.activeNavigator ? "Taking you to sign in…" : "Loading…"}
      </p>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

import { useCallback, useEffect, useMemo, useRef } from "react";
import type { ReactNode } from "react";
import {
  AuthProvider as OidcLibProvider,
  useAuth as useOidcLibAuth,
} from "react-oidc-context";

import { AuthContext } from "./AuthContext";
import type { AuthApi, AuthStatus } from "./types";

const AUTH_RETURN_TO_KEY = "policy-atlas.auth-return-to";

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
        const returnTo = sessionStorage.getItem(AUTH_RETURN_TO_KEY);
        sessionStorage.removeItem(AUTH_RETURN_TO_KEY);
        window.history.replaceState({}, document.title, returnTo ?? window.location.pathname);
      }}
    >
      <OidcAuthAdapter>{children}</OidcAuthAdapter>
    </OidcLibProvider>
  );
}

/** Adapts `react-oidc-context`'s richer surface down to our `AuthApi` shape. */
function OidcAuthAdapter({ children }: { children: ReactNode }) {
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
    void oidcRef.current.signoutRedirect();
  }, []);

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

  // Cold-visit gating (026 live-check finding, 2026-07-28): a first
  // unauthenticated entry previously rendered the app shell, whose queries
  // 401'd forever with no path to sign-in — only mid-session expiry (the
  // ReauthRedirect views) ever reached `signinRedirect`. Mirror the
  // dev-token provider's own behaviour: the PROVIDER gates, sending cold
  // visits straight to the hosted UI with the route preserved.
  const shouldRedirect =
    !oidc.isLoading && !oidc.isAuthenticated && !oidc.activeNavigator && !oidc.error;
  useEffect(() => {
    if (!shouldRedirect) return;
    const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo);
    void oidcRef.current.signinRedirect();
  }, [shouldRedirect]);

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
  // sign-in (026 live incident; the redirect gate above deliberately stands
  // down on error to avoid a redirect loop). Surface the failure with a
  // manual retry instead.
  if (!oidc.isAuthenticated && oidc.error) {
    return (
      <div role="alert" className="text-sm text-grey">
        <p>Sign-in didn&apos;t complete: {oidc.error.message}</p>
        <button
          type="button"
          onClick={retrySignIn}
          className="cursor-pointer text-[13px] text-grey underline hover:text-navy"
        >
          Sign in again
        </button>
      </div>
    );
  }

  // While signing in (loading, redirecting, or about to redirect) the app
  // shell must not mount — its queries would fire tokenless and 401.
  if (!oidc.isAuthenticated) {
    return (
      <p role="status" className="text-sm text-grey">
        Taking you to sign in…
      </p>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

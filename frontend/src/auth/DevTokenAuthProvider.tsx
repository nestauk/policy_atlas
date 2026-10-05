import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { AuthContext } from "./AuthContext";
import { DEV_TOKEN_STORAGE_KEY } from "./DevTokenLoginPanel";
import { readUnverifiedJwtSub } from "./jwt";
import type { AuthApi, AuthStatus } from "./types";

/**
 * Active when `VITE_OIDC_AUTHORITY` is unset. The backend dev issuer is a
 * keypair + mint CLI, not an interactive IdP, so there is no redirect flow
 * here: the token comes from `VITE_DEV_TOKEN` (a build-time default, handy
 * for scripted/local runs) or a paste into the splash-page Sign-in panel.
 * Token lives in `sessionStorage` only — never `localStorage`, never a
 * committed file.
 *
 * Unauthenticated users still receive `AuthContext` so the router can show
 * the splash page; the paste panel is no longer a hard gate above the app.
 */
export function DevTokenAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => {
    return import.meta.env.VITE_DEV_TOKEN ?? sessionStorage.getItem(DEV_TOKEN_STORAGE_KEY);
  });

  const acceptToken = useCallback((pasted: string) => {
    sessionStorage.setItem(DEV_TOKEN_STORAGE_KEY, pasted);
    setToken(pasted);
  }, []);

  const signOut = useCallback(() => {
    sessionStorage.removeItem(DEV_TOKEN_STORAGE_KEY);
    setToken(null);
  }, []);

  // There is no interactive IdP to redirect to in dev — "sign in" just
  // clears any current token so the splash paste panel can collect one.
  const signIn = useCallback(() => {
    signOut();
  }, [signOut]);

  // Dev auth does not redirect away from the SPA, so clearing the token keeps
  // the current route while returning the user to the splash page.
  const onUnauthenticated = signIn;

  // `AuthApi.getAccessToken` accepts a `forceRefresh` flag for shape parity
  // with the OIDC provider, but the dev issuer has no live refresh endpoint
  // to call — a human re-minting and re-pasting a token is the only
  // "refresh" it has, so this implementation ignores the argument
  // entirely (a function with fewer declared parameters still satisfies
  // the wider `AuthApi` signature).
  const getAccessToken = useCallback(async () => token, [token]);

  const user = useMemo(
    () => (token ? { sub: readUnverifiedJwtSub(token) ?? "dev-user" } : null),
    [token],
  );
  const status: AuthStatus = token ? "authenticated" : "unauthenticated";

  const value: AuthApi = useMemo(
    () => ({ getAccessToken, signIn, signOut, onUnauthenticated, user, status }),
    [getAccessToken, signIn, signOut, onUnauthenticated, user, status],
  );

  // Expose acceptToken for the splash panel via a narrow module-level bridge
  // so SplashView does not need AuthApi shape changes. Cleared on unmount.
  useEffect(() => {
    registerDevTokenAcceptor(acceptToken);
    return () => registerDevTokenAcceptor(null);
  }, [acceptToken]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

let _acceptDevToken: ((token: string) => void) | null = null;

function registerDevTokenAcceptor(fn: ((token: string) => void) | null) {
  _acceptDevToken = fn;
}

/** Accept a pasted dev token from the splash Sign-in panel. */
export function acceptDevToken(token: string): void {
  if (_acceptDevToken) {
    _acceptDevToken(token);
    return;
  }
  sessionStorage.setItem(DEV_TOKEN_STORAGE_KEY, token);
  window.location.reload();
}

import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { AuthContext } from "./AuthContext";
import { DEV_TOKEN_STORAGE_KEY, DevTokenLoginPanel } from "./DevTokenLoginPanel";
import { readUnverifiedJwtSub } from "./jwt";
import type { AuthApi, AuthStatus } from "./types";

/**
 * Active when `VITE_OIDC_AUTHORITY` is unset. The backend dev issuer is a
 * keypair + mint CLI, not an interactive IdP, so there is no redirect flow
 * here: the token comes from `VITE_DEV_TOKEN` (a build-time default, handy
 * for scripted/local runs) or a visibly-dev "paste a dev token" panel that
 * gates the app until a token is supplied. Token lives in `sessionStorage`
 * only — never `localStorage`, never a committed file.
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
  // clears any current token so the paste panel re-collects one.
  const signIn = useCallback(() => {
    signOut();
  }, [signOut]);

  // Dev auth does not redirect away from the SPA, so clearing the token keeps
  // the current route while returning the user to the visible token panel.
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

  return (
    <AuthContext.Provider value={value}>
      {token ? children : <DevTokenLoginPanel onSubmit={acceptToken} />}
    </AuthContext.Provider>
  );
}

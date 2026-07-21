import type { ReactNode } from "react";

import { AuthContext } from "./AuthContext";
import { DevTokenAuthProvider } from "./DevTokenAuthProvider";
import { OidcAuthProvider } from "./OidcAuthProvider";
import type { AuthApi } from "./types";

/**
 * The auth seam entry point: one interface (`AuthApi`), two providers
 * behind it, selected by environment. `VITE_OIDC_AUTHORITY` set →
 * `OidcAuthProvider` (react-oidc-context, Cognito-shaped); unset →
 * `DevTokenAuthProvider` (the backend's keypair + mint-CLI dev issuer).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const mockAuth = getInstalledMockAuth();
  if (import.meta.env.VITE_MOCK === "1" && mockAuth) {
    return <AuthContext.Provider value={mockAuth}>{children}</AuthContext.Provider>;
  }
  if (import.meta.env.VITE_OIDC_AUTHORITY) {
    return <OidcAuthProvider>{children}</OidcAuthProvider>;
  }
  return <DevTokenAuthProvider>{children}</DevTokenAuthProvider>;
}

function getInstalledMockAuth(): AuthApi | undefined {
  return (globalThis as typeof globalThis & { __policyAtlasMockAuth?: AuthApi }).__policyAtlasMockAuth;
}

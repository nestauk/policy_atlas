import type { ReactNode } from "react";

import { DevTokenAuthProvider } from "./DevTokenAuthProvider";
import { OidcAuthProvider } from "./OidcAuthProvider";

/**
 * The auth seam entry point: one interface (`AuthApi`), two providers
 * behind it, selected by environment. `VITE_OIDC_AUTHORITY` set →
 * `OidcAuthProvider` (react-oidc-context, Cognito-shaped); unset →
 * `DevTokenAuthProvider` (the backend's keypair + mint-CLI dev issuer).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  if (import.meta.env.VITE_OIDC_AUTHORITY) {
    return <OidcAuthProvider>{children}</OidcAuthProvider>;
  }
  return <DevTokenAuthProvider>{children}</DevTokenAuthProvider>;
}

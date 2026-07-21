import { createContext, useContext } from "react";

import type { AuthApi } from "./types";

/** Undefined outside a provider — `useAuth()` below is the only sanctioned read. */
export const AuthContext = createContext<AuthApi | undefined>(undefined);

/** Read the active `AuthApi`. Must be called under `AuthProvider`. */
export function useAuth(): AuthApi {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth() must be used within an <AuthProvider>");
  }
  return value;
}

/**
 * The auth seam: one interface, two providers behind it.
 *
 * The backend dev issuer is a keypair + mint CLI, not an interactive IdP
 * (there is no `/authorize`), so `DevTokenAuthProvider` and
 * `OidcAuthProvider` both implement this same shape — call sites never
 * branch on which provider is active.
 */

/** Lifecycle status of the current auth session. */
export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

/** The authenticated subject, as far as the frontend needs to know. */
interface AuthUser {
  /** Token `sub` claim — the owner-scoping identity the API keys on. */
  sub: string;
}

/**
 * The one auth surface every call site depends on, exposed via
 * `AuthContext` + `useAuth()`.
 */
export interface AuthApi {
  /**
   * Resolve the current bearer token, or `null` when signed out.
   *
   * @param forceRefresh - When `true`, bypass any cached token and attempt
   *   a silent refresh first. Used by the authed API client and the SSE
   *   client after a 401 to attempt exactly one silent recovery.
   */
  getAccessToken(forceRefresh?: boolean): Promise<string | null>;
  /** Begin sign-in (interactive redirect for OIDC; a no-op/reset for the
   *  dev-token seam, which has no interactive IdP to redirect to). */
  signIn(): void | Promise<void>;
  /** End the session and clear any locally held token. */
  signOut(): void | Promise<void>;
  /** Start re-authentication after an expired session, retaining the current
   * route when the identity provider redirects back to the application. */
  onUnauthenticated(): void | Promise<void>;
  /** The signed-in subject, or `null` when signed out. */
  user: AuthUser | null;
  /** Current session status. */
  status: AuthStatus;
}

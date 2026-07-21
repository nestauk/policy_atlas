/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL. Defaults to `/api` (the local dev proxy) when unset. */
  readonly VITE_API_BASE_URL?: string;
  /**
   * OIDC authority (issuer) URL. When set, the frontend uses
   * `OidcAuthProvider` (react-oidc-context, code flow + silent refresh —
   * AWS Cognito later is config only). When unset, the dev-issuer seam
   * (`DevTokenAuthProvider`) is active instead.
   */
  readonly VITE_OIDC_AUTHORITY?: string;
  /** OIDC client id. Required alongside `VITE_OIDC_AUTHORITY`. */
  readonly VITE_OIDC_CLIENT_ID?: string;
  /** OIDC redirect URI. Defaults to `window.location.origin` when unset. */
  readonly VITE_OIDC_REDIRECT_URI?: string;
  /**
   * A pre-minted dev-issuer token (see `backend` mint CLI). Visibly
   * non-production — never set in a real deployment. When unset, the dev
   * token surface falls back to a "paste a dev token" login panel backed
   * by `sessionStorage` (never `localStorage`, never committed anywhere).
   */
  readonly VITE_DEV_TOKEN?: string;
}

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
  /**
   * `"1"` shows the Options scoping capability (New task picker, nav, route).
   * Set for local dev, tests and staging; unset in production until the
   * capability is complete.
   */
  readonly VITE_OPTIONS_SCOPING?: string;
  /** `"1"` shows the Theory of change capability (New task picker). Same rule as above. */
  readonly VITE_THEORY_OF_CHANGE?: string;
  /**
   * The in-app feedback elements that are on: a comma-separated list such as
   * `"citation_flag,problem_report"` (see `src/lib/feedback.ts`). Unset or
   * empty means that every element is off. The API reads the same list from
   * `POLICY_ATLAS_FEEDBACK`.
   */
  readonly VITE_FEEDBACK?: string;
  /** The git tag or commit of this build. Shown in "Report a problem". */
  readonly VITE_PA_VERSION?: string;
  /**
   * The firewall's CAPTCHA for the waitlist form: the application integration URL
   * (the form loads `<url>/jsapi.js`) and the API key. `scripts/deploy.sh` reads both
   * from the AWS account, only when the firewall's CAPTCHA is on. Both are public by
   * design (they ship in the browser bundle) and are not secrets. Unset locally, in CI
   * and in the mock journey, where the form shows no puzzle and sends no token.
   */
  readonly VITE_WAF_CAPTCHA_SCRIPT_URL?: string;
  /** The CAPTCHA API key; see `VITE_WAF_CAPTCHA_SCRIPT_URL`. */
  readonly VITE_WAF_CAPTCHA_API_KEY?: string;
}

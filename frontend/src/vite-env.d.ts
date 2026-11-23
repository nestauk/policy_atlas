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
   * `"1"` shows the Options scoping capability (New task picker, nav, route)
   * when PostHog gives no answer: no PostHog token in the build, flags not
   * loaded yet, or no `options_scoping` flag. Where PostHog answers, its
   * feature flag decides and this value is ignored.
   */
  readonly VITE_OPTIONS_SCOPING?: string;
  /** `"1"` shows the Theory of change capability (New task picker). Same rule as above. */
  readonly VITE_THEORY_OF_CHANGE?: string;
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
  /**
   * The PostHog project token (starts `phc_`). Public by design: it can only
   * send events and read flags. The same value as the API's
   * `POSTHOG_PROJECT_TOKEN`. Unset turns browser analytics off and leaves
   * feature flags on their environment-variable defaults.
   */
  readonly VITE_POSTHOG_PROJECT_TOKEN?: string;
  /** The PostHog address, e.g. `https://eu.i.posthog.com`. Required with the token. */
  readonly VITE_POSTHOG_HOST?: string;
}

# Auth

One seam (`AuthApi`, `src/auth/types.ts`), exposed via `AuthContext` +
`useAuth()`, with two providers behind it — selected in `AuthProvider.tsx`
by `VITE_OIDC_AUTHORITY`:

- `DevTokenAuthProvider` (env unset) — the backend dev issuer is a keypair
  + mint CLI, not an interactive IdP, so there's no redirect flow: token
  comes from `VITE_DEV_TOKEN` or a visibly-dev "paste a dev token" panel
  (`sessionStorage` only, never `localStorage`).
- `OidcAuthProvider` (env set) — wraps `react-oidc-context` (authorization
  code flow + silent refresh); authority/client id are config, so AWS
  Cognito lands later as env values, not a code change.

Consumers (`src/api`, `src/store`) depend only on `AuthApi` and never
branch on which provider is active. Tokens never appear in a URL or in
`localStorage`.

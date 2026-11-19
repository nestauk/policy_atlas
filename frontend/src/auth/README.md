# Auth

Sign-in for the web app. One interface, `AuthApi` (`types.ts`), with a provider behind it.
Components get it from `useAuth()`. `AuthProvider.tsx` picks the provider:

- `OidcAuthProvider`, when `VITE_OIDC_AUTHORITY` is set. It uses `react-oidc-context` (the
  OpenID Connect (OIDC) authorization-code sign-in with silent refresh). The cloud
  environments sign in through Amazon Cognito this way. It also needs `VITE_OIDC_CLIENT_ID`.
- `DevTokenAuthProvider`, when no authority is set (local use). The token comes from
  `VITE_DEV_TOKEN`, or from the "paste a dev token" panel (`DevTokenLoginPanel.tsx`), which
  keeps it in `sessionStorage`.
- In mock mode (`VITE_MOCK=1`), the mock API supplies its own `AuthApi`.

`jwt.ts` reads the `sub` (user id) claim of a token for display only. It does not check the
token: only the API does that.

## Rules

- Code outside this folder depends only on `AuthApi`. It never checks which provider is active.
- Never put a token in an address or in `localStorage`.

## Commands

From `frontend/`: `pnpm test` runs the unit tests.

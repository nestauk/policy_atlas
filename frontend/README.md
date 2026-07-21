# Policy Atlas frontend

React 19 + Vite + TypeScript (strict) + Tailwind CSS 4. See the root
[README](../README.md) § "Running the web app" for the full backend +
frontend clean-clone walkthrough.

## Package manager: pnpm

This project uses **pnpm 10+** (owner decision, supply-chain grounds — see
`pnpm-workspace.yaml` for the security config). Do not use `npm` or `yarn`.

Install pnpm if you don't have it:

```sh
brew install pnpm          # preferred
# or: npm install -g pnpm@latest-10
# last resort (no global install permission): npx -y pnpm@10 <command>
```

The exact version this scaffold was built and pinned against is recorded in
`package.json` (`packageManager` field) — corepack will pick it up
automatically on machines that have corepack available.

## Install

```sh
pnpm install
```

Install scripts for dependencies are blocked by default (pnpm 10+
behaviour) except for a small reviewed allowlist in
`pnpm-workspace.yaml` (`onlyBuiltDependencies`). New dependencies that
need a build step will fail silently-ish (no script runs) until reviewed
and added to that list — see the comments there before adding one.

## Run dev server

```sh
pnpm dev
```

Vite serves on `:5173` by default and proxies `/api/*` to `http://localhost:8000`
(`vite.config.ts` `server.proxy`) — start the backend first (`make -C backend dev`
from the repo root) for real API calls to resolve. With no `VITE_OIDC_AUTHORITY`
set, sign in via the dev-only "paste a dev token" panel (mint one with the
backend's dev-issuer CLI — see the root README).

### Mock mode (no backend required)

```sh
VITE_MOCK=1 pnpm dev
```

Serves a scripted fixture project + SSE narrative from `src/mock/` — every
`/api/v1/*` call and the event stream are intercepted client-side. This is
what the Playwright journey below runs against.

### Environment variables

See `src/vite-env.d.ts` for the full list and defaults (`VITE_API_BASE_URL`,
`VITE_OIDC_AUTHORITY`/`VITE_OIDC_CLIENT_ID`/`VITE_OIDC_REDIRECT_URI`,
`VITE_DEV_TOKEN`) plus `VITE_MOCK` above. None are required for local dev
against the dev-issuer.

## End-to-end tests (Playwright, mock mode)

```sh
pnpm exec playwright install chromium   # once per machine
pnpm e2e                                 # playwright test
```

`playwright.config.ts` starts its own `VITE_MOCK=1` dev server (reusing one
already running on `:5173`) — no backend or Postgres needed. Chromium only.

## Gates (run from `frontend/`)

```sh
pnpm typecheck   # tsc -b --noEmit
pnpm lint        # eslint .
pnpm test        # vitest run
pnpm build       # tsc -b && vite build
pnpm e2e         # playwright test (mock mode — see above)
```

## Fonts

Nesta's brand typefaces (Averta, Zosia) are never committed to this repo — a
licensed source is a local, untracked addition. Text always renders on the
fallback system font stack declared in `src/index.css` without them; this is
expected, not a bug.

## Layout

- `src/api/` — hand-written API wiring (`client.ts`, `sse.ts`, `queries.ts`,
  `mutations.ts`); `src/api/gen/` is the OpenAPI-generated client
  (`pnpm gen`, kept in sync with `openapi.json` — see `make drift-check` at
  the repo root).
- `src/store/` — client-side state: the SSE-replay reducer + `useRunStream`.
- `src/auth/` — the `AuthApi` seam: dev-token provider (default) or OIDC
  provider (`react-oidc-context`) when `VITE_OIDC_AUTHORITY` is set.
- `src/ui/brand/` — Nesta brand tokens/components.
- `src/ui/radix/` — Radix-based UI primitives (popover, sheet, tooltip, etc.).
- `src/mock/` — the `VITE_MOCK=1` fixture project + scripted SSE narrative.
- `src/views/` — page-level views.
- `src/routes.tsx`, `src/main.tsx`, `src/App.tsx` — app shell + routing.
- `e2e/` — Playwright mock-mode journey (`pnpm e2e`); `playwright.config.ts`
  at the package root configures it.

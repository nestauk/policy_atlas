# Policy Atlas frontend

React 19 + Vite + TypeScript (strict) + Tailwind CSS 4. Scaffolded in task
025 phase F.0; real views land in phases G/H, the generated API client
lands in F.1.

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

## Gates (run from `frontend/`)

```sh
pnpm typecheck   # tsc -b --noEmit
pnpm lint        # eslint .
pnpm test        # vitest run
pnpm build       # tsc -b && vite build
```

`pnpm gen` is a placeholder until phase F.1 wires the OpenAPI-generated
client into `src/api/gen/`.

## Fonts

Nesta's brand typefaces (Averta, Zosia) are never committed to this repo.
Until a licensed source lands (phase G), text renders on the fallback
system font stack declared in `src/index.css` — this is expected, not a
bug.

## Layout

- `src/api/` — hand-written API wiring; `src/api/gen/` is the generated
  OpenAPI client placeholder (phase F.1).
- `src/store/` — client-side state (SSE-replay store, later phase).
- `src/auth/` — OIDC/Cognito wiring (`react-oidc-context`), later phase.
- `src/ui/brand/` — Nesta brand tokens/components (phase G).
- `src/ui/radix/` — Radix-based UI primitives (later phase).
- `src/views/` — page-level views.
- `src/routes.tsx`, `src/main.tsx`, `src/App.tsx` — app shell + routing.

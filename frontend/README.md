# Frontend

The Policy Atlas web app: React 19, TypeScript in strict mode, Vite and Tailwind CSS 4. To run
the whole app (API and web app together), use `make dev` from the repository root (see the
[root README](../README.md)). The visual design rules are in [DESIGN.md](../DESIGN.md).

## Package manager: pnpm

Use pnpm. Do not use npm or yarn. `package.json` pins the pnpm version in the `packageManager`
field. Install pnpm as a standalone tool (see [pnpm.io](https://pnpm.io/installation)). Do not
depend on Corepack: newer Node.js releases do not include it, and CI (continuous integration)
does not use it. CI installs pnpm with `pnpm/action-setup`, which reads the same
`packageManager` field.

`pnpm-workspace.yaml` holds the supply-chain settings. Read its comments before you add a
package:

- Packages may not run install scripts, except the ones in `onlyBuiltDependencies` (none now).
- pnpm does not install a package version that is less than 24 hours old
  (`minimumReleaseAge`).
- A dependency of a dependency may not come from git, a tarball or a local path
  (`blockExoticSubdeps`).

## Commands

Run these from `frontend/`. Install the packages first: `make frontend-install` from the root,
or `pnpm install`.

```sh
pnpm dev         # the dev server on http://localhost:5173
pnpm typecheck   # tsc -b --noEmit
pnpm lint        # eslint .
pnpm test        # vitest run (unit tests)
pnpm build       # tsc -b && vite build
pnpm e2e         # Playwright browser tests against mock data
pnpm gen         # makes src/api/gen/types.ts from openapi.json
```

From the root, `make frontend-verify-fast` runs the type check, lint and unit tests, and
`make frontend-verify` also runs the build.

The dev server sends `/api/*` to the API on `http://localhost:8000` (`vite.config.ts`). Start
the API first, or use mock mode.

## Mock mode and browser tests

`VITE_MOCK=1 pnpm dev` runs the app with no API: `src/mock/` answers every API call and plays a
scripted event stream. `pnpm e2e` starts its own mock-mode server on port 5199, so it does not
use a dev server on port 5173. Install the browser once with
`pnpm exec playwright install chromium`. The tests are in `e2e/`. `make fe-api-smoke` (from the
root) runs a separate browser test against the real local API.

## Environment variables

`src/vite-env.d.ts` describes each one except `VITE_MOCK`. None is required for local use.

- `VITE_API_BASE_URL`: the API address. The default is `/api`.
- `VITE_OIDC_AUTHORITY`, `VITE_OIDC_CLIENT_ID`, `VITE_OIDC_REDIRECT_URI`: cloud sign-in through
  OpenID Connect (OIDC). With no authority set, the app uses the local dev token.
- `VITE_DEV_TOKEN`: a local dev token. `make dev` sets it.
- `VITE_OPTIONS_SCOPING=1` and `VITE_THEORY_OF_CHANGE=1`: show those Capabilities. `make dev`
  sets both.
- `VITE_MOCK=1`: mock mode.

## Fonts

The brand fonts (Averta and Zosia) are licensed, so they are never committed. `make font-guard`
fails if a font file is tracked. If you have the files, put them in `public/fonts/`
(gitignored). Without them, the app uses the fallback fonts in `src/index.css`.

## What is in src/

- `api/`: the API client, the event-stream client, and the query and mutation hooks
  ([README](src/api/README.md)). `api/gen/` is generated ([README](src/api/gen/README.md)).
- `store/`: the state built from the event stream, and the chat transcripts
  ([README](src/store/README.md)).
- `auth/`: sign-in ([README](src/auth/README.md)).
- `ui/brand/`: the shared design pieces ([README](src/ui/brand/README.md)). `ui/radix/`: the
  overlay and tab primitives ([README](src/ui/radix/README.md)). `ui/feedback/`, `ui/motion/`
  and `ui/charts/`: error and retry states, motion, and charts.
- `lib/`: shared helpers, including `vocabulary.ts` (the screen words) and `capabilities.ts`.
- `views/`: the pages. `routes.tsx`, `routes/`, `App.tsx` and `main.tsx`: the app shell and
  routing.
- `mock/`: the mock-mode data and API.

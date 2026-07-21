---
type: Integration quirk
title: The frontend's pnpm supply-chain posture, and where it bites
description: Install scripts blocked, a 24h minimumReleaseAge that demonstrably rejected real packages during the build, exotic-subdep blocking, strict node_modules; Node 25 dropped bundled corepack; vitest's default glob collects Playwright specs unless excluded.
tags: [pnpm, supply-chain, frontend, tooling, security]
timestamp: 2026-07-21
---

# Rule

The frontend's pnpm posture (owner decision, task 025), in
`pnpm-workspace.yaml` and `package.json`:

- `onlyBuiltDependencies: []` — blocks every dependency's pre/post/install
  script by default; verified empty (no package under `node_modules/.pnpm`
  needed one at scaffold time — this stack's native binaries, e.g. esbuild,
  `@tailwindcss/oxide`, lightningcss, ship as platform `optionalDependencies`,
  not install scripts).
- `minimumReleaseAge: 1440` (24h) — refuses to install any package version
  published in the last day, giving the ecosystem a window to catch and
  unpublish compromised releases. Override path is per-package
  (`minimumReleaseAgeExclude`), never lowering the global window.
- `blockExoticSubdeps: true` — refuses git/tarball/local-path subdependencies
  buried inside the graph (bypassing registry provenance).
- Strict `node_modules` (pnpm's default — no phantom-dependency hoisting; do
  not set `shamefully-hoist: true`).

Two more tooling quirks from the same build:

- **Node 25 dropped bundled corepack.** Install pnpm standalone (e.g. via
  brew) rather than relying on `corepack enable`; keep the
  `packageManager: "pnpm@11.15.1"` pin in `package.json` anyway for
  corepack-capable machines.
- **vitest's default test-file glob collects files under the package root
  regardless of directory convention** — Playwright specs under `e2e/` match
  it unless excluded. `vite.config.ts`'s `test.exclude` adds `"e2e/**"` to
  `configDefaults.exclude`, or `pnpm test` (vitest) fails trying to run
  `e2e/journey.spec.ts` outside a Playwright runner.

# Why

Each of these reads as a one-line config choice that silently reopens a real
risk (or breaks a real workflow) if reverted without knowing why it's there.
`minimumReleaseAge` in particular is not theoretical: it demonstrably rejected
four <24h-old packages during the F.0 setup phase of this build — the gate
bites in practice, and the correct response was pinning the next-older
released version, never excluding the package from the age check.

# Watch out

Before adding an entry to `onlyBuiltDependencies`, confirm the package actually
has a script pnpm is blocking (`pnpm install` prints "Ignored build scripts"
for it), read what the script does, and document why here — don't allow-list
preemptively.

# Citations

- `frontend/pnpm-workspace.yaml`
- `frontend/package.json`
- `frontend/vite.config.ts` (`test.exclude`)

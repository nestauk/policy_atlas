---
type: Integration quirk
title: Vite 8 / plugin-react 6 wire the React Compiler through a separate babel plugin
description: The classic react({ babel: {...} }) option is gone in the Rolldown era; wiring goes through @rolldown/plugin-babel + reactCompilerPreset. Verify it ran by grepping the bundle for useMemoCache.
tags: [vite, react-compiler, frontend, tooling]
timestamp: 2026-07-21
---

# Rule

Vite 8 / `@vitejs/plugin-react` 6.x (the Rolldown era) removed the classic
`react({ babel: { plugins: [...] } })` option — the plugin no longer runs Babel
itself. React Compiler wiring instead goes through a separate
`@rolldown/plugin-babel` `babel()` plugin combined with the
`reactCompilerPreset()` helper exported from `@vitejs/plugin-react`:
`babel({ presets: [reactCompilerPreset()] })` alongside `react()` in the
plugins array. Verify the compiler actually ran (as opposed to silently
no-op-ing) by grepping the built bundle for `useMemoCache` — its presence is
the compiler's fingerprint.

# Citations

- `frontend/vite.config.ts`

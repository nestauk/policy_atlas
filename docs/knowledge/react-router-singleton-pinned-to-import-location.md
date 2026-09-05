---
type: Integration quirk
title: A module-level react-router data router is pinned to the `window.location` captured at import; `history.replaceState` does not move it
description: `createBrowserRouter` initialises at creation, so a router created at module load holds the URL of that moment; `history.replaceState` fires no `popstate`, so a callback that rewrites the URL (the OIDC sign-in return) is invisible to it, and the router renders the pre-rewrite route on the post-rewrite URL until a reload. Sync once, from `window.location`, with `navigate(target, { replace: true })`; `router.state` is `@private` (precedent in `routes.test.tsx`).
tags: [frontend, react-router, auth, oidc, task-038]
timestamp: 2026-09-05
---

# Rule

- Both app routers are module-level singletons; each starts from the URL at
  import time, and nothing that rewrites the address bar without a
  navigation (`history.replaceState`) reaches them.
- After a sign-in round trip the OIDC callback restores the stashed deep
  link with `replaceState`; the authenticated router then mounts on the
  landing route. `App.tsx` (038 V11) compares `authenticatedRouter.state.location`
  with `window.location` once auth is `authenticated` and calls
  `navigate(target, { replace: true })` only on mismatch.
- **Same-origin by construction, and why:** `replaceState` throws on any
  cross-origin URL, so the stash can never become a foreign
  `window.location`; a `replace` navigation never falls back to
  `location.assign` (react-router's `push` does). A local guard
  (`target` starts with `/`, not `//`) keeps the invariant visible if either
  control changes. The stash key keeps one consumer (the callback).
- `router.state` is annotated `@private`; the read is a stability risk, not
  a security one — a react-router minor may change its shape.

# Why

Task 036's stash-and-splash flow landed on the deep link's URL but rendered
the landing page until a reload: the router had never seen the rewrite.
The fix is one effect; the reasoning about *which* browser control makes it
safe is what the security lane asked to be written down.

# Citations

- `frontend/src/App.tsx` (the V11 effect), `frontend/src/App.test.tsx`, `frontend/src/auth/OidcAuthProvider.tsx` (`onSigninCallback`)
- [038-vocabulary-alignment/verification.md](../tasks/038-vocabulary-alignment/verification.md) (§ Phase 7, § Review findings R21)
- react-router 7.18.1 `createBrowserRouter` / `navigate` (installed package)

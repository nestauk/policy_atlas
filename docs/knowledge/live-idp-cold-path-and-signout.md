---
type: Live behaviour
title: Provider-level auth gating must cover the cold path, and the exit needs a UI consumer
description: Every pre-live harness (mock, dev-token, CI smoke) starts authenticated, so only a real cold visit against the real IdP exercises first-entry 401 handling — and an auth API without a sign-out control passes every test while stranding real sessions.
tags: [auth, frontend, oidc, cognito, live-check]
timestamp: 2026-07-28
---

# Rule

Two auth surfaces are structurally invisible to pre-live testing (both found in 026's
first live smoke, both owner-approved fixes):

1. **Cold entry.** `OidcAuthProvider` gated only expiry/renewal; nothing triggered
   `signinRedirect` on a tokenless first visit, so the shell mounted and every query
   401'd forever. Mock-auth, dev-token and CI-smoke harnesses all *start*
   authenticated — the cold path runs for the first time in production. The provider
   now auto-redirects cold visits to the hosted UI with the route stashed.
2. **Exit.** `AuthApi.signOut` existed, tested, with no UI consumer — Cognito sessions
   had no exit at all. Assert the *affordance* (a rendered control), not just the API.

# Watch out

- `history.replaceState` is invisible to react-router: post-callback return-to needs a
  router navigate (open seam, `docs/deferred.md` — includes the persistent-callback-
  error reauth-loop facet from the 026 review).
- oidc sessionStorage sessions don't survive hard reloads, but Cognito's own cookie
  makes the re-auth round-trip silent — it looks like a "signing in" flash, not a
  logout.
- Cognito's classic hosted UI duplicates its login form for responsive layouts — UI
  automation needs `:visible` selectors.

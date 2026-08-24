---
type: Frontend rule
title: React StrictMode permanently poisons useRef(true) mount flags — re-assert in the effect
description: StrictMode's dev mount rehearsal runs the cleanup once at startup and the ref's initial value never re-applies on remount, so any callback gated on a mounted ref silently no-ops for the app's whole life. Always set the ref true in the effect's mount side.
tags: [react, strictmode, useref, hooks, frontend, silent-failure]
timestamp: 2026-08-11
---

# Rule

A mount-tracking ref must be re-asserted inside the effect, not only at
declaration:

```tsx
const mounted = useRef(true);
useEffect(() => {
  mounted.current = true;   // StrictMode's rehearsal cleanup set it false
  return () => { mounted.current = false; };
}, []);
```

# Why

029 G3: the store's stream dispatch was gated on `mounted.current`; StrictMode
mounted → cleaned up → remounted, the cleanup left `false`, and every chat
stream event for a fresh chat was silently dropped in dev — the surface hung
at the activity label. Proven by the e2e chat leg failing/passing across the
fix. The bug class is invisible to unit tests that don't run StrictMode's
double-mount.

# Watch out

Related lint pins from the same slice: the strict react-hooks rules
(react-hooks/refs, set-state-in-effect) reject the render-time-ref
conversation-switch guard — the sanctioned pattern is derive-state-during-
render (setState during render of the same component). And in vitest,
Node/undici `fetch` rejects the browser-style relative URL — stub
`VITE_API_BASE_URL` to an absolute origin in hook tests.

---
type: Frontend rule
title: Frontend state fed by a stream needs the same ownership gate as the components that read it
description: 033 found stream.pendingCheckIn — SSE-fed store state with no ownership dimension — rendering the full steering card (options, free-text steer, Stop analysis) to any colleague viewing during a pending check-in. Gating the components is not enough if the store field itself is ownership-blind and new readers keep appearing.
tags: [frontend, sse, state, tenancy, "033"]
timestamp: 2026-08-25
---

# Rule

When a store field is populated from a stream (SSE, websocket), it carries
no notion of *who is looking* — the stream was authorised once for the
subscriber, but the field outlives that framing and every component that
reads it inherits its blindness. Any surface that must be role-gated
(owner-only steering, mutation affordances) needs the gate applied where
the field is **read into render**, against the current viewer's
relationship to the row (`is_owner`), not assumed from the fact the stream
delivered it.

# Why

Pre-033, only the owner could reach the workspace, so `stream.pendingCheckIn`
never needed an owner dimension. The moment colleagues could read the
task, the SSE-fed field rendered the full steering card — options,
free-text steer, Stop analysis — to any colleague viewing during a pending
check-in. The stream itself was correctly authorised; the *state* was not
ownership-aware.

# Watch out

- Widening read access to a surface converts every previously-implicit
  "only the owner ever sees this" assumption into a live bug — sweep the
  stores feeding that surface, not only its routes and components.
- The same review found the inverse shape server-side: SSE re-authorisation
  per poll is the backend's half; this rule is the frontend's half. Both
  are needed — a closed stream does not un-render state already held.

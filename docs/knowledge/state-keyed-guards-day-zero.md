---
type: Security rule
title: A guard keyed on accumulated state is weakest on day zero — test it against the deploy-day state
description: 033's ops-CLI environment guard proved database identity by resolving recent app_user subs against the Cognito pool; an empty table degraded to a confirmation a --yes flag could script away. The migration itself ships an empty app_user — the guard's weakest state WAS the state every fresh deploy is in, and a wrong write then poisons the guard's own evidence.
tags: [ops, guards, deployment, security, "033"]
timestamp: 2026-08-25
---

# Rule

When a safety guard derives its verdict from **accumulated state** (recent
rows, historical identities, prior activity), evaluate it against the state
of a *fresh deployment* — that is the day it will actually be trusted, and
usually its weakest. If the day-zero state cannot be proven, the honest
degradation is an **interactive, unliftable confirmation**, never a flag:
033 deleted its assume-yes flag outright after review showed the flag
scripted away the one check standing between a staging profile and a
production tunnel.

Second-order: a wrong write in the weak state can **poison the guard's own
evidence** — the foreign identities written by the mistake become the
"recent rows" that make every later run of the wrong pairing verify as
correct. A guard whose seed data an attacker (or an accident) can write is
self-certifying. Distinguish "no evidence" from "evidence that cannot
match" (033: an empty table degrades to confirmation; a non-empty table
with no plausibly-valid subject hard-refuses).

# Why

The 033 migration deliberately creates no `app_user` rows, so every fresh
033 deployment sits exactly in the guard's unprovable state; the Codex
review lane proved the combination (`--yes` + empty DB + wrong tunnel)
would have written staging identities into production and then verified
forever after.

# Watch out

- A snapshot restored from another environment carries that environment's
  identities — accumulated-state guards mis-verify after restores; the
  runbook, not the guard, has to carry that case.
- The unliftable confirmation has an operational cost worth documenting:
  the first command against a fresh deployment needs a human at a terminal
  (DEPLOYMENT.md § 6 records this for 033).

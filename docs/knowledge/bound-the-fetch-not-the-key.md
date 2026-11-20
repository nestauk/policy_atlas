---
type: Invariant
title: An attacker-chosen cache key cannot bound outbound fetches; bound the fetch itself
description: A per-key negative cache on the JWKS lookup bounded nothing, because the key id comes from an unauthenticated token header and a fresh one defeats it every time. The bound has to sit on the fetch, one per interval under a lock claimed before the network call, whatever key asked for it (064a Q16, review findings H-01 and M-20).
tags: [auth, jwks, cache, rate-bound, invariant, security]
generated:
  by: process:okf-migrate
  at: 2026-11-16
sources:
  - resource: "backend/src/policy_atlas/api/auth.py"
    title: "`backend/src/policy_atlas/api/auth.py` \u2014 `JwksProvider.get_key`, `refresh`."
  - resource: "backend/tests/api/test_jwks_provider.py"
    title: "`backend/tests/api/test_jwks_provider.py` \u2014 forty threads, one read; failed refresh keeps keys; no usable key keeps keys; a failed first fetch does not hold the window."
  - resource: "../adr/0045-per-user-run-cap-task-quota-offboarding.md"
    title: "[ADR 0045](../adr/0045-per-user-run-cap-task-quota-offboarding.md) \u00a7 As built 6; [task 064a contract](../tasks/064a-security-quick-wins/contract.md) Q16."
---

# Rule

When the thing a caller controls is the cache key, a negative cache keyed on it bounds
nothing: the caller sends a new key on every request and every request misses. The
JWKS (JSON Web Key Set, Cognito's list of public signing keys) lookup had exactly this
shape — the key id (`kid`) is a field of the token header, which anyone can write — so a
30-second negative cache per `kid` still let an unauthenticated client force one key-set
download per request, on the event loop.

`JwksProvider.get_key` now bounds the **fetch**: at most one key-set read per
`_MIN_REFRESH_INTERVAL_SECONDS` (30 s) in total, under a `threading.Lock` that is taken
before the refresh decision and held across the network call, with the slot stamped
*before* the call so a slow fetch still holds it. Forty threads missing at once cause one
read. Inside the window an unknown `kid` raises at once and a known key from the expired
cache is still served.

Three edges the review stack settled the same day:

- A failed refresh keeps the previous keys; the error is raised only when there are no
  keys at all. A `keys` list with no usable RSA key is a failed refresh too, not an empty
  cache.
- When there are no keys at all and the fetch fails, the slot is given back: nobody can
  verify anyway, and holding it turns a blip at boot into a window of refused tokens.
- A genuinely new signing key is found at most one window after it first appears; the
  frontend's one retry on a 401 covers that.

The two auth dependencies became plain `def` so FastAPI runs them on the worker pool and
the fetch never blocks the event loop. The cost is that requests for a known key wait on
the lock while one fetch runs (up to the client's 5-second timeout), once per window at
most — a deferred seam in `docs/deferred.md` § Accounts, organisations and administration (Limits in the code).

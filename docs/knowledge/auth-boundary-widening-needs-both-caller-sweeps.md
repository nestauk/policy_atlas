---
type: Testing rule
title: Widening an auth boundary needs sweeps for BOTH caller classes — anonymous and signed-in outsider — per route
description: A route's 401 dependency can mask a widened row grade beneath it. 037 moved eleven routes to optional auth; the one route meant to stay graded (decisions) kept its 401 for anonymous callers but silently gained the public leg for signed-in ones, and the conformance sweep that would have caught it had pruned exactly those routes from its signed-in cross-owner class. Derived test-case lists shrink silently — assert their size or membership.
tags: [auth, conformance, tenancy, testing, task-037]
timestamp: 2026-09-04
---

# Rule

When a slice changes which callers may reach a route, the conformance
evidence must cover **each caller class separately, per route**:

- **anonymous** (no token) — the always-401 / conditionally-public sweep;
- **signed-in outsider** (valid token, no grade) — the byte-identical 404
  sweep.

The two fail independently. On 037, `decisions` kept `get_current_user`
(anonymous still 401 — the sweep stayed green) while its row check moved
to the public-leg helper, so any authenticated user could read a public
Task's History. Every review lane found it; no test did.

The masking half: `test_api_conformance.py` derives its case lists from
the live route table, and pruning the conditionally-public GETs from the
always-401 class **also** silently removed them from the derived signed-in
cross-owner sweep (19 → 8 routes) — the task-033 tenancy pin stopped
running on exactly the routes whose grade had changed. A derived list that
shrinks is invisible; when a class is pruned from a shared source list,
add the pruned members back explicitly to every sibling sweep that still
owns them (as `_PROJECT_SCOPED_GET_CASES` now does), or pin the list size.

See [tenancy-predicates-in-sql](tenancy-predicates-in-sql.md) for the SQL
half of the graded read.

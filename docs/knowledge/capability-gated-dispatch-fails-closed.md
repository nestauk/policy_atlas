---
type: Invariant
title: Dispatch gated on a backend capability fails closed when the capability is missing
description: A hasattr-gated dispatch to a required enforcement mechanism (Overton's search_with_post_filter) must raise when the method is absent — falling through to the plain path silently drops the enforcement with no provenance trace.
tags: [fail-closed, search-backends, post-filter, dispatch, country-filters]
timestamp: 2026-07-12
---

# Rule

When a wire mechanism is *required* by the directives (a `source_country_post_filter`
present in validated filters) but the backend object lacks the capability
(`hasattr(backend, "search_with_post_filter")` is false), the dispatch **raises**
(`SearchDirectiveError`), never falls through to the un-enforcing path. A
capability check may select *between* equivalent implementations; it must not select
between enforcing and not enforcing.

The silent form is doubly invisible: the plain path passes no exclusion callback, so
`post_filter_excluded` is None, the event omits the field, and the coverage record
skips the call — no trace that a membership filter was dropped.

# Why

Found convergently by both step-7 families on 019 (the Claude verify lane CONFIRMED
it; the Codex adversarial pass flagged it independently) — high-confidence by
convergence. Only the live Overton backend implements the post-filter; every fixture
or scripted double silently searched unfiltered, so local replay could pass while
believing itself membership-filtered. This is the same hazard family as the recorded
Overton silent-zero: a well-formed run that silently means something else.

# Watch out

- A fixture-mode run with a Tier-2 country group now fails loudly; if that flow is
  ever wanted, implement `search_with_post_filter` on the fixture backend — don't
  relax the raise.
- New optional backend methods: ask "is this capability *selecting* or *enforcing*?"
  Enforcing capabilities get the raise treatment.

# Citations

- `src/policy_atlas/search_loop.py` (`execute_plan` post-filter dispatch)
- `tests/test_search_wire.py`
  (`test_overton_post_filter_without_capable_backend_fails_closed`)
- [019 verification.md § Review findings](../tasks/019-folding-pass/verification.md)
  (convergent finding, adopted)

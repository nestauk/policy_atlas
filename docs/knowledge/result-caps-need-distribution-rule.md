---
type: Convention
title: A total result cap needs a companion distribution rule
description: With max_results = remaining, the first provider call consumes the whole cap and every later query is silently skipped — the fan-out degrades to exactly the single-load-bearing-query shape it was built to avoid, and nothing errors.
tags: [search, budgets, fan-out, live-behaviour, convention]
timestamp: 2026-07-09
---

# Rule

A cap that bounds a *total* (per-backend result cap, HTTP budget) must ship with
a rule for how that total is *distributed* across the calls sharing it. In
`search_loop.py` this is `_distribute_quota` (`max(1, remaining // planned)`):
every planned call in a fan-out gets a per-call `max_records` share; the
fallback-verbatim call keeps the full remainder (it is deliberately the only
load-bearing call in its scenario).

# Why

The 015 live check caught the failure live: with `max_results = remaining`,
OpenAlex call #1 returned the entire 50-record cap, `remaining` hit zero, and
all 14 later planned queries were skipped — silently, because skipping at
cap-exhaustion is correct behaviour for each call in isolation. The system
degraded to exactly the single-load-bearing-query shape the multi-query fan-out
exists to avoid (contract decision 14), and no error, test, or budget guard
fired. Scripted tests structurally could not catch it: their fixture pages were
small, so the cap never bound.

# Watch out

- Any new arm or fan-out sharing an existing cap must be added to the
  `planned` denominator, or it silently competes for leftovers.
- The dual failure: an *un*-quota'd call beside quota'd ones drains what the
  quotas were protecting (the 015 review found the diversity arm doing this —
  its reserve fraction existed as a constant but was never applied).
- Bounds sized on fixtures need one live run where they actually bind before
  they are trusted (see also
  [sanitized-fixtures-audit-against-raw](sanitized-fixtures-audit-against-raw.md)).

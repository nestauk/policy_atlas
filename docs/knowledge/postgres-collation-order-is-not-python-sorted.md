---
type: Testing rule
title: Postgres collation ignores spaces at the first level, so ORDER BY is not Python's sorted
description: A test that expects ORDER BY display_name to equal sorted(names) fails on names with spaces, because the database collation compares letters first and spaces later. Compute the expected order from the database, not sorted().
tags: [testing, postgres, collation, ordering, "065"]
generated:
  by: process:okf-migrate
  at: 2026-11-17
---

# Rule

Collation is the rule a database uses to order text. The usual Postgres collations ignore spaces and case at the first level. `Ann Lee` and `Anna Bell` compare as `annlee` and `annabell`, so `Anna Bell` comes first. Python's `sorted` puts the space first, and orders the other way.

So a test must not assert that `ORDER BY name` equals `sorted(names)`. Either ask the database for the expected order (a second query with the same `ORDER BY`), or use names without spaces.

# Evidence

- `backend/tests/api/test_ops_router.py` around line 413: a comment says Postgres orders by its collation, so the expected order comes from it.


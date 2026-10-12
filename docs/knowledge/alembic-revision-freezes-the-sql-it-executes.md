---
type: Convention
title: An alembic revision freezes the SQL it executes; importing a live constant breaks a fresh upgrade head once the constant moves on
description: Revision c7e2a9f4b1d8 imported schema.FINDING_REFERENCE_UNION_SQL; when task 046 added a column that constant referenced, a fresh `upgrade head` created the view before the column existed. The merged revision had to be edited to freeze its three-branch SQL, and the review of 046 froze the next revision's copy too before it merged. Rule: a revision that creates or replaces a view, function or seed row carries its own frozen text; `schema.py` holds the copy for the running code only.
tags: [alembic, migrations, views, conventions, task-046]
timestamp: 2026-10-12
---

# Rule

- A revision never imports a live SQL constant from `policy_atlas.core.schema` (or any
  module that keeps changing). It freezes the text it executes as a module-level constant
  (`_THREE_BRANCH_UNION_SQL` in `c7e2a9f4b1d8`, `_UNIT_UNION_SQL` and `_POPULATION_UNION_SQL`
  in `f1b6d3a8c2e5`).
- The next revision that changes the view freezes its own copy, up and down.
- `schema.py` keeps one copy for the running code and the view stub for metadata; its
  comment says a revision must not import it.
- The round-trip test of a revision runs from a fresh database (`upgrade head` from empty),
  which is the case that catches an imported constant: see
  [alembic round-trip tests name explicit revisions](alembic-roundtrip-explicit-revisions.md).

# Why

Task 046 amendment 3 had to edit a merged revision (`c7e2a9f4b1d8`) because `upgrade head`
on an empty database failed at the view; the new revision then repeated the pattern (review
finding A7/B7, 2026-10-12) and was frozen before merge rather than after the next break.

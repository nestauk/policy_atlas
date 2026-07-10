---
type: Testing rule
title: Migration-roundtrip tests pin explicit revision targets and never hold seed rows across DDL
description: A relative "-1" downgrade target means "one below head" only while your migration is head; and seed rows left in an open transaction on a second connection deadlock any later migration whose DDL touches the seeded tables — observed as a 14-minute silent hang.
tags: [alembic, migrations, testing, deadlock, postgres]
timestamp: 2026-07-10
---

# Rule

A migration-roundtrip test names its downgrade target as an **explicit revision
id**, never a relative `"-1"` — the relative form silently retargets the moment
any later migration lands. And every seed row the test writes must be committed
(or rolled back) **before** alembic runs DDL on another connection: seeds
strictly after DDL, in their own short-lived transactions
(`tests/test_search_migration.py`, restructured in task 017).

# Why

017's new `orchestration_plan` table made every downgrade drop it; the old test
held `evidence_scope` seed rows in an open transaction while alembic (on a
second connection) issued `DROP TABLE` — whose FK dependency on the seeded
table blocked behind the uncommitted insert. Postgres saw no deadlock (one
side was a lock wait, not a cycle), so nothing errored: the suite hung
silently for 14 minutes.

# Watch out

The hang only appears once a *later* migration's DDL touches the seeded
tables — the test passes for every slice until it doesn't, and the failure
points at the new migration rather than the old test.

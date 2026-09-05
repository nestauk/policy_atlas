---
type: Testing rule
title: Observe insertion order at the write seam, not by reading storage back
description: A table with no order column cannot be read back to prove write order — plain ctid scrambles under page reuse, and (created_at, ctid) still ties on equal timestamps and scrambles within the tie. Capture order at the write seam with a before_cursor_execute listener instead.
tags: [testing, ordering, postgres, write-order, review-lesson]
timestamp: 2026-07-21
---

# Rule

When a contract requires the same **write order** regardless of fan-out
completion order (serial vs. parallel extraction must write findings in
selected-set order), don't try to prove it by reading storage back. Capture
order **at the write seam** instead: a SQLAlchemy `before_cursor_execute` event
listener collecting `INSERT` parameters as they are issued, filtered to the
statement and columns under test.

# Why

Two storage-side read-back attempts both failed for the same golden
(`test_parallel_vs_serial_same_write_order`). Plain `ctid` ordering scrambles
under Postgres page reuse (025 build flake) — `ctid` is a physical location, not
a logical order, and reuse invalidates it. The `(created_at, ctid)` hardening
added afterward still ties on equal timestamps and scrambles **within the tie**
(025 review-stack recurrence) — timestamp resolution at typical test-write speed
is not fine enough to break ties reliably. When a table has no dedicated order
column, there is no query that reconstructs insertion order from the row set
alone.

# Watch out

The assertion itself doesn't get weaker by moving where it's observed — it gets
stronger, because it stops depending on physical storage properties the test
never controlled in the first place. This is the same "observe at the wrong
point" failure family as
[assert-on-row-not-summary](assert-on-row-not-summary.md) — evidence anchored on
something other than what the property is actually about — just for physical
order instead of summary-vs-row drift.

# Citations

- `backend/tests/evidence_search/extract/test_extract_contract.py`
  (`test_parallel_vs_serial_same_write_order`)

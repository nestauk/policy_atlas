---
type: Testing rule
title: Assert contract-required keys on the written row, not the component summary
description: A component's completed-event summary and its persisted roll-up row are built separately and can drift; tests that assert a contracted key on the summary can stay green while the row a downstream reader consumes lacks it. Anchor the assertion on the row.
tags: [testing, rollup, summary, drift, review-lesson, group]
timestamp: 2026-07-07
---

# Rule

When a contract says "the roll-up records X", the test must read X back **from the written
row** (direct DB query), not from the `component.completed` summary. The summary and the
row payload are assembled by different builders; a key can exist in one and not the other
while every summary-anchored test passes.

If the same value legitimately appears in both, build it once (in the persisted payload)
and have the summary read the payload key — never compute it twice.

# Why

Task 012 shipped `overall_direction_spread` computed inside `_build_summary` only: the
event summary carried it, the named tests asserted it there, and the persisted
`grouping_result.groups` payload — the thing synthesise actually reads by
`grouping_run_id` — did not have it. Every test was green. The gap was caught by the
review stack's adversarial lane (unique-to-lane finding, Codex, 2026-07-07), fixed by
moving the computation into `build_groups_payload` with a sum-identity check in
`assert_grouping_invariants`, and the summary now reads the payload key.

The general failure shape: **evidence anchored on the ephemeral artifact (event/summary/log)
instead of the durable one (row) proves the wrong thing.** Downstream readers consume rows.

Related: [facet-grouping-exhaustive-partition](facet-grouping-exhaustive-partition.md)
(the invariant the fix extended), [event-log-sequence](event-log-sequence.md) (events are
an append-only trail, not the read surface).

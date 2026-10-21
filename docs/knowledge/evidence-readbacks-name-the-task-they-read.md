---
type: Testing rule
title: A readback script prints the task id it read, and a slug-to-task mapping is re-derived for every live check
description: The task 046 amendment 4 live table reported 25 options, no exclusion and "56 of 160" not-stated documents for the caregiving run; the stored row had 24 options, two exclusions and 130 documents. The slug-based readback resolved `live-caregiving` through a replay-folder `clone.json` that still pointed at the 2026-09-29 task; the readbacks keyed by task id were right. The review re-read every slug-based figure from the stored rows.
tags: [verification, live-check, evidence, readback, replay, task-046]
timestamp: 2026-10-12
---

# Rule

1. **Every readback prints the task id and the task name it read**, first, beside its
   figures (`live_metrics.py` does; `analyse_longlist.py` printed a slug only).
2. **A mapping file from a slug to a task id is written by the run that creates the task**,
   in the same step, and the live-check record quotes the id back. A mapping left from an
   earlier phase (`replay-out/<slug>/clone.json`, the drive script's `put_state`) points at
   the earlier task and keeps polling or reading it (046 amendment 2: a `pipeline` polled a run
   that did not exist; amendment 4: three slug readbacks read the base-slice tasks).
3. **Cross-check one figure per readback against the row it claims** (`counts.documents`,
   `counts.options`) before any table is written; a figure read back from a saved file is
   only as good as the file's task.
4. **The replay has limits a reader must know:** a chain on a built clone keeps the clone's
   options as seeds (M1 inflates, designs are not re-minted), `suggest --fresh` before
   `longlist --fresh` turns earlier options into seeds, and a clone whose documents were
   re-profiled needs the chain rerun before any option-level read.

# Why

The live-trace lane of the 046 review found the mismatch by pulling the stored provenance and
counts of the three amendment 4 tasks and comparing them with the table (finding LT1). See
[the live-check drive runbook](live-check-drive-runbook.md) and
[assert on the row, not the summary](assert-on-row-not-summary.md).

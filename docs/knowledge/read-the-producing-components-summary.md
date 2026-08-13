---
type: Convention
title: A displayed count comes from the producing component's own summary, not a parallel recount
description: Acquire defines its headline `acquired` as the sum of its per-backend counts, so a card that reads that payload agrees with the headline by construction. A read model that recounts the same population from rows is a second source of truth for one number — the exact shape of the bug being fixed.
tags: [read-models, counts, provenance, steering, convention]
timestamp: 2026-08-13
---

# Rule

When a component has already computed and persisted a number, the read model that displays
it reads **that** number. It does not recompute the same quantity from the underlying rows.

Two numbers derived independently from the same population will agree today and drift
later — on a dedupe rule change, a scope change, a screening-generation bump. One of them
then becomes a lie, and there is no principled way to say which.

As built: `_acquired_by_backend` reads the acquire run's `component.completed` payload and
takes `by_backend[*]["acquired"]`. Acquire computes its headline `totals["acquired"]` as
the sum of exactly those values, so the check-in chip and the per-backend line beneath it
cannot disagree — not because a test forces them to match, but because there is one number.

# Why

Task 031's defect 1a was a card whose backend line was permanently zero: `p1_bundle` summed
`backends[].count` off the coverage record, a key acquire never writes. The obvious fix —
recount the run's new sources from `project_source_snapshot` rows — would have made the
line non-zero and *still* left two independent derivations of "how many did this round
acquire", which is the failure mode the whole slice existed to remove.

Reading the producing component's summary also matches the steering module's own stated
rule: no recomputation of anything a component already computed.

# Watch out

- **Extract narrowly.** The payload is a raw component summary and can carry free text
  (acquire writes provider error strings into the same `by_backend` dict). Pull the
  specific typed fields you need — `isinstance(stats.get("acquired"), int)` — rather than
  forwarding the payload. This is a display bundle; it is scrubbed by construction only if
  you keep it that way.
- **Absent stays absent.** A run whose payload lacks the key yields an empty line, never an
  invented zero. A zero is a claim; absence is the truth.
- **Cost:** this makes the display depend on an event payload's shape. An older run whose
  payload predates the field shows nothing rather than a retroactively recomputed figure.
  That is the right trade for a per-round card and the wrong one for a durable total — pick
  per surface, and say which you picked.
- **A shared read helper can be right for one caller and wrong for another.** The same
  slice narrowed `_executed_queries` with an opt-in `run_id`: spanning every round is
  correct for P2's coverage picture and wrong for P1's one-round card. Add the narrowing as
  a parameter with the broad behaviour as the default, and assert **both** halves in one
  test — otherwise a later change quietly narrows the other caller.
- Same family:
  [success-map-is-stale-on-the-failure-path](success-map-is-stale-on-the-failure-path.md)
  (which run's summary),
  [assert-on-row-not-summary](assert-on-row-not-summary.md),
  [coverage-base-project-pool-wide](coverage-base-project-pool-wide.md).

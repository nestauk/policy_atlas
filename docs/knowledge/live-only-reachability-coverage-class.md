---
type: Testing
title: Live-only reachability is a real coverage class — enumerate the branches only a live model or enabled tracer can reach
description: Three 022 bugs passed the full deterministic suite and fell over only on live runs — a judge emitting verdicts for envelope ids it was never asked to judge, enriched persisted records re-entering a strict wire validator, and a tracing-enabled-only reader of a changed payload shape; each sat behind live-model behaviour or an observability-only branch that stubs structurally cannot exercise.
tags: [testing, live-checks, coverage, tracing, judge, stubs]
timestamp: 2026-07-14
---

# Rule

Treat "reachable only live" as a named coverage class when scoping a slice's
checks. The 022 build shipped a green 1300-test suite and still hit three
product bugs on first live contact, each in this class:

1. **Live-model surplus behaviour**: the judge emitted verdicts for span-map-only
   claim ids it had no verdict duty for — a stub scripted to the duty never
   would (fix: drop-and-count, the invented-id posture).
2. **Data-lifecycle mismatch across stages**: judge-failing claims carried
   ENRICHED citation records into a strict re-validation (`extra="forbid"`)
   that deterministic fixtures — built wire-shaped — never triggered.
3. **Observability-only branches**: `tracing.grouping_score_summary` read a
   retired payload shape; the branch only executes with Langfuse enabled, a
   config no test runs under.

For each, ask at plan time: which branches require a live model, live
enrichment, or an enabled tracer to execute at all? Those get a live check or
an explicitly-shaped fixture (enriched, not wire), not just stub coverage.

# Why

Stubs are scripted to the contract; these bugs live exactly where reality
exceeds the contract (models act on everything they can see; persisted records
outgrow their wire shape; tracing code paths are dark in CI). A suite that is
green by construction on those branches reports coverage it does not have.

# Citations

- [022 verification.md § Live-check bug fixes](../tasks/022-synthesis-refinement/verification.md)
- `test_judge_extra_verdicts_for_span_only_ids_are_dropped_not_fatal` (tests/test_synthesise.py)
- `_wire_claim_data` in `src/policy_atlas/synthesise.py`; `grouping_score_summary` in `src/policy_atlas/tracing.py`

---
type: Convention
title: A read model resolving another table's payload pins the referencing row's FK — never "latest by created_at"
description: The synthesis row records characterisation_run_id/grouping_run_id exactly so consumers resolve the artefact's OWN themes; latest-by-created_at let a later run's reused theme ids (e.g. intervention:g01) relabel an older committed artefact. Pin by the recorded FK; a NULL reference resolves to nothing, honestly.
tags: [read-models, foreign-keys, provenance, artefact, themes]
timestamp: 2026-07-29
---

# Rule

When a read model materialises row A and needs a companion payload from table
B, it resolves B through **the reference recorded on A** (here:
`synthesis_result.characterisation_run_id` / `grouping_run_id`, FK-backed to
`(evidence_scope_id, run_id)`), never through "B's latest row for the
task". A NULL reference means A never had that companion — return nothing,
don't substitute the newest B.

Shipped instance: `repository.py::_characterisation_theme_refs` /
`_grouping_theme_refs`, decoy-run regression test in
`test_artefact_theme_claim_resolves_durable_references`.

# Why

027 adversarial review: deterministic ids (`intervention:g01`) and theme names
recur across runs, so "latest" resolution let a run-2 characterisation relabel
the committed run-1 artefact's theme callouts — wrong names, wrong members,
wrong source lists, all rendering confidently. The schema already carried the
correct pin; the read model just hadn't used it.

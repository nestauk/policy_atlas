---
type: Integration quirk
title: Re-running run_experiment with the same run_name upserts into the existing Langfuse dataset run, one item per dataset item
description: Langfuse neither rejects nor clears a dataset run whose run_name already exists — a second run_experiment call with the same name writes into the same run, replacing the run item of a dataset item it scores again and leaving the others; so a partial re-run under an old label silently mixes two code versions, and a "run it again" check must use --dry-run or a new label.
tags: [langfuse, evaluation, datasets, idempotency]
timestamp: 2026-10-05
---

# Rule

`client.run_experiment(run_name=...)` on a `run_name` that already exists writes **into**
that run. Nothing fails and nothing is cleared. Verified 2026-10-05 on the self-hosted
instance: re-scoring the same fifteen dataset items under an existing run name left the
run at fifteen items with the new scores (the run item for a dataset item is upserted).
The 046 build read the same behaviour as "appends" without checking the count; the
hazard it guards against is real either way: a re-run over a *subset* of items under an
old label leaves a run that mixes two code versions, and `history.py` averages over the
mixture with nothing to show it.

So:
- A "does it make zero requests the second time" check runs with `--dry-run` (upload
  nothing) or under a new `--run-label`, never as a plain re-run.
- Run labels carry the date and short commit (`YYYY-MM-DD-<sha7>/<setting>`) so a re-run
  after a code change lands under a new name by default.
- Superseded runs stay in the dataset; `datasets.delete_run` answers 404 on this Langfuse
  version and run items have no delete call, so only the UI removes them. `history.py`
  prints every run, so note in `history.md` which label is the kept one.
- Re-running one arm under an existing label is safe only when it covers **every** item
  of that run (046, 2026-10-05: the OpenAlex arm redone for all fifteen after a
  question-mark bug replaced the failed scores cleanly).

# Why

046's rubric asked for a second run with no flags to prove zero service requests. Doing it
literally would have doubled every item in the twelve kept runs; the build used the upload
run itself as the zero-request run and a `--dry-run` for the snippet arm instead (flagged
deviation 2, confirmed by the review stack).

# Citations

- [046 verification § Zero-request check and § Flagged deviations](../tasks/046-search-baselines/verification.md)
- `scripts/evals/search/measure/baseline_recall.py` `run_baseline`, `main` (`--dry-run`,
  `--run-label`)

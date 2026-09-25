---
type: Integration quirk
title: Re-running run_experiment with the same run_name appends items to the existing Langfuse dataset run
description: Langfuse does not replace or reject a dataset run whose run_name already exists — a second run_experiment call with the same name adds its items to the same run, so "run it again" checks must use --dry-run or a new label, and history.py's per-run means silently include the duplicates.
tags: [langfuse, evaluation, datasets, idempotency]
timestamp: 2026-09-25
---

# Rule

`client.run_experiment(run_name=...)` on a `run_name` that already exists **appends** the
new items to that run. Nothing fails and nothing is replaced: the run then holds two
items per review, and any script that averages scores per run (`history.py`) averages
over both copies.

So:
- A "does it make zero requests the second time" check runs with `--dry-run` (upload
  nothing) or under a new `--run-label`, never as a plain re-run.
- Run labels carry the date and short commit (`YYYY-MM-DD-<sha7>/<setting>`) so a re-run
  after a code change lands under a new name by default.
- Superseded runs stay in the dataset unless deleted by hand; `history.py` prints every
  run, so note in `history.md` which label is the kept one.

# Why

046's rubric asked for a second run with no flags to prove zero service requests. Doing it
literally would have doubled every item in the twelve kept runs; the build used the upload
run itself as the zero-request run and a `--dry-run` for the snippet arm instead (flagged
deviation 2, confirmed by the review stack).

# Citations

- [046 verification § Zero-request check and § Flagged deviations](../tasks/046-search-baselines/verification.md)
- `scripts/evals/search/baseline_recall.py` `run_baseline`, `main` (`--dry-run`,
  `--run-label`)

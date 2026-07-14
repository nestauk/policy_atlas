---
type: Runbook
title: The orchestrate stub smoke is the standardised zero-egress full-chain check
description: Skeleton is retired (023); the smoke and future live checks run through the orchestrator CLI — no OPENAI_API_KEY selects deterministic stubs + the packaged fixture corpus. The smoke commits rows, so it runs after the suite, against the test DB, with a reset afterwards.
tags: [smoke, orchestrate, stub, testing, zero-egress, runbook]
timestamp: 2026-07-14
---

# Runbook

The walking-skeleton CLI was retired in task 023 (owner ruling, 2026-07-14): its stub
smoke role was already covered by `test_full_stub_chain_commits_each_step_and_checks_in`
(runner suite, inside `make verify`), and its live-check role belongs to the product CLI.
From 023 on, **`orchestrate` is the one check vehicle**:

```sh
printf 'What works to reduce childhood obesity?\n1\napprove\n1\n1\n' \
  | env -u OPENAI_API_KEY \
    DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
    uv run python -m policy_atlas.runtime.orchestrate
```

- **No `OPENAI_API_KEY` ⇒ stub mode**: `StubPlannerBackend` + default `RunnerBackends()`
  ⇒ the harness's default fixture search backends reading the packaged
  `src/policy_atlas/data/` records (which is why `data/` lives at the package root — the
  `importlib.resources` anchors are top-package) + the seeded stub corpus. Zero egress.
- The scripted stdin is the five-prompt console path: intent · shape-suggestion pick ·
  `approve` · two steer-point continues. Success = exit 0, `Run status: succeeded`,
  `Artefact minted: True`.
- **The smoke commits rows.** Migration-roundtrip tests fail on a contaminated DB
  (downgrade `CheckViolation` on leftover rows — the contamination survives sessions).
  The recipe is therefore: run the smoke **after** the test suite, never before or during,
  and `dropdb`/`createdb` the test DB afterwards. Observed twice in 023's build
  (deferred.md § per-lane test-DB partition, recurrence note).
- **Live checks** use the same command with keys loaded (`set -a; source .env; set +a`)
  and the target DATABASE_URL — the 022-era `python -m policy_atlas.skeleton` form is
  gone; scope every live check to what the slice changed (the contract pins it).

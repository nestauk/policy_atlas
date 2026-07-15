---
type: Runbook
title: Orchestrate is the one check vehicle — the stub smoke is automated in the suite; the manual command is for ad-hoc and live checks
description: Skeleton is retired (023). The zero-egress full-chain check is test_full_stub_end_to_end_mints_artefact (in make verify, self-cleaning); the manual orchestrate command exists for ad-hoc demos and the live-check form only — it commits rows, so ad-hoc runs against a shared DB need a reset afterwards.
tags: [smoke, orchestrate, stub, testing, zero-egress, runbook]
timestamp: 2026-07-14
---

# Runbook

The walking-skeleton CLI was retired in task 023 (owner ruling, 2026-07-14): its stub
smoke role was already covered by the suite, and its live-check role belongs to the
product CLI. From 023 on, **`orchestrate` is the one check vehicle**, in two forms:

**1. The automated gate (the default — nothing to run by hand).**
`tests/runtime/test_orchestrate.py::test_full_stub_end_to_end_mints_artefact` drives the
identical scripted flow (intent · suggestion pick · `approve` · two steer-point
continues) through `main()` with an injected console, asserts the artefact is minted,
and **cleans up its committed rows** (`delete_project_data` in a `finally`). It runs
inside `make verify` — every full gate already executes the smoke. A slice needs no
separate manual smoke step; `verification.md` cites this test. (The runner-level
`test_full_stub_chain_commits_each_step_and_checks_in` covers the same chain below the
CLI.)

**2. The manual command (ad-hoc demos + the live-check form).**

```sh
printf 'What works to reduce childhood obesity?\n1\napprove\n1\n1\n' \
  | env -u OPENAI_API_KEY \
    DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
    uv run python -m policy_atlas.runtime.orchestrate
```

- No `OPENAI_API_KEY` ⇒ stub mode: `StubPlannerBackend` + empty search backends (the
  harness default — acquire adds nothing) + the seeded synthetic stub corpus. Zero
  egress. Success = exit 0, `Run status: succeeded`, `Artefact minted: True`. The
  sanitized provider-record fixtures live test-side (`tests/provider_fixtures.py` +
  `tests/data/provider_records/`, task 023 owner rider) — inject them explicitly if an
  ad-hoc run should exercise acquire against replayed provider records.
- **Ad-hoc runs commit rows and do not clean up.** Against a shared test DB this breaks
  migration-roundtrip tests later (downgrade `CheckViolation` on leftover rows — the
  contamination survives sessions; observed twice in 023's build, see deferred.md § per-
  lane test-DB partition). Run ad-hoc smokes after any suite run you care about, and
  `dropdb`/`createdb` the DB afterwards — or point at a scratch DB.
- **Live checks** use the same command with keys loaded (`set -a; source .env; set +a`)
  and the target DATABASE_URL — the 022-era `python -m policy_atlas.skeleton` form is
  gone; scope every live check to what the slice changed (the contract pins it).

---
type: Testing rule
title: Scoped dev-DB live checks drive the real runner through the agent CLI, never a hand-rolled harness
description: The single-component driver this concept first named (`skeleton._run_component`, task 020) was retired with the skeleton in task 023; the standardised smoke and live-check vehicle since then is the runtime agent CLI (`python -m policy_atlas.runtime.agent`), which owns the run row, plan compile, harness wiring and tracing on the production execution path. Substrate discipline is unchanged: reuse an existing screened selection (never re-search); pass explicit backend instances for exactly the surfaces under test; force `DATABASE_URL` after `load_dotenv`.
tags: [live-check, dev-db, harness, verification, tracing]
timestamp: 2026-09-05
---

# Rule

A scoped live check ("run one real extract, then one real synthesise, on an
existing Task") goes through the runtime agent CLI —
`uv run --project backend python -m policy_atlas.runtime.agent` — which is
the standardised smoke and live-check vehicle (owner, 2026-07-14, task 023).
It creates the run row, compiles the plan, wires the harness and attaches
tracing on the production execution path; hand-rolled run bookkeeping in a
check script is wasted code and a divergence risk. Substrate discipline:
reuse an existing Task's screened selection (`selection_run_id=...`), never
re-search; chain the second component off the first's run id.

# History

- Task 020's live check used `skeleton._run_component(conn, project_id,
  scope_id, component, ...)` — a ~240-line script on the production path,
  which is what made its evidence trustworthy (the 0-reused/10-fresh memo
  miss it observed was designed fingerprint behaviour, not a simulation).
- Task 023 retired the skeleton module and its console script; the agent
  CLI (then `orchestrate`, renamed by task 038) took over as the check
  vehicle. This concept's filename is its id and does not change.

# Watch out

- Force `DATABASE_URL` to the dev target *after* `load_dotenv` — `.env` must
  not silently re-point the check at another database.
- The conftest guard refuses tests against the dev DB; live-check scripts
  are the sanctioned dev-DB writers — keep them in the session scratchpad,
  never in `tests/` (task 038 deleted the repo's `scripts/scratchpad`).
- Same family: [assert-on-row-not-summary](assert-on-row-not-summary.md)
  (check the persisted rows, not the roll-up);
  [run-id-fk-shapes-audit-carriers](run-id-fk-shapes-audit-carriers.md)
  (how run-scoped queries reach tables without a run_id column).

# Citations

- `backend/src/policy_atlas/runtime/agent.py` (module docstring: "Runnable as `python -m policy_atlas.runtime.agent`")
- [023 close-out](../tasks/023-codebase-health/verification.md) (skeleton retired; `orchestrate` as the standardised check vehicle)
- [020 live check](../tasks/020-extract-v2/verification.md) (the original driver and its evidence)

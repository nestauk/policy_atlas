---
type: Testing rule
title: Scoped dev-DB live checks drive one component via skeleton._run_component
description: skeleton._run_component is a ready single-component driver for scoped live checks on existing dev-DB projects — run row, plan compile, harness wiring and tracing in one call — so check scripts never hand-roll run bookkeeping. Reuse an existing screened selection (never re-search); pass explicit backend instances for exactly the surfaces under test (task 020 live check).
tags: [live-check, dev-db, harness, verification, tracing]
timestamp: 2026-07-12
---

# Rule

A scoped live check ("run one real extract, then one real synthesise, on an
existing project") drives each component through
`skeleton._run_component(conn, project_id, scope_id, component, ...)` with
explicit backend instances. It creates the run row, compiles the plan,
wires the harness and attaches tracing in one call — hand-rolled run
bookkeeping in check scripts is both wasted code and a divergence risk from
the real execution path. Substrate discipline: reuse an existing project's
screened selection run (`selection_run_id=...`), never re-search; chain the
second component off the first's run id (`extraction_run_id=...`).

# Why

Task 020's live check needed migration-on-real-data evidence plus one fresh
v2-fingerprint extract and one synthesise reading it, on the 018 replay
project. `_run_component` made the whole check a ~240-line script whose
execution path is the production one (memo behaviour, vetter, tracing all
real), which is exactly what made its evidence trustworthy — the
0-reused/10-fresh memo miss it observed was the designed fingerprint
behaviour, not a scripted simulation.

# Watch out

- Force `DATABASE_URL` to the dev target *after* `load_dotenv` — `.env` must
  not silently re-point the check at another database.
- The conftest guard refuses tests against the dev DB; live-check scripts are
  the sanctioned dev-DB writers — keep them in the session scratchpad, never
  in `tests/`.
- Same family: [assert-on-row-not-summary](assert-on-row-not-summary.md)
  (check the persisted rows, not the roll-up);
  [run-id-fk-shapes-audit-carriers](run-id-fk-shapes-audit-carriers.md)
  (how run-scoped queries reach tables without a run_id column).

---
type: Testing rule
title: Several test suites on one local Postgres fail with too many clients; give a checkout its own container
description: Three checkouts running the backend suite against one local Postgres pass its limit of 100 connections. The result looks like about 30 unrelated failures. A second Postgres container on another port, named in TEST_DATABASE_URL, removes it.
tags: [pytest, postgres, xdist, local-dev]
generated:
  by: agent:task-cycle-review
  at: 2026-11-26
---

# Rule

Each `make test` worker makes its own copy of the test database, so suites do not share rows. They still share the server's connection limit (100). With three suites at once, tests fail with `FATAL: sorry, too many clients already`, spread over files that have nothing in common. Run the suite again alone before reading the failures.

For a long task in its own checkout, start a separate container and point the suite at it:

```bash
docker run -d --name <task>-db -e POSTGRES_USER=policy_atlas -e POSTGRES_PASSWORD=policy_atlas \
  -e POSTGRES_DB=policy_atlas -p 127.0.0.1:5433:5432 pgvector/pgvector:pg17
COMPOSE_PROJECT_NAME=policy_atlas \
TEST_DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5433/<name>_test make verify
```

Two more facts:

- `tests/ops/test_pa_ops_login.py` turns the cluster-wide `pa_ops` login on and off. When its tests land on several workers at once, one can fail with `tuple concurrently updated`. It passes alone.
- A test database keeps the schema of the migration that built it. After an in-place edit of a migration that has not shipped, the first run can fail until the round-trip test has applied the migration again.

# Evidence

- `backend/tests/conftest.py` (a database for each worker; the refusal of a URL that is not a `*_test` database).
- `docs/tasks/071-self-signup-staging/verification.md` § Commands run (the red first baseline and the green rerun).

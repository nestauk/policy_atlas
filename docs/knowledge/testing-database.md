---
type: Testing convention
title: Tests run against the dev DB in a rolled-back transaction
description: There is no separate test database; the conn fixture isolates each test in a transaction that rolls back.
tags: [testing, database, pitfall]
timestamp: 2026-06-24
---

# Rule

The test suite needs a live Postgres and a `DATABASE_URL`. There is **no separate test database** —
the `conn` fixture opens a connection, begins a transaction, yields it, and rolls back, so tests are
isolated without a second DB. The migration is applied once per session (idempotent).

# Why

A rolled-back transaction gives clean per-test isolation cheaply, without standing up or migrating a
second database on every run.

# Watch out

Tests **do** touch the running `policy_atlas` database. Never point `DATABASE_URL` at anything you
care about. `conftest.py` fails loudly (with a setup hint) if `DATABASE_URL` is unset; `make verify`
pre-checks the DB is up before running pytest.

# Citations

- [tests/conftest.py](../../tests/conftest.py)
- [environment.md](../agentic-ops/environment.md)

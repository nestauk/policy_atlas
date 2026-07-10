---
type: Integration quirk
title: SQLAlchemy execution_options belong on the statement, not the Connection
description: Setting execution_options (e.g. yield_per) on a Connection is sticky — it mutates the connection's defaults for every later statement in the same transaction, including unrelated INSERTs.
tags: [sqlalchemy, database, integration-quirk, "016"]
timestamp: 2026-07-10
---

# Rule

Set `.execution_options(...)` on the *statement*, not on the `Connection`.
`connection.execution_options(yield_per=...)` mutates the connection's default
options for every later statement executed on it in the same transaction —
there is no automatic scoping to the query it was intended for. The composable
form is `select(...).execution_options(yield_per=...)` (see
`screen.py::_load_stage2_chunk_prefix`, which carries a comment recording this).

# Why

In 016, `yield_per` set at the Connection level wrapped subsequent INSERTs on
that same connection in server-side cursors, producing a
`DECLARE … CURSOR FOR INSERT` syntax error — three stage-2 tests went red at
the phase-3 gate. The failure mode is non-obvious because the statement that
broke (an INSERT) was nowhere near the SELECT that set the option; the option
lived on the connection and silently applied to everything that ran on it
afterward. Root-caused and fixed at the 016 phase-3 gate.

---
type: Invariant (verified)
title: A FastAPI yield dependency declared before get_conn tears down after it, so it can log only after the commit
description: FastAPI tears yield dependencies down in reverse order of use. A dependency that needs get_conn comes after it in the chain and ends first; one declared before get_conn ends after the commit. Use that to emit a log line only once the write is durable.
tags: [fastapi, dependencies, transactions, logging, "065"]
timestamp: 2026-11-17
---

# Rule

A FastAPI dependency with `yield` runs its setup in the order the dependencies are listed. It runs its cleanup in the opposite order.

`get_conn` commits in its own cleanup. A dependency that does not itself depend on `get_conn`, and is declared before it, cleans up after the commit. Its post-yield code therefore runs only if the commit succeeded.

The ops routes use this to write the action log line. The route queues lines on `request.state`. The after-yield code prints them. A rolled-back request prints nothing, so the log never claims an action that did not happen.

# Watch out

Reorder the dependencies and the guarantee goes. Pin it with a test that makes the commit fail.

# Evidence

- `backend/src/policy_atlas/api/routers/ops.py`: `after_commit` (logs `ops.action`) and `require_ops`.
- `backend/src/policy_atlas/api/deps.py`: `get_conn` commits in its `else` branch.

